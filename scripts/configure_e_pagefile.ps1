[CmdletBinding()]
param(
    [switch]$ValidateOnly,

    [string]$ResultPath
)

$ErrorActionPreference = 'Stop'
$targetName = 'E:\pagefile.sys'
$InitialSizeMB = [uint32]32768
$MaximumSizeMB = [uint32]32768
$reserveFreeMB = [int64]8192

if (-not $ResultPath) {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $ResultPath = Join-Path $projectRoot 'logs\pagefile_config_result.json'
}

function Test-IsTargetPageFileName {
    param([AllowNull()][object]$Name)

    return [string]::Equals(
        [string]$Name,
        $script:targetName,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function ConvertTo-PageFileSettingSnapshot {
    param([object[]]$Settings)

    return @(
        $Settings |
            Sort-Object -Property Name |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    name = [string]$_.Name
                    initial_size_mb = [uint32]$_.InitialSize
                    maximum_size_mb = [uint32]$_.MaximumSize
                }
            }
    )
}

function ConvertTo-PageFileUsageSnapshot {
    param([object[]]$Usage)

    return @(
        $Usage |
            Sort-Object -Property Name |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    name = [string]$_.Name
                    allocated_base_size_mb = [uint32]$_.AllocatedBaseSize
                    current_usage_mb = [uint32]$_.CurrentUsage
                    peak_usage_mb = [uint32]$_.PeakUsage
                }
            }
    )
}

