# 本地写实 AI 漫剧商用权利台账

> 公开仓库说明：本页保留指定历史环境的工程审计记录；所列本地模型、证据包与预演素材不随源代码仓库分发。它不是本次发布对所有模型、节点或生成内容的重新清权，也不等于本仓库整体软件许可证。

审计日期：2026-09-02

适用范围：本项目当前使用或计划使用的 RealVisXL V5、Wan2.1 I2V、ComfyUI、RIFE NCNN Vulkan、Real-ESRGAN NCNN Vulkan、SadTalker，以及 Windows/SAPI 内置语音。

> 本文是工程合规记录，不是法律意见。它只说明已找到的一手许可文本和当前项目的放行策略，不保证某项内容在所有司法辖区都具备版权、人格权或其他权利。正式发行前应由权利人/法务复核最终素材包和实际发行地区。

## 状态定义

- **已确认**：已找到发布方模型卡、仓库 LICENSE 或官方条款，当前用途在遵守列明条件时没有发现“禁止商业使用”的条款。
- **需人工确认**：一手材料不完整、适用版本不明确，或仍需核对具体素材/账户/字体/声音的授权链。未关闭前不得标为“商用已清”。
- **不可用于商用**：当前项目没有足够授权，或许可明确不覆盖拟议用途。此状态可以在获得书面授权或换用已清素材后解除。

## 执行结论

| 项目 | 当前状态 | 对本项目的决定 |
|---|---|---|
| RealVisXL V5 权重 | **已确认（许可证层面）** | 发布者在固定提交 `ac93e0d` 的模型卡声明 `openrail++`；Hugging Face 官方许可索引将其映射为 Open Rail++-M。完整标准文本、固定模型卡/API 证据已归档，本机权重 SHA-256 与发布方 LFS SHA-256 完全一致。遵守用途限制，且内容权利仍须逐件清理。 |
| RealVisXL V5 生成图 | **已确认（许可证层面）** | OpenRAIL++ 标准文本不禁止商业输出，且许可方不主张输出权利；仍须单独清理肖像、隐私、商标、著作权和违法内容风险。不得把“许可方不主张”写成“输出必然受版权保护”。 |
| Wan2.1 I2V 官方代码/权重 | **已确认** | Apache-2.0；官方 README 明示不主张生成内容权利。遵守 Apache-2.0、法律和官方使用限制。 |
| 本机 Kijai FP8 转换权重 | **已确认** | 精确文件页面标为 Apache-2.0，且源 Wan2.1 为 Apache-2.0。归档文件 SHA-256、仓库修订号和两级许可。 |
| ComfyUI | **已确认** | GPL-3.0 可用于商业生产；若对外分发 ComfyUI 或其修改版，必须履行 GPL-3.0 的对应源码和许可义务。本地生成成片不因使用 ComfyUI 自动变成 GPL。 |
| RIFE NCNN Vulkan | **已确认** | NCNN 实现及上游 RIFE 均为 MIT；保留版权及许可通知，尤其在分发可执行文件/模型包时。 |
| Real-ESRGAN NCNN Vulkan | **已确认** | NCNN 实现为 MIT，上游 Real-ESRGAN 为 BSD-3-Clause；官方便携包包含模型。分发软件/模型包时同时保留两份许可和 BSD 不背书条款。 |
| 本机 `E:\SadTalker` 代码 | **已确认（仅 SadTalker 自有代码）** | 本机仓库来自 `OpenTalker/SadTalker`，commit `cd4c0465ae0b54a6f85af57f5c65fec9fe23e7f8`；SadTalker 自有代码为 Apache-2.0，但其 LICENSE 明确排除第三方组件，不能据此覆盖 checkpoints。 |
| 本机 SadTalker 口型动画路线 | **不可用于商用** | 本机缺少新版 `.safetensors`，代码会回退到旧 checkpoints；其中 face-vid2vid 重现权重为 CC BY-NC 4.0，Wav2Lip 官方开源权重明确禁止商业使用，BFM 数据仅限内部非商用研究，另有 dlib 68 点模型非商用警告。任一项都足以阻止进入商用母版。 |
| Windows/SAPI 本地内置语音 | **需人工确认** | Windows 条款覆盖随系统提供的声音文件，但未找到像 Azure 付费 TTS 那样明确授予“合成音频可商用”的条款；不同 SAPI voice 还可能来自第三方。未获得对应 voice 的书面条款前，不能作为商用成片配音。 |
| 当前用 SAPI 生成的测试配音 | **不可用于商用** | 只允许内部试片、节奏和口型验证；正式母版必须替换为有明确商用输出条款的 TTS，或有合同/授权书的真人配音。 |
| Noto Sans SC 字幕字体 | **已确认** | 项目副本的字体内部元数据与发布方许可均为 SIL OFL 1.1；可用于字幕栅格化。若随软件分发字体文件，须保留版权与 OFL 文本，且不得单独出售字体。 |
| 当前 10 秒程序音轨 | **已确认（来源层面）** | 仅由 FFmpeg 固定种子噪声、振荡器与滤镜确定性合成，无第三方录音、音乐采样、语音或参考视频音频；脚本、哈希与 QA 已归档。 |

