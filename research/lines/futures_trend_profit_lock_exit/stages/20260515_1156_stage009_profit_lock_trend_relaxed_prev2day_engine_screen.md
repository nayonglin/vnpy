# Stage009 锁盈趋势态放宽 prev2day_stop 引擎小屏

- line_id：`futures_trend_profit_lock_exit`
- 当前模式：`day`
- 记录时间：2026-05-15 11:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：完整组合引擎 A/C 小屏，验证 Stage278 提出的结构性假设
- 是否重要突破：否，属于有效反证
- 是否触发A/B：是

## 外部调研与判断

- 参考资料：调研了趋势跟踪退出、ATR/Chandelier trailing stop、均线趋势过滤与“let winners run”相关实现和讨论。
- 我的判断：外部经验支持“趋势仍强时给持仓更多波动空间”，但不支持无差别放宽止损。本阶段采用低自由度结构：仅当锁盈已激活且 MA20/MA40 趋势仍同向时，跳过 `prev2day_stop`，其余退出不关闭。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `enable_profit_lock_trend_relaxed_prev2day_stop=False`
  - `profit_lock_trend_relax_trigger_pct=0.05`
  - `profit_lock_trend_relax_ma_fast=20`
  - `profit_lock_trend_relax_ma_slow=40`
  - `profit_lock_trend_relax_slope_days=3`
- 修改参数：无正式参数修改，默认开关关闭，正式 78-1 行为保持不变。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`，并含 `since_2022`、`since_2025`、`since_2026`、`2025-08-01~2025-11-30`、`2022-10-01~2023-09-30`。
- 账户规模：`500,000`
- 成本口径：沿用 Stage78-1 组合回测口径，报告记录总滑点；手续费为当前引擎口径 `0`。
- 样本过滤：沿用正式 Stage78-1 品种池、月度 AI 池和主力换月逻辑。
- 策略/归因口径：
  - A：`official_stage78_1_defensive_50w_no_sizing_cap`
  - C：A + 锁盈已激活且 MA20/MA40 趋势同向时跳过 `prev2day_stop`

## 结果

- A 全周期期末权益：`26,353,935`
- A 总收益：`5170.79%`
- A 最大回撤：`-40.17%`
- A Sharpe：`1.1374`
- A 总滑点：`2,057,380`
- A 总交易次数：`883`
- A 胜率：`43.36%`
- C 全周期期末权益：`18,594,465`
- C 总收益：`3618.89%`
- C 最大回撤：`-50.87%`
- C Sharpe：`0.9809`
- C 总滑点：`1,520,250`
- C 总交易次数：`871`
- C 胜率：`42.38%`
- 其他关键指标：
  - `total_relaxed_prev2day_skip_count=1754`
  - `window_win_count=1/6`
  - `dd_ok_count=3/6`
  - `weak_ok_count=2/2`
  - `full_end_minus_a=-7,759,470`
  - `full_dd_minus_a_pct=-10.70pp`
  - `since_2026_end_minus_a=-8,930`
  - 判定：`pass_engine_screen=false`，`next_step=reject_do_not_promote`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_report_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_summary_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_decision_stage279_profit_lock_trend_relaxed_prev2day_engine_screen_v1.json`

## 结论

- 本阶段结论：放宽 `prev2day_stop` 的开关真实触发，说明机制有效进入交易路径；但它显著降低全周期收益并扩大回撤，说明当前 `prev2day_stop` 对组合风险有实际保护作用，不能因为少数趋势延续案例就全局放宽。
- 是否进入下一步：否。
- 下一步：不做 Stage280；停止这条“锁盈趋势态直接跳过 prev2day_stop”的形状。若继续研究退出机制，应转向更严格的“降仓/延迟一日确认/账户层风险预算”而不是直接跳过止损。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：继续沿这个形状调 MA 参数或触发阈值会过拟合。
- 原因：C 组在全周期、2022 后、2025 后均输给 A，只有 `2025-08~2025-11` 一个弱窗口略胜；若继续调 `5%/MA20/MA40/3日斜率`，本质是在补丁式贴合历史走势。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该候选不值得继续，但本阶段有研究价值。
- 原因：它回答了 Stage278 的关键怀疑：`prev2day_stop + 已锁盈` 确实会截断一部分趋势，但它也承担组合风险刹车功能；简单放宽不是正确方向。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录为 Stage009 有效反证。
- 是否更新 `research/registry.md`：是，更新当前状态与下一步。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
