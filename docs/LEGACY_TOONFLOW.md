# Toonflow 旧适配器退役说明

2026-10-08 的许可核查发现：初始发布提交 `a2d1fe0` 中的 `integrations/toonflow/localWanComfy.ts` 基于旧版 Toonflow 1.x 供应商模板改写，其中类型/全局声明与上游模板相对应。

- 上游：[固定版本的供应商模板](https://github.com/HBAI-Ltd/Toonflow-app/blob/e03cf590eb0cab63534a4040db9acb4ec95b42a6/data/vendor/null.ts)。
- 许可：[该版本完整 LICENSE](https://github.com/HBAI-Ltd/Toonflow-app/blob/e03cf590eb0cab63534a4040db9acb4ec95b42a6/LICENSE)，仓内保留[历史许可副本](licenses/Toonflow-legacy-e03cf590-LICENSE.txt)，包含 Apache 文本及额外商业条款，不应简称为标准 Apache-2.0。

该旧文件已从当前版本的 Git 跟踪中移除。开发机实体文件保留并被 Git 忽略，没有删除本地历史实验，没有改写远端 Git 历史。仓库根目录新增的 Apache-2.0 **不追溯重新授权旧模板及历史提交**；从历史版本提取或再分发该文件时仍须核对原许可，不能用当前根许可证替代。

## 当前应使用什么

使用 [localFreeV2.ts](../integrations/toonflow/localFreeV2.ts) 和 [start_local_free.ps1](../scripts/start_local_free.ps1)，网关端口为 18766。该路线支持当前 `generateImage / generateVideo` 协议，接入步骤见 [README](../README.md#接入-toonflow可选)。

当前 2.x 参考源是另一个明确的 [MIT 版本](licenses/Toonflow-72a895c2-MIT.txt)；它不会自动改变旧版模板的许可。完整 Toonflow 应用仍须单独安装。

`start_toonflow_local_wan_adapter.ps1` / `toonflow_local_wan_adapter.py` 是保留的历史实验工具，不属于当前推荐入口。公开版本缺少旧供应商文件时，旧启动脚本会给出退役提示并停止；本机保留旧文件不代表其已经完成清权，也不要把新供应商导入旧协议服务。
