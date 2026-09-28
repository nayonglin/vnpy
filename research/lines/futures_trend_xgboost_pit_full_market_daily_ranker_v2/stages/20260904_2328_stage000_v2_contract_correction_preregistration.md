# Stage000 PIT全市场日级排序V2无标签合同纠正预注册

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker_v2`
- 记录时间：2026-09-04 23:28 CST
- 阶段性质：只纠正V1无标签缺失计数；禁止标签值、训练、预测和回测。
- 用户授权：研究操作默认授权；生产、CTP和订单硬门不变。

## 外部调研与判断

- XGBoost官方Learning to Rank仍要求按qid组织排序样本，并推荐`rank:ndcg`与组级评估；本线不改变此前日级qid判断。
- 判断：V1失败不是LTR机制证伪，而是20日失败集合并不包含于60日失败集合，导致预注册把单窗420误当并集。这个错误可在零标签条件下确定修复，不构成按收益救参。

## 冻结上游

- V1 artifact manifest：`0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a`。
- V1 summary：`926414442f4e1d6210cf41aeeb2ac480378823b5a705cc877a125380bbec0a11`。
- raw/model：`d59f3f66d0f894578fcf6527eb983cde8c3d123da641b8d0b49ddb01c2b4e509` / `1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac`。
- label/formal/fold：`426c40e5f0bc1a819e291abcc66c7f35eae6b9c5015634ddf8c42878c6afbc42` / `ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2` / `3c9514e7fe10b36a775cd8c9bfd16641d493cc8a64209319780326ba0f9fbb32`。
- V1 manifest内9项源输入继续逐项复验SHA、size和mtime；V1目录不得修改。

## 冻结修正

- volume 20日覆盖失败：273；60日失败：420；20-only：40；60-only：187；both：233；并集：460。
- open-interest 20日覆盖失败：21；60日失败：80；20-only：0；60-only：59；both：21；并集：80。
- `volume_ratio_missing`唯一正确冻结值改为460；`open_interest_ratio_missing=80`不变。
- 公式不变：20和60日正值覆盖各自至少90%，任一窗失败即ratio缺失，模型rank设0.5并置missing flag。
- 不允许删去40个20-only行，不允许补值、缩窗、降低90%或改变rank中性值。

## 其余冻结门

- 基础qid/行/宽度/日期：`1067/57528/49-53-61/2022-01-28..2026-06-30`。
- raw/model：17/19项；意外非有限值0、来源越界0、未来特征行0、missing flag错配0；连续特征非零横截面qid至少1000。
- 标签计划：`1046/52484/30-50-60`，拒绝5044，禁止任何close/return/target/relevance/PnL/score列和值。
- 正式评分：48个月、48个formal rank10、1771个挑战者、每月最少34。
- fold：37折、36 effect、1 inference、训练qid最小/最大261/1045、首末折`2023-03-31/2026-06-30`。
- future close、future return、label value、fit、predict、backtest、CTP、订单、生产写入和sealed holdout全部为0。

## Stage001决策

- 通过：`stage001_daily_ranker_v2_contract_pass_allow_stage002_preregistration_only`。
- 失败：`stage001_daily_ranker_v2_contract_fail_close_no_labels`。
- 任一门失败即闭线，不修改上游或再次纠正计数。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。

## 过拟合反思

- 运行前判断：否；V1没有模型效果，修正来自无标签集合并集。

## 继续价值反思

- 运行前判断：有，限一次Stage001 receipt；通过也不自动授权训练。
