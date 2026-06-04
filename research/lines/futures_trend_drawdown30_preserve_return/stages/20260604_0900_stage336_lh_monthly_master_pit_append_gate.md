# Stage336 lh 官方月度源 master PIT append gate

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 09:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`lh.DCE` 官方月度基本面源 master PIT 稳定账本追加闸门
- 是否重要突破：否；source pipeline 进展，不是策略晋级
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - 农业农村部生猪产品月度数据：`https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/`
  - 全国畜牧总站 2026 年 4 月畜产品和饲料价格月报：`https://www.nahs.org.cn/jcyj/scxs/202605/t20260519_472251.htm`
  - Glassnode point-in-time metrics 概念：`https://docs.glassnode.com/data/point-in-time-metrics`
  - vBase timestamp/hash verification 概念：`https://docs.vbase.com/overview/what-vbase-verifies`
- 我的判断：
  - `lh.DCE` 的 MOA/NAHS 官方源已经能抓取和解析，但如果没有稳定 master PIT ledger，后续仍容易把单次抓取误用成历史 selector。
  - 可用于未来预测力审计的数据账本必须先保存采集时点、source URL、final URL、raw hash、状态、字段 schema 和锁定字段；缺 hash、缺 schema、缺 received_at 或 selector 未锁的行必须拒绝。
  - 本阶段只解决“证据能不能累计且幂等”，不解决 alpha 是否存在。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage636_lh_monthly_master_pit_append_gate.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - master ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_lh_monthly_official_source_master_pit_ledger.csv`
  - 输入 ledger：Stage635 fetch ledger
  - reject 条件：`wrong_line_id`、`not_lh_product`、`missing_source_or_final_url`、`missing_received_at`、`missing_raw_sha256`、`active_fetch_not_validated`、`forward_monitor_not_enabled`、`history_selector_not_locked`、`event_signal_not_locked`、`paper_or_whitelist_not_locked`、`insufficient_extracted_fields`、`invalid_extracted_fields_json`、`not_monthly_source_class`
  - dedupe key：`product_vt_symbol + source_url + received_at_utc + raw_sha256`
  - selector PIT 阈值：`20` 个 received_at 日期
  - selector 月份跨度阈值：`12` 个月
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不做收益回测；只读 Stage635 `2026-06-04 08:55 CST` 的 fetch ledger
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - 输入行数 `2`
  - 要求 `active_fetch_validated=1`
  - 要求 `raw_sha256_present=1`
  - 要求 `usable_for_history_selector=0`
  - 要求 `paper_or_whitelist_allowed=0`
- 策略/归因口径：
  - 不重放策略、不看收益、不改交易规则、不生成 selector/paper/交易白名单、不连接 CTP
  - 只追加 master PIT ledger，并做内部幂等复跑验证

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`lh_monthly_master_pit_append_gate_written_selector_locked`
  - input rows：`2`
  - append rows：`2`
  - duplicate rows：`0`
  - rejected rows：`0`
  - idempotent rerun append rows：`0`
  - idempotent rerun duplicate rows：`2`
  - idempotent rerun rejected rows：`0`
  - master rows：`2`
  - active fetch rows：`2`
  - raw hash rows：`2`
  - PIT dates：`1`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`11/11`
  - product progress：`progress_pct=29.5833`，状态 `accumulating_lh_pit_evidence_selector_locked`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_report_stage636_lh_monthly_master_pit_append_gate_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_decision_stage636_lh_monthly_master_pit_append_gate_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_lh_monthly_official_source_master_pit_ledger.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_append_rows_stage636_lh_monthly_master_pit_append_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_duplicate_rows_stage636_lh_monthly_master_pit_append_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_rejected_rows_stage636_lh_monthly_master_pit_append_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_product_progress_stage636_lh_monthly_master_pit_append_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_source_progress_stage636_lh_monthly_master_pit_append_gate_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_gates_stage636_lh_monthly_master_pit_append_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage636_lh_monthly_master_pit_append_gate_chart_stage636_lh_monthly_master_pit_append_gate_v1.png`

## 图表视觉复盘

- 左上图：
  - `pit_dates=1`，红线为 `20` 日 selector 门槛，视觉上差距很大。
  - `source_classes=2`、`active_fetch_validated_rows=2`、`raw_hash_rows=2` 说明源质量有进展，但 PIT 深度不足仍是主阻塞。
- 右上图：
  - NAHS `monthly_price_release` 字节数明显大于 MOA `monthly_supply_demand_release`，两类源均为 `hash 1 fields 4`。
  - 这说明两个官方源都已进入 master，但每类源当前只有一个 PIT 样本。
- 左下图：
  - 首次 append `2` 行、rejected `0`。
  - 内部幂等复跑新增 `0` 行，说明重复运行不会膨胀样本。
- 右下图：
  - hard gates 全绿，但包含 `pit_dates_below_selector_threshold`、`selector_rows_zero`、`paper_whitelist_rows_zero`。
  - 绿色代表账本纪律有效，不代表 `lh.DCE` 可以进入 selector。

## 结论

- 本阶段结论：
  - `lh.DCE` 官方月度源证据已经从 Stage635 一次性 fetch 输出进入稳定 master PIT ledger。
  - master 账本具备 dedupe、hash、schema、received_at 和 selector 锁定检查。
  - 这仍不是 alpha 或交易候选：当前只有 `1/20` 个 PIT 日期，缺 `12` 个月跨度、独立 episode、预测力审计和 live TCA。
- 是否进入下一步：继续，但仍只做 source pipeline 和样本累计。
- 下一步：
  - 做 `lh.DCE` master PIT monitor rerun gate，确认新日期能追加、同日重复不会膨胀。
  - 等累计到至少 `20` 个 received_at 日期后，才允许固定字段 schema 做一次预测力审计协议。
  - 未达标前禁止历史回填、selector、paper、A/B 和交易白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有使用收益、没有调整交易规则、没有挑选品种参数。
  - 只是将官方源证据转成可复验、可累计、不可重复膨胀的 PIT 账本。
  - 所有交易相关输出仍为 `0`，且 PIT 样本不足被明确标记为 fail-closed。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值仍在证据累计，不在回测。
- 原因：
  - 这一步让 `lh.DCE` 具备真正 forward source ledger 的雏形。
  - 后续是否值得进入 selector，必须由多日期、多月份、独立 episode、预测力和 TCA 共同决定。
  - 当前继续宽池收益扫描仍然没有价值；应继续沿 source-first 管道推进。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage336 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
