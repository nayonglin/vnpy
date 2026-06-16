# Stage078 C9缺口补齐与核心验证链复跑

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 21:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据补齐 + 冻结口径复验；不新增交易规则。
- 是否重要突破：是。Stage898 C9 开仓 entry-day 分钟K P0 缺口从失败清零为 `0`。
- 是否触发A/B：未触发正式实盘 A/B；按 candidate promotion 验证纪律重跑 Stage863/896/897/898/899。

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader / 历史数据下载文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html
  - TqSdk GitHub：https://github.com/shinnytech/tqsdk-python
  - vn.py portfolio/backtesting 资料：https://github.com/vnpy/vnpy/blob/master/README_ENG.md
- 我的判断：
  - TqSdk 的批量下载能力适合作为历史分钟数据来源；本仓库此前 `DataDownloader` 受权限阻断，因此本次优先扫描本地分钟缓存，再用 `TqBacktest + get_kline_serial(60)` 补少数缺口。
  - vn.py 组合回测适合保留 C9 的路径依赖、仓位、资金与保证金状态；不能用事后资金曲线切片替代独立窗口回放。
  - 滚动/多起点验证是鲁棒性审计，不是 alpha 来源；C9 是否能晋升，核心仍是数据完整、风险尾、资金占用和执行语义。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage900_stage898_c9_gap_backfill.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage861_stage860_full_visual_atlas.py`
    - 新增 Stage900 C9 缺口分钟补丁合并。
    - 修正 Stage900 补丁不再被 Stage861 基准 lot 样本范围过滤，避免 C9-only 开仓日期被漏合并。
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage899_c9_monthly_time_to_positive.py`
    - 并行 worker 使用 pid 专属 static universe/eligibility CSV 副本，避免多进程同时重写同一路径导致 `EmptyDataError`。
    - 修正报告文案：Stage898 缺口已补齐，后续问题转向风险尾和近期起点归因。
- 删除脚本：无。
- 新增参数：无策略参数；新增工程运行环境 `STAGE899_WORKERS=4` 与 worker static 副本目录。
- 修改参数：无策略参数；仅修改分钟数据源合并和 Stage899 并行初始化方式。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - C9 全周期：`2018-01-02 -> 2026-05-29`
  - Stage896：`2020-01` 起半年步进，完整 3 年窗口 `7` 个，另有 terminal partial `1` 个。
  - Stage897：`2018-01` 起每年 `1月/6月`，完整 1 年窗口 `15` 个，partial `2` 个。
  - Stage899：`2018-01 -> 2026-05` 每月起点到 `2026-05-29`，窗口 `101` 个。
- 账户规模：
  - C9 / Stage819 候选：`300,000`
  - 当前正式 Stage372：`200,000`
- 成本口径：沿用各 Stage 既有 vn.py 组合回测成本、手续费、滑点设置；本阶段不改成本模型。
- 样本过滤：无按品种、方向、年份、窗口好坏的事后筛选。
- 策略/归因口径：
  - C9 固定为 `stage847_stage819_c4_05r_stop_retry_once`。
  - C10 仍为 `stage863_stage819_c4_c9_budget_lock`，仅作为预算锁反证对照。
  - 当前正式基准固定为 `official_live_stage372_20w_recovery_sleeve`。

## 结果

- Stage900 补数：
  - 输入 Stage898 gap rows `16`，去重后 symbol-date `8`。
  - 覆盖 `8/8`，剩余 `0`。
  - 本地缓存覆盖 `6` 个 symbol-date，TqBacktest 补 `2` 个 symbol-date。
  - 新增补丁分钟K `2,999` 行，unique symbols `7`。
- Stage861 重建：
  - full minute bars `1,482,591`，symbols `220`。
  - Stage900 C9 gap patch `2,999` 行。
  - Stage819 基准 entry-day 覆盖 `341/341=100%`，pressure key dates `19/19=100%`。
  - 额外核对 8 个 C9 缺口日全部进入统一分钟源。
- Stage863 全周期：
  - C4：期末权益 `46,015,805.00`，总收益 `15,238.6017%`，最大回撤 `-47.1915%`，Sharpe `1.5996`，总滑点 `3,023,410`，总交易次数 `678`，胜率 `53.0630%`，max broker10 `111.4255%`。
  - C9：期末权益 `51,297,786.20`，总收益 `16,999.2621%`，最大回撤 `-41.6664%`，Sharpe `1.6404`，总滑点 `3,646,200`，总交易次数 `790`，胜率 `53.5299%`，max broker10 `115.0507%`。
  - C10：与 C9 完全一致；budget lock events `250`，created/released `125/125`，blocked `0`，reduced volume `0`，不晋级。
- Stage896 三年滚动对照：
  - C9 完整 3 年窗口 `7/7` 正收益；收益中位 `562.2128%`，最小收益 `121.3728%`，最大收益 `2846.0419%`。
  - C9 最大回撤中位 `-42.0763%`，最差 `-56.1208%`；DD30/DD40/DD50 失败 `6/4/1`；peak broker10 `106.2112%`，broker100 失败 `2`。
  - Stage372 完整 3 年窗口 `7/7` 正收益；收益中位 `259.6375%`，最差回撤 `-39.1172%`，DD40/DD50/broker100 失败均 `0`。
  - pairwise：C9 收益胜 `7/7`，Sharpe 胜 `6/7`，回撤胜 `1/7`，broker10 胜 `0/7`；决策仍为 `stage896_c9_right_tail_with_risk_tail_not_official_replacement`，`c9_hard_fail=true`。
