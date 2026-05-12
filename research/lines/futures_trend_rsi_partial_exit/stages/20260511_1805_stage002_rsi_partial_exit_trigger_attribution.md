# Stage002 RSI分批止盈触发归因（Stage248）

- line_id：`futures_trend_rsi_partial_exit`
- 当前模式：`day`
- 记录时间：`2026-05-11 18:05`
- 阶段性质：归因审计
- 是否重要突破：否

## 外部调研与判断

- 本阶段未新增外网/GitHub 调研。
- 原因：这一步是对 Stage247 负结论做仓内归因，关键在于核对真实触发次数、触发后的后续价格路径，以及 ON/OFF 右尾分布变化。
- 我的判断：
  - 如果触发频率很低，但少数触发事件正好砍在大赢家中段，那么它依然会显著伤害长期复利。
  - 趋势系统不怕“小止盈很多次”，怕的是“少数右尾大单被截掉”。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage248_stage78_1_rsi_partial_exit_off_full.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage248_rsi_partial_exit_trigger_attribution.py`
- 说明：
  - `Stage248 off_full` 用于生成“显式关闭 RSI 分批止盈”的完整 trades/daily 产物，避免被默认 setting 污染。
  - `analyze_stage248...` 用于按持仓级别统计触发事件，并估算“提前减半”相对“持有到后续正常退出”的 giveback 金额。

## 归因口径

- ON：当前官方 `78-1` trades
- OFF：显式 `enable_rsi_partial_exit=False` 的 full-period trades
- 触发识别：`exit_reason` 包含 `long_rsi_partial_exit_half / short_rsi_partial_exit_half`
- 截断估算：
  - 对每个触发持仓，取“触发减半那部分手数”
  - 假设若不提前减半，这部分手数会以该持仓后续实际平仓成交的成交量加权均价退出
  - 若后续均价优于触发价，则记为正的 `estimated_giveback_cash`

## 结果

- 触发条数（trade-level）：`11`
- 触发涉及持仓数（position-level）：`11`
- 估算被截断收益（giveback 现金合计）：`943,390`

触发后“明显截断右尾”的代表：

- `SM409.CZCE`：
  - 触发减半：`250` 手，触发价 `7,076`
  - 后续均价：`8,216`
  - 估算被截断收益：`1,425,000`
- `lh2605.DCE`：
  - 触发减半：`100` 手，触发价 `9,985`
  - 后续均价：`9,480`
  - 这是空头持仓，后续价格继续下行
  - 估算被截断收益：`808,000`
- `FG109.CZCE`：
  - 估算被截断收益：`184,500`

也有“提前减半反而正确”的个例：

- `jm2509.DCE`：估算 `-1,462,500`
- `sp2012.SHFE`：估算 `-16,280`

但总体合计仍然为正，说明整体上更偏向“砍掉右尾”，而不是系统性地更好锁盈。

## 右尾分布对比

- OFF：
  - 持仓数：`433`
  - 总 PnL：`29,805,320`
  - 赢家总 PnL：`62,244,670`
  - `p90 / p95 / p99`：`840,000 / 1,248,380 / 3,910,640`
- ON：
  - 持仓数：`436`
  - 总 PnL：`26,830,645`
  - 赢家总 PnL：`57,797,425`
  - `p90 / p95 / p99`：`772,800 / 1,104,400 / 2,674,640`

结论：

- ON 相比 OFF，`p90/p95/p99` 全部下降，尤其 `p99` 从 `391万` 降到 `267万`。
- 这说明右尾不仅被削弱，而且是在最关键的大赢家层面被明显压扁。

## 输出文件

- report：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage248_rsi_partial_exit_trigger_attribution_report_stage248_rsi_partial_exit_trigger_attribution_v1.md`
- summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage248_rsi_partial_exit_trigger_attribution_summary_stage248_rsi_partial_exit_trigger_attribution_v1.json`
- triggers：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage248_rsi_partial_exit_trigger_attribution_triggers_stage248_rsi_partial_exit_trigger_attribution_v1.csv`
- position_summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage248_rsi_partial_exit_trigger_attribution_position_summary_stage248_rsi_partial_exit_trigger_attribution_v1.csv`
- tail_summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage248_rsi_partial_exit_trigger_attribution_tail_summary_stage248_rsi_partial_exit_trigger_attribution_v1.csv`

## 结论

- `RSI>95 减半` 的触发频率并不高，但它确实在少数关键大赢家上过早兑现利润。
- 它不是“普遍提高了锁盈效率”，而是“用少量错误的大单截断，换来一点点回撤改善”。
- 结合 Stage247 的主结论，可以更有把握地说：该规则不适合并入 `78-1` 默认基准。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只做触发事实统计与归因，不做参数搜索或结果驱动调参。

## 继续价值反思

- 运行前判断：是
- 运行后判断：否
- 原因：已经拿到足够强的负面证据，说明该方向对 `78-1` 的长期右尾不友好；继续调阈值/比例大概率是在做局部过拟合。

