# Stage330 P2 Master PIT Append Gate 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：P2 公开源 master PIT ledger 追加闸门；不重放策略、不改交易规则、不生成 selector/paper/交易白名单、不连接 CTP。
- 是否重要突破：否。它补齐前向证据累计基础设施，但仍不产生交易候选。
- 是否触发A/B：否。没有产生可接入正式版本的新策略，也没有 paper selector。

## 外部调研与判断

- 参考资料：
  - Glassnode PIT metrics：`https://docs.glassnode.com/data/point-in-time-metrics`
  - Glassnode look-ahead/PIT article：`https://insights.glassnode.com/why-use-point-in-time-data/`
  - vBase audit timestamp/hash trail：`https://docs.vbase.com/overview/what-vbase-verifies`
  - Convexly audit chain verifier：`https://www.convexly.app/research/verify`
- 我的判断：
  - PIT 数据的本质不是“多一个数据源”，而是证明某个源在某个时间点真实可得、内容可复验、后续没有被回填污染。
  - 对基本面/舆情 selector 来说，`received_at/source_url/final_url/raw_hash/status` 是最低证据标准；没有 master append gate，就容易把同一天重复抓取、修订页面或历史回填误当成样本。
  - 本阶段应该只累计证据，不允许任何 row 进入历史 selector、paper 或交易白名单。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage630_p2_master_pit_append_gate.py`
- 新增稳定证据账本：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_p2_public_source_master_pit_ledger.csv`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `REQUIRED_PIT_DATES_FOR_SELECTOR = 20`
  - `REQUIRED_MONTHS_FOR_SELECTOR = 12`
  - `REQUIRED_PRODUCTS = 3`
  - `REQUIRED_EVENT_PRODUCTS = 2`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 输入数据：Stage629 run ledger `6` 行公开源 monitor 输出。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 必须 `usable_for_forward_monitor=1`
  - 必须 `any_raw_hash_present=1`
  - 必须有 `received_at_local/received_at_utc/source_url/final_url`
  - 必须保持 `usable_for_history_selector=0`
  - 必须保持 `event_signal_ready=0`
  - 必须保持 `paper_or_whitelist_allowed=0`
- 去重键：`product_vt_symbol + source_url + received_at_utc + raw_sha256/linked_text_sha256`

## 结果

- 期末权益：不适用，本阶段不重算收益。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p2_master_pit_append_gate_written_selector_locked`
  - 首次运行：input rows `6`，append rows `6`，rejected rows `0`，master rows `6`。
  - 幂等性复跑：input rows `6`，append rows `0`，duplicate rows `6`，rejected rows `0`，master rows `6`。
  - products covered：`3`
  - min PIT dates：`1`
  - required PIT dates for selector：`20`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`9/9`
  - `ag.SHFE`：weighted rows `1.0`，PIT dates `1`，PIT months `1`，event rows `0`，progress `19.3333%`。
  - `CY.CZCE`：weighted rows `3.5`，PIT dates `1`，PIT months `1`，event rows `3`，progress `34.3333%`。
  - `SR.CZCE`：weighted rows `1.5`，PIT dates `1`，PIT months `1`，event rows `1`，progress `34.3333%`。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage630_p2_master_pit_append_gate.py`
- master ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_p2_public_source_master_pit_ledger.csv`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_report_stage630_p2_master_pit_append_gate_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_decision_stage630_p2_master_pit_append_gate_v1.json`
- append rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_append_rows_stage630_p2_master_pit_append_gate_v1.csv`
- rejected rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_rejected_rows_stage630_p2_master_pit_append_gate_v1.csv`
- product progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_product_progress_stage630_p2_master_pit_append_gate_v1.csv`
- source progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_source_progress_stage630_p2_master_pit_append_gate_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_gates_stage630_p2_master_pit_append_gate_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage630_p2_master_pit_append_gate_chart_stage630_p2_master_pit_append_gate_v1.png`

## 图表视觉复盘

- 左上图：`ag/CY/SR` 的 PIT dates 都只有 `1`，离 `20` 日 selector 红线很远；这个面板清楚防止把一次抓取误读为可用 selector。
- 右上图：SHFE Daily Data、NASS Crop Progress guide、ESMIS WASDE、ESMIS Crop Progress、ERS Cotton、ESMIS API 都有 hash，说明 master ledger 中没有“无 hash 的源证据”。
- 左下图：幂等性复跑时 new append rows 为 `0`、duplicate rows 为 `6`、rejected rows 为 `0`，说明去重键拦住了重复写入，master 不会因为重复运行膨胀。
- 右下图：所有 gate 为绿色，但其中 `pit_dates_below_selector_threshold` 是 fail-closed lock；绿色表示锁定纪律通过，不代表晋级。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage630_p2_master_pit_append_gate.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage630_p2_master_pit_append_gate.py` 首次运行：通过，追加 `6` 行。
- 同命令幂等性复跑：通过，追加 `0` 行、重复 `6` 行、master rows 保持 `6`。
- `python -m json.tool ...decision_stage630_p2_master_pit_append_gate_v1.json`：通过。
- 图表视觉检查：通过，四个面板与 CSV/decision 一致。

## 结论

- 本阶段结论：P2 公开源证据已经从一次性 run ledger 推进到稳定 master PIT ledger；这个动作提升了后续基本面/舆情研究的可实盘性和可审计性。
- 是否进入下一步：进入，但仍只能累计证据，不能交易。
- 下一步：
  1. 每个新交易日重复 Stage629 -> Stage630，累计 `20` 个 PIT received_at 日期和 `12` 个月跨度。
  2. 为 `CY/SR` 建 event episode ledger，把 USDA/ESMIS/ERS 事件和随后趋势 episode 分离记录。
  3. 为 `ag.SHFE` 寻找事件型公开源或授权源，否则它只能算 source monitor，不能算 event monitor。
  4. 达到 PIT/episode 后再做 purged walk-forward 预测力审计和 live TCA；在此之前 selector、paper、A/B、交易白名单继续为 `0`。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益回测、没有调参、没有新增品种白名单，只做证据账本、去重和 fail-closed 锁定。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：低单笔风险扩池要靠独立风险槽，而独立风险槽晋级必须先有 PIT source 和真实 TCA。Stage330 把 P2 source 证据变成可累计结构，是后续“选对品种”不走历史赢家过拟合的基础。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage330 摘要。
- 是否更新 `research/registry.md`：是，最新阶段推进到 Stage330。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
