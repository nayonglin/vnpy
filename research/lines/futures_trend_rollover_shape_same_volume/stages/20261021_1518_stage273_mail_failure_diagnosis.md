# Stage273：10月21日邮件失败定位

- 研究线：`futures_trend_rollover_shape_same_volume`。
- 性质：本机邮件链路只读排障；无策略改动、回测、行情重跑、CTP连接、SMTP连接、认证或人工补发。
- 过拟合：否，未调整任何alpha/AI/风险参数。继续价值：是，区分账户邮件投递失败和信号流水线仍在执行，防止误报无信号及重复发送。

## 直接结论

失败的是15:12账户快照邮件：CTP front/auth/login/settlement/account/positions查询均成功，send/cancel均0；outbox `account-2026-10-21` 于15:12:40记录 `failed_safe`，`error_type=gaierror`、`data_started=false`、attempts=1。即故障发生在邮件正文DATA提交前的地址解析/连接准备阶段，并非账户查询失败或SMTP认证拒绝。

同一服务随后发送 `alert-account-2026-10-21`，15:12:51记录 `accepted`、refused_count=0、data_started=true；SMTP服务器接受了该异常通知。约11秒后同一配置可发送成功，且本次沙箱外真实getaddrinfo已解析成功（2地址），支持“短暂解析故障”，不支持“邮箱长期配置错误/密码失效”。具体DNS服务器或网络层原因没有持久原始errno证据，不能编造归因。

本次沙箱内第一次getaddrinfo报gaierror/errno8，但该受限环境结果明确排除，不能用它断言用户生产网络仍失败；经批准在沙箱外只做DNS查询成功，未连接SMTP或发送邮件。

## 信号日报与时刻

15:10:06启动的 `postclose` 是另一任务。检查时仍为running，Stage173日K下载日志持续新增saved合约，已到38个合约；尚未生成shadow目录或postclose outbox，因此还没有出现这封信的SMTP失败。昨天同一日报15:10:07启动、15:19:16才被SMTP接受，说明15:10为启动时刻，并非瞬间投递完成。不得将running当成失败，也不能把下载进度当作最终日报已成功。

## 为什么没立刻补发

`core.Outbox.deliver`只允许failed_safe且allow_retry=true且attempts<2的原消息重试；accepted/unknown禁止重复发送。`runner.run_task`非恢复调用保留既有失败状态。真正恢复在18:20的`local.fian.mail.retry`触发，launchctl已验证18:20日历存在；该路径只补投递原账户消息，不在过时窗口重连账户。15:30/15:55 watchdog检查/告警，不即时重投账户原邮件。

因此本次延误是“暂时解析失败 + 原邮件无短间隔自动恢复、等18:20重试”。本次用户要求定位，未擅自补发或改变去重状态、调度、生产发布及旧mail源码。canonical生产链路仍不能替代此本机邮件事实。

## 参考与证据

- 运行事实：outputs/stage273_mail_failure_20261021/diagnosis.json（仅安全摘要，不含邮件正文、地址、凭证或资金）。
- 源码复核：本机service/transport.py、core.py、runner.py，摘要保留三个SHA。
- Python官方文档说明gaierror为getaddrinfo/getnameinfo相关地址解析错误：https://docs.python.org/3/library/socket.html#socket.gaierror 。判断以实际outbox标记、时间线及沙箱外复测为准，未把外部文档冒称本次服务日志。
- 独立agent只读复核另存本输出目录。
