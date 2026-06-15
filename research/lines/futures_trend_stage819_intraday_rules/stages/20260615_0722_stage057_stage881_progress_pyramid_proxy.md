# Stage057 Stage881 C9 `+0.5R` 顺势加仓只读代理审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 07:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读代理审计；不改策略、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否，当前只是强上限线索。
- 是否触发A/B：否；已读取 `skills/version-ab-experiment/SKILL.md`，本阶段不是正式 A/B/C，也不是可推广版本。

## 外部调研与判断

- 参考资料：
  - `https://github.com/vnpy/vnpy`
  - Turtle/trend-following pyramiding 规则资料
  - `https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf`
- 我的判断：
  - 过去 Stage867-880 主要在“少亏、过滤、提前退出”里找规则，连续误伤右尾。
  - 趋势跟随的第一性原则是让右尾变厚，而不是反复过滤亏损样本；pyramiding 只有在已有浮盈后加仓，并给新增仓设置明确止损，才有穿越周期的理由。
  - 因此本阶段只用 C9 已存在的 `+0.5R` progress 单位，不新增小数阈值、不扫加仓比例、不按品种/年份/方向过滤。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage881_stage863_progress_pyramid_proxy_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `PYRAMID_PROGRESS_R = 0.5`
  - `PYRAMID_ADD_VOLUME_MULTIPLIER = 1.0`
  - 新增仓止损：原始入场价。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage863/C9 全周期 `2018-01-01` 至 `2026-05-29`。
- 账户规模：Stage819 候选 `30w` 口径。
- 成本口径：读取 Stage863 C9 closed lots，不新增组合成交成本；新增仓只做代理 PnL，不计资金路径。
- 样本过滤：
  - 仅取 `arm == stage847_stage819_c4_05r_stop_retry_once` 的 C9 closed lots。
  - closed lots `401`，其中 entry-day 分钟K有效 `393`。
  - 分钟K读取 Stage861 full minute bars。
- 策略/归因口径：
  - 若入场日先触达 `+0.5R` progress，假设在 `+0.5R` 价位加一笔同手数仓。
  - 新增仓止损放在原始入场价；若同根或同日后续触发，则新增仓止损退出。
  - 若 entry-day 未触发新增仓止损，则代理按原始 C9 closed lot 的最终退出价退出新增仓。
  - 这是只读代理，不含新增仓保证金、后续逐日止损、资金联动、broker10 路径或真实组合成交顺序。

## 结果

- 期末权益：不适用，本阶段不是组合回测；参考 C9 为 `50,637,144.6`。
- 总收益：不适用；参考 C9 为 `16,779.0482%`。
- 最大回撤：不适用；参考 C9 为 `-42.6313%`。
- Sharpe：不适用；参考 C9 为 `1.6312`。
- 总滑点：不适用；参考 C9 为 `3,607,030`。
- 总交易次数：不适用；参考 C9 为 `786`。
- 胜率：不适用；参考 C9 为 `53.5299%`。
- 其他关键指标：
  - all_lots：`401`
  - valid_entry_day_lots：`393`
  - pyramid_candidate_lots：`176`
  - pyramid_candidate_pct：`43.8903%`
  - base_closed_lot_pnl：`53,950,264.6`
  - pyramid_proxy_delta：`+34,513,422.1`
  - proxy_closed_lot_pnl：`88,463,686.7`
  - candidate_original_pnl：`54,660,533.1`
  - candidate_big_winner_lots：`23`
  - held_to_original_exit_lots：`99`
  - entry_day_stop_lots：`76`
  - same_bar_stop_lots：`1`
  - pyramid_positive_lots：`67`
  - pyramid_negative_lots：`109`
  - pyramid_risk_cash：`16,343,686.0`

### 状态拆分

| 状态 | 笔数 | 新增仓代理PnL | 说明 |
| --- | ---: | ---: | --- |
| `held_to_original_exit` | `99` | `+39,780,918.6` | 右尾核心来源 |
| `entry_day_stop` | `76` | `-5,072,496.5` | 加仓后同日回打原始入场价，新增仓止损 |
| `same_bar_stop` | `1` | `-195,000.0` | 同根保守止损 |
| `not_candidate` | `225` | `0.0` | 未先触达 `+0.5R` 或数据/风险无效 |

### 年度拆分

- 正贡献年份：`2018/2019/2020/2021/2023/2024/2025`
- 负贡献年份：`2022/2026`
- 最大正贡献：`2025 +14,171,395.0`
- 主要风险：`2022 -170,845.1`、`2026 -261,204.4`，说明真实引擎必须做 weak-window 与 broker10 路径审计。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_report_stage881_stage863_progress_pyramid_proxy_audit_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_features_stage881_stage863_progress_pyramid_proxy_audit_v1.csv`
- state_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_state_summary_stage881_stage863_progress_pyramid_proxy_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_yearly_stage881_stage863_progress_pyramid_proxy_audit_v1.csv`
- summary_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_summary_chart_stage881_stage863_progress_pyramid_proxy_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_manifest_stage881_stage863_progress_pyramid_proxy_audit_v1.csv`
- atlas：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page001_stage881_stage863_progress_pyramid_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page002_stage881_stage863_progress_pyramid_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page003_stage881_stage863_progress_pyramid_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_atlas_page004_stage881_stage863_progress_pyramid_proxy_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage881_stage863_progress_pyramid_proxy_audit_decision_stage881_stage863_progress_pyramid_proxy_audit_v1.json`

## 结论

- 本阶段结论：`stage881_progress_pyramid_proxy_only_needs_true_engine_before_any_promotion`
- 是否进入下一步：进入一次冻结真实引擎设计审计，但不进入 A/B、不进入正式候选。
- 下一步：
  - 只允许一个真实引擎版本：`C9 + 入场日先触达 +0.5R 后同手数加仓一次 + 新增仓原入场价止损`。
  - 真实引擎必须输出权益曲线、回撤、Sharpe、滑点、交易次数、胜率、broker10、pyramid events、closed lots 和 atlas。
  - 若真实引擎不能改善 C9 的收益/回撤/Sharpe/broker10 组合，停止 pyramiding 分支；不得继续扫 `0.25R/0.5R/1R`、加仓比例、止损位置、品种、方向或年份。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：代理本身不是过拟合，但现在最容易犯的错误是把上限代理当策略结果。
- 原因：
  - 固定使用 C9 已有 `+0.5R`，没有扫新阈值。
  - 规则来自右尾增厚的一阶趋势跟随原则，而非从某个亏损窗口反推。
  - 但代理没有保证金、资金联动和新增仓后续逐日止损，真实引擎可能显著低于代理上限。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，且是 Stage879/880 后少数值得继续的方向。
- 原因：
  - 代理增量 `+34,513,422.1` 足够大，且来自 `held_to_original_exit` 的右尾延展。
  - 风险也可见：`entry_day_stop + same_bar_stop` 合计 `-5,267,496.5`，年度 `2022/2026` 为负，必须用真实引擎检验是否只是右尾年份驱动。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage057 和唯一允许下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段未跑真实组合回测；若下一阶段真实引擎成为可推广候选，再按 `version-ab-experiment` 写 `back_log.md`。
