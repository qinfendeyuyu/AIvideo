<#
Runs the official Wan VACE source implementation with a local character
reference.  Compatibility mode is a conservative first run for an 8 GB GPU;
quality mode raises the shot to two seconds / 50 official sampling steps.
#>
[CmdletBinding()]
param(
    [ValidateSet('compatibility', 'quality-segment', 'quality')]
    [string]$Mode = 'compatibility',
    [string]$ReferenceImage = 'data\outputs\real_local_talking_episode_20260805\images\scene_01.png'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv-vace\Scripts\python.exe'
$sourceRoot = Join-Path $projectRoot 'third_party\Wan2.1'
$modelRoot = Join-Path $projectRoot 'models\vace\1.3b'
$outputRoot = Join-Path $projectRoot "data\outputs\vace_walk_reference_$Mode"
$outputFile = Join-Path $outputRoot 'vace_reference_walk.mp4'
$referencePath = Join-Path $projectRoot $ReferenceImage

if (-not (Test-Path -LiteralPath $python)) { throw "Missing VACE Python runtime: $python" }
if (-not (Test-Path -LiteralPath $referencePath)) { throw "Missing reference image: $referencePath" }
if (-not (Test-Path -LiteralPath (Join-Path $modelRoot 'diffusion_pytorch_model.safetensors'))) {
    throw "Missing VACE weights. Run scripts\\vace_download_all.ps1 first."
}

if ($Mode -eq 'quality') {
    $frameNum = 33
    $steps = 50
} elseif ($Mode -eq 'quality-segment') {
    # Keep the proven 17-frame memory footprint on an 8 GB GPU, but increase
    # the denoising work for faces and background detail.  Longer shots are
    # assembled from overlapping segments after each one passes visual QA.
    $frameNum = 17
    $steps = 45
} else {
    $frameNum = 17
    $steps = 30
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$env:PYTHONPATH = $sourceRoot
$env:WAN_VACE_TEXT_CACHE_DIR = Join-Path $projectRoot 'data\cache\vace_text_conditions'
$env:WAN_VACE_VAE_CACHE_CPU = '0'
$env:WAN_VACE_VAE_CPU = '1'
$env:WAN_VACE_VAE_TILING = '0'
# On this 32 GB / 8 GB setup, loading the 1.3B BF16 transformer directly to
# CUDA avoids exhausting Windows' relatively small system commit limit.
$env:WAN_VACE_LOAD_DIT_GPU = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:CUDA_MODULE_LOADING = 'LAZY'
$env:TOKENIZERS_PARALLELISM = 'false'
$prompt = 'The same young East Asian woman from the reference image, preserving her clear facial features, short black hair, and dark teal high-collar jacket. A full-body vertical shot on a neon-lit rainy subway platform at night. She takes two continuous steps from right to left, arms swinging naturally, jacket and hair moving in the light wind and rain. The camera tracks smoothly from a low angle and pulls back slightly. Realistic continuous motion, a sharp full body, cinematic photorealistic lighting.'

& $python (Join-Path $sourceRoot 'generate.py') `
    --task vace-1.3B `
    --size '480*832' `
    --frame_num $frameNum `
    --ckpt_dir $modelRoot `
    --offload_model True `
    --t5_cpu `
    --src_ref_images $referencePath `
    --prompt $prompt `
    --base_seed 20260806 `
    --sample_solver unipc `
    --sample_steps $steps `
    --sample_shift 16 `
    --sample_guide_scale 5.0 `
    --save_file $outputFile

if ($LASTEXITCODE -ne 0) { throw "VACE generation failed with exit code $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $outputFile)) { throw "VACE exited without producing: $outputFile" }
Write-Output "VACE_OUTPUT=$outputFile"