## 一、模型权重与代码许可

### 1. RealVisXL V5

**本机对象**

- 文件：`models/image/realvisxl_v5/RealVisXL_V5.0_fp16.safetensors`
- 本机 SHA-256：`6A35A7855770AE9820A3C931D4964C3817B6D9E3C6F9C4DABB5B3A94E5643B80`
- 发布方模型卡：`SG161222/RealVisXL_V5.0`
- 已审模型卡当前提交：`ac93e0d`（Hugging Face 页面显示为 verified；访问于 2026-09-02）

**权重许可：已确认（许可证层面）**

模型卡元数据明确写有 `license: openrail++`。Hugging Face 官方文档说明，发布者可以在仓库模型卡元数据中指定许可；其官方许可证索引把 `openrail++` 映射为 “Open Rail++-M License”。标准 CreativeML Open RAIL++-M 文本允许模型使用且没有“仅限非商用”条款，并规定用途限制。虽然提交 `ac93e0d` 的 RealVisXL V5 仓库没有单独的 LICENSE 文件，本项目已经：

1. 固定并保存发布者提交 `ac93e0dda1f6d448cae19bbfab8c5e720a5e48bc` 的模型卡和 API 元数据；
2. 保存完整 CreativeML Open RAIL++-M 标准文本；
3. 从发布方固定 tree API 取得精确权重 LFS SHA-256 与文件大小；
4. 验证本机文件 `6A35...3B80` 与发布方记录逐字节哈希一致；
5. 把证据文件及其哈希记录在 `models/image/realvisxl_v5/PROVENANCE.md`。

据此，当前精确权重的许可来源与文件身份已经闭环。它仍不是对训练数据、生成图著作权、真人肖像或与既有作品相似性的担保；这些内容风险须逐件审核。

**生成输出权利：已确认（许可证层面）**

OpenRAIL++ 标准文本写明，除许可证另有规定外，许可方不主张用户生成输出中的权利；用户对输出及后续使用负责，输出不得违反许可证的用途限制。这意味着许可本身没有设置“仅非商用”限制，但不代表：

- 输出必然具备可登记或可执行的著作权；
- 模型许可会替用户清除输入图、参考人物、服装设计、商标、隐私或肖像权；
- 可以仿造真实演员、明星或参考视频人物后直接商用。

**项目规则**：只用原创文字提示和自建虚构成年人身份；不得输入参考短剧帧、演员姓名或要求复刻可识别真人；每张定稿图保存 prompt、negative prompt、seed、workflow、模型哈希和人工选择记录。

### 2. Wan2.1 I2V 14B 480p 与本机 FP8 转换

**本机工作流对象**

- 模型名：`Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`
- 转换仓库：`Kijai/WanVideo_comfy_fp8_scaled`
- 精确文件页面公开 SHA-256：`2ff922282cd84589702e6e8c26e083d1160bfc2b217dd44e1ae2688441dc495d`
- 2026-09-02 本机复算 SHA-256：`2FF922282CD84589702E6E8C26E083D1160BFC2B217DD44E1AE2688441DC495D`（完全一致）
- 本地证据：`models/wan/WAN2.1_I2V_14B_FP8_PROVENANCE.md`

**官方代码与原始权重：已确认**

Wan2.1 官方仓库的 README 明示“代码和模型”使用 Apache License 2.0，仓库同时提供完整 `LICENSE.txt`。Apache-2.0 允许商业使用、修改和分发，但分发 Work/Derivative Works 时要保留许可证、版权/专利/商标等相关通知；若有 NOTICE 文件，还须按许可证处理 NOTICE。

**FP8 转换权重：已确认**

当前精确 Kijai 文件的 Hugging Face 页面标为 Apache-2.0，其源模型也为 Wan2.1 Apache-2.0。2026-09-02 已复算 16.6 GB 本机文件，SHA-256 与固定修订文件页完全一致。若将来替换或更新权重，应把新文件视为新的待审对象并重新核对。

**生成输出权利：已确认（许可证层面）**

