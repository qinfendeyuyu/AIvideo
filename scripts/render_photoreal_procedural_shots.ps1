[CmdletBinding()]
param(
    [string]$OutputRoot = 'data\outputs\photoreal_reference_match_20260902',
    [string]$FfmpegBin = 'ffmpeg.exe',
    [string]$FfprobeBin = 'ffprobe.exe',

    [ValidateRange(0, 30)]
    [int]$Crf = 18,

    [ValidateSet('medium', 'slow', 'slower')]
    [string]$Preset = 'slow'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$targetWidth = 1080
$targetHeight = 1920
$targetFps = 30

function Resolve-ProjectPath {
    param([Parameter(Mandatory)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
}

function Resolve-Executable {
    param(
        [Parameter(Mandatory)][string]$Value,
        [Parameter(Mandatory)][string]$Label
    )

    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }

    $command = Get-Command -Name $Value -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $command) {
        throw "$Label executable was not found: $Value"
    }
    return $command.Source
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$Label
    )

    Write-Host "[render] $Label"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Get-EncodeArguments {
    param(
        [Parameter(Mandatory)][int]$Frames,
        [Parameter(Mandatory)][string]$OutputPath
    )

    return @(
        '-an',
        '-frames:v', [string]$Frames,
        '-r', [string]$targetFps,
        '-fps_mode', 'cfr',
        '-c:v', 'libx264',
        '-preset', $Preset,
        '-crf', [string]$Crf,
        '-profile:v', 'high',
        '-pix_fmt', 'yuv420p',
        '-color_range', 'tv',
        '-color_primaries', 'bt709',
        '-color_trc', 'bt709',
        '-colorspace', 'bt709',
        '-movflags', '+faststart',
        $OutputPath
    )
}

function Render-StillShot {
    param(
        [Parameter(Mandatory)][string]$InputPath,
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][int]$Frames,
        [Parameter(Mandatory)][string]$ZoomExpression,
        [Parameter(Mandatory)][string]$XExpression,
        [Parameter(Mandatory)][string]$YExpression,
        [Parameter(Mandatory)][string]$Label
    )

    $filter = "[0:v]zoompan=z='$ZoomExpression':x='$XExpression':y='$YExpression':d=${Frames}:s=${targetWidth}x${targetHeight}:fps=${targetFps},trim=end_frame=${Frames},setpts=N/(${targetFps}*TB),setsar=1,format=yuv420p[out]"
    $arguments = @(
        '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-i', $InputPath,
        '-filter_complex', $filter,
        '-map', '[out]'
    ) + (Get-EncodeArguments -Frames $Frames -OutputPath $OutputPath)
    Invoke-Checked -FilePath $script:Ffmpeg -Arguments $arguments -Label $Label
}

function Get-VideoProbe {
    param([Parameter(Mandatory)][string]$Path)

    $raw = & $script:Ffprobe @(
        '-v', 'error',
        '-select_streams', 'v:0',
        '-count_frames',
        '-show_entries', 'stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_read_frames,color_range,color_space,color_transfer,color_primaries',
        '-of', 'json',
        $Path
    )
    if ($LASTEXITCODE -ne 0) {
        throw "ffprobe failed for $Path."
    }
    return (($raw -join [Environment]::NewLine) | ConvertFrom-Json).streams[0]
}

$script:Ffmpeg = Resolve-Executable -Value $FfmpegBin -Label 'FFmpeg'
$script:Ffprobe = Resolve-Executable -Value $FfprobeBin -Label 'FFprobe'

$root = Resolve-ProjectPath $OutputRoot
$prepared = Join-Path $root 'prepared_keyframes'
$intermediate = Join-Path $root 'clips_intermediate'
$outputDirectory = Join-Path $root 'technical_preview_shots'
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$hero = Join-Path $prepared 'S01_S03_hero_1080x1920.png'
$door = Join-Path $prepared 'S02A_door_1080x1920.png'
$attendant = Join-Path $prepared 'S02B_attendant_closeup_1080x1920.png'
$starTrace = Join-Path $intermediate 'S04_star_trace_48f_v2.mp4'
$cityGate = Join-Path $prepared 'S05_S06_city_gate_master_1080x1920.png'

