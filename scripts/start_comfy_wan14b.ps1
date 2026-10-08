[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8188,

    [ValidateRange(45, 180)]
    [int]$StartupTimeoutSeconds = 120,

    [switch]$SkipPagefileGate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$pythonPath = 'D:\comfyui_env\Scripts\python.exe'
$comfyMain = 'D:\ComfyUI\main.py'
$inputDirectory = Join-Path $projectRoot 'runtime_cache\comfy_input'
$outputDirectory = Join-Path $projectRoot 'runtime_cache\comfy_output'
$tempDirectory = Join-Path $projectRoot 'runtime_cache\comfy_temp'
$userDirectory = Join-Path $projectRoot 'runtime_cache\comfy_user'
$extraModels = Join-Path $projectRoot 'configs\comfy_extra_model_paths.yaml'
$logDirectory = Join-Path $projectRoot 'logs'
$stdoutLog = Join-Path $logDirectory 'comfy_wan14b_photoreal.stdout.log'
$stderrLog = Join-Path $logDirectory 'comfy_wan14b_photoreal.stderr.log'
$processRecord = Join-Path $logDirectory 'comfy_wan14b_photoreal.process.json'

$requiredFiles = @(
    $pythonPath,
    $comfyMain,
    $extraModels,
    (Join-Path $projectRoot 'workflows\wan14b_photoreal_s01_closeup_api.json'),
    (Join-Path $projectRoot 'workflows\wan14b_photoreal_s02a_door_establishing_api.json'),
    (Join-Path $projectRoot 'workflows\wan14b_photoreal_s05_s06_shared_wide_api.json'),
    (Join-Path $inputDirectory 'photoreal10s\selected_hero_seed_146500401.png'),
    (Join-Path $inputDirectory 'photoreal10s\s02_door_establishing_seed_24090202.png'),
    (Join-Path $inputDirectory 'photoreal10s\selected_city_gate_wide_master.png'),
    'D:\ComfyUI\models\diffusion_models\Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors',
    'D:\ComfyUI\models\clip_vision\open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors',
    'D:\ComfyUI\models\vae\wan_2.1_vae.safetensors'
)

$textEncoderCandidates = @(
    'D:\ComfyUI\models\text_encoders\umt5-xxl-enc-fp8_e4m3fn.safetensors',
    'D:\ComfyUI\models\clip\umt5-xxl-enc-fp8_e4m3fn.safetensors'
)
if (-not ($textEncoderCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)) {
    throw "Wan text encoder was not found at either expected location:`r`n - $($textEncoderCandidates -join "`r`n - ")"
}

$missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($missing.Count -gt 0) {
    throw "Wan launch preflight failed. Missing:`r`n - $($missing -join "`r`n - ")"
}

if (-not $SkipPagefileGate) {
    # Gate on real allocation (Win32_PageFileUsage), not registry alone.
    # A 0-byte E:\pagefile.sys stub can exist via \\?\ path while AllocatedBaseSize stays 0.
    $usage = @(Get-CimInstance Win32_PageFileUsage)
    $secondary = $usage | Where-Object {
        [string]$_.Name -notmatch '(?i)^C:\\pagefile\.sys$' -and [int]$_.AllocatedBaseSize -ge 7000
    } | Select-Object -First 1
    $c = $usage | Where-Object { [string]$_.Name -match '(?i)^C:\\pagefile\.sys$' } | Select-Object -First 1
    $cAlloc = if ($c) { [int]$c.AllocatedBaseSize } else { 0 }
    $allocated = if ($secondary) { [int]$secondary.AllocatedBaseSize } else { $cAlloc }
    if (-not $secondary -and $cAlloc -lt 8000) {
        throw "Pagefile not active for Wan (need secondary>=7000 or C>=8000; got C=${cAlloc})."
    }

    if (-not ('WanMemoryStatusNative' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class WanMemoryStatusNative
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public class MEMORYSTATUSEX
    {
        public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
        public uint dwMemoryLoad;
        public ulong ullTotalPhys;
        public ulong ullAvailPhys;
        public ulong ullTotalPageFile;
        public ulong ullAvailPageFile;
        public ulong ullTotalVirtual;
        public ulong ullAvailVirtual;
        public ulong ullAvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX buffer);
}
'@
    }

    $memory = [WanMemoryStatusNative+MEMORYSTATUSEX]::new()
    if (-not [WanMemoryStatusNative]::GlobalMemoryStatusEx($memory)) {
        throw "GlobalMemoryStatusEx failed with Win32 error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())."
    }
    $commitLimitGiB = [math]::Round($memory.ullTotalPageFile / 1GB, 2)
    $commitAvailableGiB = [math]::Round($memory.ullAvailPageFile / 1GB, 2)
    # 32GB RAM + ~1GB C + >=8GB E => about 40+ GiB commit; require 38 as soft floor.
    if ($commitLimitGiB -lt 38) {
        throw "Commit limit is only ${commitLimitGiB} GiB (need >=38 with E: pagefile). Reboot after pagefile repair."
    }
    Write-Host "Page-file gate passed: pagefile allocated ${allocated} MB; commit limit ${commitLimitGiB} GiB; available ${commitAvailableGiB} GiB."
    if ($commitAvailableGiB -lt 12) {
        Write-Warning "Only ${commitAvailableGiB} GiB commit is free. Wan14B needs roughly 16+ GiB during load. Close browsers and other apps before generating, or the job will fail even if Comfy starts."
    }
}

function Test-TcpPortExcluded {
    param([int]$Candidate)
    $raw = netsh interface ipv4 show excludedportrange protocol=tcp 2>$null
    foreach ($line in @($raw)) {
        if ($line -match '^\s*(\d+)\s+(\d+)\s*$') {
            $start = [int]$Matches[1]
            $end = [int]$Matches[2]
            if ($Candidate -ge $start -and $Candidate -le $end) { return $true }
        }
    }
    return $false
}

# Hyper-V / WinNAT often reserves 8100-8399, which includes the old default 8188
# and surfaces as WinError 10013 (PermissionError) even when nothing is listening.
if (Test-TcpPortExcluded -Candidate $Port) {
    $fallback = @(8488, 9188, 18188, 28188, 38188, 48188) | Where-Object { -not (Test-TcpPortExcluded -Candidate $_) } | Select-Object -First 1
    if (-not $fallback) {
        throw "Port $Port is inside a Windows excluded TCP range, and no fallback port was free. Run: netsh interface ipv4 show excludedportrange protocol=tcp"
    }
    Write-Warning "Port $Port is excluded by Windows (WinError 10013). Using $fallback instead."
    $Port = [int]$fallback
}

foreach ($directory in @($inputDirectory, $outputDirectory, $tempDirectory, $userDirectory, $logDirectory)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$healthUrl = "http://127.0.0.1:$Port/system_stats"
try {
    $existing = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
    if ($null -ne $existing) {
        throw "A ComfyUI server is already responding on port $Port. Stop or reuse it instead of starting a second GPU process."
    }
}
catch {
    if ($_.Exception.Message -like 'A ComfyUI server is already responding*') {
        throw
    }
}

$arguments = @(
    $comfyMain,
    '--listen', '127.0.0.1',
    '--port', [string]$Port,
    '--input-directory', $inputDirectory,
    '--output-directory', $outputDirectory,
    '--temp-directory', $tempDirectory,
    '--user-directory', $userDirectory,
    '--extra-model-paths-config', $extraModels,
    # Keep disable-mmap: Windows + 15GB Wan weights access-violate under mmap when commit is tight.
    # Pair with patched comfy.utils DISABLE_MMAP loader (no .clone() peak) + T5 embed disk cache.
    '--disable-mmap',
    '--lowvram',
    '--reserve-vram', '0.8',
    '--disable-pinned-memory',
    '--cache-none',
    '--disable-auto-launch'
)

$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList $arguments `
    -WorkingDirectory 'D:\ComfyUI' `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        $stderrTail = @(Get-Content -LiteralPath $stderrLog -Tail 40 -ErrorAction SilentlyContinue)
        throw "ComfyUI exited during startup with code $($process.ExitCode).`r`n$($stderrTail -join "`r`n")"
    }
    try {
        $status = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
        if ($null -ne $status) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 750
    }
}

if (-not $ready) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "ComfyUI did not become ready within $StartupTimeoutSeconds seconds. Inspect $stderrLog."
}

$record = [ordered]@{
    ready = $true
    timestamp = (Get-Date).ToString('o')
    pid = $process.Id
    port = $Port
    health_url = $healthUrl
    input_directory = $inputDirectory
    output_directory = $outputDirectory
    stdout_log = $stdoutLog
    stderr_log = $stderrLog
    launch_flags = $arguments
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $processRecord -Encoding utf8
$record | Format-List
