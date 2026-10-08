[CmdletBinding()]
param(
  [string]$ComfyPython = "D:\comfyui_env\Scripts\python.exe",
  [switch]$SkipPagefileGate
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

Write-Host "Validating pagefile gate ..."
$usage = @(Get-CimInstance Win32_PageFileUsage)
$usage | Format-Table Name, AllocatedBaseSize, CurrentUsage -AutoSize
$secondary = $usage | Where-Object {
  [string]$_.Name -notmatch '(?i)^C:\\pagefile\.sys$' -and [int]$_.AllocatedBaseSize -ge 7000
} | Select-Object -First 1
$c = $usage | Where-Object { [string]$_.Name -match '(?i)^C:\\pagefile\.sys$' } | Select-Object -First 1
$cAlloc = if ($c) { [int]$c.AllocatedBaseSize } else { 0 }
$allocated = if ($secondary) { [int]$secondary.AllocatedBaseSize } else { $cAlloc }
Write-Host ("active_secondary={0} c_mb={1}" -f $(if ($secondary) { $secondary.Name } else { 'none' }), $cAlloc)
if (-not $SkipPagefileGate) {
  if (-not $secondary -and $cAlloc -lt 8000) {
    throw "Wan14B gate FAILED. Need secondary>=7000 or C>=8000 (got secondary=$allocated C=$cAlloc)."
  }
} else {
  Write-Warning "SkipPagefileGate set. Do not use for formal generation."
}
if (-not (Test-Path -LiteralPath $ComfyPython)) { throw "Comfy Python not found: $ComfyPython" }

Write-Host "Starting low-VRAM ComfyUI ..."
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_comfy_wan14b.ps1
$processRecord = Join-Path $Root "logs\comfy_wan14b_photoreal.process.json"
$comfyPort = 8488
if (Test-Path -LiteralPath $processRecord) {
  $rec = Get-Content -LiteralPath $processRecord -Raw | ConvertFrom-Json
  if ($rec.port) { $comfyPort = [int]$rec.port }
}
$comfyServer = "http://127.0.0.1:$comfyPort"
Write-Host "Comfy server: $comfyServer"

$jobs = @(
  @{ Workflow=".\workflows\wan14b_photoreal_s01_closeup_api.json"; Result=".\data\outputs\photoreal_reference_match_20260902\wan_s01.result.json"; Timeout=90 },
  @{ Workflow=".\workflows\wan14b_photoreal_s02a_door_establishing_api.json"; Result=".\data\outputs\photoreal_reference_match_20260902\wan_s02a.result.json"; Timeout=90 },
  @{ Workflow=".\workflows\wan14b_photoreal_s05_s06_shared_wide_api.json"; Result=".\data\outputs\photoreal_reference_match_20260902\wan_s05_s06.result.json"; Timeout=180 }
)
foreach ($job in $jobs) {
  if (Test-Path -LiteralPath $job.Result) {
    Write-Host ("SKIP (result exists): {0}" -f $job.Result)
    continue
  }
  Write-Host ("Submitting {0}" -f $job.Workflow)
  & $ComfyPython .\scripts\comfy_submit.py $job.Workflow --server $comfyServer --timeout-minutes $job.Timeout --result $job.Result
  if ($LASTEXITCODE -ne 0) { throw "Wan submit failed for $($job.Workflow)" }
}
Write-Host "All three Wan jobs finished. Frame-check before replacing technical_preview_pre_wan.mp4."
