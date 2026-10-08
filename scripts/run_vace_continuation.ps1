<#
Generate a memory-safe VACE continuation with a retained six-frame prefix.
The prompt intentionally matches the cached first segment prompt so this
32 GB workstation does not reload the 11 GB T5 encoder.
#>
[CmdletBinding()]
param(
    [ValidateSet('compatibility', 'quality-segment')]
    [string]$Mode = 'quality-segment',
    [string]$PreviousVideo = 'data\outputs\vace_walk_reference_quality-segment\vace_reference_walk.mp4',
    [string]$ReferenceImage = 'data\outputs\real_local_face_episode_20260805\images\scene_01.png',
    [int]$KeepFrames = 6,
    [int64]$Seed = 20260807
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv-vace\Scripts\python.exe'
$sourceRoot = Join-Path $projectRoot 'third_party\Wan2.1'
$modelRoot = Join-Path $projectRoot 'models\vace\1.3b'
$outputRoot = Join-Path $projectRoot "data\outputs\vace_walk_continuation_$Mode"
$conditionRoot = Join-Path $outputRoot 'conditions'
$outputFile = Join-Path $outputRoot 'vace_continuation.mp4'
$previousPath = Join-Path $projectRoot $PreviousVideo
$referencePath = Join-Path $projectRoot $ReferenceImage
$conditionBuilder = Join-Path $projectRoot 'scripts\build_vace_firstclip_condition.py'
$sourceVideo = Join-Path $conditionRoot 'firstclip_source.mp4'
$sourceMask = Join-Path $conditionRoot 'firstclip_mask.mp4'

if (-not (Test-Path -LiteralPath $python)) { throw "Missing VACE Python runtime: $python" }
if (-not (Test-Path -LiteralPath $previousPath)) { throw "Missing previous video: $previousPath" }
if (-not (Test-Path -LiteralPath $referencePath)) { throw "Missing reference image: $referencePath" }
if (-not (Test-Path -LiteralPath (Join-Path $modelRoot 'diffusion_pytorch_model.safetensors'))) {
    throw "Missing VACE weights."
}

$frameNum = 17
$steps = if ($Mode -eq 'quality-segment') { 45 } else { 30 }
New-Item -ItemType Directory -Force -Path $conditionRoot | Out-Null
& $python $conditionBuilder $previousPath $conditionRoot `
    --total-frames $frameNum --keep-frames $KeepFrames --fps 16
if ($LASTEXITCODE -ne 0) { throw "First-clip condition build failed: $LASTEXITCODE" }

$env:PYTHONPATH = $sourceRoot
$env:WAN_VACE_TEXT_CACHE_DIR = Join-Path $projectRoot 'data\cache\vace_text_conditions'
$env:WAN_VACE_VAE_CACHE_CPU = '0'
$env:WAN_VACE_VAE_CPU = '1'
$env:WAN_VACE_VAE_TILING = '0'
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
    --src_video $sourceVideo `
    --src_mask $sourceMask `
    --src_ref_images $referencePath `
    --prompt $prompt `
    --base_seed $Seed `
    --sample_solver unipc `
    --sample_steps $steps `
    --sample_shift 16 `
    --sample_guide_scale 5.0 `
    --save_file $outputFile

if ($LASTEXITCODE -ne 0) { throw "VACE continuation failed with exit code $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $outputFile)) { throw "VACE exited without producing: $outputFile" }
Write-Output "VACE_CONTINUATION_OUTPUT=$outputFile"
