# Stage018 入场日C2与连续账本有限合成验证结果

- line_id：futures_ai_monthly_pool_generalization；day；2026-10-20 20:43 CST记录。
- 实际运行：2026-10-20 20:41:21 CST，一次有限合成probe；不是市场回测。
- 是否重要突破：机制与未知处理进展，非alpha/模型突破。
- 继承：仅训练源halfR/retry=False，C2保留；正式源未变。

## 变更和参数

新增`tools/stage018_finite_path_ledger.py`、`stage018_run_finite_probe.py`及15项测试。预声明范围见Stage017；与Stage016一致，只实现单层一次entry、C2入场session及随后固定R持仓MTM的局部合同。普通退出、锁盈、roll和成本等尚未实现，不能拿它代替完整源直接训练。

新增研究验证参数max_sessions=5、max_supplied_paths=256，超过直接拒绝不截取；模型/策略参数新增修改删除均无。回测结果新增修改删除均无；没有真实金融回放、fit、净60日标签、下载或订单。

## 实际输出

12合成用例，46给定路径组合，185逐日合成账本行；43条known、1条execution_unknown、2条path_unknown。此185与真实月末185观察不对应。五日2^5=32条显式组合全部保留，无终态合并、无收益剪枝；不能称覆盖所有与日线兼容的真实分钟路径。

- 同日OHLC的stop-first与confirm-first路径均保留；合成次日close80时分别已实现-1R与未实现-2R，说明强制日线stop不一定是保守近似，也会改变以后持仓。
- C2仅入场session生效：neither后到期；次日即使穿1R也不重新触发。本地Stage827源码直接扫描entry_session，已绑定helper SHA。
- R固定，guard/fill tick独立；subtick只使C2 inactive不floorR；gap可亏超1R，tick取整也可使价格-R亏损超1R。
- fill不可达保留execution_unknown；持仓期间缺路径保留path_unknown且随后不伪恢复；已永久flat后缺日不擦掉已知realized，仍保留缺数据trace。
- 最后close仅估值，不强平；无费用gross price-R不是净收益或经济标签。权益、收益率、回撤、Sharpe、总滑点、交易次数、胜率均N/A。

## 验证、调研与置信

先写测试并实际观察模块缺失失败；实现前独立设计review指出subtick应inactive、flat后missing不应擦掉已知结果，先完善协议/测试，再实现。15新测试通过；root全线57测试通过。实际输出绑定fixture、trace、结果、runner、ledger与当前kernel SHA；独立全表复算另见Stage019，不以root自测代替独审。

本轮重读[Backtrader官方执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[VeighNa官方GitHub回测实现](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。调研判断：应显式规定bar撮合时点，本地C2生命周期与分钟顺序则由本地源码和反例验证；通用实现不能认证历史价格或填补缺分钟。

开始/结束新增按真实收益选参过拟合：否，固定合成机制例子没有真实收益扫描；既有历史选择偏差未消除。继续价值：是，但下一有效工作须进入完整源退出/真实覆盖与费用合同，不能仅凭合成通过声称训练样本可用或模型更好。

证据：`outputs/stage018_finite_path_probe/{README.md,fixtures.json,results.json,trace.csv,summary.json}`。独立review期间不改LINE/registry，root接纳后统一整合。

## 20:44 独审缺陷修复与重绑定

独立review发现P2：实现直接比较configured guard，漏掉实际Stage827 `max(configured_tick,1e-9)`。以E=1e-8、stop=9.5e-9、guard=filltick=1e-12构造输入，实际回归测试先失败（错误stopped，本应guard_inactive），核对源码后只修effective guard，不改R。新增第16项测试并通过，root全线58项测试通过。

20:44:36实际复跑到`outputs/stage018_finite_path_probe_guard_fixed/`，不覆盖首次输出。原12fixtures/46scenarios/185trace及全部状态数值一致，fixtures/results/trace三份逐字节SHA均相同。修正版summary锁新ledger SHA，supersession_receipt保留旧新绑定和原因；最终当前证据以guard_fixed目录与Stage019为准。复跑由缺陷修复触发，没有寻优或删除不利结果。
