# 公开仓库部署与复现边界

本页面向新电脑；`TOONFLOW_FREE_LOCAL.md` 还包含原开发机的历史记录。优先以本页和根目录 README 为安装入口。

## 支持范围

当前网关面向 Windows，内存门禁调用 `GlobalMemoryStatusEx`。非 Windows 尚未实现等价预检，会拒绝生成；不要通过注入测试用内存探针绕过生产门禁。

网关、Ollama、ComfyUI 必须同机。新网关不接受局域网/云端后端，也不使用代理或重定向。ComfyUI 与 Ollama 自身的插件行为不受网关防火墙控制；请只安装信任的节点。

`requirements.txt` 仅安装网关和本项目测试依赖。模型、PyTorch/CUDA、ComfyUI、节点和 FFmpeg 独立安装，建议网关与 ComfyUI 使用不同虚拟环境。本仓库不会修改驱动、页面文件或系统服务。

## 复现限制与开发机基线

以下是2026-10-08只读检查记录，不是经干净环境重建验证的完整锁文件：

| 组件 | 记录 |
| --- | --- |
| Windows网关Python | 3.12.5 |
| ComfyUI | `77917ed3a6291689e5c2ee8ccbdd6708e85a53a6`，本地有修改 |
| ComfyUI-WanVideoWrapper | `088128b224242e110d3906c6750e9a3a348a659b`，本地有修改 |
| ComfyUI-VideoHelperSuite | `4ee72c065db22c9d96c2427954dc69e7b908444b` |
| Comfy PyTorch | 2.6.0+cu124 |
| torchvision / torchaudio | 0.21.0+cu124 / 2.6.0+cu124 |
| Node协议测试 | 24.19.0 |

来源：[ComfyUI](https://github.com/Comfy-Org/ComfyUI)、[WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)、[VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)。各组件按其自己的安装文档及许可准备，版本升级后须重测工作流。

开发环境另有未打包的外部修改：

- ComfyUI `comfy/utils.py`：无mmap加载相关改动。
- WanWrapper `nodes.py`：Cached T5 CPU选项和FP8卸载相关改动。
- `nodes_model_loading.py` / `custom_linear.py`：低提交内存、lazy权重读取与形状处理。
- `wanvideo/modules/t5.py`：meta初始化。
- `wanvideo/modules/model.py`：block swap恢复CPU参数处理。

本次发布没有复制整套外部仓库或擅自重许可这些修改。**因此不能声明新电脑仅按上述commit安装就能复现4060 8GB视频生成。** 完整复现仍需固定并审核补丁、履行各自许可、在独立干净环境重建和实测。目前适合接入已经能独立运行所列工作流的本机ComfyUI。

## 准备 ComfyUI

1. 按 ComfyUI 官方说明创建它自己的 Python/CUDA 环境。
2. 安装需要的 WanVideoWrapper、VideoHelperSuite 及它们的依赖；依赖装到 **ComfyUI 的 Python**，不是网关的 `.venv`。
3. 按 README 的文件表准备精确模型；WanWrapper tokenizer 文件也必须存在。
4. RealVisXL 放在 ComfyUI 的 `models/checkpoints`，或自行编辑 ComfyUI 的额外模型搜索路径。不要直接使用原开发机写死E盘路径的配置。
5. 手动启动并验证，示意命令如下。把两个占位路径换成自己的真实路径：

```powershell
$comfyPython = 'C:\YOUR_COMFY_ENV\Scripts\python.exe'
$comfyRoot = 'C:\YOUR_COMFYUI'
& $comfyPython (Join-Path $comfyRoot 'main.py') `
    --listen 127.0.0.1 `
    --port 8488 `
    --lowvram `
    --reserve-vram 0.8 `
    --disable-mmap `
    --disable-pinned-memory `
    --cache-none `
    --disable-auto-launch
```

这些参数不是OOM不会发生的保证，也不代替上述本地补丁。8GB显卡上不要同时启动多个生成器。不要照搬历史 `start_comfy_wan14b.ps1`：它还校验旧样片首帧、固定盘符和特定原机环境。

若8488被系统保留，先核查本机端口；可以手动让Comfy使用另一个可用端口，再显式启动网关：

```powershell
.\.venv\Scripts\python.exe scripts\local_free_gateway.py --comfy-url http://127.0.0.1:9188
```

网关仍使用18766。简单启动器固定8488；不要以为改了Comfy端口它会自动跟随。

## 独立检查工作流

网关从以下API格式工作流构造实际请求：

- `workflows/realvisxl_v5_vertical_hero_portrait_single_api.json`：Comfy核心节点，网关会覆盖提示词、种子、画幅和保存前缀。
- `workflows/toonflow_local_wan_i2v_template.json`：Wan14B + `WanVideoTextEncodeCached` + VideoHelperSuite，网关会上传首帧、覆盖种子/帧数/前缀。

缺少类名、模型或节点参数不兼容时，应修复环境或停止验证，不要通过改成空节点、静态缩放视频来“跑通”。完整视频需 FFprobe 核对原生尺寸、帧率和总帧数，并经 FFmpeg 完整解码后才返回成功；视觉质量仍由人审核。

## 启动与个人配置

确认 Comfy8488、Ollama11434 和 `qwen2.5:7b` 可用后，在本项目根目录：

```powershell
.\scripts\start_local_free.ps1 -CheckOnly
.\scripts\start_local_free.ps1 -Background
```

新网关不读取历史 `configs/models.yaml`。该文件属于个人机器配置，不提交Git；旧实验API在它不存在时可加载公开 `configs/models.example.yaml` 供查看和测试，**不会因此安装模型或启用静默演示回退**。需要运行旧流水线时先复制示例再填写自己的路径，且不得把未清权的SadTalker/SAPI路线用于商用母版。

## 故障排查

| 现象 | 检查与处理 |
| --- | --- |
| `image_missing` / `video_missing` 非空 | 对照缺失类名与模型文件名，核对节点依赖、版本、tokenizer和搜索路径 |
| 可用提交内存不足 | 文本6GiB、图片8GiB、视频16GiB是当前预检下限；保存工作、关闭不用的应用后重试，不自动改页面文件 |
| `needs_attention` | 核对Comfy历史、队列、输出与网关任务记录；结果未知时不会自动重交 |
| Another worker already owns directory | 复用原网关；不要启动多worker或通过改端口绕过进程锁 |
| FFprobe/FFmpeg找不到 | 将两者加入PATH，重新启动网关以读取更新后的环境 |
| 出片但五官/背景/动作不合格 | 标记未通过，修改关键帧或镜头设计再试；结构校验不能代替审片 |

运行日志、任务、模型、输入和产物不随Git提交。迁移项目时另行备份它们；仅克隆源代码不会恢复已有制作任务。
