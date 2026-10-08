[CmdletBinding()]
param([switch]$SkipSubmit)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

Write-Host "=== 1) Pagefile usage gate ==="
$usage = @(Get-CimInstance Win32_PageFileUsage)
$usage | Format-Table Name, AllocatedBaseSize, CurrentUsage -AutoSize
$secondary = $usage | Where-Object {
  [string]$_.Name -notmatch '(?i)^C:\\pagefile\.sys$' -and [int]$_.AllocatedBaseSize -ge 7000
} | Select-Object -First 1
$c = $usage | Where-Object { [string]$_.Name -match '(?i)^C:\\pagefile\.sys$' } | Select-Object -First 1
$cAlloc = if ($c) { [int]$c.AllocatedBaseSize } else { 0 }
if (-not $secondary -and $cAlloc -lt 8000) {
  throw "Pagefile inactive. Need secondary>=7000 MB or C>=8000 MB."
}
if ($secondary) {
  Write-Host ("Secondary pagefile OK {0} allocated={1}MB" -f $secondary.Name, $secondary.AllocatedBaseSize)
} else {
  Write-Host "C-only large pagefile OK allocated=${cAlloc}MB"
}

Write-Host "=== 2) Input SHA checks ==="
$expected = @{
  "selected_hero_seed_146500401.png" = "D612C942E578B438AC2756FC9428B529A69D996AFB725D804BD949F4E6DC1F77"
  "s02_door_establishing_seed_24090202.png" = "5DF54818A8A3C085F90A05F4369DDEFBF325079374F167D1935CE9B8FBA4339A"
  "selected_city_gate_wide_master.png" = "B184D004F89DB64FDD597A0F3838F0BC55CD4D805855C5BB612BBB36827E490F"
}
$inputDir = Join-Path $Root "runtime_cache\comfy_input\photoreal10s"
foreach ($name in $expected.Keys) {
  $path = Join-Path $inputDir $name
  if (-not (Test-Path -LiteralPath $path)) { throw "Missing input: $path" }
  $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if ($hash -ne $expected[$name]) { throw "SHA mismatch for $name : $hash" }
  Write-Host ("OK {0}" -f $name)
}
if ($SkipSubmit) { Write-Host "SkipSubmit"; exit 0 }
Write-Host "=== 3) Wan14B gated serial submit ==="
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_wan14b_photoreal_gated.ps1
