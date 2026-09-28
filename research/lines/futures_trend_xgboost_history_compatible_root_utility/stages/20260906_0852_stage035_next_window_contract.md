# Stage035 下一时段分钟窗口库存

- 2026-09-06 08:52 CST；line_id：futures_trend_xgboost_history_compatible_root_utility。
- 前置Stage034成本对账通过，1002个独立成本持仓日、155成熟根，2021-09起有60成熟根。本阶段不是模型、不是回测、不是退出标签，仅查询冻结分钟缓存对下一窗口的支持程度。
- [LEAN成交模型](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/equity-model)明确防范陈旧数据/订单同时间戳前视成交；[GitHub示例](https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/ForwardDataOnlyFillModelAlgorithm.py)参考其订单后数据边界。中国期货时段不照搬美股时段。
- 使用原A交易日历的下一个回放日、冻结Stage501夜盘产品集合。假设完成日线后观察可用的下界为该日15:00，真实上线到达时间尚未证明，不能据此宣称执行已合格。夜盘产品先查询观察日21:00-21:05；该窗口没有记录才查下一A日09:00-09:05；其他产品只查日盘。
- 仅使用原A科学输入中full_minute_bars缓存，所有1002观察点保留，不按未来收益删行。读取实际合约/分钟时间/OHLC/volume，不使用未来收益、MFE/MAE或退出标签。
- 完全相同的重复分钟只去重，冲突分钟保留为失败；首分钟价格必须有限正数、OHLC自洽、时间严格晚于观察可用下界。首分钟成交量至少覆盖观察时实际仓位手数才记为proxy_supported；不跳过零量首分钟去挑较好的后续价格，不把5分钟合计量当首笔开盘容量。
- proxy_supported仍是历史数据必要条件，不证明盘口、排队、限价、滑点、实时可成交或原引擎使用了该缓存价格。原Stage502还会查旧seed/raw价格源，其价格来源与当前全分钟缓存需后续运行身份核验；此处不假冒原A成交价复刻。
- 不能用daily-next-open fallback、前日价格或其他合约补缺；有任何缺口就不进入当前全覆盖动作合同。记录所有窗口与原因，不改原A/Stage034/共享数据、不下载、不训练、不回测、不reviewer。
- 开始过拟合判断：本次否，只核验数据与时钟必要条件；继续价值：有，防止退出效用建立在不可用成交数据上。原收益提高且回撤降低目标不变。
