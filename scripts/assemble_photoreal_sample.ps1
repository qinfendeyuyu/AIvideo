[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputDirectory,

    [Parameter(Mandatory = $true)]
    [string]$OutputVideo,

    [string]$ConfigFile = 'assembly.json',
    [string]$FfmpegPath = 'ffmpeg',
    [string]$FfprobePath = 'ffprobe',

    [ValidateRange(0, 30)]
    [int]$Crf = 18,

    [ValidateSet('medium', 'slow', 'slower')]
    [string]$Preset = 'slow'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TargetWidth = 1080
$TargetHeight = 1920
$TargetFps = 30
$TargetFrames = 300
$TargetDuration = 10.0
$TargetIntegratedLufs = -14.0
# Leave AAC headroom, then independently enforce a final true peak <= -1.0 dBTP.
$EncodeTruePeakDbtp = -1.5
$MaximumFinalTruePeakDbtp = -1.0
$LoudnessToleranceLu = 0.5
$InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture

function Resolve-ExecutablePath {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }

    $command = Get-Command -Name $Value -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) {
        throw "$Label executable was not found: $Value"
    }
    return $command.Source
}

function Get-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [switch]$Required
    )

    $property = $Object.PSObject.Properties[$Name]
    if (-not $property) {
        if ($Required) {
            throw "Required configuration property is missing: $Name"
        }
        return $null
    }
    return $property.Value
}

function ConvertTo-FiniteDouble {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $number = 0.0
    $text = [Convert]::ToString($Value, $InvariantCulture)
    if (-not [double]::TryParse(
            $text,
            [System.Globalization.NumberStyles]::Float,
            $InvariantCulture,
            [ref]$number
        ) -or [double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        throw "$Label must be a finite number; received '$text'."
    }
    return $number
}

function Format-FilterNumber {
    param([Parameter(Mandatory = $true)][double]$Value)
    return $Value.ToString('0.#########', $InvariantCulture)
}

function Resolve-ContainedInputFile {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Label path is empty."
    }

    $candidate = if ([System.IO.Path]::IsPathRooted($Value)) {
        [System.IO.Path]::GetFullPath($Value)
    }
    else {
        [System.IO.Path]::GetFullPath((Join-Path $Root $Value))
    }

    $rootPrefix = $Root.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must remain inside the input directory: $candidate"
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "$Label file was not found: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Assert-Extension {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not [string]::Equals(
            [System.IO.Path]::GetExtension($Path),
            $Expected,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
        throw "$Label must be a $Expected file: $Path"
    }
}

function Invoke-ProbeJson {
    param(
        [Parameter(Mandatory = $true)][string]$Ffprobe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    # Windows PowerShell converts a native program's stderr into ErrorRecord
    # objects. With the script-wide Stop policy that would turn diagnostic
    # output into a terminating PowerShell error before we can inspect the
    # native exit code. Native exit codes remain the source of truth here.
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = (& $Ffprobe @Arguments 2>&1 | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        throw "$FailureMessage ffprobe exit code: $exitCode. $($raw.Trim())"
    }
    try {
        return $raw | ConvertFrom-Json
    }
    catch {
        throw "$FailureMessage ffprobe returned invalid JSON: $($_.Exception.Message)"
    }
}

function Invoke-FullDecodeCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Ffmpeg,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet('video', 'audio')][string]$Kind,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $map = if ($Kind -eq 'video') { '0:v:0' } else { '0:a:0' }
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = (& $Ffmpeg -hide_banner -loglevel error -nostdin -xerror -i $Path -map $map -f null - 2>&1 | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        throw "$Label failed the full $Kind decode check (ffmpeg exit $exitCode): $Path. $($raw.Trim())"
    }
}

