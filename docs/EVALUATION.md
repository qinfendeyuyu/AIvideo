# 评测与诚实边界（可复现）

> 目的：把「测了什么、没测什么」说清楚，而不是用口号冒充成片验收。自荐 / 答辩请直接引用本节。

## 1. 评测对象

| 项 | 内容 |
|:---|:---|
| 协议 / 状态机 | `.\.venv\Scripts\python.exe -m pytest -q` |
| 供应商契约 | `node --experimental-vm-modules .\tests\test_toonflow_provider_contract.mjs` |
| 覆盖面 | 外部地址拒绝、输入校验、内存门禁、单 worker / 进程锁、落盘失败、重启接管、未知提交、视频结构校验、取消等待、截图/动图完整性、许可文件检查 |
| 环境 | **不需要**下载模型或占用 GPU 即可跑协议测试；视频结构检查需本机 FFmpeg/FFprobe |
| 记录日期 | 2026-10-08：82 pytest + 13 组 Node 协议测试通过 |

## 2. 最近一次协议测试结果

| 指标 | 值 | 怎么读 |
|:---|:---|:---|
| Python 测试 | **82 / 82** | 仅对仓库内协议与状态机成立 |
| Node 供应商协议 | **13 组通过** | 核对 `generateImage` / `generateVideo` 契约，不是端到端 Toonflow 成片 |
| GPU 成片验收 | **未宣称通过** | 见下文边界 |

## 3. 边界（请务必读）

1. **协议通过 ≠ 画质通过**：测试不生成商业级短剧，也不证明角色一致性 / 打斗运镜达到样片水平。  
2. **干净新机 GPU 端到端尚未完成**：开发机 ComfyUI / WanVideoWrapper 存在未打包本地补丁；仅按上游 commit 安装**不能**声明已复现 4060 8GB 视频生成。详见 [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md)。  
3. **内存门禁是诚实失败**：提交内存不足时返回 503；README 动图刻意保留真实拦截，不是成功生成演示。  
4. **模型与节点许可独立**：根 Apache-2.0 不覆盖权重、Comfy 节点 GPL、OpenRAIL 等；见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。  
5. **“免费”不是零成本**：仍有硬件、电费、存储、人工与模型下载成本。

## 4. 工程侧可核对信号

| 信号 | 位置 |
|:---|:---|
| 自动化测试 | `tests/` |
| 健康检查 | `GET http://127.0.0.1:18766/health` |
| 工作流模板 | `workflows/` |
| 算法说明 | [ALGORITHMS_AND_MODELS.md](ALGORITHMS_AND_MODELS.md) |
| 截图 / 动图来源 | [SCREENSHOTS.md](SCREENSHOTS.md) · [GENERATION_WALKTHROUGH.md](GENERATION_WALKTHROUGH.md) |

## 5. 复现命令（协议层）

```powershell
git clone https://gitee.com/withthesea/ai-diy-video.git
cd ai-diy-video
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
# 可选：node --experimental-vm-modules .\tests\test_toonflow_provider_contract.mjs
```

GPU 成片验收需自备 ComfyUI + 模型，并按 [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) 核对补丁与基线；**本仓库当前不以「GPU 样片满分」作为对外基线。**
