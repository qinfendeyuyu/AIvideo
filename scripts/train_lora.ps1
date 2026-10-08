[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Config,
    [Parameter(Mandatory = $true)] [string] $Dataset,
    [int] $MinImages = 80,
    [string] $Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& $Python (Join-Path $PSScriptRoot "validate_dataset.py") $Dataset --min-images $MinImages
if ($LASTEXITCODE -ne 0) { throw "Dataset validation failed; training was not started." }

if (-not $env:SD_SCRIPTS) {
    throw "Set SD_SCRIPTS to a local sd-scripts checkout before training."
}
$trainer = Join-Path $env:SD_SCRIPTS "sdxl_train_network.py"
if (-not (Test-Path -LiteralPath $trainer)) {
    throw "sdxl_train_network.py not found: $trainer"
}
if (-not (Test-Path -LiteralPath $Config)) {
    throw "Training config not found: $Config"
}

& $Python $trainer --config_file $Config
if ($LASTEXITCODE -ne 0) { throw "LoRA trainer exited with code $LASTEXITCODE" }