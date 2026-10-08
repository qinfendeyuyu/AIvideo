<#
Downloads one official Wan model file with resumable curl and atomically moves
it into the model directory only after curl reports success. This avoids a
half-downloaded shard being mistaken for a usable local model.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RelativePath,
    [string]$Repository = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers',
    [string]$ModelDirectory = 'models\wan\t2v_1.3b'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelRoot = Join-Path $projectRoot $ModelDirectory
$stagingRoot = Join-Path $modelRoot '.direct-download'
$destination = Join-Path $modelRoot $RelativePath
$staging = Join-Path $stagingRoot $RelativePath

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $staging) | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null

$uri = "https://huggingface.co/$Repository/resolve/main/$RelativePath"
$headers = @(& curl.exe --silent --show-error --head --location --max-time 60 $uri)
$sizeMatch = $headers | Select-String -Pattern '^X-Linked-Size:\s*(\d+)\s*$' | Select-Object -First 1
if ($null -eq $sizeMatch) {
    $sizeMatch = $headers | Select-String -Pattern '^content-length:\s*(\d+)\s*$' | Select-Object -Last 1
}
if ($null -eq $sizeMatch) {
    throw "Cannot determine official model file size for $RelativePath"
}
$expectedSize = [Int64]$sizeMatch.Matches[0].Groups[1].Value

if (Test-Path -LiteralPath $destination) {
    $destinationSize = (Get-Item -LiteralPath $destination).Length
    if ($destinationSize -eq $expectedSize) {
        Write-Output "READY $RelativePath"
        exit 0
    }
    if (-not (Test-Path -LiteralPath $staging)) {
        Move-Item -LiteralPath $destination -Destination $staging
    }
}

while ($true) {
    $before = if (Test-Path -LiteralPath $staging) { (Get-Item -LiteralPath $staging).Length } else { 0 }
    & curl.exe --fail --location --retry 20 --retry-delay 5 --continue-at - --output $staging $uri
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed for $RelativePath (curl exit $LASTEXITCODE). Re-run the same command to resume."
    }
    $actualSize = (Get-Item -LiteralPath $staging).Length
    if ($actualSize -eq $expectedSize) {
        break
    }
    if ($actualSize -gt $expectedSize) {
        throw "Model download size exceeds official size for ${RelativePath}: $actualSize > $expectedSize"
    }
    if ($actualSize -le $before) {
        throw "Model download made no progress for ${RelativePath}: $actualSize / $expectedSize bytes"
    }
    Write-Output "RESUME $RelativePath $actualSize/$expectedSize"
}
Move-Item -LiteralPath $staging -Destination $destination -Force
Write-Output "READY $RelativePath"
