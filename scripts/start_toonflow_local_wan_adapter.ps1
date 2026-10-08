[CmdletBinding()]
param(
  [string]$ComfyPython = "",
  [string]$HostAddr = "127.0.0.1",
  [int]$Port = 18765,
  [string]$Token = "local-wan",
  [string]$ComfyServer = "",
  [switch]$SkipComfyHealth
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

if (-not $ComfyPython) {
  $candidates = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    "D:\comfyui_env\Scripts\python.exe"
  )
  $ComfyPython = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $ComfyPython -or -not (Test-Path -LiteralPath $ComfyPython)) {
  throw "Python not found. Need project .venv or D:\comfyui_env with fastapi/httpx/uvicorn."
}

# Prefer an interpreter that actually has uvicorn (project .venv), not bare Comfy env.
& $ComfyPython -c "import uvicorn, fastapi, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
  $fallback = Join-Path $Root ".venv\Scripts\python.exe"
  if ((Test-Path -LiteralPath $fallback) -and ($fallback -ne $ComfyPython)) {
    Write-Warning "Selected Python lacks uvicorn; switching to $fallback"
    $ComfyPython = $fallback
    & $ComfyPython -c "import uvicorn, fastapi, httpx"
    if ($LASTEXITCODE -ne 0) { throw "Project .venv is also missing uvicorn/fastapi/httpx. Run: .\.venv\Scripts\pip install fastapi uvicorn httpx" }
  } else {
    throw "Python at $ComfyPython lacks uvicorn. Install into project .venv: .\.venv\Scripts\pip install fastapi uvicorn httpx"
  }
}

if (-not $ComfyServer) {
  $recordPath = Join-Path $Root "logs\comfy_wan14b_photoreal.process.json"
  $ComfyServer = "http://127.0.0.1:8488"
  if (Test-Path -LiteralPath $recordPath) {
    $rec = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    if ($rec.port) { $ComfyServer = "http://127.0.0.1:$($rec.port)" }
  }
}

if (-not $SkipComfyHealth) {
  try {
    $null = Invoke-RestMethod -Uri ($ComfyServer.TrimEnd('/') + '/system_stats') -TimeoutSec 5
    Write-Host "ComfyUI OK: $ComfyServer"
  } catch {
    Write-Warning "ComfyUI not reachable at $ComfyServer. Start it first: .\scripts\start_comfy_wan14b.ps1"
  }
}

$env:ADAPTER_HOST = $HostAddr
$env:ADAPTER_PORT = "$Port"
$env:TOONFLOW_ADAPTER_TOKEN = $Token
$env:COMFY_SERVER = $ComfyServer

Write-Host "Starting Toonflow local Wan adapter on http://${HostAddr}:${Port}"
Write-Host "Token=$Token  (set this as Toonflow vendor apiKey)"
Write-Host "Vendor file: integrations\toonflow\localWanComfy.ts"

& $ComfyPython -m uvicorn toonflow_local_wan_adapter:app `
  --app-dir .\scripts `
  --host $HostAddr `
  --port $Port
