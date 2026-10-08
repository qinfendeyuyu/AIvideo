[CmdletBinding()]
param(
    [string]$FfmpegPath = 'ffmpeg',
    [string]$FfprobePath = 'ffprobe',

    [ValidateRange(0, 30)]
    [int]$Crf = 18,

    [ValidateSet('medium', 'slow', 'slower')]
    [string]$Preset = 'slow'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$inputRoot = Join-Path $projectRoot 'data\outputs\photoreal_reference_match_20260902'
$configRelativePath = 'technical_preview_assets\assembly.json'
$outputVideo = Join-Path $inputRoot 'technical_preview_pre_wan.mp4'
$assembler = Join-Path $PSScriptRoot 'assemble_photoreal_sample.ps1'

$requiredRelativePaths = @(
    $configRelativePath,
    'technical_preview_assets\subtitles.ass',
    'technical_preview_assets\procedural_soundscape_10s_48k_stereo.wav',
    'technical_preview_shots\S01_hero_closeup_push_45f.mp4',
    'technical_preview_shots\S02_door_to_attendant_hardcut_48f.mp4',
    'technical_preview_shots\S03_hero_answer_push_51f.mp4',
    'technical_preview_shots\S04_star_trace_48f.mp4',
    'technical_preview_shots\S05_city_gate_tight_push_51f.mp4',
    'technical_preview_shots\S06_city_gate_wide_push_57f.mp4'
)

if (-not (Test-Path -LiteralPath $assembler -PathType Leaf)) {
    throw "Strict assembly script was not found: $assembler"
}
if (-not (Test-Path -LiteralPath $inputRoot -PathType Container)) {
    throw "Preview input root was not found: $inputRoot"
}

$missing = @(
    foreach ($relativePath in $requiredRelativePaths) {
        $candidate = Join-Path $inputRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $candidate
        }
    }
)
if ($missing.Count -gt 0) {
    throw "Technical preview inputs are incomplete. Missing:`r`n - $($missing -join "`r`n - ")"
}

Write-Host 'All six procedural shots, subtitle, and original procedural audio are present.'
Write-Host "Output: $outputVideo"

& $assembler `
    -InputDirectory $inputRoot `
    -OutputVideo $outputVideo `
    -ConfigFile $configRelativePath `
    -FfmpegPath $FfmpegPath `
    -FfprobePath $FfprobePath `
    -Crf $Crf `
    -Preset $Preset

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
