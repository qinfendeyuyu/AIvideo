[CmdletBinding()]
param(
    [string]$FfmpegPath = 'E:\ffmpeg\bin\ffmpeg.exe',
    [string]$FfprobePath = 'E:\ffmpeg\bin\ffprobe.exe',
    [string]$OutputPath = '',
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-ExecutablePath {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }

    $command = Get-Command $Value -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "$Label executable was not found: $Value"
    }
    return $command.Source
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $projectRoot 'data\outputs\photoreal_reference_match_20260902\technical_preview_assets\procedural_soundscape_10s_48k_stereo.wav'
}

$ffmpeg = Resolve-ExecutablePath -Value $FfmpegPath -Label 'ffmpeg'
$ffprobe = Resolve-ExecutablePath -Value $FfprobePath -Label 'ffprobe'
$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputFullPath
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null

if ((Test-Path -LiteralPath $outputFullPath) -and -not $Force) {
    throw "Output already exists. Pass -Force to replace it: $outputFullPath"
}

$partialPath = "$outputFullPath.partial.wav"
if (Test-Path -LiteralPath $partialPath) {
    Remove-Item -LiteralPath $partialPath -Force
}

# Every source is deterministic: sine oscillators are analytic and all noise
# generators have fixed seeds. No recorded sample, TTS, or premade music is used.
$inputArguments = @(
    '-f', 'lavfi', '-i', 'anoisesrc=sample_rate=48000:amplitude=0.18:duration=10:color=pink:seed=24090201',
    '-f', 'lavfi', '-i', 'anoisesrc=sample_rate=48000:amplitude=0.12:duration=10:color=pink:seed=24090202',
    '-f', 'lavfi', '-i', 'sine=frequency=55:sample_rate=48000:duration=10',
    '-f', 'lavfi', '-i', 'sine=frequency=82.5:sample_rate=48000:duration=10',
    '-f', 'lavfi', '-i', 'sine=frequency=672:sample_rate=48000:duration=1.40',
    '-f', 'lavfi', '-i', 'sine=frequency=1008:sample_rate=48000:duration=1.10',
    '-f', 'lavfi', '-i', 'sine=frequency=70:sample_rate=48000:duration=0.36',
    '-f', 'lavfi', '-i', 'anoisesrc=sample_rate=48000:amplitude=0.20:duration=0.36:color=brown:seed=24090203',
    '-f', 'lavfi', '-i', 'anoisesrc=sample_rate=48000:amplitude=0.16:duration=1.25:color=pink:seed=24090204',
    '-f', 'lavfi', '-i', 'sine=frequency=88:sample_rate=48000:duration=0.24',
    '-f', 'lavfi', '-i', 'sine=frequency=210:sample_rate=48000:duration=0.92',
    '-f', 'lavfi', '-i', 'sine=frequency=315:sample_rate=48000:duration=0.78'
)

