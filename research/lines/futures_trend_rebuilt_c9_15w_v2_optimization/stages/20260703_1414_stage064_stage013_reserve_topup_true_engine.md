# Stage064 Stage013 reserve-topup true-engine

> 作废说明：本文件是 14:14 首轮记录，当时把 `engine_broker_identity_max_abs` 这种引擎内部时点诊断误纳入硬会计审计，导致 `0/30` 失败。硬会计恒等式本身已在 14:25 复跑中通过；正式引用请使用 `20260703_1425_stage064_stage013_reserve_topup_true_engine.md`。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T14:14:52
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否，资金部署层候选研究；不是 alpha 突破
- 是否触发A/B：是；资金/保证金治理层和候选正式版可能相关，因此按 A vs C 思路记录

## 外部调研与判断

- Capital correction / pysystemtrade 类资料支持把实际账户资本变化作为资金部署问题。
- TWR/MWR 资料提醒外部入金必须从策略收益里剥离，否则会把补钱误算成收益。
- 本次判断：储备金只允许影响 broker sizing equity 和保证金容量，不允许计入策略 alpha；不做按 2022/2023 低点定制的充值日期或金额。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage064_stage013_reserve_topup_true_engine.py`
- 修改脚本：无正式入口修改
- 删除脚本：无
- 新增参数：`stage064_initial_reserve_capital`、`stage064_topup_floor_equity`、`stage064_base_trading_capital`、`stage064_topup_min_amount`
- 修改参数：无正式交易参数
- 删除参数：无

## 回测参数

- 版本：Stage013 account-state pilot + reserve top-up true-engine sizing equity
- 储备金档位：`50,000`、`100,000`、`150,000`；主口径为 `100,000`
- 起点：`2021-07` 到 `2026-01` 逐半年
- 终点：`2026-07-02`
- 交易袖本金：`150,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_candidate_ai_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`

## 结果（100k 主口径）

- 期末权益/总收益：逐起点详见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage064_stage013_reserve_topup_true_engine/rebuilt_c9_v2_stage064_stage013_reserve_topup_true_engine_summary_stage064_stage013_reserve_topup_true_engine_v1.csv`
- 策略自身正收益：`9/10`
- 策略自身最小/中位收益：`-21.5920% / 32.0769%`
- 策略自身最大回撤最差值：`-46.6622%`
- 总账户最小收益：`-12.9552%`
- 总账户最大回撤最差值：`-34.6516%`
- 总滑点：`168280.0000`
- 总交易次数：`1867`
- 胜率：本阶段沿用日线/成交汇总，不新增逐笔胜率口径，避免把资金转账当交易胜负。
- 会计校验：`0/30` 通过，最大残差 `72665.00000000`

## 统计口径 Review

- 策略收益只看 `strategy_equity_ex_cashflow`，对应 `150000 + cumulative net_pnl`。
- 储备金转入只增加 `broker_equity_with_cashflow`，用于手数/保证金容量，不写入 `net_pnl`。
- 总账户收益用 `150000 + reserve_capital` 做分母；如果用 150000 分母算含入金权益，会虚增收益，禁止作为结论。
- `total_account_equity - (150000 + reserve_capital)` 必须等于累计 `net_pnl`；本阶段以此做强校验。

## 结论

- 决策：`stage064_reserve_topup_keep_research_only`
- 原因：资金层确实降低总账户回撤/水下压力，但它不是 alpha；是否晋级要看策略自身收益和新增手数是否稳定，且必须先接受总资金分母被扩大后的收益稀释。当前只建议保留为资金治理研究线，不直接替换正式策略。

## 后续规划和 TODO

- 如果保留，下一步只做 forward/shadow 资金层演练，不把储备金本身写入 alpha 或 AI 特征。
- 如果继续，优先检查新增手数集中在哪些月份/品种，以及是否只是放大 2022/2023 亏损。

## 过拟合反思

- 运行前：否。储备金档位和补入规则是固定、低自由度、跨起点评估；没有按 2022/2023 低点定制日期或金额。
- 运行后：基本否。若后续用某个坏起点反推专属储备金额、充值日期或 sweep 规则，就会转为过拟合；本阶段没有这样做。

## 继续价值反思

- 运行前：有。用户实际资金不止 15 万，资金治理层可以回答是否因 15 万袖口亏损后容量下降导致回本慢。
- 运行后：有，但只作为资金治理继续；是否上线要和 alpha 晋级分开，后续看 shadow 资金层和新增手数归因。
