# PIT全市场日级XGBoost横截面排序线

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker`
- 研究对象：使用已冻结TqSdk全市场真实合约日线，在日级横截面上训练时间有序XGBRanker，并仅在正式月度评估日研究一个池外候选替换rank10的可能性。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；正式C9/15w、固定`fu.SHFE`、成本、保证金、整数手、相关性和最多持仓规则均不变。
- 上游数据资格：`futures_trend_xgboost_pit_full_market_source_rebuild` Stage002已通过，4,603合约、80品种、894,144条归一化日线、105,440条PIT主力映射，允许另立模型预注册。
- 当前状态：Stage001唯一无标签合同已执行并因volume ratio缺失计数`460 != 420`失败闭线；其余五个门通过，尚未读取未来收益、构造标签值、训练模型、运行策略回测或触碰生产。
- 核心假设：现有月度900行附近的XGBoost研究样本不足；将同一PIT源组织为大量日级query，并直接优化组内排序，可能比点式分类或月度残差更匹配选品问题。
- 证据边界：2021-01-18至2026-06-30全部属于已观察development；任何历史通过都不能称sealed holdout或线上收益保证。
- 隔离边界：只写本研究线与`research/registry.md`；禁止修改源重建产物、旧失败线、共享映射、数据库、生产release、CTP或订单。

## 当前阶段

- Stage000：`stages/20260904_2247_stage000_daily_ranker_design.md`。
- Stage000A：`stages/20260904_2255_stage000a_daily_query_feasibility.md`；1,067个query/57,528基础行，1,046个同合约计划query/52,484行，允许Stage001预注册。
- Stage001：`stages/20260904_2255_stage001_daily_ranker_contract_preregistration.md`；只允许构造无标签17项原始/19项模型特征面板、标签计划与37折purged walk-forward计划。
- Stage001结果：`stages/20260904_2320_stage001_daily_ranker_contract_fail_close.md`；实际volume 20/60日覆盖失败并集为460，Stage000A误把60日单窗失败420当并集，冻结feature gate失败。
- Stage002：禁止进入；本线禁止重跑、改硬门、删行、补值、缩窗或训练。

## 过拟合反思

- 当前判断：否。
- 原因：Stage001只暴露无标签覆盖集合的计数错误，没有接触收益、预测或回测；但在本线执行后修改420硬门仍属于违反预注册，故不允许救援。

## 继续价值反思

- 当前判断：本线无。
- 原因：唯一Stage001已失败闭线。本结构只有在新研究线中事前冻结正确的20/60失败并集460、完整复验无标签合同后才有继续价值；本线不得进入标签或模型阶段。
