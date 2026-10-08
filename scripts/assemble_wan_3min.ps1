# Assemble completed 16fps Wan clips → concat → RIFE 30fps episode.
[CmdletBinding()]
param(
    [string]$OutDir = 'E:\AI漫剧\ai-comic-drama\data\outputs\wan_3min_local_20260927',
    [int]$TargetFps = 30,
    [int]$VulkanGpuId = 1,
    [switch]$RifeOnlyIfComplete
)

$ErrorActionPreference = 'Stop'
$ffmpeg = 'E:\FFmpeg\bin\ffmpeg.exe'
$ffprobe = 'E:\FFmpeg\bin\ffprobe.exe'
$rifeRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'third_party\postprocess\tools\rife-ncnn-vulkan-20221029-windows'
$rifeExe = Join-Path $rifeRoot 'rife-ncnn-vulkan.exe'
$clipsDir = Join-Path $OutDir 'clips_16fps'
$storyboard = Get-Content -LiteralPath (Join-Path $OutDir 'storyboard_3min.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$expected = $storyboard.shots.Count

$clips = Get-ChildItem -LiteralPath $clipsDir -Filter '*.mp4' -ErrorAction SilentlyContinue | Sort-Object Name
if (-not $clips -or $clips.Count -eq 0) { throw "No clips in $clipsDir" }
Write-Host "Found $($clips.Count)/$expected clips"

if ($RifeOnlyIfComplete -and $clips.Count -lt $expected) {
    throw "Incomplete: $($clips.Count)/$expected — refuse assemble"
}

$listFile = Join-Path $OutDir 'concat_list.txt'
$lines = foreach ($c in $clips) {
    $p = $c.FullName.Replace('\', '/')
    "file '$p'"
}
Set-Content -LiteralPath $listFile -Value $lines -Encoding utf8

$concat16 = Join-Path $OutDir ("episode_partial_{0}clips_16fps.mp4" -f $clips.Count)
if ($clips.Count -eq $expected) {
    $concat16 = Join-Path $OutDir 'episode_3min_16fps.mp4'
}

& $ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $listFile -c copy $concat16
if ($LASTEXITCODE -ne 0) { throw 'concat failed' }
& $ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate,nb_frames -show_entries format=duration -of default=nw=1 $concat16

# RIFE to 30fps
$work = Join-Path $OutDir ("rife_assemble_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
$srcDir = Join-Path $work '01_source'
$rifeDir = Join-Path $work '02_rife'
New-Item -ItemType Directory -Force -Path $srcDir, $rifeDir | Out-Null
& $ffmpeg -hide_banner -loglevel error -y -i $concat16 -map '0:v:0' -fps_mode passthrough (Join-Path $srcDir '%08d.png')
$n = (Get-ChildItem -LiteralPath $srcDir -Filter '*.png').Count
$probe = & $ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 $concat16
$parts = $probe -split '/'
$srcFps = [double]$parts[0] / [double]$parts[1]
$targetFrames = [int][math]::Round($n * $TargetFps / $srcFps)
Write-Host "RIFE $n @$srcFps -> $targetFrames @$TargetFps"
& $rifeExe -i $srcDir -o $rifeDir -n $targetFrames -m (Join-Path $rifeRoot 'rife-v4.6') -g $VulkanGpuId -j '1:2:2' -f '%08d.png'
if ($LASTEXITCODE -ne 0) { throw 'RIFE failed' }

$out30 = if ($clips.Count -eq $expected) {
    Join-Path $OutDir 'episode_3min_rife_30fps.mp4'
} else {
    Join-Path $OutDir ("episode_partial_{0}clips_rife_30fps.mp4" -f $clips.Count)
}
& $ffmpeg -hide_banner -loglevel error -y -framerate $TargetFps -start_number 1 `
    -i (Join-Path $rifeDir '%08d.png') `
    -c:v libx264 -preset slow -crf 16 -profile:v high -pix_fmt yuv420p `
    -movflags '+faststart' -color_primaries bt709 -color_trc bt709 -colorspace bt709 -an $out30
& $ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate,nb_frames,width,height -show_entries format=duration,size -of default=nw=1 $out30
Write-Host "DONE $out30"
