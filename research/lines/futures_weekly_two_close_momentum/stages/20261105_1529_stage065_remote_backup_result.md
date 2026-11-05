# Stage065 远端备份结果

- 本次为研究资料备份，策略和回测参数未改动，无新增回测。
- 研究分支：`codex/weekly19-stop-reversal-20261103`。
- 固定备份提交：`c72d9745de09dba313c11cece604e5f0aaddb534`。
- 固定备份标签：`s21-200k-touch-backup-20261105`。
- 分支与标签已 atomic push 到 `git@github.com:nayonglin/vnpy.git`，远端分支和标签解引用均为该提交。master 前后仍为 `491d13617f61cac88b94476dc36171dc81691f30`。
- 独立 GitHub 克隆已取得完整提交/树元数据；290 项源码内容的 Git blob ID 与远端树逐项一致。
- GitHub API 另行确认 manifest 与 8 分卷，9 个对象的 blob ID 和字节数均匹配本地。
- 本地完整解压恢复 10,909 文件、1,743,394,097 字节，逐项 SHA256 通过；290 项源码哈希通过。当前线测试 39 passed，22 subtests passed。
- 原研究审查脚本 Stage054/055 各有一处文件尾空行，作为原始证据保留，未为了格式检查改写冻结脚本。其他暂存文件的 diff --check 通过。
- 远端整包重新下载并解压未完成：SSH 回读持续低速，直接 HTTPS 与已有本地 SOCKS 路径超时；停止了仅用于验收的临时下载。不得将本次远端对象核对和本地恢复说成“远端全部字节重新下载恢复通过”。
- 证据：`reviews/stage065_remote_snapshot_api.json`、`reviews/stage065_remote_readback.json` 和独立审查证书；恢复步骤见 `BACKUP.md`。

本次过拟合判断为否：没有新增收益筛选、优化或调参。继续价值为是：代码、参数、历史输出、复盘与必要行情已有远端副本和可核验恢复清单；新机器仍需安装环境并按映射处理冻结来源路径。
