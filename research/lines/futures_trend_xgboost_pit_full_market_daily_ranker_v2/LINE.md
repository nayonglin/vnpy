# PIT全市场日级XGBoost横截面排序V2线

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker_v2`
- 研究对象：在完全不读取标签和效果的前提下，纠正V1对`volume_ratio_20_60`缺失集合的预注册计数，再决定是否允许日级XGBRanker训练预注册。
- 上游：关闭的`futures_trend_xgboost_pit_full_market_daily_ranker` Stage001 final，只读复用其manifest-backed无标签特征、标签日期计划、正式评分身份与fold计划。
- 唯一合同差异：volume 20日或60日正值覆盖任一不足90%即ratio缺失，其并集冻结为460；V1错误值420是60日单窗失败数。
- 不变项：1,067/57,528基础面板、1,046/52,484标签计划、17项原始/19项模型特征、20日持有期、252最低成熟qid、37折、正式身份和全部零副作用门。
- 当前状态：Stage002唯一development OOS执行在`2024-01-31`因最高分挑战者`sc.INE`缺少预注册标签计划而技术失败并闭线；独立review为审计`PASS`、研究推进`BLOCK`，不得回退次高者、重跑或给出收益/回撤结论。
- 隔离边界：只写本线与`research/registry.md`；V1 final、源重建、正式版本、CTP和订单均只读或禁止。

## 当前阶段

- Stage000：`stages/20260904_2328_stage000_v2_contract_correction_preregistration.md`。
- Stage001：`stages/20260904_2328_stage001_v2_contract_requalification_pass.md`；V1上游、纠正合同、volume并集460和零副作用全门通过。
- Stage002预注册：`stages/20260904_2340_stage002_daily_ranker_development_oos_preregistration.md`；固定52,484标签、19特征、64棵深度2单Ranker、37折/74 fits和一席selector。
- Stage002结果：`stages/20260905_0015_stage002_daily_ranker_technical_fail_close.md`；第10个测试月在pre-effect seal后触发`effect_label_missing:2024-01-31`，最终manifest离线复验通过，但完整效果门未打开。
- Stage002事后review：`reviews/20260905_stage002_postrun_independent_review.md`；P0/P1/P2/P3=`0/0/1/1`，P2限定final report的错误计数，P3限定partial效果文件不可作完整结论。

## 过拟合反思

- 当前判断：否。
- 原因：唯一执行严格使用事前冻结模型与selector，并在首个合同违规处停止；没有按已见的9个月部分效果调参或改变候选资格。现在若补标签、回退次高者、删月或重跑则属于过拟合救援，明确禁止。

## 继续价值反思

- 当前判断：本线无继续价值，关闭；总目标仍有价值。
- 原因：标签资格缺口使完整36月效果合同不可完成，本线不能给出alpha、收益或回撤结论。后续只能以独立的新标签覆盖或新经济信息机制另立预注册线，不能修改本线规则救援。
