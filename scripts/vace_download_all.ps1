<#
Downloads the complete official Wan VACE 1.3B checkpoint in resumable streams.
Every file is size-checked before being exposed to the local VACE runtime.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 3)]
    [int]$Workers = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelRoot = Join-Path $projectRoot 'models\vace\1.3b'
$workerScript = Join-Path $PSScriptRoot 'wan_direct_download.ps1'
$logRoot = Join-Path $projectRoot 'logs'
$repository = 'Wan-AI/Wan2.1-VACE-1.3B'
$modelDirectory = 'models\vace\1.3b'
New-Item -ItemType Directory -Force -Path $modelRoot, $logRoot | Out-Null

# These are the exact assets read by the official Wan VACE source runtime.
$files = @(
    'config.json',
    'diffusion_pytorch_model.safetensors',
    'models_t5_umt5-xxl-enc-bf16.pth',
    'Wan2.1_VAE.pth',
    'google/umt5-xxl/special_tokens_map.json',
    'google/umt5-xxl/spiece.model',
    'google/umt5-xxl/tokenizer.json',
    'google/umt5-xxl/tokenizer_config.json'
)

Write-Output "VACE download: validating and resuming $($files.Count) required official files."
for ($offset = 0; $offset -lt $files.Count; $offset += $Workers) {
    $batch = @($files | Select-Object -Skip $offset -First $Workers)
    $processes = foreach ($relative in $batch) {
        $tag = $relative -replace '[^A-Za-z0-9]+', '_'
        Start-Process -FilePath powershell.exe -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $workerScript,
            '-RelativePath', $relative,
            '-Repository', $repository,
            '-ModelDirectory', $modelDirectory
        ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $logRoot "vace_$tag.out.log") `
          -RedirectStandardError (Join-Path $logRoot "vace_$tag.err.log")
    }
    $processes | Wait-Process
    foreach ($process in $processes) {
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "VACE download child failed with exit code $($process.ExitCode). Check $logRoot."
        }
    }
    Write-Output "VACE download batch complete: $([math]::Min($offset + $batch.Count, $files.Count))/$($files.Count)."
}

Write-Output 'VACE download complete.'
