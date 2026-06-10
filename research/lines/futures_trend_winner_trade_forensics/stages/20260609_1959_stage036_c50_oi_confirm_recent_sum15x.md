# Stage036 Stage757 增加5日OI合计1.5倍过滤

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-09 19:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 策略回测，基于 Stage757 增加 OI 恢复的较强过滤条件
- 是否重要突破：否
- 是否触发A/B：是，风险放大规则可能被误认为可接正式或进入下一验证

## 外部调研与判断

- 参考资料：
  - CME Open Interest：`https://www.cmegroup.com/education/lessons/open-interest`
  - Britannica Volume & Open Interest：`https://www.britannica.com/money/futures-volume-open-interest`
  - GitHub futures trend-following 模板：`https://github.com/quantiacs/strategy-futures-trend-following`
- 我的判断：公开资料支持“价格同向 + OI 上升”作为趋势确认或趋势强度参考，但没有资料支持“最近5日 OI 合计必须是前5日 1.5倍”是普世阈值。本阶段只做用户在 2.0 完全不触发后提出的单点验证，不展开阈值扫描。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage762_c50_oi_confirm_recent_sum15x.py`
- 修改脚本：无新增策略核心修改，复用 Stage761 已加入的默认关闭 OI 合计比例参数
- 删除脚本：无
- 新增参数：无
- 修改参数：
  - `oi_price_confirm_risk_restore_recent_sum_min_ratio` 从 `2.0` 改为 `1.5`
  - 保持 `oi_price_confirm_risk_restore_recent_sum_days=5`
  - 保持 `risk_multiplier=0.40`、命中恢复到等效 `0.80`、关闭连败缩放和 recovery sleeve
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：基础成本、2x 成本、3x 成本压力
- 样本过滤：全周期日线；OI 合计条件使用策略内同一 `history["open_interest"]` 字段，取最新 `5` 根已完成日线合计与再前 `5` 根合计比较
- 策略/归因口径：
  - 先满足 Stage757 原 OI 条件：价格沿交易方向且 OI 上升
  - 再要求 `recent_5_oi_sum >= prior_5_oi_sum * 1.5`
  - 两者同时满足才把风险从等效 `0.40` 恢复到 `0.80`
  - 不改信号、不改 AI 池、不改品种池、不改退出

## 结果

- 期末权益：`5,756,760`
- 总收益：`1051.3520%`
- 最大回撤：`-40.7337%`
- Sharpe：`1.3311`
- 总滑点：`489,560`
- 总交易次数：`686`
- 胜率：非零交易日胜率 `52.9711%`
- 其他关键指标：
  - 相对 Stage748 C50：期末权益多 `191,410`，收益多 `38.282pp`，最大回撤恶化 `1.0256pp`，Sharpe 多 `0.0026`，滑点多 `19,310`
  - 相对 Stage757：期末权益少 `3,814,300`，收益少 `762.860pp`，最大回撤改善 `0.9121pp`，Sharpe 少 `0.1199`
  - Stage762 仍破 DD40，且 2x 成本压力下最大回撤为 `-44.0518%`
  - 原 OI 同向确认但未通过 1.5倍合计条件：`117` 行
  - 实际恢复仓位：`7` 笔，覆盖 `5` 个品种、`3` 个年份
  - 恢复仓位样本：盈利 `4`、亏损 `3`，胜率 `57.1429%`，总 realized PnL `+538,880`，平均 R `3.1733`，中位 R `0.4102`
  - 恢复仓位年份分布：`2020` 4笔 `+3,440`，`2021` 2笔 `+553,640`，`2022` 1笔 `-18,200`，`2023-2026` 无触发
  - 2x 成本：`5,267,200/953.4400%/-44.0518%/Sharpe1.2376`
  - 3x 成本：`4,777,640/855.5280%/-47.5838%/Sharpe1.1448`
  - 决策：`c50_oi_confirm_recent_sum15x_not_promoted`
  - hard fail：`candidate_full_dd40_fail_vs_stage748`、`candidate_cost2_deployable_fail`
  - watch fail：`restore_sample_lt30`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_report_stage762_c50_oi_confirm_recent_sum15x_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_summary_stage762_c50_oi_confirm_recent_sum15x_v1.csv`
- orders：无单独 orders 输出；使用 closed lots 和 curve 输出
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_curve_stage762_c50_oi_confirm_recent_sum15x_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_closed_lots_stage762_c50_oi_confirm_recent_sum15x_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_restore_group_stats_stage762_c50_oi_confirm_recent_sum15x_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage762_c50_oi_confirm_recent_sum15x_recent_sum_reason_stats_stage762_c50_oi_confirm_recent_sum15x_v1.csv`

## 结论

- 本阶段结论：`1.5倍` 比 `2倍` 能释放少量交易，但只恢复 `7` 笔，且收益主要来自 `2021` 的两笔右尾；全周期只比 Stage748 多 `19.141万`，代价是 DD40 失败和成本压力失败。它不是可穿越周期的高质量机会识别器。
- 是否进入下一步：不进入交易化验证
- 下一步：停止围绕 `1.5/2.0` 硬倍数做救参；如果继续 OI，应转成只读分布研究或多因子 watch，先要求覆盖 2023-2026 与多起点稳定性。

## 过拟合反思

- 运行前判断：有过拟合风险，但可做一次单点，因为 Stage761 已显示 `1.5` 接近原 OI 候选分布 p95，不是无边界扫描。
- 运行后判断：不应接入；继续扫 `1.4/1.45/1.55` 会明显过拟合。
- 原因：实际触发只有 `7` 笔，年份覆盖停留在 `2020-2022`，且收益高度依赖少数右尾，无法证明跨周期普适性。

## 继续价值反思

- 运行前判断：有有限价值，可验证强 OI 聚集是否能过滤 Stage757 左尾。
- 运行后判断：该具体倍数条件无继续价值。
- 原因：样本过少、覆盖年份不足、DD40 与 2x 成本均失败；它没有解决 Stage757 的本质问题，只是把多数 OI 恢复交易关掉。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`
