# Stage029 Stage853 Stage852后分钟K缺口根因审计

## 基本信息

- 改动时间：2026-06-15 00:22 CST。
- 所属研究线：`futures_trend_stage819_intraday_rules`。
- 阶段性质：只读数据缺口审计。
- 是否重要突破：否。
- 是否触发 A/B：否。本阶段没有新策略候选。
- 是否修改正式版：否。
- 是否下载/补写分钟数据：否。本阶段只审计现有两个分钟源。
- 是否连接 CTP/SimNow：否。
- 是否调用下单：否。
- 决策标签：`stage853_minute_gap_mostly_true_missing_contract_or_date_no_rule`。

## 外部/GitHub调研

- 沿用 Stage028 调研判断：CME/CFTC 的止损资料支持“日内规则必须逐根分钟K可执行、且要考虑滑点”的要求；vn.py/VeighNa 提供实现框架背景。
- 本阶段没有引入外部策略或新规则；只做本地数据源存在性审计。
- 调研判断：继续方向不是找新阈值，而是先把真实合约分钟K补到可审计水平。

参考链接：

- https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
- https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
- https://github.com/vnpy/vnpy

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage853_stage852_minute_gap_audit.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_gap_requests_stage853_stage852_minute_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_gap_detail_stage853_stage852_minute_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_root_cause_summary_stage853_stage852_minute_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_fetch_plan_by_symbol_stage853_stage852_minute_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_summary_stage853_stage852_minute_gap_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_report_stage853_stage852_minute_gap_audit_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage853_stage852_minute_gap_audit_decision_stage853_stage852_minute_gap_audit_v1.json`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 回测结果：无新增回测；只读取 Stage825/849/852 输出和两个既有分钟源。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 输入与方法

- 缺口请求来源：
  - Stage825 entry-day missing lots：`114` 个。
  - Stage849 pressure key-date missing rows：`12` 个。
  - 去重后 gap requests：`126` 个。
- 被审计分钟源：
  - `qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv`
  - `qmt_roll_stage498_actual_trade_fill_key_readiness_completed_minute_bars_stage498_actual_trade_fill_key_readiness_v1.csv`
- 方法：
  - 只为缺口涉及的 `vt_symbol` 和 `product` 建 minute source index。
  - 对每个 `vt_symbol + required_date` 检查 exact contract/date 是否存在。
  - 若 exact contract/date 不存在，再检查同 product/date 是否存在其他合约分钟K。
  - 生成按 symbol 的补数优先级，按缺口绝对 PnL 影响排序。

## 新增结果

- gap requests：`126`
- exact contract/date 已在源内可用：`0`
- exact contract/date 不可用，需要补数：`126`
- 涉及待补 exact symbols：`80`
- 需要补数的缺口绝对 PnL 影响：`15,812,315`
- 需要补数的 big-winner requests：`8`
- 同产品当天有其他合约但 exact contract 缺失：`1`

### 根因汇总

- `exact_contract_missing_all_sources`：`79` 个请求，`52` 个 distinct symbols，priority_abs_pnl `2,974,840`，big_winner `3`。
- `exact_contract_missing_required_date`：`46` 个请求，`27` 个 distinct symbols，priority_abs_pnl `12,811,975`，big_winner `5`。
- `exact_contract_missing_required_date_but_product_date_exists`：`1` 个请求，priority_abs_pnl `25,500`。

### 补数优先级靠前

- `ru2501.SHFE`：`2024-09-12`，priority_abs_pnl `2,097,600`
- `fu2209.SHFE`：`2022-04-18 -> 2022-05-31`，`6` 个缺失日期，priority_abs_pnl `1,895,420`
- `fu2205.SHFE`：`2022-03-25 -> 2022-04-01`，`3` 个缺失日期，priority_abs_pnl `1,773,040`
- `hc2210.SHFE`：`2022-07-07`，priority_abs_pnl `1,430,310`，big_winner `1`
- `rb2210.SHFE`：`2022-07-07`，priority_abs_pnl `1,174,250`，big_winner `1`
- `FG601.CZCE`：`2025-11-05`，priority_abs_pnl `950,000`，big_winner `1`
- `AP210.CZCE`：`2022-04-06`，priority_abs_pnl `861,560`
- `ru2605.SHFE`：`2026-01-27 -> 2026-02-25`，`3` 个缺失日期，priority_abs_pnl `750,300`，big_winner `1`
- `jm2209.DCE`：`2022-05-25 -> 2022-07-06`，`2` 个缺失日期，priority_abs_pnl `712,230`

## 判断

- 这不是 Stage825 的时区/过滤逻辑漏掉了现成数据：`exact_contract_date_available_requests=0`。
- 大部分缺口是真实合约分钟源缺失，或者该合约在现有源内有其他日期但缺目标日期。
- 同产品其他合约不能替代 exact contract，因为本线分析的是真实成交合约的分钟路径。
- 因此下一步必须先补 exact contract/date 分钟K，再重跑 Stage825/849 图谱；不能直接写规则。

## 后续规划和 TODO

- TODO 1：按 `fetch_plan_by_symbol` 补 exact contract/date 分钟K，优先 `ru2501`、`fu2209`、`fu2205`、`hc2210`、`rb2210`、`FG601`、`AP210`、`ru2605`、`jm2209`。
- TODO 2：补数后重跑 Stage825 的 entry-day features/atlas，确认 `227/341` 覆盖率是否明显提升。
- TODO 3：补数后重跑 Stage849 的 pressure episode atlas，重点补 `FG_short` 和 `fu_long`。
- TODO 4：补数前禁止继续写 `PDEG-v0`、产品方向阈值、R 倍数、OR 或重试次数规则。

## 反思

- 运行前过拟合判断：否。本阶段只做数据存在性审计，不引入交易规则。
- 运行后过拟合判断：否。结果明确显示缺口是真数据问题，继续写规则会把缺数据误当成策略线索。
- 运行前继续价值判断：有价值。Stage852 已证明缺口影响大，必须定位缺口类型。
- 运行后继续价值判断：有价值但受数据约束。若能补数，下一步继续图谱；若不能补数，应暂停当前规则分支。