$filterGraph = @(
    '[0:a]highpass=f=90,lowpass=f=1800,volume=0.117,pan=stereo|c0=0.96*c0|c1=0.78*c0[a0]',
    '[1:a]highpass=f=300,lowpass=f=5200,volume=0.1032,pan=stereo|c0=0.72*c0|c1=0.94*c0[a1]',
    '[2:a]lowpass=f=130,volume=0.022,pan=stereo|c0=0.90*c0|c1=0.76*c0[a2]',
    '[3:a]lowpass=f=180,volume=0.010,pan=stereo|c0=0.68*c0|c1=0.86*c0[a3]',
    '[4:a]afade=t=in:st=0:d=0.008,afade=t=out:st=0.04:d=1.30,aecho=0.8:0.35:70|140:0.24|0.11,volume=0.105,pan=stereo|c0=0.82*c0|c1=0.98*c0,adelay=480|515[a4]',
    '[5:a]afade=t=in:st=0:d=0.005,afade=t=out:st=0.03:d=1.02,aecho=0.8:0.30:105:0.13,volume=0.060,pan=stereo|c0=0.98*c0|c1=0.76*c0,adelay=505|535[a5]',
    '[6:a]afade=t=in:st=0:d=0.004,afade=t=out:st=0.01:d=0.34,lowpass=f=220,volume=0.19,pan=stereo|c0=0.94*c0|c1=0.78*c0,adelay=1510|1530[a6]',
    '[7:a]highpass=f=95,lowpass=f=850,afade=t=in:st=0:d=0.01,afade=t=out:st=0.02:d=0.33,volume=0.36,pan=stereo|c0=0.84*c0|c1=0.98*c0,adelay=1475|1495[a7]',
    '[8:a]highpass=f=560,lowpass=f=5600,afade=t=in:st=0:d=0.58,afade=t=out:st=0.58:d=0.67,volume=0.50,pan=stereo|c0=0.92*c0|c1=0.68*c0,adelay=4920|4995[a8]',
    '[9:a]asplit=2[stepBase1][stepBase2]',
    '[stepBase1]afade=t=in:st=0:d=0.004,afade=t=out:st=0.01:d=0.22,lowpass=f=260,volume=0.16,pan=stereo|c0=0.96*c0|c1=0.75*c0,adelay=6850|6870[a9]',
    '[stepBase2]afade=t=in:st=0:d=0.004,afade=t=out:st=0.01:d=0.22,lowpass=f=240,volume=0.13,pan=stereo|c0=0.72*c0|c1=0.94*c0,adelay=7460|7480[a10]',
    '[10:a]afade=t=in:st=0:d=0.008,afade=t=out:st=0.03:d=0.86,aecho=0.8:0.25:85:0.10,volume=0.075,pan=stereo|c0=0.88*c0|c1=0.96*c0,adelay=8350|8370[a11]',
    '[11:a]afade=t=in:st=0:d=0.006,afade=t=out:st=0.02:d=0.73,volume=0.038,pan=stereo|c0=0.96*c0|c1=0.82*c0,adelay=8370|8390[a12]',
    '[a0][a1][a2][a3][a4][a5][a6][a7][a8][a9][a10][a11][a12]amix=inputs=13:duration=longest:dropout_transition=0,highpass=f=30,lowpass=f=16000,loudnorm=I=-20:LRA=7:TP=-2,aresample=48000,apad=whole_dur=10,atrim=duration=10,afade=t=out:st=9.60:d=0.40:curve=exp,asetpts=N/SR/TB[aout]'
) -join ';'

$encodeArguments = @(
    '-hide_banner', '-loglevel', 'warning', '-nostdin', '-y'
) + $inputArguments + @(
    '-filter_complex', $filterGraph,
    '-map', '[aout]',
    '-vn',
    '-ar', '48000',
    '-ac', '2',
    '-c:a', 'pcm_s24le',
    '-metadata', 'title=Original procedural 10-second dramatic soundscape',
    '-metadata', 'comment=Synthesized only with deterministic FFmpeg signal generators and filters; no samples and no voice.',
    $partialPath
)

& $ffmpeg @encodeArguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $partialPath -PathType Leaf)) {
    throw "Audio render failed with ffmpeg exit code $LASTEXITCODE."
}

$probeRaw = & $ffprobe -v error -show_entries 'format=duration:stream=codec_name,sample_rate,channels,channel_layout,bits_per_sample,duration,duration_ts,time_base' -of json $partialPath
if ($LASTEXITCODE -ne 0) {
    throw "ffprobe failed with exit code $LASTEXITCODE."
}
$probe = $probeRaw | ConvertFrom-Json
if ($probe.streams.Count -ne 1) {
    throw "Expected exactly one audio stream, found $($probe.streams.Count)."
}
$stream = $probe.streams[0]
$duration = [double]::Parse([string]$probe.format.duration, [Globalization.CultureInfo]::InvariantCulture)
if ([Math]::Abs($duration - 10.0) -gt 0.0005) {
    throw "Expected a 10.000-second WAV; ffprobe reported $duration seconds."
}
if ([int]$stream.sample_rate -ne 48000 -or [int]$stream.channels -ne 2) {
    throw "Expected 48 kHz stereo; ffprobe reported $($stream.sample_rate) Hz / $($stream.channels) channels."
}
if ([string]$stream.codec_name -ne 'pcm_s24le' -or [int]$stream.bits_per_sample -ne 24) {
    throw "Expected 24-bit PCM WAV; ffprobe reported $($stream.codec_name), $($stream.bits_per_sample) bits."
}

& $ffmpeg -hide_banner -loglevel error -nostdin -i $partialPath -f null NUL
if ($LASTEXITCODE -ne 0) {
    throw "The generated WAV failed a full audio decode check (ffmpeg exit $LASTEXITCODE)."
}