foreach ($required in @($hero, $door, $attendant, $starTrace, $cityGate)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required source is missing: $required"
    }
}

$outputs = [ordered]@{
    S01 = Join-Path $outputDirectory 'S01_hero_closeup_push_45f.mp4'
    S02 = Join-Path $outputDirectory 'S02_door_to_attendant_hardcut_48f.mp4'
    S03 = Join-Path $outputDirectory 'S03_hero_answer_push_51f.mp4'
    S04 = Join-Path $outputDirectory 'S04_star_trace_48f.mp4'
    S05 = Join-Path $outputDirectory 'S05_city_gate_tight_push_51f.mp4'
    S06 = Join-Path $outputDirectory 'S06_city_gate_wide_push_57f.mp4'
}

# S01: restrained 3.4% push-in, centered on the lead's eyes.
Render-StillShot -InputPath $hero -OutputPath $outputs.S01 -Frames 45 `
    -ZoomExpression 'min(1.034,1+on*0.0007727273)' `
    -XExpression 'iw/2-(iw/zoom/2)+on*0.025' `
    -YExpression 'ih/2-(ih/zoom/2)+on*0.035' `
    -Label 'S01 hero close-up (45 frames)'

# S02: exactly 18 frames of the doorway establishment, followed by a hard cut
# to exactly 30 frames of the attendant close-up. No dissolve is introduced.
$s02Filter = @(
    "[0:v]zoompan=z='min(1.020,1+on*0.0011764706)':x='iw/2-(iw/zoom/2)+on*0.08':y='ih/2-(ih/zoom/2)':d=18:s=${targetWidth}x${targetHeight}:fps=${targetFps},trim=end_frame=18,setpts=N/(${targetFps}*TB),setsar=1,format=yuv420p[door]"
    "[1:v]zoompan=z='min(1.030,1+on*0.0010344828)':x='iw/2-(iw/zoom/2)-on*0.03':y='ih/2-(ih/zoom/2)+on*0.04':d=30:s=${targetWidth}x${targetHeight}:fps=${targetFps},trim=end_frame=30,setpts=N/(${targetFps}*TB),setsar=1,format=yuv420p[face]"
    "[door][face]concat=n=2:v=1:a=0,trim=end_frame=48,setpts=N/(${targetFps}*TB),setsar=1,format=yuv420p[out]"
) -join ';'
$s02Arguments = @(
    '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
    '-i', $door,
    '-i', $attendant,
    '-filter_complex', $s02Filter,
    '-map', '[out]'
) + (Get-EncodeArguments -Frames 48 -OutputPath $outputs.S02)
Invoke-Checked -FilePath $script:Ffmpeg -Arguments $s02Arguments -Label 'S02 doorway hard-cut to attendant (48 frames)'

# S03 deliberately begins tighter and drifts in the opposite horizontal
# direction from S01 so the repeated identity master does not feel duplicated.
Render-StillShot -InputPath $hero -OutputPath $outputs.S03 -Frames 51 `
    -ZoomExpression 'min(1.065,1.025+on*0.0008)' `
    -XExpression 'iw/2-(iw/zoom/2)-on*0.045' `
    -YExpression 'ih/2-(ih/zoom/2)+on*0.018' `
    -Label 'S03 hero answer close-up (51 frames)'

# S04 is already the accepted procedural trace. Normalize it through the same
# delivery encoder and force its timestamp/frame contract instead of stream-copying.
$s04Filter = "[0:v]fps=${targetFps},scale=${targetWidth}:${targetHeight}:flags=lanczos,setsar=1,trim=start_frame=0:end_frame=48,setpts=N/(${targetFps}*TB),format=yuv420p[out]"
$s04Arguments = @(
    '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
    '-i', $starTrace,
    '-filter_complex', $s04Filter,
    '-map', '[out]'
) + (Get-EncodeArguments -Frames 48 -OutputPath $outputs.S04)
Invoke-Checked -FilePath $script:Ffmpeg -Arguments $s04Arguments -Label 'S04 normalized star trace (48 frames)'