function Get-RegistryPagingFiles {
    $memoryManagerPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'
    $pagingFilesValue = (Get-ItemProperty -LiteralPath $memoryManagerPath -Name PagingFiles).PagingFiles
    if ($null -eq $pagingFilesValue) {
        return @()
    }

    return @($pagingFilesValue | ForEach-Object { [string]$_ })
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $ValidateOnly -and -not $isAdministrator) {
        throw 'Administrator privileges are required. Re-run PowerShell as Administrator, or use -ValidateOnly for a read-only check.'
    }

    # Win32_LogicalDisk can be queried by a standard user, unlike Get-Volume on
    # some locked-down Windows installations. DriveType 3 means a fixed disk.
    try {
        $volume = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='E:'"
    }
    catch {
        throw "Unable to read E: disk metadata through CIM: $($_.Exception.Message) On a locked-down system, run even -ValidateOnly from an elevated PowerShell window."
    }
    if ($null -eq $volume) {
        throw 'E: logical disk was not found.'
    }
    if ([uint32]$volume.DriveType -ne 3) {
        throw "E: must be a fixed disk; found Win32_LogicalDisk DriveType '$($volume.DriveType)'."
    }
    if ($volume.FileSystem -ne 'NTFS') {
        throw "E: must be NTFS; found '$($volume.FileSystem)'."
    }
    try {
        $computerBefore = Get-CimInstance -ClassName Win32_ComputerSystem
        $settingsBeforeRaw = @(Get-CimInstance -ClassName Win32_PageFileSetting)
        $usageBeforeRaw = @(Get-CimInstance -ClassName Win32_PageFileUsage)
        $registryBefore = @(Get-RegistryPagingFiles)
    }
    catch {
        throw "Unable to read the current Windows page-file configuration: $($_.Exception.Message) On a locked-down system, run even -ValidateOnly from an elevated PowerShell window."
    }

    $blankSettingsBefore = @(
        $settingsBeforeRaw |
            Where-Object { [string]::IsNullOrWhiteSpace([string]$_.Name) }
    )
    $targetSettingsBefore = @(
        $settingsBeforeRaw |
            Where-Object { Test-IsTargetPageFileName -Name $_.Name }
    )
    if ($targetSettingsBefore.Count -gt 1) {
        throw "Found $($targetSettingsBefore.Count) duplicate settings for '$targetName'; refusing to choose one automatically."
    }

    $targetUsageBefore = @(
        $usageBeforeRaw |
            Where-Object { Test-IsTargetPageFileName -Name $_.Name }
    )
    $allocatedTargetMB = [int64]0
    if ($targetUsageBefore.Count -gt 0) {
        $allocatedMeasure = $targetUsageBefore | Measure-Object -Property AllocatedBaseSize -Sum
        if ($null -ne $allocatedMeasure.Sum) {
            $allocatedTargetMB = [int64]$allocatedMeasure.Sum
        }
    }

    # An already active E: page file has consumed its disk space, so only its
    # requested growth needs to be available. Keep an additional 8 GiB free.
    $requiredGrowthMB = [math]::Max([int64]0, ([int64]$MaximumSizeMB - $allocatedTargetMB))
    $minimumFreeBytes = ($requiredGrowthMB + $reserveFreeMB) * 1MB
    if ([int64]$volume.FreeSpace -lt $minimumFreeBytes) {
        $requiredGiB = [math]::Round($minimumFreeBytes / 1GB, 2)
        $freeGiB = [math]::Round($volume.FreeSpace / 1GB, 2)
        throw "E: needs ${requiredGiB} GiB free for page-file growth plus reserve; only ${freeGiB} GiB is available."
    }

    $settingsBefore = @(ConvertTo-PageFileSettingSnapshot -Settings $settingsBeforeRaw)
    $usageBefore = @(ConvertTo-PageFileUsageSnapshot -Usage $usageBeforeRaw)
    $targetMatchesBefore = (
        -not [bool]$computerBefore.AutomaticManagedPagefile -and
        $blankSettingsBefore.Count -eq 0 -and
        $targetSettingsBefore.Count -eq 1 -and
        [uint32]$targetSettingsBefore[0].InitialSize -eq $InitialSizeMB -and
        [uint32]$targetSettingsBefore[0].MaximumSize -eq $MaximumSizeMB
    )

    if ($ValidateOnly) {
        $result = [ordered]@{
            success = $true
            read_only = $true
            configuration_matches = $targetMatchesBefore
            timestamp = (Get-Date).ToString('o')
            target_name = $targetName
            requested_initial_size_mb = $InitialSizeMB
            requested_maximum_size_mb = $MaximumSizeMB
            automatic_managed_pagefile = [bool]$computerBefore.AutomaticManagedPagefile
            blank_setting_count = $blankSettingsBefore.Count
            active_target_allocated_mb = $allocatedTargetMB
            required_growth_mb = $requiredGrowthMB
            reserve_free_mb = $reserveFreeMB
            e_drive_type = 'Fixed'
            e_filesystem = [string]$volume.FileSystem
            e_free_gib = [math]::Round($volume.FreeSpace / 1GB, 2)
            settings = $settingsBefore
            active_usage = $usageBefore
            registry_paging_files = $registryBefore
            note = 'Read-only validation; no page-file setting was changed.'
        }
        $exitCode = 0
    }
    else {
        # Snapshot every nonblank, non-target setting. These settings must remain
        # equivalent in name and sizes after the targeted repair.
        $otherSettingsBefore = @(
            $settingsBefore |
                Where-Object {
                    -not [string]::IsNullOrWhiteSpace([string]$_.name) -and
                    -not (Test-IsTargetPageFileName -Name $_.name)
                }
        )
        $otherSettingsBeforeJson = ConvertTo-Json -InputObject @($otherSettingsBefore) -Compress

        if ([bool]$computerBefore.AutomaticManagedPagefile) {
            Set-CimInstance -InputObject $computerBefore -Property @{ AutomaticManagedPagefile = $false } | Out-Null
        }

        # Remove only malformed WMI settings whose Name is null, empty, or all
        # whitespace. No nonblank setting and no physical pagefile is deleted.
        foreach ($blankSetting in $blankSettingsBefore) {
            Remove-CimInstance -InputObject $blankSetting
        }

        if ($targetSettingsBefore.Count -eq 1) {
            Set-CimInstance -InputObject $targetSettingsBefore[0] -Property @{
                InitialSize = $InitialSizeMB
                MaximumSize = $MaximumSizeMB
            } | Out-Null
        }
        else {
            New-CimInstance -ClassName Win32_PageFileSetting -Property @{
                Name = $targetName
                InitialSize = $InitialSizeMB
                MaximumSize = $MaximumSizeMB
            } | Out-Null
        }

        # All checks below are read-only verification of the resulting settings.
        $computerAfter = Get-CimInstance -ClassName Win32_ComputerSystem
        $settingsAfterRaw = @(Get-CimInstance -ClassName Win32_PageFileSetting)
        $usageAfterRaw = @(Get-CimInstance -ClassName Win32_PageFileUsage)
        $registryAfter = @(Get-RegistryPagingFiles)

        $blankSettingsAfter = @(
            $settingsAfterRaw |
                Where-Object { [string]::IsNullOrWhiteSpace([string]$_.Name) }
        )
        if ($blankSettingsAfter.Count -ne 0) {
            throw "Blank page-file setting cleanup failed; $($blankSettingsAfter.Count) malformed setting(s) remain."
        }

        $targetSettingsAfter = @(
            $settingsAfterRaw |
                Where-Object { Test-IsTargetPageFileName -Name $_.Name }
        )
        if ($targetSettingsAfter.Count -ne 1) {
            throw "Expected exactly one '$targetName' setting after configuration; found $($targetSettingsAfter.Count)."
        }
        if (
            [uint32]$targetSettingsAfter[0].InitialSize -ne $InitialSizeMB -or
            [uint32]$targetSettingsAfter[0].MaximumSize -ne $MaximumSizeMB
        ) {
            throw "The '$targetName' setting does not match the requested sizes after configuration."
        }
        if ([bool]$computerAfter.AutomaticManagedPagefile) {
            throw 'AutomaticManagedPagefile is still enabled after configuration.'
        }

        $settingsAfter = @(ConvertTo-PageFileSettingSnapshot -Settings $settingsAfterRaw)
        $otherSettingsAfter = @(
            $settingsAfter |
                Where-Object {
                    -not [string]::IsNullOrWhiteSpace([string]$_.name) -and
                    -not (Test-IsTargetPageFileName -Name $_.name)
                }
        )
        $otherSettingsAfterJson = ConvertTo-Json -InputObject @($otherSettingsAfter) -Compress
        if (-not [string]::Equals(
            $otherSettingsBeforeJson,
            $otherSettingsAfterJson,
            [System.StringComparison]::Ordinal
        )) {
            throw 'A non-target page-file setting changed unexpectedly; inspect the before/after state before rebooting.'
        }

        $usageAfter = @(ConvertTo-PageFileUsageSnapshot -Usage $usageAfterRaw)
        $result = [ordered]@{
            success = $true
            read_only = $false
            configuration_matches = $true
            timestamp = (Get-Date).ToString('o')
            reboot_required = $true
            target_name = [string]$targetSettingsAfter[0].Name
            initial_size_mb = [uint32]$targetSettingsAfter[0].InitialSize
            maximum_size_mb = [uint32]$targetSettingsAfter[0].MaximumSize
            blank_settings_removed = $blankSettingsBefore.Count
            other_settings_preserved = $otherSettingsAfter.Count
            active_target_allocated_mb_before_reboot = $allocatedTargetMB
            required_growth_mb = $requiredGrowthMB
            reserve_free_mb = $reserveFreeMB
            e_drive_type = 'Fixed'
            e_filesystem = [string]$volume.FileSystem
            e_free_gib_before_reboot = [math]::Round($volume.FreeSpace / 1GB, 2)
            settings_before = $settingsBefore
            settings_after = $settingsAfter
            active_usage_before = $usageBefore
            active_usage_after = $usageAfter
            registry_paging_files_before = $registryBefore
            registry_paging_files_after = $registryAfter
            note = 'Only WMI settings were changed. No physical pagefile was deleted. Reboot is required before activation is verified.'
        }
        $exitCode = 0
    }
}
catch {
    $result = [ordered]@{
        success = $false
        read_only = [bool]$ValidateOnly
        timestamp = (Get-Date).ToString('o')
        error = $_.Exception.Message
    }
    $exitCode = 1
}

$resultDirectory = Split-Path -Parent $ResultPath
if ($resultDirectory) {
    New-Item -ItemType Directory -Force -Path $resultDirectory | Out-Null
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ResultPath -Encoding utf8
$result | Format-List | Out-Host

if ($result.settings_after) {
    $result.settings_after | Format-Table -AutoSize | Out-Host
}
elseif ($result.settings) {
    $result.settings | Format-Table -AutoSize | Out-Host
}

exit $exitCode
