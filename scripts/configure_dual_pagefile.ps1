# Configure dual pagefiles: tiny boot-volume pagefile on C: + 32GB working pagefile on E:.
# Windows often refuses to honor a non-system-only pagefile and falls back to C:.
# Requires Administrator. Reboot after success.

[CmdletBinding()]
param(
    [string]$ResultPath = ".\logs\pagefile_dual_config.json"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator privileges are required."
}

$computer = Get-CimInstance Win32_ComputerSystem
if ([bool]$computer.AutomaticManagedPagefile) {
    Set-CimInstance -InputObject $computer -Property @{ AutomaticManagedPagefile = $false } | Out-Null
}

# Remove blank/malformed settings only.
Get-CimInstance Win32_PageFileSetting |
    Where-Object { [string]::IsNullOrWhiteSpace([string]$_.Name) } |
    ForEach-Object { Remove-CimInstance -InputObject $_ }

function Set-Or-NewPageFile {
    param([string]$Name, [uint32]$Initial, [uint32]$Maximum)
    $existing = @(Get-CimInstance Win32_PageFileSetting | Where-Object {
        [string]::Equals([string]$_.Name, $Name, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($existing.Count -gt 1) {
        throw "Duplicate pagefile settings for $Name"
    }
    if ($existing.Count -eq 1) {
        Set-CimInstance -InputObject $existing[0] -Property @{
            InitialSize = $Initial
            MaximumSize = $Maximum
        } | Out-Null
    }
    else {
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{
            Name = $Name
            InitialSize = $Initial
            MaximumSize = $Maximum
        } | Out-Null
    }
}

# Keep a small crash-dump capable pagefile on the boot volume.
Set-Or-NewPageFile -Name "C:\pagefile.sys" -Initial 2048 -Maximum 4096
# Main working set for Wan14B.
Set-Or-NewPageFile -Name "E:\pagefile.sys" -Initial 32768 -Maximum 32768

$mm = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
Set-ItemProperty -LiteralPath $mm -Name PagingFiles -Value @(
    "C:\pagefile.sys 2048 4096",
    "E:\pagefile.sys 32768 32768"
)

$settings = @(Get-CimInstance Win32_PageFileSetting | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{ name = $_.Name; initial_size_mb = $_.InitialSize; maximum_size_mb = $_.MaximumSize }
})
$usage = @(Get-CimInstance Win32_PageFileUsage | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{ name = $_.Name; allocated_base_size_mb = $_.AllocatedBaseSize; current_usage_mb = $_.CurrentUsage }
})

$result = [ordered]@{
    success = $true
    reboot_required = $true
    timestamp = (Get-Date).ToString("o")
    settings = $settings
    active_usage_before_reboot = $usage
    registry_paging_files = @((Get-ItemProperty $mm -Name PagingFiles).PagingFiles)
    note = "Dual pagefile configured. Reboot required. After reboot, E: should allocate ~32768 MB."
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ResultPath -Encoding utf8
$result | Format-List
$result.settings | Format-Table -AutoSize
Write-Host "REBOOT_REQUIRED"
