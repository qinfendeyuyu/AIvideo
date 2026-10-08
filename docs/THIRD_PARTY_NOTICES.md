# 第三方组件、模型与许可说明

核验日期：**2026-10-08**。本文对应公开源码和默认本地网关路线；不是整机软件物料清单、法律意见或成片商用保证。

## 1. 四种权利分开处理

| 对象 | 适用规则 |
| --- | --- |
| AIvideo 自有代码与文档贡献 | 适用仓库根目录 `LICENSE` 的 Apache-2.0；不替第三方重新授权。 |
| 第三方代码、运行依赖及字体 | 适用各自版权通知和许可证。下文记录的旧 Toonflow 适配器已从当前公开版本移除；历史内容不能仅凭新增的根目录 Apache-2.0 分发。 |
| 模型权重、量化转换、LoRA、tokenizer | 核验精确文件的来源、修订号、SHA-256 和许可；工具的代码许可证不等于模型许可证。权重不随本仓库分发。 |
| 输入素材及生成图像、视频、声音 | 不因项目采用 Apache-2.0 而自动获得版权、肖像、声音、商标或商用授权。需要逐项审查。 |

“没有按次 API 费用”不等于“没有许可条件”。本仓库的本地 HTTP 调用、安装说明和模型名称也不构成第三方背书。

## 2. 已随仓库提供的第三方内容

### Noto Sans SC 字体

- 路径：`assets/fonts/NotoSansSC/NotoSansSC-VF.ttf`。
- 本次重新计算的 SHA-256：`763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`。
- 内部版本和来源记录见[字体说明](../assets/fonts/NotoSansSC/README.md)。
- 版权：2014–2021 Adobe；Reserved Font Name 为 `Source`。
- 许可：SIL Open Font License 1.1，完整文本已随文件保存为 [OFL.txt](../assets/fonts/NotoSansSC/OFL.txt)。

随项目分发字体必须保留版权和 OFL 文本；不得单独出售字体。把字幕栅格化进视频，不会使视频因此继承 OFL。修改字体还须遵守保留名称等条件。证据：[Noto CJK 官方许可](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE)。

### Toonflow 两代适配器：不能混用许可证

| 本项目文件 | 核验来源 | 处理要求 |
| --- | --- | --- |
| `integrations/toonflow/localFreeV2.ts` | 核对新版 `72a895c26aab3f54c5a914517615362208fa6008` 的 provider 协议；该版本为 MIT，版权 `2026 HBAI-Ltd`。 | 本地网关实现与上游软件分开；如分发来源于上游的协议片段/实质代码，保留对应 MIT 版权和许可文本。 |
| 历史 `integrations/toonflow/localWanComfy.ts`，不再随当前公开版本分发 | 旧版 `e03cf590eb0cab63534a4040db9acb4ec95b42a6` 的 `data/vendor/null.ts` 模板；类型声明、宿主全局声明及模板结构存在明显对应。 | 旧来源采用 Apache-2.0 **并附补充协议**，不能标成纯 Apache-2.0 或用新版 MIT 追溯覆盖。Git 历史 `a2d1fe0` 仍含该文件；未改写历史。 |

