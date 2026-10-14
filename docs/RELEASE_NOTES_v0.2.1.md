# 镜语 · JingYu 0.2.1

本地 AI 漫剧生成网关工程基线（Apache-2.0）。

## 本版要点

- 对外品牌：**镜语 · JingYu**（原展示名 AIvideo）
- 本机闭环：Ollama 草案 → RealVisXL 静帧 → Wan2.1 I2V 短片
- Windows 提交内存预检；未知提交进入 `needs_attention`，不盲目重试
- 中英 README、截图/操作动图、本地样片 6 镜拼接预览
- 协议测试基线：82+ pytest + Toonflow 供应商 Node 契约

## 可直接核对

- 样片：`docs/samples/wan_30s_preview/preview_concat.mp4`
- 边界：`docs/EVALUATION.md`（协议通过 ≠ 商用画质）
- 部署：`docs/PUBLIC_DEPLOYMENT.md`

## 快速验证（无需 GPU）

```powershell
git clone https://gitee.com/withthesea/ai-diy-video.git
cd ai-diy-video
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

完整生成另需本机 Ollama + ComfyUI + 模型权重。详见 `CHANGELOG.md`。
