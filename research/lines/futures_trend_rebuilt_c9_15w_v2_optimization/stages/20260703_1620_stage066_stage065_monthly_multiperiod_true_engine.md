# Stage066 Stage065 monthly multiperiod true-engine

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T16:20:52
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否，资金治理扩样本审计；不是 alpha 突破
- 是否触发A/B：是；资金/保证金治理层与候选部署相关，按 A vs C 口径记录

## 外部调研与判断

- GIPS/TWR 口径要求现金流与策略收益分离；本阶段总账户分母固定 300,000。
- pysystemtrade capital correction 支持把资本变化作为资金治理，不把储备释放算作 alpha。
- 本次判断：只扩逐月独立起点，不改储备比例、释放阈值或日期。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage066_stage065_monthly_multiperiod_true_engine.py`
- 修改脚本：无正式入口修改
- 删除脚本：无
- 新增参数：无正式参数；研究脚本新增逐月起点集合
- 修改参数：无正式交易参数；固定 `30w total = 15w trading + 15w reserve`
- 删除参数：无

## 回测参数

- 起点：`2021-07` 到 `2026-01` 逐月，共 `55` 个起点/臂
- 终点：`2026-07-02`
- 对照臂：A0 不释放、C1 日级释放、C2 月末释放
- 交易袖本金：`150,000`；储备袖本金：`150,000`；总账户分母：`300,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_candidate_ai_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`

## 结果摘要

- A0 不释放：正收益 `37/55`，最小/中位收益 `-12.9506%/6.5077%`，最差回撤 `-31.5206%`，最长水下 `1070` 天。
- C1 日级释放：正收益 `46/55`，最小/中位收益 `-11.1293%/11.9460%`，最差回撤 `-31.9343%`，最长水下 `1057` 天。
- C2 月末释放：正收益 `43/55`，最小/中位收益 `-15.6456%/8.1810%`，最差回撤 `-31.5206%`，最长水下 `1020` 天。
- 月末释放总滑点 `854100.0000`，总交易次数 `9979`。
- 胜率：本阶段不新增逐笔胜率口径，避免把资金转移误读为交易胜负。
- 会计校验：`165/165` 通过，最大残差 `0.00000000`。

## 统计口径 Review

- 总账户权益 `total_account_equity = broker_equity_with_cashflow + reserve_remaining`。
- 总账户收益分母固定 `300,000`，储备释放只改变后续 sizing equity，不创造 PnL。
- 水下天数按 `total_account_equity < 300000`。

## 结论

- 决策：`stage066_monthly_multiperiod_keep_research_only`
- 原因：逐月独立起点显示月末释放能改善不释放的正收益数量、中位收益和最长水下天数，但最小收益比不释放更差，且正收益数量和收益中位数仍弱于日级释放；日级释放收益更强但最差回撤更深，二者都没有解决最差回撤，因此先不晋级。

## 后续规划和 TODO

- 先做日级 vs 月末释放新增手数归因，确认收益差来自哪些月份/品种/开仓。
- 不继续 sweep 储备比例、释放阈值或具体日期。

## 过拟合反思

- 运行前：否。只扩展逐月起点样本，固定 30w=15w交易袖+15w储备袖、固定日级/月末释放规则，不调金额、阈值或日期。
- 运行后：否。逐月结果没有触发任何参数救援；如果后续按 2022/2023 个别月份改释放日或金额，才会转为过拟合。

## 继续价值反思

- 运行前：有。逐半年样本不足以判断 2022/2023 启动月份的水下问题，必须扩成逐月独立起点。
- 运行后：有，但只作为资金治理继续；下一步应做新增手数/品种/月度归因，而不是继续 sweep 储备比例。
