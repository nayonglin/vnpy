# Stage267 Stage526容量缺口本地回填审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-03 01:06 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读容量数据覆盖审计；不改策略、不改参数、不生成交易候选。
- 是否重要突破：否。它提升 Stage526 容量审计可信度，但不改变收益/回撤路径。
- 是否触发A/B：否。不是可接入正式版本的新策略模块，只是扩池前的可成交性基础审计。

## 外部调研与判断

- 参考资料：
  - TqSdk / vn.py 生态的历史K线可提供 `volume`、`open_interest/open_oi/close_oi` 等容量字段。
  - `pysystemtrade` 文档把品种权重、相关估计、instrument diversification multiplier 和成本建模拆开处理，说明扩池不能只看收益，还必须单独审计容量与相关风险。
  - 时间序列动量/CTA 研究支持多市场分散，但不支持“盲目扩大品种池就能自然获得alpha”。
- 我的判断：
  - “降低单笔风险 + 扩大品种池”方向仍值得做，但前提是先有容量闸门、相关簇闸门和 point-in-time 选品器。
  - 本阶段不能用成交窗口分钟片段冒充日成交量；只有完整日线或足够完整的分钟日才允许进入容量重算。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage566_stage526_liquidity_gap_backfill_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MIN_FULL_LIKE_MINUTE_BARS = 180`
  - `SOFT_ORDER_VOLUME_PCT = 0.25`
  - `HARD_ORDER_VOLUME_PCT = 0.50`
  - `MAX_ORDER_VOLUME_PCT = 1.00`
  - `STRESS_POSITION_OI_PCT = 1.00`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526 / Stage565 事件账本，2020-2026。
- 账户规模：Stage526 `50万` 下单口径。
- 成本口径：正常成本；本阶段不重算策略收益，只继承 Stage526 指标。
- 样本过滤：只处理 Stage565 中 `volume_data_gap_event == 1` 或 `oi_data_gap_event == 1` 的交易事件。
- 策略/归因口径：
  - 原始事件数 `687`。
  - 原始容量缺口事件 `96`。
  - 本地数据源优先级：完整日线正成交量/OI > 完整分钟近似日 > 不完整日线/分钟上下文 > 未解决。
  - 分钟线被接受的最低条件：同日分钟条数 `>=180` 且成交量/OI均为正；否则只记录上下文，不进入日成交量重算。

## 结果

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`
- 其他关键指标：
  - decision：`liquidity_gap_partially_backfilled_capacity_not_closed`
  - 闸门：`7/8`
  - 接受回填事件：`88/96`
  - 接受回填率：`91.6667%`
  - 仅上下文事件：`8`
  - 未解决缺口事件：`8`
  - 完整日线回填：`0`
  - 完整分钟近似回填：`88`
  - 原始正成交量/OI覆盖率：`86.0262% / 86.0262%`
  - 回填后正成交量/OI覆盖率：`98.8355% / 98.8355%`
  - 回填后 p95 订单量/日成交量：`0.1870%`
  - 回填后 max 订单量/日成交量：`1.0381%`
  - 回填后硬容量压力事件占比：`0.7278%`
  - 回填后持仓/OI压力事件占比：`0.2911%`
  - 硬容量压力交易日PnL占绝对交易日PnL：`0.2715%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_report_stage566_stage526_liquidity_gap_backfill_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_summary_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- gap_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_gap_events_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- backfill_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_backfill_candidates_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- resolved_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_resolved_events_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_annual_before_after_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_gates_stage566_stage526_liquidity_gap_backfill_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_decision_stage566_stage526_liquidity_gap_backfill_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage566_stage526_liquidity_gap_backfill_audit_chart_stage566_stage526_liquidity_gap_backfill_audit_v1.png`

## 图表视觉分析

- 左上图显示原始缺口主要集中在 `2020` 和 `2026`。回填后 `2020` 的蓝柱基本被橙柱吸收，但仍剩 `5` 个未解决/上下文事件；`2026` 仍剩 `2` 个未解决事件，且年度覆盖率仍未达到 95%。
- 右上图显示接受回填全部来自 `minute_full_like`，没有完整日线直接补齐。这意味着本阶段已经显著改善覆盖率，但严格数据源仍不如真实日线成交量/OI，需要后续补日线最终关账。
- 左下图显示未解决缺口不是大面积分散，而是 `OI.CZCE` 2 个事件加若干单事件产品，后续补数据范围可控。
- 右下图显示回填后年度覆盖曲线明显抬升，但容量压力曲线没有发生结论性反转；`2025` 的最大订单/日成交量仍约 `1.0381%`，来自 Stage266 已识别的 `fu2509.SHFE` 边界事件。

## 结论

- 本阶段把 Stage526 容量覆盖从 `86.0262%` 提升到 `98.8355%`，说明 Stage266 的主要缺口确实可以用本地完整分钟数据补上。
- 容量审计仍不能完全关账，原因不是覆盖率，而是单次最大订单/日成交量仍为 `1.0381%`，略超 `1%` 硬边界。
- 这支持一个更清晰的判断：Stage526 当前订单容量大体可承载，低单笔风险扩池不应被流动性直接否决；但扩池仍必须先过容量闸门和 point-in-time 选品器，不能靠盲目扩大品种池。
- 本阶段不改变 Stage526 的核心收益风险结论：正常成本仍是主候选，`3x` 成本压力和真实滑点采样仍是更重要的实盘边界。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：回填规则在运行前固定，只按数据质量判断是否接受，不按收益好坏、品种好坏或历史亏损窗口调规则；没有新增交易信号和参数搜索。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：扩池和低单笔风险方向要走下去，必须先知道容量和相关风险是否可控。本阶段把容量盲区缩小到 `8` 个事件和一个 `fu2509.SHFE` 边界事件，后续可以更有针对性地补真实日线和真实成交滑点账本。

## 合入建议

- 是否更新本线 `LINE.md`：是。Stage267 是 Stage266 后的直接数据质量推进，应替代“先补2020/2026缺口”的下一步描述。
- 是否更新 `research/registry.md`：是。当前线最新关键阶段应从 Stage266 更新为 Stage267。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或路线废弃；保留在本线 stage 与 LINE 即可。
