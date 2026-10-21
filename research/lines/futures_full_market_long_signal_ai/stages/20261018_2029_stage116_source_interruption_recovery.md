# Stage116：原始来源下载中断恢复与环境失败终态

- 时间：2026-10-18 20:24—20:29 CST，精确执行时间以 started/completion 中 UTC 为准。
- 研究线：`futures_full_market_long_signal_ai`。
- 重要突破：否。仅恢复来源工程；没有收益、模型或现金实验进展。
- 起因：root 与本 agent 已用 PID 存在性检查确认原 Stage109 PID26043 已不存在，缺少 completion。原 progress 陈旧，不能用其 2872/2874 代替逐文件事实。

## 实际恢复方案

逐文件确认原请求日志中 2,895 个唯一 started，原 dates 中 2,893 个真正完成的新响应及 13 个复用响应；2023-12-13、2023-12-14 仅有 started，raw/normalized/date 均不存在。剩余 680 个日期从未 started。原 Stage109 脚本、started、progress、requests_started 和所有原始响应一律未改。

新增 `tools/stage116_source_recovery.py`，导入 SHA 固定的 Stage109 fetch/normalize/finalize，仅把输出目录和未 started 队列换成本阶段；保留原 4 小时起点，2 并发、单请求 25 秒、2MiB、全局 3GiB、无重试、不跟随重定向、相同日期及端点。对两条在途中断保留 `interrupted_unknown`，不重发；为未知接收字节预留 4MiB 上限，而不伪称字节为零。小型日期记录复制到本阶段，原 raw/normalized 继续按绝对路径引用，来源映射完整保留。

实施前 3 个边界 fixture 先因 planner 缺失失败，实施后全部通过：已完成和在途均不重新入队、存在无日志 orphan raw 时拒绝、重复 started 或无 started 完成记录拒绝。没有重复旧测试集或金融资格检查。

## 意外环境故障及真实结果

20:27:23 CST 在 sandbox 内启动后，SHFE 域名 DNS 立即报 `Errno 8: nodename nor servname provided, or not known`。按原连续五次网络失败规则停止；双并发已有尾项，因此共 6 个新请求完成为 `network_error`、响应均 0 字节。没有发起剩余 674 日期，也没有重试这 6 个失败日期。

- 原新请求 started：2,895；原真正完成：2,893。
- 本阶段新增 started/finished：6/6，均网络错误。
- 合计新请求 started/finished：2,901/2,899。
- 完整 3,588 日期状态：2,893 HTTP200 +13 复用 +2 interrupted_unknown +6 network_error +674 not_requested。
- 6 个失败日期：2023-12-15、18、19、20、21、22。
- 已知原新响应字节：904,917,388；未知在途字节上限：4,194,304；本阶段新响应字节：0。
- stop_reason：`five_consecutive_block_or_network_failures`。
- 真实金融 fit/cash/SQL：0/0/0。

`outputs/stage116_source_recovery/` 内 completion 是明确的复合恢复终态，stage109/implementation_sha 保留原 fetch/normalize 实现身份，另以 execution_stage116、wrapper SHA、恢复协议、原始请求日志绑定解释不同执行。**不声称原无中断单遍成功，也不把 unknown 伪装 finished。** 原 finalizer 中 supported_dates 仍是 scope 观测计数，不能当 unique source days；后续科学投影直接读取绑定 raw，不依赖该派生计数。

## 绑定

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| wrapper | 12,755 | `f57e61f56abcf44e82d20baa4467940230b225355d69475300566a14397f775e` |
| completion_receipt.json | 3,920 | `52e0fa4540b97f1b64159cabd151876c97c54e9e449c4d094a784f409f2f9fec` |
| date_manifest.jsonl | 8,278,188 | `0e0523e51a91f72d936b92fa23e4a65aed740f8a4394872cdec8d9f11d57fa63` |
| recovery_receipt.json | 2,421 | `1327aa98888c28f337c0f65eebb83e6f303c050ca76298ebc68bee0957e38f91` |
| recovery_protocol.json | 10,388 | `8786699153b831dc63462839d38ad1bcc2e57faacf29aebfb2449b099533188c` |
| source_provenance.jsonl | 970,011 | `29a36ea88e5ae87e180d5ab55cf0a3a3fe480f7f3fe7e5259efa3c6236c41e01` |

## 反思及后续

当前不是按收益调整参数的过拟合：没有读取新金融结果、改变假设或风险；既有同史多轮选择风险仍然存在。纠正明确运行环境问题、保留原始失败和严格缺失语义有继续价值，但缺资料本身不构成策略改进。首次恢复本应采用原网络许可环境，这一疏漏已如实报告 root；不自行绕过固定网络失败停止规则或重跑。下一步由 root 选择接受缺失进行固定检验，或明确授权纠正 sandbox 环境后仅获取从未 started 的 674 日期；所有失败证据保持原样。

新增/修改/删除策略参数：均无。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率：均 N/A（本阶段没有回测）。未改 LINE/registry、正式策略、生产或其他研究线。