Wan2.1 官方 README 明示项目方不主张用户生成内容中的权利，同时要求用户对输出负责并遵守许可和适用法律。该声明不清理输入关键帧中的第三方权利，也不保证纯 AI 输出在发行地区可获得版权保护。

**项目规则**：Wan 只驱动已经通过权利审查的原创关键帧；禁止把参考短剧视频、演员画面或无授权人物照片作为 I2V 输入。

### 3. ComfyUI

**代码许可：已确认**

ComfyUI 官方仓库使用 GNU GPL v3.0。GPL-3.0 不禁止商业使用。仅在本机运行 ComfyUI 生成图片/视频，不会自动把生成成片置于 GPL；但如果把 ComfyUI、本项目对 ComfyUI 的修改版或包含其代码的程序交付给客户，则须按实际组合方式履行 GPL-3.0，包括保留许可、提供对应源码和不得增加冲突限制等义务。

**模型权重：不适用**

ComfyUI 的 GPL 只解决 ComfyUI 软件本身，不能替代节点、模型、字体、音频和输入素材各自的许可。

**项目规则**：发布前导出所有 custom nodes 清单、版本/commit 与 LICENSE。当前台账没有自动覆盖 `ComfyUI-WanVideoWrapper`、VideoHelperSuite 或其他扩展；任何未登记扩展均为 **需人工确认**。

### 4. RIFE NCNN Vulkan

**本机对象**

- 发布包：`rife-ncnn-vulkan-20221029-windows.zip`
- 本机归档 SHA-256：`D8E4D772D26CD8006EF0AD0BC82EB191B53C68677D1AE2F42506D74CBBBEA606`
- 发布包内 `LICENSE` 已保留在可执行文件旁。

**代码许可：已确认**

`nihui/rife-ncnn-vulkan` 为 MIT License；其官方 README 说明便携包含运行所需二进制与模型。上游 `hzwer/ECCV2022-RIFE` 也为 MIT License。MIT 允许商业使用、修改、再许可和销售，但复制/实质部分中必须保留版权和许可声明。

**模型权重许可：已确认（限当前官方发布包）**

当前权重来自官方便携发布包，发布包自带 MIT LICENSE，且上游模型仓库同为 MIT。不要把来自其他 GUI、网盘或第三方训练的 RIFE 权重混入已清目录；若更换权重，重新审计。

**处理输出**

插帧输出的可商用性主要继承输入视频的权利状态。RIFE 的 MIT 许可不替无授权输入素材取得权利。

### 5. Real-ESRGAN NCNN Vulkan

**本机对象**

- 发布包：`realesrgan-ncnn-vulkan-20220424-windows.zip`
- 本机归档 SHA-256：`ABC02804E17982A3BE33675E4D471E91EA374E65B70167ABC09E31ACB412802D`
- 本地已保留 `LICENSE-NCNN-MIT.txt` 与 `LICENSE-REALESRGAN-BSD3.txt`。

**NCNN 实现代码：已确认**

`xinntao/Real-ESRGAN-ncnn-vulkan` 为 MIT License，并在 LICENSE 中同时保留其借用项目 `realsr-ncnn-vulkan` 的 MIT 文本。

**上游代码及官方模型：已确认（限当前官方发布包）**

`xinntao/Real-ESRGAN` 仓库为 BSD-3-Clause；官方 README 明示其便携 NCNN 可执行包包含所需二进制和模型。本项目使用的是官方发布 URL 对应包，并已保留 BSD-3-Clause 文本。BSD-3-Clause 允许商业使用，但要求源代码/二进制分发时保留版权、条件和免责声明，并禁止未经书面许可用权利人/贡献者名称为产品背书。

**处理输出**

超分输出的权利状态取决于输入图/视频。MIT/BSD 许可允许使用工具，却不替输入素材清权，也不保证放大后的人脸、标识或受保护作品可商用。

### 6. SadTalker 口型动画

**总体结论：本机现有路线不可用于商用母版。** SadTalker 仓库将其自有代码改为 Apache-2.0，并在 README 中称已移除非商用限制；但仓库 LICENSE 同时明确写有“except for the third-party components”。Apache-2.0 只能覆盖 SadTalker 有权许可的部分，不能把第三方的非商用权重、代码或数据改成可商用。当前本机推理链至少存在四个独立阻断项。

#### 本机版本与实际加载路径

