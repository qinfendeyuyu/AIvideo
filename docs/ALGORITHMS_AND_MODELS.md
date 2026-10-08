# 算法、模型与实际实现

本页描述本仓库当前的**本地免费网关**，不是把上游模型的全部能力都算作本项目功能。代码核对日期：2026-10-08。项目接入已有模型进行推理，**没有训练或发布自有基础模型**，也没有已验收的角色专属 LoRA。

入口是 [local_free_gateway.py](../scripts/local_free_gateway.py) 与[本地工作台](../app/static/local_free.html)。三个入口可独立调用：文本草案、静帧、单首帧视频；由人选择与审核素材，不会自动从一句话完成整集。

## 1. 模型分工与真实参数

| 环节 | 当前模型 / 组件 | 网关实际采用的设置 |
| --- | --- | --- |
| 剧本与提示词草案 | Ollama `qwen2.5:7b` | CPU；上下文 4096 token，最多输出 2048 token；`temperature=0.45`；请求结束后卸载 |
| 文生图 | `RealVisXL_V5.0_fp16.safetensors` | 40 步，CFG 5.5，`dpmpp_2m_sde` + `karras`，`denoise=1.0`，一次一张 |
| 图生视频主模型 | `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | 20 步，CFG 5.5，`unipc`，`shift=5.0`，BF16 基础精度 + scaled FP8 权重 |
| 视频文本条件 | `umt5-xxl-enc-fp8_e4m3fn.safetensors` | `WanVideoTextEncodeCached`；CPU 编码、磁盘缓存 |
| 首帧视觉条件 | `open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors` | CLIP Vision 编码，使用一张首帧 |
| 视频潜空间编解码 | `wan_2.1_vae.safetensors` | BF16；当前 `enable_vae_tiling=false` |
| 视频导出 | VideoHelperSuite `VHS_VideoCombine` | H.264 / MP4，8 fps，无音轨 |

图片原生尺寸：竖图 720×1280、横图 1280×720、方图 1024×1024。图片 JSON 模板中保留的 832×1216 会被网关覆盖；判断实际输出应同时看模板和 `_workflow()`，不能只看模板默认值。

视频固定原生尺寸 480×832，约为 15:26，**不是精确 9:16，更不是 1080p**。请求中的 `duration=2/3/4` 对应 17/25/33 帧，关系为 `frames = duration × 8 + 1`；按 8 fps 封装时，文件通常长 2.125 / 3.125 / 4.125 秒。网关没有自动补帧或裁切这多出的一帧。

参数依据：[图像工作流](../workflows/realvisxl_v5_vertical_hero_portrait_single_api.json)、[视频工作流](../workflows/toonflow_local_wan_i2v_template.json)、[网关代码](../scripts/local_free_gateway.py)。这些是本项目的低显存配置，不应当作模型发布方的最佳画质基准。

## 2. 文本：自回归语言模型，不是自动导演系统

Qwen2.5-7B-Instruct 是约 7.61B 参数的 Transformer 因果语言模型，使用 RoPE、SwiGLU、RMSNorm 和 GQA 等结构；按上下文逐个预测后续 token。这里用它起草中文剧情、镜头描述和英文提示词，不用它直接生成画面。[Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)

网关实际请求本机 Ollama 的 `qwen2.5:7b` 标签，并设置 `num_gpu=0`、`num_ctx=4096`、`num_predict=2048`、`keep_alive=0`。这是为了给图像与视频留出显存；模型官方支持的更长上下文，不等于本接口已经开放该长度。Ollama 标签对应的本机模型摘要、量化格式仍需部署者核验，网关未将其锁定为不可变哈希。[Ollama 模型条目](https://ollama.com/library/qwen2.5:7b)

目前没有结构化分镜 JSON 的强制校验、自动人物设定库、长剧集记忆或剧情事实检查。输出需要人工编辑，不能把语言模型的描述当作视频动作一定能被执行的保证。

## 3. 静帧：SDXL 系列潜空间扩散

RealVisXL V5 是面向写实图像的 SDXL 系列模型。本项目采用其已有权重；没有自行训练这个模型。[RealVisXL 发布方模型卡](https://huggingface.co/SG161222/RealVisXL_V5.0)

SDXL 的基本思路是在较小的潜空间中进行条件扩散采样，再通过 VAE 解码成图像。文本编码器将提示词转换为条件；模型在采样过程中逐步估计图像结构与细节。SDXL 可以接 Refiner，但当前工作流**只有一个 RealVisXL checkpoint，不加载独立 Refiner**。[SDXL 官方模型卡](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)

本项目的顺序是：加载 checkpoint → 正负提示词编码 → 指定尺寸的 latent → KSampler → VAE 解码 → PNG。

- `dpmpp_2m_sde` 是采用随机微分方程形式的 DPM++ 采样器；`karras` 控制采样噪声等级的分布。采样器与调度器不是另一个图像模型。[k-diffusion 上游实现](https://github.com/crowsonkb/k-diffusion)
- CFG 控制条件引导强度，负面提示词参与条件引导；它们不是人脸、肢体或水印的硬性约束。提高 CFG 或步数不保证质量单调上升。
- 当前入口是**纯文生图**，不接受参考图和蒙版，不调用 ControlNet、IP-Adapter、人脸修复、超分或角色 LoRA。仓库中另有历史修图工作流，不代表本入口已经接入它们。

清晰人脸需要合适的首帧构图、主体像素面积、光照和人工筛选。不能仅靠提示词写“8K”就得到真实 8K 细节，也不能用放大尺寸冒充原生精度。

## 4. 动态镜头：Wan2.1 单首帧图生视频

Wan2.1 使用 Flow Matching 框架下的 Diffusion Transformer（DiT），结合时空 VAE 和文本条件生成视频潜变量；Wan-VAE 负责视频的时空压缩与解码。这里使用的是 **I2V-14B-480P** 路线，不是 T2V，也不是 Wan2.2 或其他上游演示模型。[Wan2.1 官方架构说明](https://github.com/Wan-Video/Wan2.1#introduction-of-wan21)

当前视频工作流执行以下步骤：

1. 检查首帧确实为 PNG、JPEG 或 WebP，拒绝远程 URL 与本地文件路径；通过后上传给同机 ComfyUI。
2. 将首帧以 Lanczos 重采样并中心裁切至 480×832。输入图边缘可能被裁掉，所以人脸和重要道具不宜贴边。
3. 用 UMT5 编码正负文本；用 CLIP Vision 编码首帧，同时由 Wan-VAE 准备首帧潜空间条件。
4. 通过 WanVideoSampler 生成 17、25 或 33 帧潜变量；当前使用 `unipc`。UniPC 属于预测—校正采样框架，不是动作识别或骨骼动画模块。[UniPC 作者实现](https://github.com/wl-zhao/UniPC)
5. Wan-VAE 解码后导出 H.264 MP4；网关核验尺寸、帧率、总帧数，并要求 FFmpeg 完整解码无错误后才标记成功。

这是生成新的时序图像，不是对一张静图做平移缩放。不过，“走路”“打斗”“镜头推进”目前只通过文字引导，**没有骨骼、轨迹、摄影机矩阵或动作参考视频控制**，因此不能保证动作幅度、物理接触、脸部稳定或镜头路径符合要求。单首帧也不等于跨镜头身份锁定。

当前没有尾帧条件、额外参考图、视频参考、音频驱动、自动口型、配音、超分、插帧或自动整集合成。Toonflow 供应商会明确拒绝这些不支持的参数，见 [localFreeV2.ts](../integrations/toonflow/localFreeV2.ts)。

## 5. 8GB 显存策略：用内存与等待换显存空间

这些策略解决的是资源占用，不是质量上限：

- **Scaled FP8 权重**：视频主模型使用带缩放的低精度权重表示，基础运算精度仍配置为 BF16；不能据此宣称与完整 BF16 结果逐像素相同。权重来源是 [Kijai 转换发布仓库](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled)，不是本项目转换或训练的专属模型。
- **Block swap**：当前配置 `blocks_to_swap=37`，并卸载图像与文本 embedding。Wan 14B 有 40 个 Transformer block，交换机制在 CPU 内存与 GPU 之间搬运部分模块，以减少驻留显存；额外传输会增加等待与主内存压力。[WanVideoWrapper 节点定义](https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/main/nodes_model_loading.py)
- **CPU 文本编码和缓存**：Qwen 与视频 UMT5 文本处理使用 CPU；视频文本节点开启磁盘缓存，避免相同条件重复编码。网关本身不实现该节点内部的模型加载和缓存算法。
- **串行图片 / 视频任务**：同一任务目录只有一个工作进程、一个媒体任务处于提交或运行状态。但它不控制其他程序向 ComfyUI 提交任务，也不是整台机器的 GPU 全局互斥锁。
- **Windows 提交内存预检**：文本、图片、视频分别要求可用提交内存至少 6 / 8 / 16 GiB。这不是显存读数，也不是机器标称 RAM；达到门槛仍可能 OOM。程序不会自动修改页面文件或关闭其他应用。

当前 VAE tiling 明确关闭，不能将“VAE 分块解码”列为本工作流已开启的省显存能力。开发机还有未随仓库发布的 ComfyUI / WanVideoWrapper 外部低内存修改，因此只下载上游代码**尚不等于复现 4060 Laptop 8GB 的完整运行环境**。版本基线与缺口见[公开部署说明](PUBLIC_DEPLOYMENT.md)。

## 6. 可恢复任务与质量验收是两回事

任务以 JSON 原子替换落盘，保存种子、请求参数、构造的工作流和 ComfyUI `prompt_id`。网关重启后继续查询已确认的任务；如果提交结果未知，则转为 `needs_attention` 并暂停后续媒体任务，避免盲目重复占用显卡。

这属于应用层排队与故障恢复，不是新训练算法。当前没有记录所有模型文件的内容哈希，也没有锁定全部驱动、节点及依赖版本；**固定 seed 只帮助复查，不能保证跨环境逐像素复现**。

自动验收只检查“文件能否读取、格式与声明是否一致”。它不判断脸是否漂亮、眼睛是否错位、动作是否真实或角色是否同一个人。建议每镜人工检查：五官与手部、主体和背景清晰度、服装连续性、动作接触、时序闪烁、裁切及最终声音/素材权利。网关状态 `succeeded` 意味着素材生成与结构校验成功，不意味着商业画质验收通过。

## 7. 历史实验与后续方向

[models.example.yaml](../configs/models.example.yaml) 的旧流水线、SadTalker、系统 SAPI 配音，以及其他历史脚本，不是新网关的运行配置。新网关不读取该 YAML；旧路线中未清权的声音和肖像驱动不能因为源代码在仓库内就视为可商用。

角色 LoRA / 参考条件、动作控制、无损中间素材管理、质量评分、插帧超分、配音口型和整集剪辑都可以是后续工程方向，但当前没有在此入口完成和验收。引入每项能力前都需要重新核验实际模型、依赖许可证、素材授权、资源需求和输出效果。

延长生成时间只能允许更复杂的计算、更多候选与人工返修，不能承诺免费模型最终达到指定商业样片的效果。软件源码许可也不会覆盖模型权重、输入素材或输出内容的权利；具体记录见[商业权利核验台账](COMMERCIAL_RIGHTS_LEDGER.md)，以实际使用版本的发布方许可与授权为准。
