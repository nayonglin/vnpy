# Stage001 日级排序V2无标签合同复资格通过

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker_v2`
- 记录时间：2026-09-04 23:28 CST
- 决策：`stage001_daily_ranker_v2_contract_pass_allow_stage002_preregistration_only`。
- 是否重要突破：否；仅修复无标签合同记账。
- 执行性质：唯一Stage001 V2 receipt；未读取标签、未训练、未预测、未回测。

## 结果

- V1 bundle复验：10项产物、9项源输入，SHA/size/mtime全部有效。
- V2 receipt：4项产物、5项直接输入，manifest离线复验`verified=true`、错误0。
- V2五门：upstream manifest、输入稳定、纠正合同、流动性并集、零副作用全部通过。
- volume：20日失败273、60日失败420、only20 40、only60 187、both 233、并集460。
- open-interest：20日失败21、60日失败80、only20 0、only60 59、both 21、并集80。
- 纠正后V1六门全部通过：基础`1067/57528`、标签计划`1046/52484`、17/19特征、48正式月、37折和零副作用均命中。
- 回归：V2/V1/source共`45 passed`；V2 runner编译通过。

## 变更记录

- 新增参数：`volume_ratio_missing=460`，来自不变20/60窗口规则的失败集合并集。
- 修改参数：仅替代V1错误审计预期420；模型与策略参数无修改。
- 删除参数：无。
- 新增/修改/删除回测结果：无。

## 零副作用

- future close、future return、label value、fit、predict、backtest、CTP、订单和生产写入全部为0。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。

## 过拟合反思

- 运行后判断：否；修正完全来自无标签集合运算，V1/V2均未产生模型效果。

## 继续价值反思

- 运行后判断：有；允许另发Stage002训练预注册。
- 限制：不得把Stage001通过表述为alpha有效，也不得在看到Stage002结果后修改特征、持有期、qid、树参数或替换规则救援。
