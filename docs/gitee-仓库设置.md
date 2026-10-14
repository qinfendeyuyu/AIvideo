# Gitee 仓库设置（自荐前必做）

代码再完整，**仓库设置页空白 / 无 Release / 简介过时** 也会被编辑当成「水项目」直接滑过。下列项需在网页完成。

## 1. 管理 → 仓库设置 → 基本信息

| 字段 | 建议填写 |
|:---|:---|
| 仓库介绍 | `镜语 JingYu：本地 AI 漫剧生成网关，Ollama + ComfyUI 静帧/短 I2V，内存预检与可恢复队列。Apache-2.0 · Windows+NVIDIA。` |
| 主页 | `https://gitee.com/withthesea/ai-diy-video` |
| 开源许可 | Apache-2.0（与 LICENSE 一致） |

保存后刷新仓库首页，确认 About 与 README 一句话一致。

## 2. 关联「开源软件」信息（自荐强相关）

路径因版面可能为：**仓库 → 开源软件 / 软件信息 / 申请上架**。

- 分类优先：**人工智能**、**多媒体**、或带「创作工具」的贴近项  
- 软件简介：粘贴 [`gitee-自荐文案.md`](gitee-自荐文案.md) 中「一句话简介」  
- 详细介绍：粘贴同文件「详细介绍」全文  
- 截图：上传 `docs/screenshots/workbench-overview.png`、`generation-panels.png`、`service-status.png`  

## 3. Releases

推送文档后建议打 Tag（或在网页「发行版」创建）：

```bash
git tag -a v0.2.0 -m "v0.2.0 engineering baseline"
git push gitee v0.2.0
gitee release create --tag v0.2.1 -n "镜语 JingYu 0.2.1" -b "品牌更名镜语 · JingYu；样片与工程基线。详见 CHANGELOG。" --no-tui
```

有至少一个正式版，编辑才会信「可交付」。

## 4. Issues / 可维护信号

请在 **管理 → Issue 模板** 粘贴：

- [`issue-templates/bug.md`](issue-templates/bug.md)
- [`issue-templates/feature.md`](issue-templates/feature.md)

并确认已开启 Issues；仓库内已有 `CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`。

## 5. 自荐提交节奏

1. 完成上面 1–4，确认首页有截图、Release、协议徽标  
2. 用 [`gitee-自荐文案.md`](gitee-自荐文案.md) 再投一次  
3. **一个工作日无动静 ≈ 默认未过**；改简介首句或补一张真实界面图后再投，勿同文连刷  

## 6. 无法靠改代码解决的

| 信号 | 建议 |
|:---|:---|
| Star / Fork 极低 | 请真实体验后再点星；勿刷量 |
| 无企业背书 | 写「开源本机网关 + 可复现协议测试」即可 |
| GPU 成片难复现 | 保持 `EVALUATION.md` 诚实表述，勿包装成画质满分 |