$volumeLog = (& $ffmpeg -hide_banner -nostats -nostdin -i $partialPath -af volumedetect -f null NUL 2>&1 | Out-String)
$peakMatch = [regex]::Match($volumeLog, 'max_volume:\s*(?<value>-?(?:\d+(?:\.\d+)?|inf))\s*dB')
if (-not $peakMatch.Success) {
    throw 'Could not read max_volume from ffmpeg volumedetect output.'
}
$samplePeakDb = [double]::Parse($peakMatch.Groups['value'].Value, [Globalization.CultureInfo]::InvariantCulture)
if ($samplePeakDb -ge -0.1) {
    throw "Unsafe sample peak detected: $samplePeakDb dBFS."
}

# A near-silent tail prevents a hard cut or click when this WAV is muxed as an
# exact 10-second track. Treat the last 50 ms as a hard delivery gate.
$tailVolumeLog = (& $ffmpeg -hide_banner -nostats -nostdin -i $partialPath -af 'atrim=start=9.95:end=10,asetpts=PTS-STARTPTS,volumedetect' -f null NUL 2>&1 | Out-String)
$tailPeakMatch = [regex]::Match($tailVolumeLog, 'max_volume:\s*(?<value>-?(?:\d+(?:\.\d+)?|inf))\s*dB')
if (-not $tailPeakMatch.Success) {
    throw 'Could not read the final 50 ms peak from ffmpeg volumedetect output.'
}
$tailPeakText = $tailPeakMatch.Groups['value'].Value
$tailPeakDb = if ($tailPeakText -eq '-inf') {
    -200.0
}
else {
    [double]::Parse($tailPeakText, [Globalization.CultureInfo]::InvariantCulture)
}
if ($tailPeakDb -gt -40.0) {
    throw "Tail-silence gate failed: final 50 ms peak is $tailPeakDb dBFS; required <= -40.0 dBFS."
}

$loudnessLog = (& $ffmpeg -hide_banner -nostats -nostdin -i $partialPath -af 'loudnorm=I=-20:LRA=7:TP=-2:print_format=json' -f null NUL 2>&1 | Out-String)
$jsonMatches = [regex]::Matches($loudnessLog, '(?s)\{\s*"input_i".*?\}')
if ($jsonMatches.Count -eq 0) {
    throw 'Could not read loudness statistics from ffmpeg loudnorm output.'
}
$loudness = $jsonMatches[$jsonMatches.Count - 1].Value | ConvertFrom-Json

if (Test-Path -LiteralPath $outputFullPath) {
    Remove-Item -LiteralPath $outputFullPath -Force
}
Move-Item -LiteralPath $partialPath -Destination $outputFullPath

$hash = (Get-FileHash -LiteralPath $outputFullPath -Algorithm SHA256).Hash
$qa = [ordered]@{
    generated_utc = [DateTime]::UtcNow.ToString('o')
    path = $outputFullPath
    sha256 = $hash
    synthesis = 'Deterministic FFmpeg generators and filters only; no samples, music recording, speech, or TTS.'
    codec = [string]$stream.codec_name
    bits_per_sample = [int]$stream.bits_per_sample
    sample_rate_hz = [int]$stream.sample_rate
    channels = [int]$stream.channels
    channel_layout = [string]$stream.channel_layout
    duration_seconds = $duration
    duration_samples = [int64]$stream.duration_ts
    sample_peak_dbfs = $samplePeakDb
    tail_fade_start_seconds = 9.60
    tail_fade_duration_seconds = 0.40
    tail_50ms_peak_dbfs = $tailPeakDb
    tail_peak_gate_dbfs = -40.0
    integrated_lufs = [double]::Parse([string]$loudness.input_i, [Globalization.CultureInfo]::InvariantCulture)
    true_peak_dbtp = [double]::Parse([string]$loudness.input_tp, [Globalization.CultureInfo]::InvariantCulture)
    loudness_range_lu = [double]::Parse([string]$loudness.input_lra, [Globalization.CultureInfo]::InvariantCulture)
    full_decode_ok = $true
    ffmpeg = (& $ffmpeg -version | Select-Object -First 1)
}
$qaPath = Join-Path $outputDirectory 'audio_qa.json'
$qa | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $qaPath -Encoding utf8

Write-Host "Rendered: $outputFullPath"
Write-Host "SHA256:  $hash"
Write-Host ("QA: 10.000 s, 48000 Hz, stereo, PCM 24-bit, {0:N1} LUFS, {1:N1} dBTP, sample peak {2:N1} dBFS, final 50 ms peak {3:N1} dBFS" -f $qa.integrated_lufs, $qa.true_peak_dbtp, $qa.sample_peak_dbfs, $qa.tail_50ms_peak_dbfs)
Write-Host "Report:   $qaPath"
