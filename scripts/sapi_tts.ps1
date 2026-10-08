[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $TextPath,
    [Parameter(Mandatory = $true)] [string] $OutputPath,
    [Parameter(Mandatory = $true)] [string] $VoiceName,
    [Parameter(Mandatory = $true)] [int] $Rate
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = Get-Content -LiteralPath $TextPath -Raw -Encoding utf8
if ([string]::IsNullOrWhiteSpace($text)) { throw 'Text is empty.' }
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $available = $synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Name -eq $VoiceName }
    if (-not $available) { throw "Configured Windows voice is unavailable: $VoiceName" }
    $synth.SelectVoice($VoiceName)
    $synth.Rate = [Math]::Max(-10, [Math]::Min(10, $Rate))
    $synth.SetOutputToWaveFile($OutputPath)
    $synth.Speak($text)
} finally {
    $synth.Dispose()
}