- 安装目录：`E:\SadTalker`
- 官方来源：`https://github.com/OpenTalker/SadTalker.git`
- 本机 commit：`cd4c0465ae0b54a6f85af57f5c65fec9fe23e7f8`
- `checkpoints` 中没有 `SadTalker_V0.0.2_256.safetensors` 或 `SadTalker_V0.0.2_512.safetensors`。
- 本机 `src/utils/init_path.py` 在找不到任何 `.safetensors` 时明确回退到旧权重：`facevid2vid_00189-model.pth.tar`、`epoch_20.pth`、`wav2lip.pth`、`auido2pose_00140-model.pth` 和 `auido2exp_00300-model.pth`。

SadTalker 官方 README 本身把这些旧权重分别标为 face-vid2vid 重现模型、Deep3DFaceReconstruction 3DMM extractor 和 Wav2Lip 模型，并说明训练过程使用了 Deep3DFaceReconstruction 与 Wav2Lip。由此不能把当前本机路线视为“仅使用 Apache-2.0 SadTalker 自有权重”。

#### 逐项许可结论

| 本机组件 | 本机 SHA-256 | 官方一手证据 | 状态 | 商用判定 |
|---|---|---|---|---|
| SadTalker 自有代码 | commit `cd4c0465ae0b54a6f85af57f5c65fec9fe23e7f8` | 官方 LICENSE：Apache-2.0，但明确排除第三方组件；官方 README 称移除了 SadTalker 自身的非商用限制。 | **已确认（仅自有代码）** | 单独使用/修改自有代码可商业化并履行 Apache-2.0；不能据此放行完整 checkpoints 路线。 |
| `facevid2vid_00189-model.pth.tar` | `FBAD01D46F0510276DC4521322DDE6824A873A4222CD0740C85762E7067EA71D` | SadTalker README 指向 `zhanglonghao1992/One-Shot_Free-View_Neural_Talking_Head_Synthesis`；该重现仓库 LICENSE 为 CC BY-NC 4.0，只允许非商业用途。 | **不可用于商用** | 当前默认人脸渲染权重不能进入商业成片。必须取得权利人书面商业许可或整体替换为许可链清晰的渲染器和权重。 |
| `wav2lip.pth` | `B78B681B68AD9FE6C6FB1DEBC6FF43AD05834A8AF8A62FFC4167B7B34EF63C37` | Wav2Lip 官方 README 明示开源代码、模型及其结果仅可用于 research/academic/personal，任何商业使用均被严格禁止，原因包括训练集 LRS2。 | **不可用于商用** | 不得用于商用母版。需另购官方商业许可/服务，或使用另一个有完整商业训练数据与权重许可的方案。 |
| `auido2pose_00140-model.pth` 中的音频编码器链 | 未在本次追加审计计算 | SadTalker README 明示训练使用 Wav2Lip；本机代码虽已注释运行时加载独立 `wav2lip.pth` 的语句，但没有一手材料证明 `auido2pose` checkpoint 未含基于/初始化自 Wav2Lip 的参数或已获得商业授权。 | **需人工确认；整链仍不可商用** | 删除独立 `wav2lip.pth` 不足以完成清权。须由 SadTalker 发布方提供该 checkpoint 的训练与权利声明，或替换整条音频编码器/姿态模型。 |
| `epoch_20.pth` | `6D17A6B23457B521801BAAE583CB6A58F7238FE6721FC3D65D76407460E9149B` | Deep3DFaceReconstruction 代码为 MIT，但其官方 README 要求用户另行取得 BFM09，并明确因 BFM 许可必须申请后下载；未找到对本机精确 `epoch_20.pth` 训练数据和权重输出的独立商业授权。 | **需人工确认；整链仍不可商用** | MIT 代码许可不等于权重和 BFM 数据可商用。 |
| `BFM_Fitting/01_MorphableModel.mat` | `37B1F0742DB356A3B1568A8365A06F5B0FE0AB687AC1C3068C803666CBD4D8E2` | University of Basel 的 BFM 非商用许可只允许内部、非商业研究/评估/测试，并禁止将数据用于直接或间接营利产品。 | **不可用于商用** | 该文件参与 3DMM fitting；在未取得 Basel 商业许可前，SadTalker 3DMM 推理不能用于商用母版。 |
| `BFM_Fitting/Exp_Pca.bin` | `E7F31380E6CBDAF2AEEC698DB220BAC4F221946E4D551D88C092D47EC49B1726` | Deep3DFaceReconstruction README 称 expression basis 来自 FaceWarehouse 并转到 BFM topology；本次未找到适用于该精确二进制的独立商业许可。 | **需人工确认；整链仍不可商用** | 在取得权利链之前不得作为商业组件使用。 |
| `shape_predictor_68_face_landmarks.dat` | `FBDC2CB80EB9AA7A758672CBFDDA32BA6300EFE9B6E6C7A299FF7E736B11B92F` | dlib 官方模型仓库明确说明，该模型训练所用 iBUG 300-W 数据集排除商业使用，因此该训练模型不能用于商业产品。 | **不可用于商用** | 本机当前 SadTalker 源码未发现推理时直接加载该文件，但不得在商业路线中启用或随商业软件包分发。 |
| PIRender 相关 facerender 代码来源 | 不适用 | SadTalker README 说明 facerender 代码大量借鉴 PIRender；PIRender 官方 LICENSE 为 CC BY-NC 4.0。SadTalker 没有提供足以证明相关实现已获单独商业授权的公开一手材料。 | **需人工确认；整链仍不可商用** | 不能仅凭 SadTalker 顶层 Apache-2.0 覆盖该来源；需发布方书面澄清或替换。 |
| face-alignment / SFD / 2DFAN4 | 本次未逐文件固定来源 | `1adrianb/face-alignment` 官方仓库为 BSD-3-Clause；但当前本机缓存权重的精确来源、版本与适用许可尚未形成闭环。 | **需人工确认** | 不是本次最先触发的阻断项，但替代其他组件后仍须补齐哈希与来源。 |
| GFPGAN enhancer | 当前 `gfpgan/weights` 缺少 `GFPGANv1.4.pth` | GFPGAN 官方仓库称项目为 Apache-2.0，但其 LICENSE 另列第三方组件和非商用 DFDNet；本机没有完整 enhancer 权重，无法对实际运行组合放行。 | **需人工确认** | 商业母版暂时禁用 `--enhancer gfpgan`，直至精确模型、代码路径和第三方组件完成审计。 |

