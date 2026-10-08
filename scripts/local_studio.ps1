# AI Comic Drama local studio launcher for this Windows machine.
# Usage examples:
#   .\scripts\local_studio.ps1 status
#   .\scripts\local_studio.ps1 demo
#   .\scripts\local_studio.ps1 face -RunId face_check_local
#   .\scripts\local_studio.ps1 episode -EpisodeInput configs\episode.example.yaml -RunId season01_ep01
#   .\scripts\local_studio.ps1 resume -RunId season01_ep01
#   .\scripts\local_studio.ps1 api
#   .\scripts\local_studio.ps1 kokoro-setup
#   .\scripts\local_studio.ps1 wan14b
#   .\scripts\local_studio.ps1 pagefile-status
#   .\scripts\local_studio.ps1 after-reboot-wan

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("status", "demo", "face", "episode", "resume", "api", "preflight", "kokoro-setup", "wan14b", "pagefile-dual", "pagefile-status", "after-reboot-wan")]
    [string]$Command = "status",

    [string]$RunId = "",
    [string]$EpisodeInput = "configs\episode.example.yaml",
    [string]$Config = "configs\models.yaml",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8088,
    [switch]$SkipServices
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Create it with: py -3.12 -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

function Invoke-StudioPython {
    param([Parameter(Mandatory = $true)][string[]]$PythonArgs)
    & $Python @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE : $($PythonArgs -join ' ')"
    }
}

switch ($Command) {
    "status" {
        $statusArgs = @("scripts\studio_status.py", "--config", $Config)
        if ($SkipServices) { $statusArgs += "--skip-services" }
        Invoke-StudioPython -PythonArgs $statusArgs
    }
    "preflight" {
        $pf = @("scripts\preflight.py", "--config", $Config)
        if (-not $SkipServices) { $pf += "--check-services" }
        Invoke-StudioPython -PythonArgs $pf
    }
    "demo" {
        if (-not $RunId) { $RunId = "demo_local_$(Get-Date -Format 'yyyyMMdd_HHmmss')" }
        Write-Host "Running offline diagnostic episode: $RunId"
        Invoke-StudioPython -PythonArgs @("scripts\run_episode.py", "--demo", "--run-id", $RunId)
        Write-Host "Output: $(Join-Path $Root "data\outputs\$RunId\episode.mp4")"
    }
    "face" {
        if (-not $RunId) { $RunId = "face_check_$(Get-Date -Format 'yyyyMMdd_HHmmss')" }
        Write-Host "Running face-sample episode: $RunId"
        Invoke-StudioPython -PythonArgs @(
            "scripts\run_episode.py",
            "--config", $Config,
            "--input", "configs\episode.face-sample.yaml",
            "--run-id", $RunId
        )
        Write-Host "Output: $(Join-Path $Root "data\outputs\$RunId\episode.mp4")"
    }
    "episode" {
        if (-not $RunId) { throw "episode requires -RunId" }
        Write-Host "Running episode: $RunId from $EpisodeInput"
        Invoke-StudioPython -PythonArgs @(
            "scripts\run_episode.py",
            "--config", $Config,
            "--input", $EpisodeInput,
            "--run-id", $RunId
        )
        Write-Host "Output: $(Join-Path $Root "data\outputs\$RunId\episode.mp4")"
    }
    "resume" {
        if (-not $RunId) { throw "resume requires -RunId" }
        Write-Host "Resuming episode: $RunId"
        Invoke-StudioPython -PythonArgs @(
            "scripts\run_episode.py",
            "--config", $Config,
            "--input", $EpisodeInput,
            "--run-id", $RunId,
            "--resume"
        )
    }
    "api" {
        Write-Host "Starting local API at http://${HostAddress}:${Port}"
        Write-Host "Health: http://${HostAddress}:${Port}/api/v1/health"
        Write-Host "Studio: http://${HostAddress}:${Port}/"
        & $Python -m uvicorn app.main:app --host $HostAddress --port $Port
    }
    "kokoro-setup" {
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_kokoro.ps1
    }
    "wan14b" {
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_wan14b_photoreal_gated.ps1
    }
    "pagefile-dual" {
        Write-Host "Launching elevated dual pagefile config (approve UAC)..."
        Write-Host "NOTE: This will NOT reboot. Reboot yourself later if settings change."
        Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $Root "scripts\configure_dual_pagefile.ps1"),
            "-ResultPath", (Join-Path $Root "logs\pagefile_dual_config.json")
        ) -Wait
        Write-Host "When YOU choose to reboot, afterward run: .\scripts\local_studio.ps1 after-reboot-wan"
    }
    "pagefile-status" {
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pagefile_status.ps1
    }
    "after-reboot-wan" {
        powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\after_reboot_wan14b.ps1
    }
}
