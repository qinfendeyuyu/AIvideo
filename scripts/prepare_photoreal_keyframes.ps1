[CmdletBinding()]
param(
    [string]$OutputRoot = 'data\outputs\photoreal_reference_match_20260902',
    [string]$FfmpegBin = 'ffmpeg.exe',
    [string]$FfprobeBin = 'ffprobe.exe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Resolve-ProjectPath {
    param([Parameter(Mandatory)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$Label
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$root = Resolve-ProjectPath $OutputRoot
$keyframes = Join-Path $root 'keyframes'
$prepared = Join-Path $root 'prepared_keyframes'
$provenance = Join-Path $root 'keyframe_provenance'
New-Item -ItemType Directory -Force -Path $prepared, $provenance | Out-Null

$hero = Join-Path $keyframes 'S01_S03_hero_master_832x1216.png'
$door = Join-Path $keyframes 'S02A_door_establishing_seed_24090202.png'
$attendant = Join-Path $keyframes 'S02B_attendant_closeup_seed_24090212.png'
$starSource = Join-Path $keyframes 'S04_star_chart_source_crop_only_seed_24090214.png'
$citySource = Join-Path $keyframes 'S05_S06_city_gate_master_seed_24090206.png'

foreach ($required in @($hero, $door, $attendant, $starSource, $citySource)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required keyframe is missing: $required"
    }
}

$standardScale = 'scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920:(iw-1080)/2:(ih-1920)/2,setsar=1,unsharp=5:5:0.25:3:3:0.10'
$standardJobs = @(
    @{ Input = $hero; Output = (Join-Path $prepared 'S01_S03_hero_1080x1920.png') },
    @{ Input = $door; Output = (Join-Path $prepared 'S02A_door_1080x1920.png') },
    @{ Input = $attendant; Output = (Join-Path $prepared 'S02B_attendant_closeup_1080x1920.png') }
)

foreach ($job in $standardJobs) {
    Invoke-Checked -FilePath $FfmpegBin -Label "Prepare $($job.Output)" -Arguments @(
        '-hide_banner', '-loglevel', 'error', '-y',
        '-i', $job.Input,
        '-vf', $standardScale,
        '-frames:v', '1', '-update', '1',
        $job.Output
    )
}

# The accepted source chart contains pseudo-writing outside its central blue
# astronomical disk. Crop strictly inside that disk before scaling so no
# generated pseudo-text can reach the delivery frame.
$starPrepared = Join-Path $prepared 'S04_star_chart_clean_crop_1080x1920.png'
$starFilter = 'crop=600:600:52:305,scale=1920:1920:flags=lanczos,crop=1080:1920:420:0,setsar=1,unsharp=5:5:0.35:3:3:0.15'
Invoke-Checked -FilePath $FfmpegBin -Label 'Prepare clean star-chart crop' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $starSource,
    '-vf', $starFilter,
    '-frames:v', '1', '-update', '1',
    $starPrepared
)

# The strongest city-gate composition arrived with the robe and sash colours
# swapped. Apply a deterministic 180-degree hue transform only inside a union
# of (a) a colour-derived garment mask and (b) a conservative polygon wholly
# inside the body. This preserves the moon, skyline, doors and skin exactly.
$huePreview = Join-Path $provenance 'S05_S06_hue180_full_preview.png'
$colourMask = Join-Path $provenance 'S05_S06_colour_mask.png'
$innerMask = Join-Path $provenance 'S05_S06_inner_garment_mask.png'
$unionMask = Join-Path $provenance 'S05_S06_union_garment_mask.png'
$cityColourMatched = Join-Path $keyframes 'S05_S06_city_gate_master_SELECTED.png'
$cityPrepared = Join-Path $prepared 'S05_S06_city_gate_master_1080x1920.png'

Invoke-Checked -FilePath $FfmpegBin -Label 'Create hue-rotated city preview' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $citySource,
    '-vf', 'hue=h=180:s=0.85',
    '-frames:v', '1', '-update', '1',
    $huePreview
)

