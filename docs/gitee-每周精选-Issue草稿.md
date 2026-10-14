# 每周精选自荐 Issue 草稿

提交入口：https://gitee.com/gitee-community/weekly-collection/issues/new

---

**标题建议：** 自荐：镜语 JingYu — 本地 AI 漫剧生成网关（Windows + NVIDIA）

**正文可粘贴：**

## 项目

- 名称：镜语 · JingYu  
- 地址：https://gitee.com/withthesea/ai-diy-video  
- 协议：Apache-2.0  
- 发行版：v0.2.1  

## 推荐语

本机 AI 漫剧工作台：Ollama 写草案、ComfyUI 出静帧与短 I2V，带 Windows 内存预检和可恢复队列。不默认回退收费 API；协议测试可复现（`pytest` 即可验收工程），GPU 成片需自备模型。适合想本地闭环做逐镜试拍的开发者。

## 可核对路径

- README / 样片：`docs/samples/wan_30s_preview/preview_concat.mp4`  
- 边界：`docs/EVALUATION.md`  
- 无需 GPU 验证：clone 后 `pip install -r requirements.txt && pytest -q`  

## 备注

1. 完整可运行本机网关，不是 Demo PPT。  
2. 差异点在诚实失败与可恢复队列，不是再包一层云端按次 API。  
3. 欢迎按文档复现协议测试后再评。
