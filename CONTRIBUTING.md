# 贡献指南 · Contributing

感谢关注 **AIvideo**。欢迎 Issue、文档改进、缺陷修复与协议测试补强。

**唯一官方源码仓库（请使用此地址引用）**  
https://gitee.com/withthesea/ai-diy-video

涉及项目介绍、截图、演示、论文/答辩引用时，**一律标注上述 Gitee 地址**，勿把镜像仓库当作主入口。

## 如何参与

1. 在 Gitee 上 Fork 本仓库  
2. 新建分支：`feature/简短说明` 或 `fix/简短说明`  
3. 在项目 `.venv` 中验证：  
   `.\.venv\Scripts\python.exe -m pytest -q`  
   涉及供应商时：`node --experimental-vm-modules .\tests\test_toonflow_provider_contract.mjs`  
4. 提交清晰 commit message（说明**为什么**改）  
5. 发起 Pull Request，并关联 Issue  

首次参与请先读：README「诚实边界」/ [docs/EVALUATION.md](docs/EVALUATION.md) / Issue 模板。

## 开发约定

- 遵守 Apache-2.0 文件头与版权声明  
- 网关只连数字 loopback；不要引入公网回退、代理跟随或收费 API 默认路径  
- 不要提交密钥、`.env`、私人 `models.yaml`、生成成片、模型权重、SSH 运维脚本  
- 行为变更请同步更新 `docs/` 或 README 对应小节  
- 禁止用占位素材、假进度条或关掉内存门禁来“证明成功”  

## 维护者响应承诺

维护者将尽量：

- **72 小时内**确认有效 Issue（含优先级）  
- 缺陷类 Issue 标注优先级与复现状态  
- PR 在合理时间内给出 Review 或修改建议  

安全漏洞请按 [SECURITY.md](SECURITY.md) 私下披露，勿在公开 Issue 贴完整利用细节。

## 行为准则

参与本项目即表示同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 许可

贡献的代码默认按 **Apache License 2.0** 授权；请同时阅读根目录 `NOTICE` 与 [docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md)。
