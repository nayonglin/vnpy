# Stage169 SH shadow/broker 持仓差异归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-02 17:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘 shadow/broker 对账差异只读归因
- 是否重要突破：是，定位到 Stage901 回放使用的 AI eligibility 历史月度截面断档
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：未做外部网络调研。本次是本地实盘执行链路法证，证据来自 Stage901 shadow、Stage905 dry-run、Stage906 reconciliation、Stage931 execution ledger、Stage935/Stage182 月更摘要以及本线历史阶段记录。
- 我的判断：这不是新的 SH 交易信号，也不是实盘漏下 SH；当前差异来自今天重跑后的 shadow 输入历史断档，导致 2026-06-22 的候选回放退回使用 2026-02-27 AI 池。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage901 `analysis_start=2026-06-16`，`analysis_end=2026-07-02`
- 账户规模：`150,000`
- 成本口径：沿用官方 live shadow 口径
- 样本过滤：官方 live default `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 策略/归因口径：只读 shadow/broker 持仓差异归因；不连接 CTP，不调用订单 API

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage906 当前差异：`SH609.CZCE short shadow=5 broker=0`；`rb2610.SHFE short shadow=0 broker=11`。
  - Stage906 状态：`reconcile_divergent_fail_closed`，`account_state_alignment=divergent`，`order_api_called_count=0`。
  - Stage905 dry-run：`executor_no_intents`，intent `0`，send/cancel order `0`。
  - Stage901 当前 shadow 交易：2026-06-23 开 `SH609.CZCE short 5`、`lh2609.DCE short 1`；2026-06-25 平 `lh2609.DCE short 1`；没有当前 rb 理论交易。
  - Stage901 当前持仓：`SH609.CZCE short -5`。
  - 执行 ledger：无 `SH609`/`rb2610` 自动委托记录；只有 2026-06-24 `FG609.CZCE` 平/开/再平记录。
  - 当前 combined AI eligibility 2026 截面仅有 `2026-01-30`、`2026-02-27`、`2026-06-30`，缺 `2026-03-31`、`2026-04-30`、`2026-05-29`。
  - Stage901 2026-06-22 entry candidates 的 `ai_product_pool_signal_date=2026-02-27`；该池含 `SH.CZCE`、`lh.DCE`，不含 `rb.SHFE`，所以回放中 SH/lh 被允许、rb 被 `ai_product_pool_blocked`。
  - 历史阶段记录显示 2026-06-23/24/26 时 shadow/broker 曾为 `rb2610.SHFE short 11` 对齐；2026-06-29 记录显示当时 Stage935 expected/current 均为 `2026-05-29`，池子含 `rb.SHFE`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_report_20260702_stage906_official_live_reconciliation_worker_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_summary_20260702_stage906_official_live_reconciliation_worker_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_phase_d_execution_ledger.ndjson`
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`

## 结论

- 本阶段结论：当前 `SH609.CZCE` 差异是 shadow 回放口径错误，不是实盘应持仓。直接原因是 Stage182 live inference 每次只把官方 Stage78 eligibility 与本次最新 live eligibility 拼成 combined，7 月月更后 combined 只保留 `2026-06-30` 最新池，未保留 3/31、4/30、5/29 live 重建截面；因此 Stage901 回放 2026-06-22 时不能使用 6/30，只能向前落到 2/27，导致 SH/lh 替代原先的 rb 路径。
- 是否进入下一步：是
- 下一步：
  1. 不允许据当前 shadow 去补 SH 或强平 rb；保持 fail-closed。
  2. 修复 Stage182/Stage935 的 combined eligibility 拼接逻辑，至少保留 live 重建历史截面，并增加 Stage901/Stage935 对历史月度断档的校验。
  3. 用 2026-06-29 Stage935 摘要里记录的 `2026-05-29` 正式线上池，或可验证的原始 5 月底 eligibility，重建 6 月 16 日以来 shadow，再对齐 broker。

## 过拟合反思

- 运行前判断：否。本次只做执行链路和数据版本归因，不根据交易盈亏调参数。
- 运行后判断：否。结论基于时间序列一致性、执行 ledger 和 AI eligibility 缺口，不是为了让某个回测结果更好而反推。
- 原因：如果把当前 SH shadow 直接当真，反而是在用错误输入拟合当前文件状态；正确做法是恢复当时线上 PIT 输入。

## 继续价值反思

- 运行前判断：是。shadow/broker 差异会直接影响后续是否允许自动执行，必须优先归因。
- 运行后判断：是。已定位到月度 AI 池历史截面丢失这个可修复的执行接线问题。
- 原因：修复后能避免后续月更把历史 live shadow 重放改写，属于实盘安全问题，不是单纯研究优化。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，避免与并行研究线整理冲突。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；若后续完成 Stage182/935 修复并重新对账 aligned，再追加正式摘要。
