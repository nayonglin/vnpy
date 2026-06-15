# Stage062 Stage886 pressure-state 内分钟级失败结构只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 08:35 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage885 后续只读结构审计；不新增交易规则、不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于压力状态内的失败结构反证，不是可推广策略突破。
- 是否触发正式 A/B：否。Stage886 只读，不进入正式候选、不写根目录 `back_log.md`。
- 决策：`stage886_pressure_failure_shape_not_trade_rule_mixed_or_right_tail_cost`

## 外部调研与判断

- vn.py/VeighNa 官方项目定位支持组合策略回测与实盘框架；本阶段继续做组合路径后的只读结构审计，而不是把单笔代理当成正式结果。
- CME open interest 资料支持把 OI 与价格共同看作参与度/资金流状态，但 OI 不能单独决定退出。
- 趋势跟随 portfolio heat / units 资料提醒，持仓集中度是生存线问题；但高参与度、高持仓压力往往也和趋势右尾相伴，不能简单去杠杆。
- Backtrader 成交语义资料继续提醒，任何真实止损/退出必须在当时可判定；本阶段所有 `next20` 和 `remaining PnL` 只用于事后归因。
- 我的判断：Stage885 已证明 pressure state 不能一刀切退出；Stage886 只检查固定分钟结构是否能把高压右尾和高压失败分开。结果显示不能，至少当前 price failure 结构仍会误伤右尾。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage886_stage885_pressure_failure_structure_audit.py`
- 新增输出前缀：`qmt_roll_stage886_stage885_pressure_failure_structure_audit_*`
- 新增交易规则：无。
- 新增参数：无交易参数；新增只读结构定义：
  - 样本：C17 pressure day 上 Stage885 top product-direction 的 active lots。
  - `directional_close_return_pct`：压力日从第一根分钟开盘到最后一根分钟收盘的信号方向收益；long 用 `close/open`，short 用 `open/close`。
  - `close_location_signal_side`：收盘位于当日区间的信号侧位置；long 越接近 `1` 越靠近高点，short 越接近 `1` 越靠近低点。
  - `price_failure_shape = no_net_signal_progress and close_in_adverse_half and adverse_dominates_progress`
  - `signal_resilience_shape = directional_close_return_pct > 0 and close_location_signal_side >= 0.5 and signal_side_progress_pct >= adverse_excursion_pct`
- 修改参数：无官方配置修改；C17 路径和 Stage819 候选配置保持不变。
- 删除参数：无。
- 阈值约束：只使用 `0` 与 `0.5` 的方向/半区间判定；不扫描分钟窗口、小数阈值、OI 阈值、成交量阈值、品种、方向或年份。

## 回测与审计参数

- 数据区间：沿用 Stage883 / Stage885 全周期 `2018-01-01 -> 2026-05-29`。
- 上游候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 账户规模：`300000`
- 输入：
  - Stage885 daily state：`qmt_roll_stage885_stage884_holding_pressure_state_audit_daily_state_stage885_stage884_holding_pressure_state_audit_v1.csv`
  - Stage885 product-direction daily：`qmt_roll_stage885_stage884_holding_pressure_state_audit_product_direction_daily_stage885_stage884_holding_pressure_state_audit_v1.csv`
  - C17 closed lots：Stage883 closed lots，经 Stage885 输入修正路径读取。
  - 分钟数据：Stage861 full minute bars。
- `same_day_eod_exit_proxy_delta = - remaining_pnl_after_focus_close` 只作为 EOD 退出代理归因，不作为真实组合引擎结果。

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

- pressure top-product active lot rows：`61`
- pressure days covered：`25`
- products covered：`5`
- missing minute rows：`10`
- 缺失分钟行集中在 `AP005.CZCE`、`jm2101.DCE`、`jm2401.DCE` 的部分 pressure days；这些行不用于 price failure / signal resilience 结构判断。

### shape proxy

- `price_failure_shape`：`22` 行、`9` 天、`5` 个产品，held beyond rows `20`。
  - median directional close return：`-1.0198%`
  - median close location signal-side：`0.1284`
  - median OI change：`-0.2047%`
  - remaining PnL after focus close：`+2,853,650`
  - EOD exit proxy delta：`-2,853,650`
  - loser saved：`499,380`
  - winner cut：`-3,353,030`
  - median next20 return：`22.1098%`
  - negative next20 share：`11.1111%`
- `adverse_price_oi_up_failure_shape`：`11` 行、`4` 天，remaining PnL `+2,110,870`，EOD exit proxy `-2,110,870`，negative next20 share `0%`。
- `adverse_price_oi_down_failure_shape`：`11` 行、`5` 天，remaining PnL `+742,780`，EOD exit proxy `-742,780`，negative next20 share `20%`。
- `signal_resilience_shape`：`23` 行、`9` 天，remaining PnL `+1,595,950`，EOD exit proxy `-1,595,950`，negative next20 share `0%`。
- 全部 pressure top-product lots：`61` 行、`25` 天，remaining PnL `+4,991,380`，EOD exit proxy `-4,991,380`，negative next20 share `8%`。

### worst pressure days by next20

- `2021-02-25` OI.CZCE long：price failure，next20 `-10.8417%`，future20 min `-12.7035%`，但 remaining PnL 仅 `+630`。
- `2023-11-10` jm.DCE long：分钟缺失，next20 `-3.3567%`，future20 min `-4.9271%`。
- `2022-01-05` OI.CZCE long：price failure，next20 `+0.1403%`，future20 min `-5.6071%`，remaining PnL `+25,000`。
- 结论：真正负的 pressure days 不多，且 price failure 结构没有把负样本集中起来。

### best pressure days by next20

- `2020-10-23` MA.CZCE long：price failure，但 next20 `+55.9349%`，future20 min `+8.8130%`。
- `2021-08-18` CF.CZCE long：price failure，remaining PnL `-494,700`，但 next20 `+48.6084%`。
- `2022-02-15` jm.DCE long：price failure，remaining PnL `+1,803,600`，next20 `+24.4108%`。
- `2020-11-23` AP.CZCE short：price failure，remaining PnL `+284,920`，next20 `+23.8621%`。
- 结论：不少“当日收弱”的高压样本仍是后续趋势右尾的一部分，不能实时退出。

## 视觉复核

- summary chart 非空：红色 price failure pressure days 并不集中在后续负 `next20`；散点左下角没有形成明确亏损簇。
- atlas page001 非空：展示 bad_price_failure 样本，确有当日信号侧收弱，但其中只有少数真正后续亏损。
- atlas page003 非空：展示 good_signal_resilience 样本，顺势收盘和 OI 上行确有右尾参与度，但这只能解释右尾，不能给出退出左尾的充分条件。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_report_stage886_stage885_pressure_failure_structure_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_decision_stage886_stage885_pressure_failure_structure_audit_v1.json`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_features_stage886_stage885_pressure_failure_structure_audit_v1.csv`
- day summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_day_summary_stage886_stage885_pressure_failure_structure_audit_v1.csv`
- state summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_state_summary_stage886_stage885_pressure_failure_structure_audit_v1.csv`
- shape proxy：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_shape_proxy_stage886_stage885_pressure_failure_structure_audit_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_summary_chart_stage886_stage885_pressure_failure_structure_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage886_stage885_pressure_failure_structure_audit_atlas_page001_stage886_stage885_pressure_failure_structure_audit_v1.png` 至 `page004`

