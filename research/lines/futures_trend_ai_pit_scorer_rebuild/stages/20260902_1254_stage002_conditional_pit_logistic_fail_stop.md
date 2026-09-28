# Stage002 条件PIT逻辑回归基线失败收口

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 完成时间：2026-09-02 12:54 CST
- 决策：`stage002_conditional_pit_logistic_fail_stop_no_xgboost`
- 是否重要突破：否；实现层标签泄漏被技术门拦截
- 策略回测/CTP/订单：`0/0/0`

## 二元结论

- 本阶段**无效**，不得用其AUC、Rank IC、Top10代理或模型参数支持任何XGBoost/收益结论。
- 失败原因不是逻辑回归效果差，而是清洗阶段新增的`pit_future_rank_centered_60d`、`pit_future_rank_pct_60d`、`pit_target_future_top_half_60d`都以`_60d`结尾，被旧后缀特征发现规则误纳入模型。
- 冻结门要求108项，实际发现111项；`feature_count_exact=false`，决策正确fail closed。

## 无效运行证据

- 8个fold双跑，共16次模型训练；预测、Scaler、系数重复差均0。
- 数据边界本身通过：PIT违规0、未上市OOS行0、非完整标签OOS行0，47个OOS月、797行。
- 泄漏后出现AUC=`1.0`、月均Rank IC=`0.981237`、中位Rank IC=`0.987070`；这些异常高值是标签进入特征的反证，不能称为模型提升。
- 12项技术门仅特征数门失败，其他门通过；单门失败即全阶段失败。

## 产物身份

- `stage002_summary.json` SHA256=`2be847d9b0df073d5492656d2a134ac8a03e3828f7f0478d262bc901151b3411`
- `artifact_manifest.json` SHA256=`20ccebe644f955015326faefa1fa572fcefa8bdded039a2ad983d29e8aa50589`
- 其余CSV仅作失败法证，不得作为后续模型输入。

## 版本变更与回测记录

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增/修改/删除回测结果：均无；策略回测次数0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。
- `back_log.md`未追加，因为没有策略回测。

## 运行后反思

- 是否过拟合：若接受本结果，**是**，且属于直接标签泄漏；技术门使其没有进入下一阶段。
- 是否值得继续：当前Stage002结果**否**；只修特征发现合同后重跑同一冻结LR有价值，因为修复不看任何有效模型效果，也不改变样本、fold、模型参数或效果门。

