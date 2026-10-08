<#!
Download the exact FP16 files required by MimicMotion with resumable transfers.

The script intentionally does not download optional demo videos.  Every file is
verified by byte length so a failed or truncated download can never be mistaken
for a usable motion model.
#>
[CmdletBinding()]
param(
    [string]$MirrorBase = "https://huggingface.co"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot "third_party\MimicMotion"
$modelRoot = Join-Path $projectRoot "models\mimicmotion"
$svdRoot = Join-Path $modelRoot "svd_xt_1_1"
$tokenGetter = Join-Path $projectRoot ".venv-mimicmotion\Scripts\python.exe"
$hfToken = $env:HF_TOKEN

# Prefer a token passed by environment variable, but fall back to the official
# Hugging Face CLI login cache. Do not print or persist the token here.
if ([string]::IsNullOrWhiteSpace($hfToken) -and (Test-Path -LiteralPath $tokenGetter)) {
    $hfToken = (& $tokenGetter -c "from huggingface_hub import get_token; print(get_token() or '')").Trim()
}

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "inference.py"))) {
    throw "MimicMotion source is missing: $sourceRoot"
}

$files = @(
    @{ RelativePath = "MimicMotion_1-1.pth"; Bytes = 3049867447; Url = "$MirrorBase/tencent/MimicMotion/resolve/main/MimicMotion_1-1.pth" },
    @{ RelativePath = "svd_xt_1_1\image_encoder\config.json"; Bytes = 685; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/image_encoder/config.json" },
    @{ RelativePath = "svd_xt_1_1\image_encoder\model.fp16.safetensors"; Bytes = 1264217240; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/image_encoder/model.fp16.safetensors" },
    @{ RelativePath = "svd_xt_1_1\unet\config.json"; Bytes = 984; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/unet/config.json" },
    @{ RelativePath = "svd_xt_1_1\unet\diffusion_pytorch_model.fp16.safetensors"; Bytes = 3049435836; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/unet/diffusion_pytorch_model.fp16.safetensors" },
    @{ RelativePath = "svd_xt_1_1\vae\config.json"; Bytes = 607; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/vae/config.json" },
    @{ RelativePath = "svd_xt_1_1\vae\diffusion_pytorch_model.fp16.safetensors"; Bytes = 195531910; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/vae/diffusion_pytorch_model.fp16.safetensors" },
    @{ RelativePath = "svd_xt_1_1\scheduler\scheduler_config.json"; Bytes = 533; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/scheduler/scheduler_config.json" },
    @{ RelativePath = "svd_xt_1_1\feature_extractor\preprocessor_config.json"; Bytes = 518; Url = "$MirrorBase/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/feature_extractor/preprocessor_config.json" },
    @{ RelativePath = "dwpose\yolox_l.onnx"; Bytes = 216746733; Url = "$MirrorBase/yzd-v/DWPose/resolve/main/yolox_l.onnx" },
    @{ RelativePath = "dwpose\dw-ll_ucoco_384.onnx"; Bytes = 134399116; Url = "$MirrorBase/yzd-v/DWPose/resolve/main/dw-ll_ucoco_384.onnx" }
)

foreach ($file in $files) {
    $target = Join-Path $modelRoot $file.RelativePath
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $currentBytes = if (Test-Path -LiteralPath $target) { (Get-Item -LiteralPath $target).Length } else { 0 }
    if ($currentBytes -eq $file.Bytes) {
        Write-Host "Verified: $($file.RelativePath)"
        continue
    }
    if ($currentBytes -gt $file.Bytes) {
        throw "Downloaded file exceeds its official expected length: $target"
    }

    Write-Host "Downloading $($file.RelativePath) ($currentBytes / $($file.Bytes) bytes)"
    # hf-mirror rejects a Range header starting at byte zero for some small
    # metadata files.  Send a range request only when there is real partial
    # content to resume; each script re-run then obtains a fresh signed URL.
    $curlArgs = @("--fail", "--location", "--silent", "--show-error", "--retry", "0", "--connect-timeout", "30", "--output", $target)
    # The SVD base is a gated model. A local CLI login token (or a token in
    # the current process environment) is forwarded but is never logged or
    # written to the project configuration.
    if (-not [string]::IsNullOrWhiteSpace($hfToken)) {
        $curlArgs += @("--header", "Authorization: Bearer $hfToken")
    }
    if ($currentBytes -gt 0) {
        $curlArgs += @("--continue-at", "-")
    }
    & curl.exe @curlArgs $file.Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed for $($file.RelativePath); rerun this script to resume."
    }
    $finalBytes = (Get-Item -LiteralPath $target).Length
    if ($finalBytes -ne $file.Bytes) {
        throw "Incomplete download for $($file.RelativePath): expected $($file.Bytes), got $finalBytes. Rerun to resume."
    }
    Write-Host "Verified: $($file.RelativePath)"
}

Write-Host "MimicMotion FP16 model files are complete: $modelRoot"