# S05: noticeably tighter crop for the reaction beat while keeping the moon
# and the complete upper-body silhouette in frame.
Render-StillShot -InputPath $cityGate -OutputPath $outputs.S05 -Frames 51 `
    -ZoomExpression 'min(1.128,1.090+on*0.00076)' `
    -XExpression 'iw/2-(iw/zoom/2)+on*0.02' `
    -YExpression 'ih/2-(ih/zoom/2)+on*0.08' `
    -Label 'S05 city gate tight push (51 frames)'

# S06: wide composition and gentler motion, distinct from S05. This is only a
# deterministic fallback; the final master will replace it with Wan motion.
Render-StillShot -InputPath $cityGate -OutputPath $outputs.S06 -Frames 57 `
    -ZoomExpression 'min(1.022,1+on*0.0003928571)' `
    -XExpression 'iw/2-(iw/zoom/2)-on*0.018' `
    -YExpression 'ih/2-(ih/zoom/2)+on*0.030' `
    -Label 'S06 city gate wide push (57 frames)'

$expectedFrames = [ordered]@{
    S01 = 45
    S02 = 48
    S03 = 51
    S04 = 48
    S05 = 51
    S06 = 57
}

$validation = foreach ($shot in $outputs.Keys) {
    $path = $outputs[$shot]
    $probe = Get-VideoProbe -Path $path
    $actualFrames = [int]$probe.nb_read_frames

    if ($probe.codec_name -ne 'h264') { throw "$shot codec is $($probe.codec_name), expected h264." }
    if ($probe.profile -ne 'High') { throw "$shot profile is $($probe.profile), expected High." }
    if ([int]$probe.width -ne $targetWidth -or [int]$probe.height -ne $targetHeight) {
        throw "$shot dimensions are $($probe.width)x$($probe.height), expected ${targetWidth}x${targetHeight}."
    }
    if ($probe.pix_fmt -ne 'yuv420p') { throw "$shot pixel format is $($probe.pix_fmt), expected yuv420p." }
    if ($probe.r_frame_rate -ne '30/1' -or $probe.avg_frame_rate -ne '30/1') {
        throw "$shot frame rate is r=$($probe.r_frame_rate), avg=$($probe.avg_frame_rate); expected 30/1."
    }
    if ($actualFrames -ne $expectedFrames[$shot]) {
        throw "$shot has $actualFrames decoded frames, expected $($expectedFrames[$shot])."
    }
    if ($probe.color_space -ne 'bt709' -or $probe.color_transfer -ne 'bt709' -or $probe.color_primaries -ne 'bt709') {
        throw "$shot does not carry complete BT.709 signalling."
    }

    $file = Get-Item -LiteralPath $path
    [pscustomobject][ordered]@{
        shot = $shot
        file = $file.FullName
        frames = $actualFrames
        width = [int]$probe.width
        height = [int]$probe.height
        fps = $probe.avg_frame_rate
        codec = $probe.codec_name
        profile = $probe.profile
        pixel_format = $probe.pix_fmt
        color_range = $probe.color_range
        color_space = $probe.color_space
        color_transfer = $probe.color_transfer
        color_primaries = $probe.color_primaries
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
}

$report = [ordered]@{
    schema_version = '1.0'
    generated_at = (Get-Date).ToString('o')
    purpose = 'Deterministic CPU-only technical preview; Wan motion will replace selected fallback shots.'
    ffmpeg = (& $script:Ffmpeg -version | Select-Object -First 1)
    output_directory = $outputDirectory
    shots = @($validation)
}
$reportPath = Join-Path $outputDirectory 'validation.json'
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8

$report | ConvertTo-Json -Depth 6
