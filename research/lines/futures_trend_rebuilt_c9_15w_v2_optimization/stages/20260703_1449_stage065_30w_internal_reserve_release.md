# Stage065 30w internal reserve release

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T14:49:34
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否，资金治理候选研究；不是 alpha 突破
- 是否触发A/B：是；资金/保证金治理层与候选正式部署相关，按 A vs C 口径记录

## 外部调研与判断

- GIPS/TWR 口径强调现金流必须与投资收益分离；本阶段 30w 从第一天作为总账户分母，避免把储备释放误算成收益。
- pysystemtrade capital correction 思路支持把资本变化作为 deployment/capital multiplier 问题，而不是信号 alpha。
- CPPI/动态资金配置资料支持 risky sleeve + safety sleeve 的结构性思考，但本策略不做 CPPI 乘数扫参，只测试固定 15w/15w 和固定释放节奏。
- 本次判断：候选释放规则以月末为主，日级只保留为容量上限参考；不按 2022/2023 亏损低点定制日期、金额或阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage065_stage013_30w_internal_reserve_release.py`
- 修改脚本：无正式入口修改
- 删除脚本：无
- 新增参数：`enable_stage065_month_end_release`；复用 Stage064 的 `stage064_initial_reserve_capital`、`stage064_topup_floor_equity` 等会计字段
- 修改参数：无正式交易参数；研究固定 `30w total = 15w trading + 15w reserve`
- 删除参数：无

## 回测参数

- 版本：Stage013 account-state pilot + 30w internal reserve release
- 对照臂：A0 `30w idle reserve no release`，C1 `30w daily floor release reference`，C2 `30w month-end floor release`
- 起点：`2021-07` 到 `2026-01` 逐半年
- 终点：`2026-07-02`
- 交易袖本金：`150,000`
- 储备袖本金：`150,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_candidate_ai_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`

## 结果（月末释放主候选）

- 逐起点详见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage065_stage013_30w_internal_reserve_release/rebuilt_c9_v2_stage065_stage013_30w_internal_reserve_release_summary_stage065_stage013_30w_internal_reserve_release_v1.csv`
- 总账户正收益：`8/10`
- 总账户最小/中位收益：`-9.4727% / 8.5494%`
- 总账户最差最大回撤：`-30.7006%`
- 最大水下天数：`527`
- 总滑点：`138900.0000`
- 总交易次数：`1867`
- 胜率：本阶段不新增逐笔胜率口径，避免把资金转移误读为交易胜负。
- 会计校验：`10/10` 通过，最大残差 `0.00000000`

## 对照摘要

- A0 不释放：最小/中位总账户收益 `-9.9295%/5.8853%`，最差回撤 `-30.7006%`。
- C1 日级释放：最小/中位总账户收益 `-10.7960%/16.0384%`，最差回撤 `-30.7006%`。
- C2 月末释放：最小/中位总账户收益 `-9.4727%/8.5494%`，最差回撤 `-30.7006%`。

## 统计口径 Review

- 总账户权益 `total_account_equity = broker_equity_with_cashflow + reserve_remaining`。
- 总账户收益分母固定 `300,000`，不允许用 `150,000` 作为含储备收益分母。
- 储备释放是内部资金搬运，必须满足 `total_account_equity - 300000 = cumulative net_pnl`。
- 水下天数按 `total_account_equity < 300000`，不是按 broker sleeve 是否低于 `150000`。

## 结论

- 决策：`stage065_month_end_release_keep_research_only`
- 原因：30w 总账户口径更清晰；月末释放是低自由度规则，水下天数优于不释放和日级释放，但收益中位数低于日级释放、2023-01 起点仍未回到 30w、最差回撤未改善，因此暂不直接晋级，先保留为资金治理候选。

## 后续规划和 TODO

- 若继续，应优先做 month-end vs daily 的新增手数/品种/月度归因，看释放是否只是放大坏交易。
- 不继续 sweep 储备比例、释放阈值或具体日期；这些会把资金治理变成针对历史弱窗口的过拟合。

## 过拟合反思

- 运行前：否。金额来自用户实际资金结构 15w/15w，释放节奏只测试结构性日级/月末规则，没有按亏损月份、产品或阈值反推。
- 运行后：基本否。本阶段没有 sweep 储备比例、释放阈值或具体日期；若继续为了 2022/2023 曲线去调释放日或金额，就会变成过拟合。

## 继续价值反思

- 运行前：有。它把账户分母、交易袖容量和储备释放拆开，可直接回答 30w 账户下水下期是否仍长。
- 运行后：有，但只作为资金治理继续。若要晋级，需要先确认新增手数不是集中放大坏交易，并在 shadow 资金层观察。
