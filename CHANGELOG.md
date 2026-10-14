# Changelog

## 0.2.2 — 2026-10-14

- **文档精简**：移除 Gitee 自荐文案、仓库设置稿、每周精选草稿及重复的 `docs/issue-templates/`（正式模板保留在 `.gitee/ISSUE_TEMPLATE/`）。

## 0.2.1 — 2026-10-14

- **项目更名**：对外品牌定为 **镜语 · JingYu**（原展示名 AIvideo）；仓库地址暂不变。

## 0.2.0 — 2026-10-14

- **开源工程基线**：按 IAS-DAS 文档体例重写 README / README.en；新增 `docs/EVALUATION.md`、`docs/ROADMAP.md`、`docs/项目简介.md`；Issue 模板放在 `.gitee/ISSUE_TEMPLATE/`。
- **社区文件**：`CONTRIBUTING.md` · `SECURITY.md` · `CODE_OF_CONDUCT.md` · `CONTRIBUTORS.md` · `CHANGELOG.md`。
- **本地 Wan 批处理**：`scripts/run_wan_3min_batch.py` 支持帧数 / 步数 / 分辨率 CLI 覆盖（`4c8eeb3`）。
- **文档素材**：操作动图、真实工作台截图与本地 Wan 样片已挂 README。

## 0.1.0 — 2026-10-08

- 公开发布本地免费网关与逐镜工作台（`a2d1fe0`）。
- Apache-2.0 根许可证、`NOTICE`、第三方许可台账与算法说明。
- 协议/状态机测试基线：82 pytest + Toonflow 供应商 Node 协议测试。
- 明确边界：干净新机 GPU 端到端与商用画质验收尚未完成。
