# Stage346 CJ.CZCE 仓单 master PIT append gate

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 11:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池路线的 CJ 官方仓单源 master PIT append gate；不联网、不做收益回测、不改交易规则、不连接 CTP、不生成 selector/paper/A/B/交易白名单。
- 是否重要突破：否。属于 PIT 数据纪律加强，不是策略突破。
- 是否触发A/B：否。selector/paper/whitelist 仍为 `0/0/0`。

## 外部调研与判断

- 参考资料：
  - Point-in-time data and look-ahead bias：`https://www.pfolio.io/academy/look-ahead-bias`
  - AKShare CZCE warehouse receipt function：`https://deepwiki.com/akfamily/akshare/4.2-futures-and-commodities`
  - AKShare GitHub：`https://github.com/akfamily/akshare`
  - CZCE 仓单日报：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
- 我的判断：
  - Stage345 证明了 CJ 仓单源可抓，但还不能把 `6` 个官方仓单日期当成 `6` 个前向 PIT 样本，因为这些历史日期是同一次采集得到的。
  - 真正能防止 look-ahead 的 PIT 口径应按 `received_pit_date` 统计，也就是数据被我们实际收到/归档的日期；`official_date` 只能作为事件日期和 parser 验证。
  - 因此本阶段的核心不是增加收益指标，而是把 CJ 从“source probe 成功”推进到“可前向累计且不会同日重复膨胀样本”的 master ledger。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage646_cj_warehouse_master_pit_append_gate.py`
- 修改脚本：无既有策略脚本修改；本阶段脚本首轮图表中失败闸门红条不可见，已修正为失败项满宽红条。
- 删除脚本：无。
- 新增参数：
  - `REQUIRED_SOURCE_ROWS = 6`
  - `REQUIRED_COLLECTION_PIT_DATES_FOR_SELECTOR = 20`
  - `REQUIRED_EPISODES = 3`
  - master ledger：`qmt_roll_cj_czce_warehouse_master_pit_ledger.csv`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：非收益回测；输入为 Stage645 的 `6` 条 CJ 仓单抓取结果。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只接受 `CJ.CZCE`
  - `fetch_status=ok`
  - `raw_sha256_present=1`
  - `usable_for_forward_monitor=1`
  - `usable_for_history_selector=0`
  - `selector/paper/trading whitelist=0/0/0`
- 策略/归因口径：只做 master PIT append、去重、拒绝异常行、幂等复跑和 selector 锁定；不看未来收益。

## 结果

- 期末权益：不适用，非回测。
- 总收益：不适用，非回测。
- 最大回撤：不适用，非回测。
- Sharpe：不适用，非回测。
- 总滑点：不适用，非回测。
- 总交易次数：不适用，非回测。
- 胜率：不适用，非回测。
- 其他关键指标：
  - decision：`cj_warehouse_master_pit_append_gate_written_collection_pit_one_selector_locked`
  - 首次运行：input rows `6`，append rows `6`，duplicate rows `0`，rejected rows `0`，master rows `6`
  - 修图后复跑：input rows `6`，append rows `0`，duplicate rows `6`，rejected rows `0`
  - idempotent rerun append rows：`0`
  - idempotent rerun duplicate rows：`6`
  - official dates：`6`
  - collection PIT dates：`1`
  - required collection PIT dates for selector：`20`
  - raw hash rows：`6`
  - selector rows：`0`
  - paper/trading whitelist rows：`0/0`
  - hard gates：`11/13`

## 图表视觉复盘

- 左上：master ledger 保留了 6 个官方仓单日期，仓单数量从 `5838/6278` 上升到 `7769/7770`，有效预报量在 4 月高位后回落；说明 source 有真实变化，适合做前向监控。
- 右上：`official dates=6`、`raw hashes=6`，但 `collection PIT dates=1`；红线 `20` 明确显示 selector 离门槛很远。这个图是本阶段最关键的口径修正。
- 左下：修图后复跑显示 `already duplicate rows=6`、`append rows=0`、`rejected rows=0`、`rerun new rows=0`，说明 master ledger 已经幂等，不会重复膨胀样本。
- 右下：红灯只有两个：`collection_pit_dates_reach_20` 和 `independent_episodes_reach_3`；其余 source/去重/锁定闸门均为绿色。图表首轮失败项红条不可见，已修正后复验通过。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_report_stage646_cj_warehouse_master_pit_append_gate_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_decision_stage646_cj_warehouse_master_pit_append_gate_v1.json`
- master ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_cj_czce_warehouse_master_pit_ledger.csv`
- append rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_append_rows_stage646_cj_warehouse_master_pit_append_gate_v1.csv`
- duplicate rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_duplicate_rows_stage646_cj_warehouse_master_pit_append_gate_v1.csv`
- rejected rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_rejected_rows_stage646_cj_warehouse_master_pit_append_gate_v1.csv`
- product progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_product_progress_stage646_cj_warehouse_master_pit_append_gate_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_gates_stage646_cj_warehouse_master_pit_append_gate_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage646_cj_warehouse_master_pit_append_gate_chart_stage646_cj_warehouse_master_pit_append_gate_v1.png`
- orders/daily/quality：不适用，非交易回测。

## 结论

- 本阶段结论：CJ 仓单源已进入稳定 master PIT ledger，并通过 hash、timestamp、dedupe、幂等复跑和 fail-closed 闸门。
- 重要口径修正：`official_dates=6` 只能说明 parser 和事件日期覆盖，不能说明已经有 `6` 个前向样本；严格可用于 selector 进度的 `collection_pit_dates=1`。
- 是否进入下一步：进入前向自然日累计；不进入 selector/paper/A/B/交易白名单。
- 下一步：
  - 把 CJ collector 纳入新自然日 monitor，只允许新 `received_pit_date` 增加 collection 样本。
  - 累计到 `20` 个 collection PIT dates 后，固定跑 `20/63/126` outcome schedule。
  - 继续找独立月度/季节性官方或授权源；仓单单源不足以作为交易 alpha。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有看收益、没有调参数、没有回放交易，只把数据层从“可抓取”推进到“可审计且不会前视/重复膨胀”；并且主动把 Stage345 的 `6` 个官方日期收紧为 `1` 个 collection PIT 日期，反而降低了过拟合和前视风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但仍是 monitor/source 层。
- 原因：CJ 现在有了稳定 ledger，未来每天新增采集可以自然累计；这使“低单笔风险扩池、选低相关品种”的路线有了一个可执行样本，但离真实交易仍差 `19` 个 collection PIT 日期、`3` 个 episode、outcome audit 和 live TCA。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage346 当前状态。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破、路线废弃或跨线合并。
