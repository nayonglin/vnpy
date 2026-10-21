# Stage684：0.5%单族风险顺序历史敏感性

2026-10-21 17:41 CST；line_id futures_full_market_long_signal_ai；day；非重要突破。

用户已明确要求.5%，以675的.25%为研究A，685为C，680的1%只读参照。只改SINGLE_RISK=.005，其他风险/模型/信号/止损/费用/容量不改；2015-01-05—2026-10-16连续2862日/100万，最多0fit2cash/0旧账重跑/0SQL下载。

- [ ] 685最小机械适配与实效fixture；最终source_ready冻结。
- [ ] 686最终sourceGO后，root唯一actual_run1；不得因超时重启。
- [ ] 686一次完整两新账独审，沿用年度数值等价契约，不重审旧账。
- [ ] 687三风险六账户全日频/年度CSV、HTML和真实浏览器PNG导出。
- [ ] 688完整中文结果/判断、一次更新LINE/registry，交付后不自动扫参。

开始反思：是否存在过拟合风险？是，已看过.25%/1%同历史后追加.5%，因此有选择偏差；有限单点比较有价值，但不能证明最优/稳定泛化。不把用户明确请求误当允许自动扫网格。收益提高但回撤变坏仍是交换，非自然晋级。

协议：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage684_single_risk_halfpct_protocol/protocol.json
