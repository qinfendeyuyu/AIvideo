[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputVideo,

    [Parameter(Mandatory = $true)]
    [string]$OutputVideo,

    [int]$TargetFps = 24,
    [int]$VulkanGpuId = 1,
    [string]$WorkDirectory
)

$ErrorActionPreference = 'Stop'
$ffmpeg = 'E:\ffmpeg\bin\ffmpeg.exe'
$ffprobe = 'E:\ffmpeg\bin\ffprobe.exe'
$rifeRoot = Join-Path $PSScriptRoot '..\third_party\postprocess\tools\rife-ncnn-vulkan-20221029-windows'
$esrRoot = Join-Path $PSScriptRoot '..\third_party\postprocess\tools\realesrgan-ncnn-vulkan-20220424-windows'
$rifeExe = Join-Path $rifeRoot 'rife-ncnn-vulkan.exe'
$esrExe = Join-Path $esrRoot 'realesrgan-ncnn-vulkan.exe'

foreach ($required in @($InputVideo, $ffmpeg, $ffprobe, $rifeExe, $esrExe)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file not found: $required"
    }
}

$inputResolved = (Resolve-Path -LiteralPath $InputVideo).Path
$outputFull = [System.IO.Path]::GetFullPath($OutputVideo)
$outputDirectory = Split-Path -Parent $outputFull
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$probe = & $ffprobe -v error -select_streams v:0 `
    -show_entries stream=width,height,r_frame_rate,nb_frames `
    -show_entries format=duration -of json $inputResolved | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $probe.streams) {
    throw 'ffprobe could not read the input video.'
}

$stream = $probe.streams[0]
if ([int]$stream.width -ne 480 -or [int]$stream.height -ne 832) {
    throw "This quality-locked profile expects 480x832 input; received $($stream.width)x$($stream.height)."
}

$rateParts = $stream.r_frame_rate -split '/'
$sourceFps = [double]$rateParts[0] / [double]$rateParts[1]
$sourceFrames = [int]$stream.nb_frames
$targetFrames = [int][math]::Round($sourceFrames * $TargetFps / $sourceFps)
if ($sourceFrames -lt 2 -or $targetFrames -le $sourceFrames) {
    throw "Invalid interpolation request: $sourceFrames frames at $sourceFps fps to $targetFrames frames at $TargetFps fps."
}

if (-not $WorkDirectory) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $WorkDirectory = Join-Path $outputDirectory "postprocess_${stamp}"
}
$workFull = [System.IO.Path]::GetFullPath($WorkDirectory)
if (Test-Path -LiteralPath $workFull) {
    $existing = Get-ChildItem -LiteralPath $workFull -Force -ErrorAction SilentlyContinue
    if ($existing) {
        throw "Work directory must be new or empty: $workFull"
    }
}

$sourceDir = Join-Path $workFull '01_source'
$rifeDir = Join-Path $workFull '02_rife24'
$upscaleDir = Join-Path $workFull '03_upscale3x'
New-Item -ItemType Directory -Force -Path $sourceDir, $rifeDir, $upscaleDir | Out-Null

& $ffmpeg -hide_banner -loglevel error -y -i $inputResolved `
    -map '0:v:0' -fps_mode passthrough (Join-Path $sourceDir '%08d.png')
if ($LASTEXITCODE -ne 0) { throw 'Source-frame extraction failed.' }

& $rifeExe -i $sourceDir -o $rifeDir -n $targetFrames `
    -m (Join-Path $rifeRoot 'rife-v4.6') -g $VulkanGpuId -j '1:2:2' -f '%08d.png'
if ($LASTEXITCODE -ne 0) { throw 'RIFE interpolation failed.' }

& $esrExe -i $rifeDir -o $upscaleDir -m (Join-Path $esrRoot 'models') `
    -n 'realesr-animevideov3' -s 3 -t 256 -g $VulkanGpuId -j '1:1:2' -f png
if ($LASTEXITCODE -ne 0) { throw 'Real-ESRGAN upscaling failed.' }

& $ffmpeg -hide_banner -loglevel error -y -framerate $TargetFps -start_number 1 `
    -i (Join-Path $upscaleDir '%08d.png') `
    -vf 'crop=1404:2496:18:0,scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p' `
    -c:v libx264 -preset slow -crf 14 -profile:v high -level:v 4.1 `
    -movflags '+faststart' -color_primaries bt709 -color_trc bt709 -colorspace bt709 `
    $outputFull
if ($LASTEXITCODE -ne 0) { throw 'Final video encoding failed.' }

$result = [ordered]@{
    input = $inputResolved
    output = $outputFull
    source_width = [int]$stream.width
    source_height = [int]$stream.height
    source_fps = $sourceFps
    source_frames = $sourceFrames
    target_width = 1080
    target_height = 1920
    target_fps = $TargetFps
    target_frames = $targetFrames
    vulkan_gpu_id = $VulkanGpuId
    rife_model = 'rife-v4.6'
    upscaler_model = 'realesr-animevideov3-x3'
    work_directory = $workFull
    frames_retained = $true
}
$manifestPath = [System.IO.Path]::ChangeExtension($outputFull, '.postprocess.json')
$result | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8
$result | Format-List | Out-Host

Write-Warning "Temporary frames remain at $workFull for visual QA; they were not deleted automatically."