- Stage897 一年冷启动：
  - 完整 1 年窗口 `15` 个，正收益 `12/15=80.00%`。
  - 收益中位 `60.8912%`，p10 `-4.8311%`，最小 `-8.7233%`，最大 `636.6463%`。
  - 最差回撤 `-35.0696%`，DD30/DD40/DD50 失败 `3/0/0`，peak broker10 `95.5352%`，broker100 失败 `0`。
  - 负收益窗口仍为 `2018-01`、`2018-06`、`2022-01`；决策仍为 `stage897_c9_rolling1y_has_negative_windows_not_annual_all_positive`。
- Stage898 完整性审计：
  - `metric_check_count=225`
  - `metric_fail_count=0`
  - `p0_fail_count=0`
  - `minute_entry_missing_lots=0`
  - `minute_duplicate_rows=0`
  - `c9_open_missing_full_minute_entry_day_count=0`
  - 决策：`pass_with_execution_semantics_watch`
  - P1 watch 仍有 `3` 项，核心是执行语义/跨时段重试，不是 entry-day 数据缺口。
- Stage899 月度起点转正：
  - 全部月度起点 `101` 个，曾转正 `99` 个，未转正 `2` 个，empty result `1` 个。
  - 全部月度起点转正率 `98.0198%`；当前期末正收益窗口 `92/101=91.0891%`。
  - 成熟 1 年以上起点 `89/89` 曾转正且当前全部正收益；最小期末收益 `72.5755%`。
  - 最长转正等待为 `2018-03` 起点：`158` 日历日 / `108` 交易日，约 `5.191` 个月。
  - 全月度最差持有期回撤 `-58.0872%`。
  - 未转正窗口：`2026-04 -> 2026-05-29`，收益 `-6.86%`、回撤 `-7.00%`；`2026-05 -> 2026-05-29`，收益 `0.00%`、回撤 `0.00%`。

## 输出文件

- Stage900 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_stage898_c9_gap_backfill_report_stage900_stage898_c9_gap_backfill_v1.md`
- Stage900 minute bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_stage898_c9_gap_backfill_minute_bars_stage900_stage898_c9_gap_backfill_v1.csv`
- Stage861 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_summary_stage861_stage860_full_visual_atlas_v1.csv`
- Stage863 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage863_stage847_c10_budget_lock_engine_summary_stage863_stage847_c10_budget_lock_engine_v1.csv`
- Stage896 aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_aggregate_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`
- Stage897 aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_aggregate_stage897_c9_janjun_rolling1y_v1.csv`
- Stage898 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_summary_stage898_c9_backtest_integrity_audit_v1.csv`
- Stage899 aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_aggregate_stage899_c9_monthly_time_to_positive_v1.csv`
- Stage899 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_decision_stage899_c9_monthly_time_to_positive_v1.json`

## 结论

- 本阶段结论：
  - 用户要求的 1 和 2 已完成：Stage898 指出的 C9 entry-day 分钟K缺口已全部补齐，并且 Stage863/896/897/898/899 核心验证链已在新分钟源上重跑。
  - C9 的数据硬门槛显著改善：Stage898 P0 失败清零，不能再沿用旧的“8 笔 entry-day 缺口”否决理由。
  - 但 C9 仍不能直接晋升为当前正式默认版本：Stage896 明确显示 C9 收益/Sharpe 强，但风险尾弱于 Stage372，DD50 与 broker100 仍失败；Stage897 仍有 3 个完整 1 年负收益窗口；Stage899 仍显示部分近期起点未转正和全月度最差回撤 `-58.0872%`。
- 是否进入下一步：进入下一步只读风险尾/执行语义归因，不进入正式版替换。
- 下一步：
  - 归因 Stage896 的 `2020-07 -> 2023-06-30` 与 `2020-01 -> 2022-12-31` 风险尾，重点是 DD50、broker100、slippage 与 stop_retry 事件关系。
  - 单独解释 Stage899 `2026-04/2026-05` 未转正窗口和 `2018-03` 最长转正等待，不按月份写屏蔽规则。
  - 若要继续走正式化，必须先给出账户级保证金/风险尾处理方案，且不允许扫 R 倍数、重试次数、品种、方向、年份或起点月份救参。

## 过拟合反思

- 运行前判断：否。本阶段是补齐已知数据缺口并重跑冻结验证链，不新增策略规则、不扫参数。
- 运行后判断：本轮执行本身没有新增过拟合；但若用“缺口清零 + 高收益”直接晋升 C9，就是选择性忽略风险尾，属于过拟合式决策。
- 原因：Stage896/897/899 的失败点不是数据缺口，而是风险尾、资金占用、冷启动和近期体验问题；这些必须正面处理。

## 继续价值反思

- 运行前判断：有价值。C9 的晋升被数据缺口和核心验证链复验卡住，补洞是硬前置。
- 运行后判断：仍有价值，但价值范围收缩到风险尾归因和执行语义确认；不再是继续寻找小参数提升收益。
- 原因：Stage898 已经证明当前输出内部一致且 entry-day 数据覆盖完整；剩余矛盾集中在 C9 的高进攻性如何穿越 2022 类压力段，以及能否在不砍右尾的情况下降低 broker10/DD50。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage078 最新状态。
- 是否更新 `research/registry.md`：否，研究线归属未变。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