## 结论

- Stage886 反证了“高压 + 当日分钟级收弱/区间弱位/逆向主导”作为直接退出规则。
- `price_failure_shape` 的 EOD 退出代理会少赚 `2,853,650`；它救下的亏损只有 `499,380`，但会误伤 `3,353,030` 的后续赢家。
- `adverse_price_oi_up` 和 `adverse_price_oi_down` 都不能单独作为充分失败条件；尤其 `adverse_price_oi_up` 的 negative next20 share 为 `0%`。
- `signal_resilience_shape` 可作为右尾参与度解释标签，但不是左尾退出标签。
- 不进入真实引擎、不触发 A/B、不做阈值救参。

## 过拟合反思

- 运行前判断：否。本阶段沿用 Stage885 pressure state，并只用方向收益、半区间收盘位置和 OI 正负做固定结构标签，没有扫参。
- 运行后判断：否。当前结论是反证，不靠筛年份/品种/方向救正；若继续拆 `price_failure_shape` 的具体品种、年份、OI 小数阈值或分钟窗口，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage885 已证明高压不是退出规则，但需要确认高压内部是否存在更细的分钟级失败结构。
- 运行后判断：作为退出规则继续价值低；作为认知标签仍有价值。下一步如果继续，不应再救 pressure-day close 弱势结构，而应转向“新开仓/加仓前的组合风险预算”或“高压状态下是否禁止新增 sleeve，而不是平掉既有右尾”这种更贴近问题本质的方向。

## 后续规划和 TODO

- 不接 Stage886 price failure 退出引擎。
- 不扫描 `0.25/0.5/0.75` close-location、OI 变化阈值、成交量阈值、分钟窗口、品种、方向或年份。
- 若继续本线，优先做一个只读审计：在 Stage883 sleeve 触发前，检查当时是否已处于或即将进入 Stage885 pressure state；目标不是平掉既有仓位，而是判断“新增 sleeve 是否应被组合压力闸门阻断”。