#### 为什么“换新版 SadTalker safetensors”也不能自动放行

SadTalker 官方 README 把新版 `SadTalker_V0.0.2_256.safetensors` 和 `SadTalker_V0.0.2_512.safetensors` 描述为“packaged sadtalker checkpoints of old version”。公开材料没有提供足以证明 face-vid2vid、Wav2Lip、BFM、PIRender 等受限组件已被重新训练、替换或另行商业授权的清权说明。因此仅把旧 `.pth/.tar` 合并为 `.safetensors` 是文件格式/打包变化，不是许可链清理。

#### 项目强制决策

1. `E:\SadTalker` 只可用于内部技术测试，不得生成进入商用母版的任何镜头。
2. 已由该目录生成的口型视频一律标记 `research-only`；不能通过剪辑、重编码、超分或只截取嘴部来消除上游许可限制。
3. 只有在取得 face-vid2vid/PIRender、Wav2Lip、BFM/FaceWarehouse 及所有实际加载权重的书面商业授权，或完全替换受限组件并重新完成端到端来源审计后，才可重新评估。
4. 替代方案必须逐项证明：代码许可、精确 checkpoint 许可、训练数据商业权利、生成输出条款，以及人脸/声音输入授权。仅有“Apache/MIT 代码仓库”不构成模型商用放行。

## 二、声音、字体、音乐与素材

### 1. Windows/SAPI 内置语音

**SAPI 技术调用：已确认可在合法 Windows 实例中运行**

Microsoft Learn 文档说明 SAPI 是 Windows 的语音合成接口，可以选择已安装的 TTS engine/voice 并产生音频输出。Windows OEM 条款授予在获许可设备上安装和运行 Windows 的权利。

**合成音频商用权：需人工确认**

Windows OEM 条款明确把随 Windows 提供的 sound files 纳入 Windows 软件许可，并保留所有未明确授予的权利；本次审阅未在 Windows/SAPI 一手条款中找到“本地内置 voice 生成的音频可用于商业成片”的明确授权。SAPI 只是接口，实际 voice 还可能有 Microsoft 或第三方的独立条款。

Microsoft 对 Azure 付费层 Text-to-Speech 另有明确的一手条款：付费层预置神经声音的输出可用于商业目的。该条款针对 Azure TTS 服务及相应付费客户，不能反推或移植到 Windows 本地 SAPI voice。

**项目决定：当前 SAPI 测试配音不可用于商用母版。** 可以保留为内部节奏/口型占位音频，最终必须替换为以下任一方案：

- 与真人配音员签署覆盖作品、媒体、地区、期限、广告投放和 AI 处理范围的书面授权；
- 使用模型与具体 voice 均有明确商业输出条款的本地 TTS，并归档模型卡、数据/voice 许可与哈希；
- 使用 Azure TTS 付费层预置声音，保存发票/订阅层级、生成日期、voice 名称、输入文本及当日 Product Terms 快照，并遵守合成媒体披露要求。

