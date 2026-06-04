# Stage348 ec.INE/SCFIS master PIT append gate

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 11:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`ec.INE`/SCFIS 第二独立槽 source monitor 的 master PIT append gate；不联网、不做收益回测、不改交易规则、不连接 CTP、不生成 selector/paper/A/B/交易白名单。
- 是否重要突破：否。属于 PIT 数据层推进，不是策略突破。
- 是否触发A/B：否。selector/paper/whitelist 仍为 `0/0/0`。

## 外部调研与判断

- 参考资料：
  - 上海航运交易所 SCFIS 当前查询：`https://www.sse.net.cn/index/singleIndex?indexType=scfis`
  - 上海航运交易所 SCFIS 指数简介：`https://www.sse.net.cn/indexIntro?indexName=scfis`
  - Point-in-time data and look-ahead bias：`https://www.pfolio.io/academy/look-ahead-bias`
  - PIT metrics concept：`https://docs.glassnode.com/data/point-in-time-metrics`
- 我的判断：
  - SCFIS 是外部官方指数，不能靠历史回填直接进 selector；必须按实际 `received_pit_date`、source URL、raw hash 和 parsed value 建 PIT ledger。
  - Stage647 的 INE/context/methodology 页面可作为 source contract 证据，但不能混入数值型 selector ledger；本阶段只允许 `SSE SCFIS current index query` 且 `parse_ok=1` 的当前值行进入 master。
  - 单个 SCFIS 日期只证明 parser 与账本可用，不构成 alpha 或交易证据。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage648_ec_scfis_master_pit_append_gate.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR = 20`
  - `REQUIRED_EPISODES = 3`
  - `REQUIRED_PARSED_ROWS = 1`
  - master ledger：`qmt_roll_ec_ine_scfis_master_pit_ledger.csv`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：非收益回测；输入为 Stage647 的 `4` 条官方源抓取结果。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只接受 `source_name = SSE SCFIS current index query`
  - `source_authority = index_publisher_official`
  - `source_class = official_underlying_index_current_value`
  - `http_status=200`
  - `fetch_status=ok`
  - `parse_ok=1`
  - `raw_sha256_present=1`
  - `usable_for_history_selector=0`
  - `selector/paper/trading whitelist=0/0/0`
- 策略/归因口径：只做 SCFIS 当前值 master PIT append、context 行拒绝、去重、幂等复跑和 selector 锁定；不看未来收益。

## 结果

- 期末权益：不适用，非回测。
- 总收益：不适用，非回测。
- 最大回撤：不适用，非回测。
- Sharpe：不适用，非回测。
- 总滑点：不适用，非回测。
- 总交易次数：不适用，非回测。
- 胜率：不适用，非回测。
- 其他关键指标：
  - decision：`ec_scfis_master_pit_append_gate_written_collection_pit_one_selector_locked`
  - input rows：`4`
  - append rows：`1`
  - duplicate rows：`0`
  - rejected context rows：`3`
  - idempotent rerun append rows：`0`
  - idempotent rerun duplicate rows：`1`
  - master rows：`1`
  - SCFIS dates：`1`
  - collection PIT dates：`1`
  - latest SCFIS Europe：`2026-06-01 2038.09`，环比 `+9.4%`
  - raw hash rows：`1`
  - selector rows：`0`
  - paper/trading whitelist rows：`0/0`
  - hard gates：`12/14`

## 图表视觉复盘

- 左上：master ledger 中只有一个 SCFIS 欧线点：`2026-06-01 2038.09/+9.4%`。这说明 parser 和账本可用，但图形上也很直观地显示没有时间序列，不能做趋势判断。
- 右上：master rows、SCFIS dates、collection PIT dates、raw hashes 均为 `1`，selector rows 为 `0`；`20 PIT selector gate` 红线远高于当前样本。
- 左下：append rows `1`、rejected context rows `3`、rerun new rows `0`。3 条 context 行被拒绝是正确行为，避免 INE 产品页和方法论页混进数值型 selector ledger。
- 右下：红灯只有 `collection_pit_dates_reach_20` 和 `independent_episodes_reach_3`，其余 source/parse/hash/去重/锁定闸门为绿。结论：source ledger 可累计，但不可交易。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_report_stage648_ec_scfis_master_pit_append_gate_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_decision_stage648_ec_scfis_master_pit_append_gate_v1.json`
- master ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_ec_ine_scfis_master_pit_ledger.csv`
- append rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_append_rows_stage648_ec_scfis_master_pit_append_gate_v1.csv`
- duplicate rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_duplicate_rows_stage648_ec_scfis_master_pit_append_gate_v1.csv`
- rejected rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_rejected_rows_stage648_ec_scfis_master_pit_append_gate_v1.csv`
- product progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_product_progress_stage648_ec_scfis_master_pit_append_gate_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_gates_stage648_ec_scfis_master_pit_append_gate_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage648_ec_scfis_master_pit_append_gate_chart_stage648_ec_scfis_master_pit_append_gate_v1.png`
- orders/daily/quality：不适用，非交易回测。

## 结论

- 本阶段结论：`ec.INE/SCFIS` 已有稳定 master PIT ledger，SCFIS 当前欧线值可被解析、hash 留痕、按实际接收日累计，并且 context 行不会污染 selector ledger。
- 它不是交易候选：当前只有 `1` 个 collection PIT date、`0` 个 outcome episode、`0` 个 live TCA，本地 `ec.INE` futures proxy 也仍需修复新鲜度。
- 是否进入下一步：进入前向自然日累计；不进入 selector/paper/A/B/交易白名单。
- 下一步：
  - 每个新自然日复跑 SCFIS collector，只允许新 `received_pit_date` 增加样本。
  - 修复 `ec.INE` 本地 futures proxy 新鲜度，重新审计 tail corr/rolling corr。
  - 满 `20` 个 collection PIT dates 后，再固定做 `20/63/126` outcome schedule。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有回放收益、没有调参数、没有把单点指数解释成 alpha；反而把 Stage647 的 4 条 source 严格过滤成 1 条数值 master row，并拒绝 3 条 context 行。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但仍是 monitor/source 层。
- 原因：`ec.INE/SCFIS` 是 CJ 之外的第二个独立经济驱动来源，且官方当前值可解析；但真实交易要求的数据新鲜度、PIT 深度、episode、outcome 和 TCA 还都没闭合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage348 当前状态。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破、路线废弃或跨线合并。
