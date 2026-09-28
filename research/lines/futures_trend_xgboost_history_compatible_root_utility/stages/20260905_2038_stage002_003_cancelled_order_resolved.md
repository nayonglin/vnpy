# Stage002/003 撤单事件语义闭合

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 记录时间：2026-09-05 20:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：A基准局部执行追踪及离线生命周期判定；不是策略候选，不是重要突破，不启动reviewer。

## 调研与判断

- 外部参考：[scikit-learn时序验证](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data)、[mlfinpy事件标签](https://github.com/baobach/mlfinpy/blob/main/mlfinpy/labeling/labeling.py)。采用严格结束时点，不用未来成交与否改当时决策。
- 现场源码和旁路追踪确认：历史候选的opened是计划快照，计划形成后仍可能被保证金逻辑撤销。不能据此推断券商有仓位，也不能自动填零标签。

## 新增与未改内容

- 新增：只读执行追踪工具、隔离启动测试、撤单生命周期判定器及6项测试。
- 模型/策略参数新增、修改、删除：均无。仅诊断终点2020-05-13，固定追踪CF009.CZCE。
- 原Stage001 failed和Stage002 bootstrap failed产物保留。启动失败发生在回放前；修复后Stage002B只运行A一次，无S或模型。

## 事实链

1. 2020-05-11 CF009.CZCE根事件36，逻辑目标从0变为多头6手。
2. 初次再平衡生成`BACKTESTING.25`，volume6、traded0、SUBMITTING。
3. 同日`_process_forced_margin_deleverage`把该品种逻辑层清空、目标归零，记录forced_margin_deleverage 6手。
4. 第二次再平衡撤销该订单；当日on_bars结束时CANCELLED、traded0、实际仓位0、目标0、逻辑层空、活动订单空。后两交易日保持无该根成交。
5. Stage901导出daily时把四个forced_margin_deleverage统计字段统一写0，所以daily统计为0不能反证本事件发生；本线不修生产代码，只以真实订单/执行trace为准。

## 局部A回放指标

- 区间：2020-01-02至2020-05-13；起始权益150,000。
- 期末权益：180,440。
- 总收益：20.2933333333%。
- 最大回撤：-6.7261415659%。
- Sharpe：2.4803706558。
- 总滑点：2,300；手续费0，继承冻结基准，不是完整实盘成本。
- 总交易次数：28条成交记录，不是28个完整往返。
- 胜率：非零损益日胜率63.3333333333%，不是逐笔胜率。
- 运行约48.91秒；7张可比表与冻结A对应前缀逐值一致；110条旁路trace。
- 本次新增S回放0、效用标签0、模型训练0、reviewer0。上述指标不代表新策略改善。
- 输入1501项，file contract `705c477f8b4976d851a2cbb17b399282e999af6df2522aaaee3cb1fcc2ccfcd8`。
- worker PID63166已退出；原始9表校验后无损gzip归档；本次私有runtime已清理。

## 生命周期结果与后续

- Stage003通过：276事件全保留，273 mature、1 mature_cancelled_unfilled、1 right_censored_open、1 right_censored_pending_entry；无未解决归属。
- 撤单事件终止于2020-05-11，root_trade_id/first_fill_date为空，不伪造成交。未来仍需实际S反事实，按终止日期算接受减跳过，不赋常数0。
- 该终止日短标签只衡量声明窗口内效用，不能捕获所有延后机会成本；后续必须看真实全路径C，不能加总单事件标签当组合收益。
- 不计撤销事件亦有2021-04-01前65条成熟成交事件，首个可训练月与目标改善空间不变。
- 下一步：冻结全部274个已终止事件标签计划、10特征双头模型及逐月前向规则，再运行最小批次；保持2条删失为空，禁止用未来成交补标签。
- 最终相关测试38项通过；正式目录git clean，HEAD仍`d492ee072aa5a9d71477235d79f17d2a5db59db3`。

## 反思

- 运行前/后是否过拟合：本次否，旁路追踪没有改变策略或按收益筛样本；整个历史多轮研究仍有选择偏差，不宣称未见样本外。
- 是否有价值继续：是，历史及时性和完整生命周期必要条件已闭合；尚无XGBoost收益证据，下一步只能作为开发验证。
- 不更新其他研究线、registry或根memory/back_log；仅更新本线LINE。
