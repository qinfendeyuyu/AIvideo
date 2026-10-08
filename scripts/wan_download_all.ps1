<#
Coordinates the complete official Wan 2.1 T2V 1.3B download in two resumable
streams. Each child uses wan_direct_download.ps1, which only exposes a file to
the runtime after curl has finished successfully.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 4)]
    [int]$Workers = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelRoot = Join-Path $projectRoot 'models\wan\t2v_1.3b'
$workerScript = Join-Path $PSScriptRoot 'wan_direct_download.ps1'
$logRoot = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Force -Path $modelRoot, $logRoot | Out-Null

$files = @(
    'model_index.json',
    'scheduler/scheduler_config.json',
    'text_encoder/config.json',
    'text_encoder/model-00001-of-00005.safetensors',
    'text_encoder/model-00002-of-00005.safetensors',
    'text_encoder/model-00003-of-00005.safetensors',
    'text_encoder/model-00004-of-00005.safetensors',
    'text_encoder/model-00005-of-00005.safetensors',
    'text_encoder/model.safetensors.index.json',
    'tokenizer/special_tokens_map.json',
    'tokenizer/spiece.model',
    'tokenizer/tokenizer.json',
    'tokenizer/tokenizer_config.json',
    'transformer/config.json',
    'transformer/diffusion_pytorch_model-00001-of-00002.safetensors',
    'transformer/diffusion_pytorch_model-00002-of-00002.safetensors',
    'transformer/diffusion_pytorch_model.safetensors.index.json',
    'vae/config.json',
    'vae/diffusion_pytorch_model.safetensors'
)

$pending = @($files)
Write-Output "Wan download: validating and resuming $($pending.Count) required files."

for ($offset = 0; $offset -lt $pending.Count; $offset += $Workers) {
    $batch = @($pending | Select-Object -Skip $offset -First $Workers)
    $processes = foreach ($relative in $batch) {
        $tag = $relative -replace '[^A-Za-z0-9]+', '_'
        Start-Process -FilePath powershell.exe -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $workerScript, '-RelativePath', $relative
        ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $logRoot "wan_$tag.out.log") `
          -RedirectStandardError (Join-Path $logRoot "wan_$tag.err.log")
    }
    $processes | Wait-Process
    foreach ($process in $processes) {
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "Wan download child failed with exit code $($process.ExitCode). Check $logRoot."
        }
    }
    Write-Output "Wan download batch complete: $([math]::Min($offset + $batch.Count, $pending.Count))/$($pending.Count) pending files."
}

Write-Output 'Wan download complete.'
