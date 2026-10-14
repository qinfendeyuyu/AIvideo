# 本地生成样片说明

本页记录随仓库发布的 Wan I2V 工程预览片段，供 README 展示与复现核对。**不是商用短剧画质验收。**

## 试片信息

| 项 | 内容 |
|:---|:---|
| 标题 | 司天署·30秒画质试片 |
| 模型 | Wan2.1 I2V 14B FP8 + RealVisXL V5 关键帧 |
| 分辨率 | 480×832 · 16fps |
| 硬件 | RTX 4060 Laptop 8GB（开发机） |
| 拼接总长 | 18.375s（6 镜） |
| 元数据 | [samples/wan_30s_preview/manifest.json](samples/wan_30s_preview/manifest.json) |

## 文件

| 文件 | 说明 |
|:---|:---|
| `samples/wan_30s_preview/preview_concat.mp4` | P01→P06 顺序拼接 |
| `samples/wan_30s_preview/clips/00_P01.mp4` … `05_P06.mp4` | 分镜单镜 |
| `samples/wan_30s_preview/poster.png` | P01 首帧封面 |

## 诚实边界

1. P01–P03 约 5s/镜（81 帧），P04–P06 约 1s/镜（17 帧），同一试片内参数不一致。  
2. P04–P05 来自远程台式 harvest 后同步；P01–P03、P06 为本机生成。  
3. 仅证明本机链路**能出片**，不证明干净新机可零补丁复现，也不证明达到参考样片画质。  
4. 样片人物与场景为原创提示词生成；商用发布前须自行核验肖像与素材权利。

## 如何更新样片

1. 在本地完成新镜头并 ffprobe 核对尺寸、帧率、时长。  
2. 复制到 `docs/samples/wan_30s_preview/clips/`，更新 `manifest.json`。  
3. 在 `clips/` 目录内用 ffmpeg concat 重建 `preview_concat.mp4`。  
4. 更新 README 样片小节与拍摄日期。