一手证据：[新版完整 MIT 许可](https://github.com/HBAI-Ltd/Toonflow-app/blob/72a895c26aab3f54c5a914517615362208fa6008/LICENSE)、[旧版模板](https://github.com/HBAI-Ltd/Toonflow-app/blob/e03cf590eb0cab63534a4040db9acb4ec95b42a6/data/vendor/null.ts)、[旧版完整许可及补充协议](https://github.com/HBAI-Ltd/Toonflow-app/blob/e03cf590eb0cab63534a4040db9acb4ec95b42a6/LICENSE)。

旧版补充协议对向多个独立第三方提供产品设置额外书面授权条件，也要求保留应用标识；它不是只有标准 Apache-2.0。**附上旧许可文本并不自动消除该授权条件。** 本轮按维护者决定从当前公开版本移除旧适配器，保留本机备份、不改写 Git 历史。若从历史提交恢复、产品化或再分发该文件，仍须核验原许可及额外授权要求；本项目不宣称历史文件“已完成无条件开源清权”。自有新增贡献的 Apache-2.0 不改变上游部分的权利状态。不要把所有历史版本或全部第三方文件描述为无例外均属 Apache-2.0。

随仓库保留的核验文本：[新版 MIT](licenses/Toonflow-72a895c2-MIT.txt)、[旧版完整许可](licenses/Toonflow-legacy-e03cf590-LICENSE.txt)。旧文本用于说明历史来源，不表示旧模板重新获授权或重新成为当前发布文件。

## 3. 默认生成路线的模型权重

以下许可结论只对应所列来源。网页核验不是本次对开发机所有模型重新下载、复算哈希或追溯训练数据的证明。历史精确权重记录见[商用权利台账](COMMERCIAL_RIGHTS_LEDGER.md)；其中未随 Git 发布的本机证据包不能当成新用户已持有的证据。

| 用途/文件 | 发布方许可证据 | 使用及分发边界 |
| --- | --- | --- |
| 文本：`qwen2.5:7b` / Qwen2.5-7B-Instruct | [Qwen 固定模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/a09a35458c702b33eeacc393d103063234e8bc28/README.md)标注 Apache-2.0；[Ollama 的 7b 条目](https://ollama.com/library/qwen2.5:7b)亦给出 Apache-2.0。 | 仅针对 7B，不能概括整个 Qwen 家族。Ollama 的标签可变，部署时记录实际模型 digest 和 `ollama show --license qwen2.5:7b` 输出。 |
| 图像：`RealVisXL_V5.0_fp16.safetensors` | 发布者[固定模型卡](https://huggingface.co/SG161222/RealVisXL_V5.0/blob/ac93e0dda1f6d448cae19bbfab8c5e720a5e48bc/README.md)声明 `openrail++`。 | 不是 Apache/MIT。遵守 Open RAIL++-M 的用途限制、分发和通知要求；不能写成不受限制的商用模型。 |
| 视频原始模型：Wan2.1 I2V 14B 480P | [官方固定许可](https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P/blob/6b73f84e66371cdfe870c72acd6826e1d61cf279/LICENSE.txt)为 Apache-2.0。 | 分发代码/权重或修改版本时履行 Apache-2.0 的通知和修改标示要求；生成内容仍需另审。 |
| 视频量化：`Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | [Kijai 固定文件页](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/blob/72cfd0d6f2269b14f94c38bfee2744e0ed172c38/I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors)声明 Apache-2.0，来源为 Wan2.1。 | 公开 SHA-256 为 `2ff922282cd84589702e6e8c26e083d1160bfc2b217dd44e1ae2688441dc495d`。本次未重新读取 16GB 权重复算，不把历史审计冒充本次验证。 |
| 文本编码：`umt5-xxl-enc-fp8_e4m3fn.safetensors` | 上游 [Google UMT5-XXL 固定模型卡](https://huggingface.co/google/umt5-xxl/blob/66cb9e7e85526fe440a945569e42c72fb6cbc0ad/README.md)为 Apache-2.0。 | 该文件是提取/转换的编码器，不是直接等同于整个上游 checkpoint；具体转换来源、revision、哈希及通知仍须补证。 |
| 视觉编码：`open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors` | 对应架构上游 [LAION OpenCLIP XLM-R 模型卡](https://huggingface.co/laion/CLIP-ViT-H-14-frozen-xlm-roberta-large-laion5B-s13B-b90k)为 MIT；核验 revision `f9ab955287d06ac45c7654f26fecd29301c70a1f`。 | 不要误写成整个 Wan 包都为 Apache。转换文件与此来源的精确对应关系、SHA-256 及 MIT 通知仍须补证；保留上游模型卡的使用与训练数据说明。 |
| 解码：`wan_2.1_vae.safetensors` | Wan2.1 官方模型许可为 Apache-2.0；本文件为单独打包的 VAE。 | 仍要核验具体提取/转换来源、revision 和哈希，不能仅凭文件名放行其他来源的同名文件。 |

RealVisXL 的 `openrail++` 对应 [Hugging Face 许可索引](https://huggingface.co/docs/hub/repositories-licenses)中的 Open Rail++-M。标准文本可核对 [SDXL 固定 LICENSE.md](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/a81e67334a28f3f88edc9115339e21c32eddc562/LICENSE.md)。许可方不主张输出权利，不等于替用户清理输入素材、肖像或输出相似性风险。

**Kijai 仓库不能整仓套同一许可。** 本次核验的 [WanVideo_comfy 固定模型卡](https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/README.md)列有多种来源，未声明覆盖所有文件的统一 `license`。它与 `WanVideo_comfy_fp8_scaled` 是两个仓库。UMT5、CLIP、VAE 等转换组件在来源与哈希闭环前，标记为“待补证”，不把默认完整链路宣传为“商用已全部清权”。

## 4. 独立安装的软件和节点

以下组件不打包进本仓库。固定提交来自[部署基线](PUBLIC_DEPLOYMENT.md)，仅用于限定已核验的上游许可，并非干净环境复现承诺。

| 组件 | 已核验来源与许可证 | 要点 |
| --- | --- | --- |
| Ollama | [官方 LICENSE](https://github.com/ollama/ollama/blob/main/LICENSE)：MIT | 软件许可不覆盖下载的模型；升级后复核实际包及第三方通知。 |
| ComfyUI | [`77917ed` LICENSE](https://github.com/Comfy-Org/ComfyUI/blob/77917ed3a6291689e5c2ee8ccbdd6708e85a53a6/LICENSE)：GPL v3 | 可用于商业制作；若交付软件/修改版，评估对应源码、许可和组合分发义务。 |
| ComfyUI-WanVideoWrapper | [`088128b` LICENSE](https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/088128b224242e110d3906c6750e9a3a348a659b/LICENSE)：Apache-2.0 | 节点仓库顶层许可不替各模型、移植子组件重新授权；外部本机补丁未在本仓库发布。 |
| ComfyUI-VideoHelperSuite | [`4ee72c0` LICENSE](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/4ee72c065db22c9d96c2427954dc69e7b908444b/LICENSE)：GPL v3 | 不要误写为 MIT/Apache；一起打包分发时保留其许可并履行对应义务。 |
| Toonflow 新版宿主 | [`72a895c` LICENSE](https://github.com/HBAI-Ltd/Toonflow-app/blob/72a895c26aab3f54c5a914517615362208fa6008/LICENSE)：MIT | 可选外部宿主；不包含在本仓库，旧版例外见上文。 |
| FFmpeg / FFprobe | [官方法律说明](https://ffmpeg.org/legal.html)：通常 LGPL-2.1-or-later，启用 GPL 组件时改变整体适用许可 | 本项目多处使用 `libx264`；不得不检查构建就宣称所用 FFmpeg 是 LGPL-only。保存 `ffmpeg -version`、`-buildconf`、`-L` 和发行包来源；再分发须另查对应源码及外部库义务。 |
| PyTorch | [v2.6.0 LICENSE](https://github.com/pytorch/pytorch/blob/v2.6.0/LICENSE)：BSD 风格许可及第三方通知 | CUDA、cuDNN、驱动和其他二进制组件不是由本项目授予 Apache 许可。 |
| Diffusers / Transformers | [Diffusers LICENSE](https://github.com/huggingface/diffusers/blob/main/LICENSE)、[Transformers LICENSE](https://github.com/huggingface/transformers/blob/main/LICENSE)：Apache-2.0 | 旧实验 worker 或模型后端单独安装；主分支链接不是安装版本锁，须记录实际安装版本。 |
| NumPy / OpenCV（部分 QA、旧脚本） | [NumPy v2.1.0 LICENSE](https://github.com/numpy/numpy/blob/v2.1.0/LICENSE.txt)：BSD-3-Clause；[OpenCV 4.10.0 LICENSE](https://github.com/opencv/opencv/blob/4.10.0/LICENSE)：Apache-2.0 | 此处为已核验许可样本版本，不代表锁定安装版本；wheel 内第三方库也需盘点。 |

使用 GPL 程序处理视频，通常不使输出视频自动变为 GPL；这与将该程序、修改版或包含其代码的组合软件分发给他人是不同问题。通过 HTTP 或独立进程调用也不是对任意整合方式都自动免责的法律结论。Apache-2.0 的专利条款不替第三方编解码器专利提供许可；FFmpeg 官方页也提示相关风险。

## 5. 网关 Python 直接依赖

`requirements.txt` 使用 `>=`，**不是锁文件**。下表核验的是其中列出的最低版本官方许可，不代表未来任意版本/所有传递依赖自动获审。虚拟环境与 wheel 未随 Git 分发；未来制作离线安装包/可执行包时应导出实际依赖清单，并保留每个包附带的 LICENSE、NOTICE 和二进制库通知。

| 直接依赖 | 核验版本 | 许可证 / 官方证据 |
| --- | --- | --- |
| FastAPI | 0.111.0 | [MIT](https://github.com/fastapi/fastapi/blob/0.111.0/LICENSE) |
| Uvicorn | 0.30.0 | [BSD-3-Clause](https://github.com/encode/uvicorn/blob/0.30.0/LICENSE.md)；`standard` extra 会额外安装依赖。 |
| Pydantic | 2.7.0 | [MIT](https://github.com/pydantic/pydantic/blob/v2.7.0/LICENSE) |
| pydantic-settings | 2.3.0 | [MIT](https://github.com/pydantic/pydantic-settings/blob/v2.3.0/LICENSE) |
| PyYAML | 6.0.1 | [MIT](https://github.com/yaml/pyyaml/blob/6.0.1/LICENSE) |
| HTTPX | 0.27.0 | [BSD-3-Clause](https://github.com/encode/httpx/blob/0.27.0/LICENSE.md) |
| python-multipart | 0.0.9 | [Apache-2.0](https://github.com/Kludex/python-multipart/blob/0.0.9/LICENSE.txt) |
| Pillow | 10.3.0 | [HPND](https://github.com/python-pillow/Pillow/blob/10.3.0/LICENSE)；不要把该版本写成 MIT。 |
| pytest（测试） | 8.2.0 | [MIT](https://github.com/pytest-dev/pytest/blob/8.2.0/LICENSE) |

Starlette、AnyIO、pydantic-core、HTTP Core、图像编解码器等传递依赖以及 Python/Node 运行时尚未在本页做逐包实际安装版本审计。此清单不应被当成已完成的 SBOM。

文档截图另用独立安装的 Playwright / Chromium，不是网关必需依赖，也未打包进仓库。[Playwright 官方 LICENSE](https://github.com/microsoft/playwright/blob/main/LICENSE)为 Apache-2.0；浏览器及其第三方组件保留各自许可，不能从 Playwright 的许可推导整个浏览器均为 Apache。若分发截图工具运行环境，也须核对实际包内通知。[Chromium 官方许可](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/LICENSE)

## 6. 可选、历史路线不自动放行

- RIFE 与 Real-ESRGAN 有自己的实现、权重和二进制许可链；使用前核对[历史台账](COMMERCIAL_RIGHTS_LEDGER.md)限定的包，不把任意同名下载包套用旧结论。
- SadTalker、Wav2Lip、BFM、Windows/SAPI 测试配音等存在第三方权重、数据或声音授权限制/缺口。**本项目没有把历史测试路线放行为商用母版。** 详见历史台账，不由新的 Apache-2.0 改变。
- Animagine、AnimateDiff、VACE、MimicMotion、Kokoro 及任意新增 LoRA/voice 属于另行审核项；有实验脚本不表示已安装、已验证质量或已完成商业权利审查。
- 本次项目截图用于说明界面和工程流程；截图不是模型最终质量达标证明，也不授予截图中任何第三方内容的新权利。

## 7. 对外发行前的最小核对表

- [ ] 软件包内所有实际文件有归属和许可；自有代码与第三方例外明确分开。
- [ ] 发行包不含已移除的旧 Toonflow 适配器；若恢复历史文件，另行解决上游许可和额外授权条件。
- [ ] 每个模型/转换文件记录下载 URL、不可变 revision、SHA-256、完整许可及必要通知；UMT5、CLIP、VAE 来源缺口已关闭。
- [ ] 整合/修改/打包 ComfyUI、VHS、FFmpeg 时，适用源码及通知义务已落实。
- [ ] 实际安装依赖和二进制组件清单已生成，未仅凭本页最低版本表替代核查。
- [ ] 真人肖像、声音、音乐、字体、商标、参考图及委托素材均具有拟议用途授权。
- [ ] 成片完成视觉、相似性、内容合规和发行地区/平台规则审查；不存在以本地开源替代这些审查的承诺。

发现链接、文件来源或许可变更时，请按精确版本更新本页。许可事实以权利人适用于该版本的完整文本为准；本页的摘要不是替代许可证。
