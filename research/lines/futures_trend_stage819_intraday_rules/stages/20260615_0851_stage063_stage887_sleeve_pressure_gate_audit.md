# Stage063 Stage887 sleeve 触发压力闸门只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 08:51 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage883 sleeve 触发前组合压力闸门只读审计；不新增交易规则、不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于 sleeve/pyramiding 救援路线反证。
- 是否触发正式 A/B：否。Stage887 只读，不进入正式候选、不写根目录 `back_log.md`。
- 决策：`stage887_sleeve_pressure_gate_not_promoted_proxy_cost_or_too_blunt`

## 外部调研与判断

- vn.py/VeighNa 官方项目支持组合策略历史回测与实盘框架；本阶段继续按组合状态做只读审计，不把单笔代理当正式结果。
- CME open interest 资料支持把 OI 和价格当作参与度辅助信息，但不能把 OI 或高参与度单独当作退出/禁入充分条件。
- 趋势跟随 pyramiding 的通用经验是加仓必须被 portfolio heat 约束；Stage887 因此只看新增 sleeve 的前置风险预算，而不是回头砍已有右尾仓位。
- 我的判断：Stage886 已反证高压持仓平仓；Stage887 的第一性问题是“新增 1 手 sleeve 是否在已热/将热时让保证金分子继续膨胀”。结果显示，当前固定 heat gate 仍过钝，无法低误伤地阻断坏 sleeve。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage887_stage883_sleeve_pressure_gate_audit.py`
- 新增输出前缀：`qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_*`
- 新增交易规则：无。
- 新增参数：无交易参数；新增只读 gate：
  - `G0_prev_pressure`：前一交易日已经是 Stage885 holding pressure state。
  - `G1_pre_add_heat80`：sleeve 触发前估算 broker10/equity 已经 `>=80%`。
  - `G2_projected_after_add_heat80`：新增 1 手 sleeve 后估算 broker10/equity 将 `>=80%`。
  - `G3_pre_or_projected_heat80`：G1 或 G2。
  - `G4_prev_pressure_or_projected_after_heat80`：G0 或 G2。
  - `G5_prev_pressure_same_product_direction`：前一日 pressure 且本次 sleeve 产品方向等于前一日 top product-direction。
  - `A0/A1` current-day pressure 只做事后归因，不作为实时 gate。
- 修改参数：无官方配置修改；Stage883 C17 和 Stage819 候选配置保持不变。
- 删除参数：无。
- 阈值约束：只使用 Stage885 既定 `80%` account heat，不扫描 `75/85/90`、小数阈值、产品方向、年份、分钟窗口或 OI 阈值。

## 回测与审计参数

- 数据区间：沿用 Stage883 / Stage885 全周期 `2018-01-01 -> 2026-05-29`。
- 上游候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 账户规模：`300000`
- 输入：
  - Stage883 pyramid events：`qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_pyramid_events_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
  - Stage883 entry risk：`qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_entry_risk_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
  - Stage883 closed lots：`qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_closed_lots_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
  - Stage885 daily state：`qmt_roll_stage885_stage884_holding_pressure_state_audit_daily_state_stage885_stage884_holding_pressure_state_audit_v1.csv`
  - 分钟数据：Stage861 full minute bars。
- `skip_proxy_delta = - addon_realized_pnl` 只作为“若跳过该 sleeve”的只读代理，不是完整组合引擎。

## 源结果复述

### C17 结果

- 期末权益：`51,683,814.65`
- 总收益：`17,127.9382%`
- 最大回撤：`-41.1625%`
- Sharpe：`1.6223`
- 总滑点：`3,921,000`
- 总交易次数：`1,051`
- 胜率：`53.4863%`
- max broker10 margin/equity：`127.4316%`
- p95 broker10 margin/equity：`63.7936%`

## 新增审计结果

### 样本覆盖

- Stage883 pyramid events：`175`
- PnL available events：`175`
- addon PnL sum：`220,565.15`
- entry-day stopped events：`76`
- ever active on later pressure day：`24`
- ever active on same-product pressure day：`11`
- closed lots 中 `stage883_pyramid` 已结算 `174` 笔；另 1 笔用 stopped event estimate 补足，因此本阶段事件样本 PnL 为 `220,565.15`。

### live gate proxy

- `G0_prev_pressure`：阻断 `2` 次，skip proxy `-4,240`，loser saved `0`，winner cut `-4,240`。
- `G1_pre_add_heat80`：阻断 `70` 次，skip proxy `-101,875.95`，loser saved `48,310.80`，winner cut `-150,186.75`；覆盖后来 pressure events `18` 次、same-product pressure `9` 次。
- `G2_projected_after_add_heat80`：阻断 `79` 次，skip proxy `-114,051.15`，loser saved `56,695.80`，winner cut `-170,746.95`；覆盖后来 pressure events `18` 次、same-product pressure `9` 次。
- `G3_pre_or_projected_heat80` 与 `G4_prev_pressure_or_projected_after_heat80` 与 G2 等价：阻断 `79` 次，skip proxy `-114,051.15`。
- `G5_prev_pressure_same_product_direction`：阻断 `0` 次，过窄，不能命中。
- 结论：没有一个 live gate 同时满足 skip proxy 为正、winner cut 小于 loser saved。

