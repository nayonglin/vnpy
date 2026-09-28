# 全市场PIT单槽逻辑回归与XGBoost融合线

- line_id：`futures_trend_xgboost_pit_full_market_one_slot_ensemble`
- 研究对象：当前线上逻辑回归 Top10 + 固定 `fu.SHFE` 的独立全市场池外单槽替换研究。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；正式 C9/15w、成本、保证金、整数手、相关性和最多4持仓规则均不变。
- 上游数据资格：`futures_trend_xgboost_pit_full_market_source_rebuild` Stage002 已通过原54个月覆盖门，决策 `stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。
- 当前状态：Stage001唯一冻结无标签特征资格审计失败并闭线；48个月和1,819个action行身份完整，但两行20日正成交量仅17/20，低于冻结的18/20。未读取未来标签、训练模型、运行策略回测或触碰生产。
- 核心假设：静态18品种内反复换特征已经被多条研究线反证；全市场池外候选相对线上rank10的趋势路径、流动性和期限结构差，可能包含一个可泛化的非线性单槽替换信号。
- 证据边界：`2022-01..2026-06` 全部属于已观察开发期，只能形成development OOS证据，不能称独立holdout；正式效果仍需未来新增月份。
- 隔离边界：只写本研究线；禁止修改共享映射、数据库、生产release、正式AI、CTP、订单或旧研究线。

## 冻结研究臂

- A：正式线上逻辑回归 Top10 + 固定 `fu.SHFE`，不改变任何席位。
- B：保留A前9名和固定fu；固定pairwise LogisticRegression仅在预测联合胜率严格大于0.5时，用一个池外候选替换rank10。
- C：保留A前9名和固定fu；将同折LogisticRegression与XGBoost概率固定50/50平均，仅在融合概率严格大于0.5时替换rank10。C是唯一未来晋级候选。
- B/C都不得在A-rank10或候选不满足同一PIT资格时行动；同月最多替换一个席位。

## 冻结阶段

- Stage000：`stages/20260904_1441_stage000_model_contract_design.md`。
- Stage001：`stages/20260904_1508_stage001_feature_qualification_fail_close.md`；决策`stage001_full_market_feature_contract_fail_close_no_labels`。
- Stage002：禁止实现或执行；Stage001前置合同已失败。
- Stage003：不适用。

## Stage001结论

- action-ready月份、action行、rank10锚点、池外候选分别为`48/1819/48/1771`，全部身份门通过。
- 收益与持仓窗口覆盖不足均为0；曲线资格`1819/1819`。
- `2022-06-30 ZC.CZCE`与`2023-10-31 wr.SHFE`的20日正成交量均为`17/20`，低于冻结要求`18/20`。
- 标签、fit/predict、回测、CTP、订单和生产写入均为0；正式线上A不变。
- 禁止降到85%、删两行/两品种/两月份、补值、缩窗或重跑救援。

## 过拟合反思

- 当前判断：Stage001本身没有效果过拟合；事后放宽完整性门会构成过拟合。
- 原因：本阶段未读标签或收益，只执行事前冻结数据门；已知仅差两行后再修改阈值或样本将直接利用失败位置。

## 继续价值反思

- 当前研究线：没有继续价值，关闭。
- XGBoost总方向：仍可研究，但必须换新的事前经济机制、独立数据源或未来未见月份，不能针对本次两条失败行修改合同。