不得克隆参考视频演员或他人的声音；自定义/克隆声音必须另有声音权利人的明示书面同意。

### 2. 字体

**当前 10 秒预演使用的 Noto Sans SC：已确认。**

- 项目文件：`assets/fonts/NotoSansSC/NotoSansSC-VF.ttf`
- SHA-256：`763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`
- 字体内部版本：`Version 2.04;241114210130;non-release`
- 字体内部许可：SIL Open Font License 1.1
- 项目许可副本：`assets/fonts/NotoSansSC/OFL.txt`

发布方 Noto CJK 的官方 LICENSE 允许字体的使用、嵌入和随软件再分发，但字体不得单独出售；分发字体文件时须保留版权与许可文本。OFL 明确说明，用该字体创建的文档不因此受 OFL 约束。因此，将字形栅格化进成片字幕不会让视频继承 OFL。

此结论只覆盖上述哈希的项目副本。后续每个片头、海报或替换字体仍须记录文件名、版本、来源和许可证；Windows 中“预装可用”本身不等于所有字体都可随项目打包。

### 3. 音乐和音效

**当前 10 秒预演程序音轨：已确认（素材来源层面）。** `technical_preview_assets/procedural_soundscape_10s_48k_stereo.wav` 由 `scripts/render_photoreal_preview_audio.ps1` 仅用 FFmpeg 固定种子噪声、正弦振荡器、滤波、包络、延迟、声像和混音生成；不含第三方录音、素材库采样、现成音乐、语音/TTS 或参考视频音频。尾部淡出版 WAV SHA-256 为 `51BA635930E430318028E04679824CC7451C97C5F93729AA2E59590C790B5225`，生成说明与机器 QA 已归档。因此它没有外部录音授权链；FFmpeg 二进制本身的许可/编解码器义务仍须按实际分发方式处理。

其他最终母版音乐/音效仍为**需逐条确认**。每条必须满足以下之一：项目原创且能证明创作过程；受托创作并取得书面转让/许可；或来自明确允许商业影视使用的素材库并保存订单、许可证和下载凭证。不得直接使用参考短剧音轨、平台抓取音乐、短视频热歌或来源不明音效。

若用生成式音乐/音效，还要同时核对生成服务/模型、输入素材、订阅层级、输出条款和训练/模仿限制；“AI 生成”本身不是权利证明。

### 4. 剧本、角色、图片、视频及参考素材

**状态：需逐件确认。** 本项目当前原则是原创虚构故事、原创角色和原创提示词。参考视频仅用于测量镜头节奏、景别、字幕位置和画面质量，不得复制或嵌入其画面、音频、台词、人物脸、服装细节、角色设定、专有场景或平台标识。

每个成片镜头必须能回溯到：原创脚本版本、生成 workflow、模型哈希、prompt/seed、输入关键帧和人工修改记录。任何真人照片、客户 Logo、商标、古画、摄影作品、纹样或素材库文件都必须单独附权利凭证。

## 三、生成输出权利的共同限制

模型方“不主张输出权利”仅表示模型许可方不向用户索取该输出；它不能解决以下问题：

1. 纯 AI 输出在发行地是否达到著作权保护所需的人类创作门槛；
2. 输出是否与受保护作品实质性相似；
3. 是否侵犯真人肖像、姓名、声音、隐私或商业形象；
4. 是否包含商标、平台 UI、水印、字体、音乐或素材库的未授权元素；
5. 是否违反 OpenRAIL++、Wan 使用限制或适用法律。

因此，项目应保留足以证明人类创作控制的材料：脚本改写、镜头设计、候选取舍、局部重绘、剪辑、调色、声音设计和最终审核记录。

## 四、商用母版放行清单

以下项目全部关闭后，才可以把文件标记为 `commercial-cleared`：

