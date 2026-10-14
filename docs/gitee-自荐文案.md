# Gitee 开源推荐 · 自荐粘贴稿（务实版）

> 编辑在 30 秒内要确认三件事：**能跑、有差异点、不是刷屏文案**。  
> 本版刻意少形容词，多给可核对路径。提交前请先完成 [`gitee-仓库设置.md`](gitee-仓库设置.md)。

## 软件名称

镜语 · JingYu（免费本地 AI 漫剧工作台）

## 一句话简介（软件简介栏）

开源本地 AI 漫剧生成网关：Ollama 草案 + ComfyUI 静帧/短 I2V，Windows 内存预检与可恢复队列；可选 Toonflow 供应商。Apache-2.0。协议测试可复现，**不宣称一键精品短剧**。

## 详细介绍（软件详细介绍栏）

### 解决什么问题

云端按次 API 成本高、素材外流；很多“一键短剧”演示难复现。镜语提供本机 loopback 网关：文本、文生图、单首帧图生视频串行入队，内存不足明确拒绝，未知提交暂停等待人工核对，适合逐镜人审制作。

### 仓库里能直接核对的东西

| 核对项 | 路径 |
|:---|:---|
| 工程基线 README | `README.md` |
| 协议测试与边界 | `docs/EVALUATION.md` |
| 部署与复现限制 | `docs/PUBLIC_DEPLOYMENT.md` |
| 算法与模型说明 | `docs/ALGORITHMS_AND_MODELS.md` |
| 真实截图 / 操作动图 | `docs/screenshots/`（动图含真实 503） |
| 第三方权利台账 | `docs/THIRD_PARTY_NOTICES.md` |
| 协议 | Apache-2.0 · https://gitee.com/withthesea/ai-diy-video |

### 核心能力（按优先级）

1. **本机闭环**：网关只连 loopback，不默认回退收费 API  
2. **诚实失败**：提交内存预检；未知 Comfy 提交 → `needs_attention`  
3. **逐镜链路**：Ollama → RealVisXL → Wan2.1 I2V（2–4 秒级短片）  
4. **可选 Toonflow**：自定义媒体供应商，无需 API Key  
5. **可测协议**：82+ pytest + 供应商 Node 契约（非 GPU 画质验收）

### 快速体验（审核可复制）

```powershell
git clone https://gitee.com/withthesea/ai-diy-video.git
cd ai-diy-video
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
# 完整生成另需本机 Ollama + ComfyUI + 模型，见 docs/PUBLIC_DEPLOYMENT.md
.\scripts\start_local_free.ps1 -CheckOnly
```

- 工作台：http://127.0.0.1:18766/（需本机服务就绪）  
- 仅验证工程时可只跑 `pytest`，无需 GPU  

### 技术栈

Python 3.12 · FastAPI · Ollama · ComfyUI · RealVisXL V5 · Wan2.1 I2V 14B FP8 · FFmpeg · 可选 Toonflow

### 明确不做 / 边界

- 协议测试通过 **不代表** 商用短剧画质  
- 干净新机 GPU 端到端复现 **尚未** 作为对外满分基线  
- 模型权重不随仓库分发；成片商用权利需另行核验  

### 适用场景

本机漫剧/短剧分镜试拍、本地提示词闭环、需要可审计队列的二次开发。

---

## 提交前检查清单

- [x] 仓库 About / 显示名已改为镜语 JingYu  
- [x] 已创建 Release `v0.2.1`（空壳 1.0 已删）  
- [ ] 开源软件分类选人工智能 / 多媒体等贴近项（网页填写）  
- [x] Issue 模板已进 `.gitee/ISSUE_TEMPLATE/`  
- [ ] 开源软件信息页上传截图并粘贴简介（网页）  
- [ ] 一句话里有 **协议 + 能跑 + 差异点**，没有「最强 / 一键精品 / 商用保证」空话（提交自荐时核对）

## 备注栏三句（可粘贴）

1. 完整可运行本机网关（脚本/健康检查/协议测试），不是 Demo PPT。  
2. 差异点在诚实失败与可恢复队列，不是再包一层云端按次 API。  
3. 边界写在 `docs/EVALUATION.md`，欢迎按文档复现协议测试后再评。