$redCondition = 'max(between(X,210,520)*between(Y,500,1130)*gt(r(X,Y),38)*gt(r(X,Y),1.02*g(X,Y))*gt(r(X,Y),0.98*b(X,Y)),between(X,252,468)*between(Y,662,725))'
$colourMaskFilter = "format=rgb24,geq=r='if($redCondition,255,0)':g='if($redCondition,255,0)':b='if($redCondition,255,0)',dilation,dilation,dilation,dilation,dilation,erosion,erosion,erosion,erosion,erosion,boxblur=2:1"
Invoke-Checked -FilePath $FfmpegBin -Label 'Create colour-derived garment mask' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $citySource,
    '-vf', $colourMaskFilter,
    '-frames:v', '1', '-update', '1',
    $colourMask
)

$innerCondition = 'max(max(between(Y,550,620)*between(X,285-0.70*(Y-550),420+0.75*(Y-550)),between(Y,620,800)*between(X,235+0.10*(Y-620),475-0.10*(Y-620))),between(Y,800,1090)*between(X,260+0.02*(Y-800),450-0.02*(Y-800)))'
$innerMaskFilter = "format=rgb24,geq=r='if($innerCondition,255,0)':g='if($innerCondition,255,0)':b='if($innerCondition,255,0)',boxblur=2:1"
Invoke-Checked -FilePath $FfmpegBin -Label 'Create conservative inner-garment mask' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'lavfi', '-i', 'color=c=black:s=704x1216',
    '-vf', $innerMaskFilter,
    '-frames:v', '1', '-update', '1',
    $innerMask
)

Invoke-Checked -FilePath $FfmpegBin -Label 'Union garment masks' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $colourMask, '-i', $innerMask,
    '-filter_complex', "[0:v][1:v]blend=all_expr='max(A,B)'[m]",
    '-map', '[m]', '-frames:v', '1', '-update', '1',
    $unionMask
)

Invoke-Checked -FilePath $FfmpegBin -Label 'Apply garment-only colour correction' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $citySource, '-i', $huePreview, '-i', $unionMask,
    '-filter_complex', '[0:v][1:v][2:v]maskedmerge[out]',
    '-map', '[out]', '-frames:v', '1', '-update', '1',
    $cityColourMatched
)

Invoke-Checked -FilePath $FfmpegBin -Label 'Prepare city-gate delivery keyframe' -Arguments @(
    '-hide_banner', '-loglevel', 'error', '-y',
    '-i', $cityColourMatched,
    '-vf', $standardScale,
    '-frames:v', '1', '-update', '1',
    $cityPrepared
)

$expectedNames = @(
    'S01_S03_hero_1080x1920.png',
    'S02A_door_1080x1920.png',
    'S02B_attendant_closeup_1080x1920.png',
    'S04_star_chart_clean_crop_1080x1920.png',
    'S05_S06_city_gate_master_1080x1920.png'
)

$records = foreach ($name in $expectedNames) {
    $path = Join-Path $prepared $name
    $probe = & $FfprobeBin -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 $path
    if ($LASTEXITCODE -ne 0 -or $probe.Trim() -ne '1080x1920') {
        throw "Prepared keyframe has invalid dimensions: $path ($probe)"
    }
    $file = Get-Item -LiteralPath $path
    [pscustomobject][ordered]@{
        file = $file.FullName
        width = 1080
        height = 1920
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
}

$manifest = [ordered]@{
    schema_version = '1.0'
    generated_at = (Get-Date).ToString('o')
    deterministic = $true
    ffmpeg = (& $FfmpegBin -version | Select-Object -First 1)
    prepared_keyframes = @($records)
    notes = @(
        'S04 is cropped entirely inside the nonlinguistic blue chart disk.',
        'S05/S06 hue correction is confined to the recorded union garment mask.',
        'No face enhancer, generative inpaint, reference-video frame or external image asset is used in this preparation stage.'
    )
}
$manifestPath = Join-Path $prepared 'manifest.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8

$manifest | ConvertTo-Json -Depth 6