- [x] RealVisXL V5 完整 OpenRAIL++ 文本、固定模型卡/API、commit、URL 与本机/发布方一致的 SHA-256 已归档。
- [x] Wan FP8 本机 SHA-256 与已审固定修订文件一致；Apache-2.0 来源和本地证据记录已归档（若交付模型本体，仍须随包保留适用 LICENSE/NOTICE）。
- [ ] ComfyUI 及所有 custom nodes 的版本和许可清单完整；若分发软件，GPL 对应源码方案已落实。
- [ ] RIFE 与 Real-ESRGAN 只使用本台账哈希对应的官方包；两套工具的许可文件随软件分发包保留。
- [ ] 商用母版不含任何由当前 `E:\SadTalker` 路线生成的画面；若未来重新启用，受限 checkpoints/数据已全部替换或取得逐项书面商业许可，并完成新哈希审计。
- [ ] 正式母版不含 Windows/SAPI 占位配音；最终 voice 的商业输出权及声音人格授权已存档。
- [ ] 剧本、角色名、台词、人物设计和镜头素材均为原创或已取得书面授权。
- [ ] 每个真人/声音/Logo/素材库元素都有覆盖目标媒体、地区、期限和商业推广的书面授权。
- [x] 当前 10 秒预演的 Noto Sans SC 字体文件、哈希和 OFL 1.1 已归档；若正式母版新增/替换字体须重新核对。
- [x] 当前 10 秒预演的程序音轨脚本、来源说明、哈希和 QA 已归档；若正式母版新增音乐/音效须逐条清权。
- [ ] 未使用参考短剧的画面、音轨、台词、可识别演员形象或水印；相似性人工复核已签字。
- [ ] 已检查成片编码器、封装格式、发布平台和发行地区可能涉及的专利/编解码器条款；本台账未审计这些项目。
- [ ] 保存最终母版 SHA-256、生成日志、人工编辑记录、权利凭证包和审片签字记录。

## 五、官方/一手来源

以下链接均于 **2026-09-02** 访问：