### 事后压力归因

- 后来参与 same-product pressure 的 `11` 笔 sleeve：addon PnL `+29,792.40`，positive PnL share `63.6364%`，entry-day stopped share `27.2727%`。
- 后来参与 pressure 但非 same-product 的 `13` 笔 sleeve：addon PnL `+37,691.60`，positive PnL share `69.2308%`。
- 从未参与后续 pressure 的 `151` 笔 sleeve：addon PnL `+153,081.15`。
- 判断：即使只事后看“后来参与压力日”的 sleeve，它们本身仍是净正，不支持“会参与压力就禁止新增 sleeve”。

### current-day pressure 归因

- `A0_current_day_pressure_attribution`：阻断 `10` 次，skip proxy `-26,517.50`，loser saved `8,222.50`，winner cut `-34,740.00`。
- `A1_current_pressure_same_product_direction_attribution`：阻断 `6` 次，skip proxy `-1,827.50`，loser saved `6,877.50`，winner cut `-8,705.00`。
- 注意：A0/A1 本来就不是实时 gate，只说明即使用后验 current-day pressure 也无法得到低误伤的阻断证据。

## 视觉复核

- summary chart 非空：80% heat 线上方红绿混杂，无法形成“热度高就禁加仓”的干净边界；gate bar 全部在 0 以下。
- atlas page001 非空：live gate 确实能抓到部分亏损 sleeve，符合“热时不该加”的直觉，但样本收益贡献不足。
- atlas page003 非空：同样的 live gate 会误伤 `ru2101.SHFE`、`cu2007.SHFE`、`FG109.CZCE` 等高热赢家 sleeve，说明直觉不能写成规则。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_report_stage887_stage883_sleeve_pressure_gate_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_decision_stage887_stage883_sleeve_pressure_gate_audit_v1.json`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_features_stage887_stage883_sleeve_pressure_gate_audit_v1.csv`
- gate summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_gate_summary_stage887_stage883_sleeve_pressure_gate_audit_v1.csv`
- pressure attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_pressure_attribution_stage887_stage883_sleeve_pressure_gate_audit_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_summary_chart_stage887_stage883_sleeve_pressure_gate_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage887_stage883_sleeve_pressure_gate_audit_atlas_page001_stage887_stage883_sleeve_pressure_gate_audit_v1.png` 至 `page004`

## 结论

- Stage887 反证了对 Stage883 sleeve 做固定 `80%` pressure/heat 前置闸门。
- `G2/G3/G4` 虽能覆盖 `79` 次 sleeve 和 `18` 次后来 pressure events，但 skip proxy 为 `-114,051.15`，winner cut `-170,746.95` 明显大于 loser saved `56,695.80`。
- 后来参与 same-product pressure 的 sleeve 也净赚 `+29,792.40`，说明“参与压力”不是错误充分条件。
- 不进入真实引擎、不触发 A/B、不做阈值救参。
- sleeve/pyramiding 分支应停止继续救援；继续扫 heat 阈值、产品方向、年份或分钟窗口会过拟合。

## 过拟合反思

- 运行前判断：否。本阶段只使用 Stage885 固定 pressure 定义和 `80%` account heat，不扫阈值、不筛品种方向。
- 运行后判断：否。当前结论是反证，不用少数亏损 sleeve 反推规则；若继续用 `75/85/90`、产品方向、年份或分钟窗口救结果，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。它直接检验 C17 的新增保证金分子是否能被前置组合压力约束，而不是砍已有右尾。
- 运行后判断：sleeve/pyramiding 方向继续价值低。Stage882、883、884、885、886、887 已连续说明：加仓能带来右尾，但保证金分子和压力路径无法用低误伤规则治理。若继续本线，应停止 sleeve/pyramiding 救援，回到 C9 本体，寻找新的低自由度外生信息源或账户级非交易层生存线。

## 后续规划和 TODO

- 不接 Stage887 pressure gate 引擎。
- 不扫描 heat 阈值、产品方向、年份、分钟窗口、OI 阈值或 `1/2/3` 手 sleeve。
- 本线下一步应做阶段性路线收束：把 Stage881-887 的 pyramiding/sleeve 证据合并成一份 route closure，明确不再围绕新增仓救参；若继续寻找规则，只能回到 C9 本体或引入独立外生低自由度信息。