function Get-LoudnormMeasurement {
    param(
        [Parameter(Mandatory = $true)][string]$Ffmpeg,
        [Parameter(Mandatory = $true)][string]$InputPath,
        [Parameter(Mandatory = $true)][string]$Filter,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = (& $Ffmpeg -hide_banner -nostats -nostdin -i $InputPath -map '0:a:0' -af $Filter -f null - 2>&1 | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        throw "$Label failed (ffmpeg exit $exitCode): $($raw.Trim())"
    }

    $jsonMatches = [regex]::Matches($raw, '(?s)\{\s*"input_i"\s*:.*?\}')
    if ($jsonMatches.Count -eq 0) {
        throw "$Label did not return loudnorm JSON."
    }

    try {
        return $jsonMatches[$jsonMatches.Count - 1].Value | ConvertFrom-Json
    }
    catch {
        throw "$Label returned invalid loudnorm JSON: $($_.Exception.Message)"
    }
}

function Get-RationalValue {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $parts = $Value -split '/'
    if ($parts.Count -ne 2) {
        throw "$Label is not a rational value: $Value"
    }
    $numerator = ConvertTo-FiniteDouble -Value $parts[0] -Label "$Label numerator"
    $denominator = ConvertTo-FiniteDouble -Value $parts[1] -Label "$Label denominator"
    if ($denominator -eq 0) {
        throw "$Label has a zero denominator: $Value"
    }
    return $numerator / $denominator
}

function ConvertTo-FilterPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    # The subtitle path is copied to a GUID work directory first. These escapes
    # are still required for a Windows drive colon inside an ffmpeg filter graph.
    return $Path.Replace('\', '/').Replace(':', '\:').Replace("'", "\'").Replace('[', '\[').Replace(']', '\]')
}

function Assert-FfmpegCapability {
    param(
        [Parameter(Mandatory = $true)][string]$Ffmpeg,
        [Parameter(Mandatory = $true)][ValidateSet('encoder', 'filter')][string]$Kind,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = (& $Ffmpeg -hide_banner -h "$Kind=$Name" 2>&1 | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0 -or $raw -match 'not recognized' -or $raw -match 'Unknown') {
        throw "ffmpeg does not provide the required $Kind '$Name'."
    }
}

$workDirectory = $null
$partialOutput = $null
$committedPaths = New-Object System.Collections.Generic.List[string]
$success = $false

try {
    $ffmpeg = Resolve-ExecutablePath -Value $FfmpegPath -Label 'ffmpeg'
    $ffprobe = Resolve-ExecutablePath -Value $FfprobePath -Label 'ffprobe'
    Assert-FfmpegCapability -Ffmpeg $ffmpeg -Kind encoder -Name 'libx264'
    Assert-FfmpegCapability -Ffmpeg $ffmpeg -Kind filter -Name 'subtitles'
    Assert-FfmpegCapability -Ffmpeg $ffmpeg -Kind filter -Name 'loudnorm'

    if (-not (Test-Path -LiteralPath $InputDirectory -PathType Container)) {
        throw "Input directory was not found: $InputDirectory"
    }
    $inputRoot = (Resolve-Path -LiteralPath $InputDirectory).Path

    $configPath = Resolve-ContainedInputFile -Root $inputRoot -Value $ConfigFile -Label 'Configuration'
    try {
        $config = [System.IO.File]::ReadAllText($configPath) | ConvertFrom-Json
    }
    catch {
        throw "Configuration is not valid JSON: $configPath. $($_.Exception.Message)"
    }

    $outputFull = [System.IO.Path]::GetFullPath($OutputVideo)
    Assert-Extension -Path $outputFull -Expected '.mp4' -Label 'Output video'
    $outputDirectory = Split-Path -Parent $outputFull
    if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    $outputDirectory = (Resolve-Path -LiteralPath $outputDirectory).Path
    $outputFull = Join-Path $outputDirectory ([System.IO.Path]::GetFileName($outputFull))
    $qaPath = [System.IO.Path]::ChangeExtension($outputFull, '.qa.json')
    $shaPath = [System.IO.Path]::ChangeExtension($outputFull, '.sha256')

    foreach ($destination in @($outputFull, $qaPath, $shaPath)) {
        if (Test-Path -LiteralPath $destination) {
            throw "Refusing to overwrite an existing deliverable: $destination"
        }
    }

    $shotsValue = Get-ObjectProperty -Object $config -Name 'shots' -Required
    $shotConfigs = @($shotsValue)
    if ($shotConfigs.Count -ne 6) {
        throw "Configuration must contain exactly 6 shots; found $($shotConfigs.Count)."
    }

    $scaleModeValue = Get-ObjectProperty -Object $config -Name 'scale_mode'
    $scaleMode = if ($null -eq $scaleModeValue -or [string]::IsNullOrWhiteSpace([string]$scaleModeValue)) {
        'cover'
    }
    else {
        ([string]$scaleModeValue).ToLowerInvariant()
    }
    if ($scaleMode -notin @('cover', 'contain')) {
        throw "scale_mode must be 'cover' or 'contain'; received '$scaleMode'."
    }

    $subtitleValue = Get-ObjectProperty -Object $config -Name 'subtitle' -Required
    $subtitlePath = Resolve-ContainedInputFile -Root $inputRoot -Value ([string]$subtitleValue) -Label 'Subtitle'
    Assert-Extension -Path $subtitlePath -Expected '.ass' -Label 'Subtitle'
    $assText = [System.IO.File]::ReadAllText($subtitlePath)
    if ($assText -notmatch '(?im)^\s*\[Script Info\]\s*$' -or
        $assText -notmatch '(?im)^\s*\[Events\]\s*$' -or
        $assText -notmatch '(?im)^\s*Dialogue\s*:') {
        throw "ASS subtitle must contain [Script Info], [Events], and at least one Dialogue entry: $subtitlePath"
    }

    $resolvedShots = New-Object System.Collections.Generic.List[object]
    $seenShotPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    $totalConfiguredFrames = 0

    for ($index = 0; $index -lt $shotConfigs.Count; $index++) {
        $number = $index + 1
        $entry = $shotConfigs[$index]
        $fileValue = Get-ObjectProperty -Object $entry -Name 'file' -Required
        $startValue = Get-ObjectProperty -Object $entry -Name 'start' -Required
        $durationValue = Get-ObjectProperty -Object $entry -Name 'duration' -Required

        $shotPath = Resolve-ContainedInputFile -Root $inputRoot -Value ([string]$fileValue) -Label "Shot $number"
        Assert-Extension -Path $shotPath -Expected '.mp4' -Label "Shot $number"
        if (-not $seenShotPaths.Add($shotPath)) {
            throw "Each configured shot must reference a unique MP4; duplicate: $shotPath"
        }

        $start = ConvertTo-FiniteDouble -Value $startValue -Label "Shot $number start"
        $duration = ConvertTo-FiniteDouble -Value $durationValue -Label "Shot $number duration"
        if ($start -lt 0) { throw "Shot $number start cannot be negative." }
        if ($duration -le 0) { throw "Shot $number duration must be positive." }

        $exactFrameCount = $duration * $TargetFps
        $frameCount = [int][math]::Round($exactFrameCount)
        if ([math]::Abs($exactFrameCount - $frameCount) -gt 0.001) {
            throw "Shot $number duration must land on a 30 fps frame boundary; received $(Format-FilterNumber $duration)s."
        }
        if ($frameCount -lt 1) { throw "Shot $number must contribute at least one frame." }
        $totalConfiguredFrames += $frameCount

        Write-Host "Preflight shot $number/6: $([System.IO.Path]::GetFileName($shotPath))"
        $sourceProbe = Invoke-ProbeJson -Ffprobe $ffprobe -Arguments @(
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=index,codec_name,width,height,duration,avg_frame_rate,r_frame_rate',
            '-show_entries', 'format=duration',
            '-of', 'json',
            $shotPath
        ) -FailureMessage "Shot $number could not be probed."

        $sourceStreams = @($sourceProbe.streams)
        if ($sourceStreams.Count -ne 1) {
            throw "Shot $number must expose a readable first video stream."
        }
        $sourceStream = $sourceStreams[0]
        if ([int]$sourceStream.width -lt 1 -or [int]$sourceStream.height -lt 1) {
            throw "Shot $number has invalid dimensions."
        }
        $durationText = if ($sourceStream.PSObject.Properties['duration'] -and
            -not [string]::IsNullOrWhiteSpace([string]$sourceStream.duration) -and
            [string]$sourceStream.duration -ne 'N/A') {
            [string]$sourceStream.duration
        }
        else {
            [string]$sourceProbe.format.duration
        }
        $sourceDuration = ConvertTo-FiniteDouble -Value $durationText -Label "Shot $number source duration"
        $requiredEnd = $start + $duration
        if ($sourceDuration + 0.001 -lt $requiredEnd) {
            throw "Shot $number is too short: needs through $(Format-FilterNumber $requiredEnd)s, source duration is $(Format-FilterNumber $sourceDuration)s."
        }

        Invoke-FullDecodeCheck -Ffmpeg $ffmpeg -Path $shotPath -Kind video -Label "Shot $number"
        $resolvedShots.Add([pscustomobject][ordered]@{
                number = $number
                path = $shotPath
                start_seconds = $start
                duration_seconds = $duration
                output_frames = $frameCount
                source_duration_seconds = $sourceDuration
                source_width = [int]$sourceStream.width
                source_height = [int]$sourceStream.height
                source_codec = [string]$sourceStream.codec_name
                source_avg_frame_rate = [string]$sourceStream.avg_frame_rate
            })
    }

    if ($totalConfiguredFrames -ne $TargetFrames) {
        throw "Configured shot durations must total exactly $TargetFrames frames / 10.00 seconds; received $totalConfiguredFrames frames."
    }

    $audioPath = $null
    $audioStart = 0.0
    $audioFirstPass = $null
    $audioValue = Get-ObjectProperty -Object $config -Name 'audio'
    if ($null -ne $audioValue) {
        $audioFileValue = Get-ObjectProperty -Object $audioValue -Name 'file' -Required
        $audioStartValue = Get-ObjectProperty -Object $audioValue -Name 'start'
        if ($null -ne $audioStartValue) {
            $audioStart = ConvertTo-FiniteDouble -Value $audioStartValue -Label 'Audio start'
        }
        if ($audioStart -lt 0) { throw 'Audio start cannot be negative.' }

        $audioPath = Resolve-ContainedInputFile -Root $inputRoot -Value ([string]$audioFileValue) -Label 'Audio'
        Assert-Extension -Path $audioPath -Expected '.wav' -Label 'Audio'
        Write-Host "Preflight audio: $([System.IO.Path]::GetFileName($audioPath))"
        $audioProbe = Invoke-ProbeJson -Ffprobe $ffprobe -Arguments @(
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=index,codec_name,duration,sample_rate,channels,channel_layout',
            '-show_entries', 'format=duration',
            '-of', 'json',
            $audioPath
        ) -FailureMessage 'Audio could not be probed.'
        $audioStreams = @($audioProbe.streams)
        if ($audioStreams.Count -ne 1) {
            throw 'Audio WAV must expose a readable first audio stream.'
        }
        $audioStream = $audioStreams[0]
        $audioDurationText = if ($audioStream.PSObject.Properties['duration'] -and
            -not [string]::IsNullOrWhiteSpace([string]$audioStream.duration) -and
            [string]$audioStream.duration -ne 'N/A') {
            [string]$audioStream.duration
        }
        else {
            [string]$audioProbe.format.duration
        }
        $audioDuration = ConvertTo-FiniteDouble -Value $audioDurationText -Label 'Audio source duration'
        if ($audioDuration + 0.001 -lt ($audioStart + $TargetDuration)) {
            throw "Audio is too short: needs through $(Format-FilterNumber ($audioStart + $TargetDuration))s, source duration is $(Format-FilterNumber $audioDuration)s. Silence is not padded."
        }
        Invoke-FullDecodeCheck -Ffmpeg $ffmpeg -Path $audioPath -Kind audio -Label 'Audio'

        $analysisFilter = @(
            "atrim=start=$(Format-FilterNumber $audioStart):duration=10",
            'asetpts=PTS-STARTPTS',
            'aresample=48000',
            'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo',
            "loudnorm=I=-14:TP=$(Format-FilterNumber $EncodeTruePeakDbtp):LRA=11:print_format=json"
        ) -join ','
        $audioFirstPass = Get-LoudnormMeasurement -Ffmpeg $ffmpeg -InputPath $audioPath -Filter $analysisFilter -Label 'Audio loudness analysis'
        foreach ($measurementName in @('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')) {
            $null = ConvertTo-FiniteDouble -Value (Get-ObjectProperty -Object $audioFirstPass -Name $measurementName -Required) -Label "Audio loudnorm $measurementName"
        }
    }

    $inputPaths = @($resolvedShots | ForEach-Object { $_.path })
    if ($audioPath) { $inputPaths += $audioPath }
    $inputPaths += @($subtitlePath, $configPath)
    foreach ($inputPath in $inputPaths) {
        if ([string]::Equals($outputFull, $inputPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($qaPath, $inputPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($shaPath, $inputPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "A deliverable path would overwrite an input: $inputPath"
        }
    }

    $systemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $workDirectory = Join-Path $systemTempRoot ("assemble_photoreal_" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $workDirectory | Out-Null
    $workDirectory = (Resolve-Path -LiteralPath $workDirectory).Path
    $safeSubtitlePath = Join-Path $workDirectory 'subtitles.ass'
    Copy-Item -LiteralPath $subtitlePath -Destination $safeSubtitlePath
    $filterScriptPath = Join-Path $workDirectory 'filter_complex.txt'
    $qaTempPath = Join-Path $workDirectory 'output.qa.json'
    $shaTempPath = Join-Path $workDirectory 'output.sha256'
    $partialOutput = Join-Path $outputDirectory ('.' + [System.IO.Path]::GetFileNameWithoutExtension($outputFull) + '.partial.' + [guid]::NewGuid().ToString('N') + '.mp4')

    $scaleFilter = if ($scaleMode -eq 'cover') {
        "scale=${TargetWidth}:${TargetHeight}:force_original_aspect_ratio=increase:flags=lanczos,crop=${TargetWidth}:${TargetHeight}:(iw-${TargetWidth})/2:(ih-${TargetHeight})/2"
    }
    else {
        "scale=${TargetWidth}:${TargetHeight}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${TargetWidth}:${TargetHeight}:(ow-iw)/2:(oh-ih)/2:color=black"
    }

    $filterLines = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -lt $resolvedShots.Count; $index++) {
        $shot = $resolvedShots[$index]
        $filterLines.Add(
            "[$index`:v:0]trim=start=$(Format-FilterNumber $shot.start_seconds):duration=$(Format-FilterNumber $shot.duration_seconds)," +
            "setpts=PTS-STARTPTS,fps=fps=${TargetFps}:round=near,trim=end_frame=$($shot.output_frames)," +
            "setpts=N/(${TargetFps}*TB),$scaleFilter,setsar=1,format=yuv420p[v$index]"
        )
    }

    $concatInputs = (0..5 | ForEach-Object { "[v$_]" }) -join ''
    $escapedSubtitle = ConvertTo-FilterPath -Path $safeSubtitlePath
    $filterLines.Add(
        "${concatInputs}concat=n=6:v=1:a=0,trim=end_frame=${TargetFrames},setpts=N/(${TargetFps}*TB)," +
        "subtitles=filename='$escapedSubtitle',format=yuv420p," +
        'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[vout]'
    )

    if ($audioPath) {
        $measuredI = Format-FilterNumber (ConvertTo-FiniteDouble -Value $audioFirstPass.input_i -Label 'Audio measured I')
        $measuredTp = Format-FilterNumber (ConvertTo-FiniteDouble -Value $audioFirstPass.input_tp -Label 'Audio measured TP')
        $measuredLra = Format-FilterNumber (ConvertTo-FiniteDouble -Value $audioFirstPass.input_lra -Label 'Audio measured LRA')
        $measuredThresh = Format-FilterNumber (ConvertTo-FiniteDouble -Value $audioFirstPass.input_thresh -Label 'Audio measured threshold')
        $offset = Format-FilterNumber (ConvertTo-FiniteDouble -Value $audioFirstPass.target_offset -Label 'Audio loudnorm offset')
        $filterLines.Add(
            "[6:a:0]atrim=start=$(Format-FilterNumber $audioStart):duration=10,asetpts=PTS-STARTPTS," +
            'aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,' +
            "loudnorm=I=-14:TP=$(Format-FilterNumber $EncodeTruePeakDbtp):LRA=11:" +
            "measured_I=${measuredI}:measured_TP=${measuredTp}:measured_LRA=${measuredLra}:" +
            "measured_thresh=${measuredThresh}:offset=${offset}:linear=true:print_format=summary," +
            'atrim=start=0:duration=10,asetpts=N/SR/TB[aout]'
        )
    }

    $filterGraph = ($filterLines -join ";`r`n")
    [System.IO.File]::WriteAllText($filterScriptPath, $filterGraph, (New-Object System.Text.UTF8Encoding($false)))

    $encodeArguments = New-Object System.Collections.Generic.List[string]
    foreach ($shot in $resolvedShots) {
        $encodeArguments.Add('-i')
        $encodeArguments.Add($shot.path)
    }
    if ($audioPath) {
        $encodeArguments.Add('-i')
        $encodeArguments.Add($audioPath)
    }
    $encodeArguments.Add('-filter_complex_script')
    $encodeArguments.Add($filterScriptPath)
    $encodeArguments.Add('-map')
    $encodeArguments.Add('[vout]')
    if ($audioPath) {
        $encodeArguments.Add('-map')
        $encodeArguments.Add('[aout]')
    }
    else {
        $encodeArguments.Add('-an')
    }
    foreach ($argument in @(
            '-c:v', 'libx264',
            '-preset', $Preset,
            '-crf', [string]$Crf,
            '-profile:v', 'high',
            '-level:v', '4.1',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-fps_mode', 'cfr',
            '-frames:v', '300',
            '-color_range', 'tv',
            '-color_primaries', 'bt709',
            '-color_trc', 'bt709',
            '-colorspace', 'bt709',
            '-g', '60',
            '-keyint_min', '30',
            '-sc_threshold', '0'
        )) {
        $encodeArguments.Add($argument)
    }
    if ($audioPath) {
        foreach ($argument in @('-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2')) {
            $encodeArguments.Add($argument)
        }
    }
    foreach ($argument in @('-t', '10.000000', '-movflags', '+faststart', '-y', $partialOutput)) {
        $encodeArguments.Add($argument)
    }

    Write-Host 'Encoding strict 10.00-second sample...'
    & $ffmpeg -hide_banner -loglevel error -nostdin @encodeArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $partialOutput -PathType Leaf)) {
        throw "Final encoding failed (ffmpeg exit $LASTEXITCODE)."
    }

    Write-Host 'Running final decode/probe QA...'
    Invoke-FullDecodeCheck -Ffmpeg $ffmpeg -Path $partialOutput -Kind video -Label 'Encoded output'
    $finalProbe = Invoke-ProbeJson -Ffprobe $ffprobe -Arguments @(
        '-v', 'error',
        '-count_frames',
        '-show_entries', 'stream=index,codec_type,codec_name,profile,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration,color_range,color_space,color_transfer,color_primaries,sample_rate,channels,channel_layout',
        '-show_entries', 'format=duration,size,bit_rate,format_name',
        '-of', 'json',
        $partialOutput
    ) -FailureMessage 'Encoded output could not be probed.'

    $videoStreams = @($finalProbe.streams | Where-Object { $_.codec_type -eq 'video' })
    $audioStreams = @($finalProbe.streams | Where-Object { $_.codec_type -eq 'audio' })
    if ($videoStreams.Count -ne 1) { throw "QA expected exactly one video stream; found $($videoStreams.Count)." }
    if ($audioPath -and $audioStreams.Count -ne 1) { throw "QA expected exactly one audio stream; found $($audioStreams.Count)." }
    if (-not $audioPath -and $audioStreams.Count -ne 0) { throw 'QA found unexpected audio in a video-only assembly.' }

    $videoStream = $videoStreams[0]
    if ([string]$videoStream.codec_name -ne 'h264') { throw "QA codec mismatch: $($videoStream.codec_name)." }
    if (-not [string]::Equals([string]$videoStream.profile, 'High', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "QA H.264 profile mismatch: $($videoStream.profile)."
    }
    if ([string]$videoStream.pix_fmt -ne 'yuv420p') { throw "QA pixel format mismatch: $($videoStream.pix_fmt)." }
    if ([int]$videoStream.width -ne $TargetWidth -or [int]$videoStream.height -ne $TargetHeight) {
        throw "QA dimensions mismatch: $($videoStream.width)x$($videoStream.height)."
    }
    $rFrameRate = Get-RationalValue -Value ([string]$videoStream.r_frame_rate) -Label 'r_frame_rate'
    $avgFrameRate = Get-RationalValue -Value ([string]$videoStream.avg_frame_rate) -Label 'avg_frame_rate'
    if ([math]::Abs($rFrameRate - $TargetFps) -gt 0.000001 -or [math]::Abs($avgFrameRate - $TargetFps) -gt 0.000001) {
        throw "QA CFR mismatch: r=$($videoStream.r_frame_rate), avg=$($videoStream.avg_frame_rate)."
    }
    if ([int]$videoStream.nb_frames -ne $TargetFrames -or [int]$videoStream.nb_read_frames -ne $TargetFrames) {
        throw "QA frame count mismatch: declared=$($videoStream.nb_frames), decoded=$($videoStream.nb_read_frames), expected=$TargetFrames."
    }
    $videoDuration = ConvertTo-FiniteDouble -Value $videoStream.duration -Label 'Final video duration'
    $formatDuration = ConvertTo-FiniteDouble -Value $finalProbe.format.duration -Label 'Final container duration'
    if ([math]::Abs($videoDuration - $TargetDuration) -gt 0.001 -or [math]::Abs($formatDuration - $TargetDuration) -gt 0.02) {
        throw "QA duration mismatch: video=$(Format-FilterNumber $videoDuration)s, container=$(Format-FilterNumber $formatDuration)s."
    }
    if ([string]$videoStream.color_primaries -ne 'bt709' -or
        [string]$videoStream.color_transfer -ne 'bt709' -or
        [string]$videoStream.color_space -ne 'bt709') {
        throw "QA BT.709 tags missing: primaries=$($videoStream.color_primaries), transfer=$($videoStream.color_transfer), space=$($videoStream.color_space)."
    }

    $finalLoudness = $null
    if ($audioPath) {
        $finalAudioStream = $audioStreams[0]
        if ([string]$finalAudioStream.codec_name -ne 'aac') { throw "QA audio codec mismatch: $($finalAudioStream.codec_name)." }
        if ([int]$finalAudioStream.sample_rate -ne 48000) { throw "QA audio sample rate mismatch: $($finalAudioStream.sample_rate)." }
        $qaLoudnormFilter = 'loudnorm=I=-14:TP=-1:LRA=11:print_format=json'
        $finalLoudness = Get-LoudnormMeasurement -Ffmpeg $ffmpeg -InputPath $partialOutput -Filter $qaLoudnormFilter -Label 'Final loudness QA'
        $finalIntegrated = ConvertTo-FiniteDouble -Value $finalLoudness.input_i -Label 'Final integrated loudness'
        $finalTruePeak = ConvertTo-FiniteDouble -Value $finalLoudness.input_tp -Label 'Final true peak'
        if ([math]::Abs($finalIntegrated - $TargetIntegratedLufs) -gt $LoudnessToleranceLu) {
            throw "QA loudness mismatch: $(Format-FilterNumber $finalIntegrated) LUFS, expected -14 +/- $LoudnessToleranceLu LU."
        }
        if ($finalTruePeak -gt $MaximumFinalTruePeakDbtp) {
            throw "QA true peak too high: $(Format-FilterNumber $finalTruePeak) dBTP, maximum is -1.0 dBTP."
        }
    }

    $hash = (Get-FileHash -LiteralPath $partialOutput -Algorithm SHA256).Hash.ToLowerInvariant()
    $qa = [ordered]@{
        schema_version = 1
        status = 'passed'
        generated_utc = [DateTime]::UtcNow.ToString('o', $InvariantCulture)
        output = $outputFull
        config = $configPath
        sha256 = $hash
        target = [ordered]@{
            duration_seconds = $TargetDuration
            width = $TargetWidth
            height = $TargetHeight
            fps = $TargetFps
            frames = $TargetFrames
            codec = 'h264'
            profile = 'High'
            pixel_format = 'yuv420p'
            color = 'bt709'
            integrated_lufs = if ($audioPath) { $TargetIntegratedLufs } else { $null }
            maximum_true_peak_dbtp = if ($audioPath) { $MaximumFinalTruePeakDbtp } else { $null }
        }
        inputs = [ordered]@{
            directory = $inputRoot
            # Windows PowerShell 5.1 can throw "Argument types do not match"
            # while unrolling a generic List[object] with @(...). Materialize
            # the CLR array explicitly so QA serialization works on both 5.1
            # and PowerShell 7.
            shots = $resolvedShots.ToArray()
            subtitle = $subtitlePath
            audio = if ($audioPath) {
                [ordered]@{ path = $audioPath; start_seconds = $audioStart }
            }
            else { $null }
        }
        qa_checks = [ordered]@{
            all_inputs_fully_decodable = $true
            configured_frames_exact = $true
            output_fully_decodable = $true
            video_duration_exact = $true
            cfr_30 = $true
            frame_count_300 = $true
            dimensions_1080x1920 = $true
            h264_high = $true
            yuv420p = $true
            bt709 = $true
            audio_present = [bool]$audioPath
            loudness_passed = if ($audioPath) { $true } else { $null }
        }
        loudness_first_pass = $audioFirstPass
        loudness_final = $finalLoudness
        ffprobe = $finalProbe
    }
    $qaJson = $qa | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($qaTempPath, $qaJson, (New-Object System.Text.UTF8Encoding($false)))
    $shaLine = "$hash *$([System.IO.Path]::GetFileName($outputFull))`r`n"
    [System.IO.File]::WriteAllText($shaTempPath, $shaLine, (New-Object System.Text.UTF8Encoding($false)))

    # Commit only after every check passes. Existing deliverables were rejected above.
    Move-Item -LiteralPath $qaTempPath -Destination $qaPath
    $committedPaths.Add($qaPath)
    Move-Item -LiteralPath $shaTempPath -Destination $shaPath
    $committedPaths.Add($shaPath)
    Move-Item -LiteralPath $partialOutput -Destination $outputFull
    $partialOutput = $null
    $committedPaths.Add($outputFull)
    $success = $true

    Write-Host "PASS: $outputFull"
    Write-Host "QA:   $qaPath"
    Write-Host "SHA:  $shaPath"
}
catch {
    foreach ($path in $committedPaths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
    $failureLocation = if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {
        ' ' + $_.InvocationInfo.PositionMessage.Trim()
    }
    else { '' }
    Write-Error "ASSEMBLY FAILED: $($_.Exception.Message)$failureLocation"
    exit 1
}
finally {
    if ($partialOutput -and (Test-Path -LiteralPath $partialOutput -PathType Leaf)) {
        Remove-Item -LiteralPath $partialOutput -Force -ErrorAction SilentlyContinue
    }
    if ($workDirectory -and (Test-Path -LiteralPath $workDirectory -PathType Container)) {
        $resolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
        $resolvedWork = [System.IO.Path]::GetFullPath($workDirectory)
        $safeName = [System.IO.Path]::GetFileName($resolvedWork) -match '^assemble_photoreal_[0-9a-f]{32}$'
        if ($safeName -and $resolvedWork.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not $success) {
    exit 1
}