| 对象 | 官方/一手来源 | 证据用途 |
|---|---|---|
| RealVisXL V5 | [Hugging Face 发布方模型卡](https://huggingface.co/SG161222/RealVisXL_V5.0/blob/main/README.md) | 模型卡标记 `license: openrail++`，确认精确模型名称。 |
| RealVisXL V5 文件树 | [Hugging Face 发布方文件列表](https://huggingface.co/SG161222/RealVisXL_V5.0/tree/main) | 当前提交 `ac93e0d`、权重文件名/大小，以及仓库没有独立 LICENSE 文件。 |
| Hugging Face 许可标识 | [Hugging Face Hub Licenses](https://huggingface.co/docs/hub/repositories-licenses) | `openrail++` 对应 Open Rail++-M License。 |
| OpenRAIL++ 标准文本/输出条款 | [Stability AI SDXL 1.0 LICENSE.md](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/a81e67334a28f3f88edc9115339e21c32eddc562/LICENSE.md) | 标准条款、用途限制及许可方不主张输出权利的表述。 |
| Wan2.1 | [Wan2.1 官方 README](https://github.com/Wan-Video/Wan2.1/blob/main/README.md) | 代码/模型 Apache-2.0；官方不主张生成内容权利及使用责任说明。 |
| Wan2.1 完整许可 | [Wan2.1 官方 LICENSE.txt](https://github.com/Wan-Video/Wan2.1/blob/main/LICENSE.txt) | Apache License 2.0 完整文本。 |
| Kijai FP8 精确权重 | [固定修订下的精确文件页](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/blob/72cfd0d6f2269b14f94c38bfee2744e0ed172c38/I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors) | Apache-2.0 标签、文件大小、修订号及公开 SHA-256。 |
| ComfyUI | [ComfyUI 官方 LICENSE](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) | GNU GPL v3.0 完整文本。 |
| RIFE NCNN | [rife-ncnn-vulkan LICENSE](https://github.com/nihui/rife-ncnn-vulkan/blob/master/LICENSE) | NCNN 实现 MIT License。 |
| RIFE 上游 | [ECCV2022-RIFE LICENSE](https://github.com/hzwer/ECCV2022-RIFE/blob/main/LICENSE) | 上游算法仓库 MIT License。 |
| RIFE 官方便携包说明 | [rife-ncnn-vulkan README](https://github.com/nihui/rife-ncnn-vulkan/blob/master/README.md) | 官方包包含二进制和模型。 |
| Real-ESRGAN NCNN | [Real-ESRGAN-ncnn-vulkan LICENSE](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/blob/master/LICENSE) | NCNN 实现及 realsr 借用部分 MIT License。 |
| Real-ESRGAN 上游 | [Real-ESRGAN LICENSE](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE) | BSD-3-Clause 完整文本。 |
| Real-ESRGAN 官方包说明 | [Real-ESRGAN README](https://github.com/xinntao/Real-ESRGAN/blob/master/README.md) | 官方便携 NCNN 包包含所需二进制和模型。 |
| SadTalker 代码许可 | [OpenTalker/SadTalker LICENSE](https://github.com/OpenTalker/SadTalker/blob/main/LICENSE) | SadTalker 自有代码为 Apache-2.0，并明确排除第三方组件。 |
| SadTalker checkpoints/第三方说明 | [OpenTalker/SadTalker README](https://github.com/OpenTalker/SadTalker/blob/main/README.md) | 新旧 checkpoints 列表、face-vid2vid/Deep3DFaceReconstruction/Wav2Lip 来源，以及训练/代码借用声明。 |
| SadTalker 官方权重发布 | [SadTalker v0.0.2-rc Release](https://github.com/OpenTalker/SadTalker/releases/tag/v0.0.2-rc) | 官方 release 及新版打包权重来源。 |
| face-vid2vid 重现项目 | [One-Shot Free-View LICENSE](https://github.com/zhanglonghao1992/One-Shot_Free-View_Neural_Talking_Head_Synthesis/blob/main/LICENSE.md) | CC BY-NC 4.0，只允许非商业用途。 |
| Wav2Lip 开源权重 | [Rudrabha/Wav2Lip 官方 README](https://github.com/Rudrabha/Wav2Lip/blob/master/README.md) | 明示开源代码、模型/结果仅限研究、学术、个人用途，商业使用严格禁止。 |
| Deep3DFaceReconstruction 代码 | [Microsoft Deep3DFaceReconstruction LICENSE](https://github.com/microsoft/Deep3DFaceReconstruction/blob/master/LICENSE) | 代码为 MIT；不替代 BFM 数据许可。 |
| Deep3DFaceReconstruction 依赖链 | [Microsoft Deep3DFaceReconstruction README](https://github.com/microsoft/Deep3DFaceReconstruction/blob/master/readme.md) | 明示必须单独申请 BFM09，并列出 FaceWarehouse expression basis 等依赖。 |
| Basel Face Model | [University of Basel BFM Non-Commercial License](https://faces.dmi.unibas.ch/bfm/content/basel_face_model/downloads/BFM_NonCommercial_License_Agreement.pdf) | 仅限内部非商业研究/评估/测试，并限制分发及营利用途。 |
| dlib 68 点 landmark 权重 | [dlib-models 官方 README](https://github.com/davisking/dlib-models/blob/master/README.md) | 发布者明确说明训练集许可排除商业使用，模型不能用于商业产品。 |
| PIRender | [RenYurui/PIRender LICENSE](https://github.com/RenYurui/PIRender/blob/main/LICENSE.md) | CC BY-NC 4.0，只允许非商业用途。 |
| face-alignment | [1adrianb/face-alignment](https://github.com/1adrianb/face-alignment) | 代码仓库 BSD-3-Clause；本机精确缓存权重仍需固定来源。 |
| GFPGAN | [TencentARC/GFPGAN LICENSE](https://github.com/TencentARC/GFPGAN/blob/master/LICENSE) | 主项目 Apache-2.0，但官方 LICENSE 另列第三方组件及非商用 DFDNet。 |
| Windows/SAPI 技术用途 | [Microsoft Learn: TTSApp (SAPI 5.4)](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125104%28v%3Dvs.85%29) | SAPI 可选择 voice 并产生/播放合成音频的技术说明；不是商业输出授权。 |
| Windows 系统与内置声音条款 | [Microsoft Windows 11 OEM License Terms](https://www.microsoft.com/content/dam/microsoft/usetm/documents/windows/11/oem-%28pre-installed%29/UseTerms_OEM_Windows_11_English.pdf) | 条款适用于 Windows 及随系统提供的 fonts/icons/images/sound files，并保留未明确授予的权利。实际设备若适用其他获取渠道/地区条款，应以本机条款为准。 |
| Azure TTS 对照条款 | [Microsoft Product Terms: Microsoft Azure](https://www.microsoft.com/licensing/terms/en-US/productoffering/MicrosoftAzure/allprograms) | 仅付费层预置神经 TTS 的输出明确可商用；不能套用于本地 SAPI voice。 |
| Noto Sans CJK | [Noto CJK Sans 官方 LICENSE](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE) | SIL OFL 1.1 完整文本；允许使用/嵌入/随软件销售，禁止单独出售字体，并说明生成文档不受 OFL 约束。 |

## 六、维护规则

- 任一模型、权重、节点、便携工具或 voice 更新后，旧结论不自动继承；新增一条版本、哈希、来源和许可记录。
- 不以博客、论坛、视频教程、搜索摘要或“大家都在用”作为放行证据；至少需要发布方模型卡、官方仓库 LICENSE、官方产品条款或权利人书面授权。
- 许可网页可能变更。正式发行证据包中应保存当日网页/PDF、提交哈希和许可原文副本，而不只保存链接。
- `已确认` 只覆盖本台账写明的版本和用途；发行平台规则、广告审查、生成式 AI 标识、编解码器专利和各地区法律必须另行核对。
