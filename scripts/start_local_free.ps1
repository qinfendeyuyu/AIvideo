[CmdletBinding()]
param(
    [switch]$StartComfy,
    [switch]$Background,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskScript = Join-Path $taskRoot 'scripts\local_free_gateway.py'
$taskUrl = 'http://127.0.0.1:18766'
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Project .venv is missing. No packages are installed automatically.' }
if (-not (Test-Path -LiteralPath $taskScript -PathType Leaf)) { throw 'local_free_gateway.py is missing.' }
& $taskPython -c 'import fastapi, httpx, uvicorn, PIL'
if ($LASTEXITCODE -ne 0) { throw 'Required local Python packages are missing. See requirements.txt; nothing has been downloaded.' }

function Read-LocalJson([string]$Url) {
    # Do not inherit environment/system proxies when contacting local services.
    $taskResult = & $taskPython -c 'import httpx,json,sys; c=httpx.Client(trust_env=False,follow_redirects=False,timeout=4); r=c.get(sys.argv[1]); r.raise_for_status(); print(json.dumps(r.json(),ensure_ascii=True))' $Url 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($taskResult | ConvertFrom-Json)
}

$taskExisting = Read-LocalJson ($taskUrl + '/health')
if ($null -ne $taskExisting) {
    if ($taskExisting.service -ne 'local-free-gateway') { throw 'Port 18766 belongs to a different service. It has not been stopped.' }
}

if ($StartComfy -and -not $CheckOnly) {
    $taskComfy = Read-LocalJson 'http://127.0.0.1:8488/system_stats'
    if ($null -eq $taskComfy) {
        & (Join-Path $taskRoot 'scripts\start_comfy_wan14b.ps1') -Port 8488
        if ($LASTEXITCODE -ne 0) { throw 'ComfyUI startup failed.' }
        $taskComfy = Read-LocalJson 'http://127.0.0.1:8488/system_stats'
        if ($null -eq $taskComfy) { throw 'ComfyUI is not on port 8488. Inspect its log; this strict launcher will not guess another server.' }
    }
}

if ($null -ne $taskExisting) {
    Write-Host "Already running: $taskUrl"
    (Read-LocalJson ($taskUrl + '/health')) | ConvertTo-Json -Depth 8
    return
}

if ($CheckOnly) {
    Push-Location -LiteralPath $taskRoot
    try {
        & $taskPython -c 'import json; from scripts.local_free_gateway import create_app; g=create_app(start_worker=False).state.gateway; print(json.dumps(g.health(),ensure_ascii=True,indent=2))'
        if ($LASTEXITCODE -ne 0) { throw 'Local readiness check failed.' }
    } finally { Pop-Location }
    return
}

Write-Host 'Local only: Ollama 11434, ComfyUI 8488. No cloud fallback or automatic model downloads.'
Write-Host "Workbench: $taskUrl"
Write-Host 'Image/video tasks share ONE queue. Do not run a second gateway worker or another GPU generator.'
if (-not $Background) {
    & $taskPython $taskScript
    if ($LASTEXITCODE -ne 0) { throw "Gateway exited: $LASTEXITCODE" }
    return
}

$taskLogDir = Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Force -Path $taskLogDir | Out-Null
$taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$taskStdout = Join-Path $taskLogDir "local_free_$taskStamp.stdout.log"
$taskStderr = Join-Path $taskLogDir "local_free_$taskStamp.stderr.log"
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList @('"' + $taskScript + '"') `
    -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput $taskStdout `
    -RedirectStandardError $taskStderr -PassThru
$taskReady = $false
for ($taskAttempt = 0; $taskAttempt -lt 12; $taskAttempt++) {
    if ($taskProcess.HasExited) { throw "Gateway exited during startup. Log: $taskStderr" }
    $taskResponse = Read-LocalJson ($taskUrl + '/jobs')
    if ($null -ne $taskResponse) { $taskReady = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $taskReady) { throw "Gateway has not responded yet. PID $($taskProcess.Id); inspect $taskStderr before retrying." }
$taskRecord = [ordered]@{pid=$taskProcess.Id;url=$taskUrl;started=(Get-Date).ToString('o');stdout=$taskStdout;stderr=$taskStderr}
$taskRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskLogDir 'local_free.process.json') -Encoding utf8
$taskRecord | Format-List
