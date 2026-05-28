# Stage133 xsmom趋势质量过滤审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 02:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定结构 A/B/C 审计；不改 Stage079/C3，不扫小数阈值。
- 是否重要突破：否。出现 Stage079 目标下可行的备选，但不优于当前主候选 Stage103。
- 是否触发A/B：是。A=Stage079；C0=Stage103；C1=63日方向一致性>=50%；C2=每日方向一致性Top半数。

## 外部调研与判断

- 参考资料：
  - 商品期货动量、周度动量、carry/momentum 组合研究支持“动量不是单一形状”，但也提示必须考虑成本、期限结构和风险预算。
  - 公开动量实现里常见 FIP/Frog-in-the-Pan、趋势一致性、skewness filter 等思路，用于区分平滑持续趋势和少数跳涨驱动的动量。
  - GitHub 上可见 `Momentum-Investing` 这类实现使用 FIP score、skewness 和 inverse volatility weighting，但未找到可直接迁移到本地中国期货、整数手和保证金口径的现成实现。
- 我的判断：
  - Stage104 已显示短持有坏窗口常发生在强趋势暴涨后反转，说明“趋势质量”比“动量强度”更接近问题本质。
  - 本阶段只测试两个自然形状：同方向日数过半、以及每天取方向一致性最高半数；不测试 `55%/60%`、`20/126日`、Top比例等相邻小数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage433_xsmom_trend_quality_filter.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `xsmom_fip63_positive_broker10_guard`：xsmom 信号方向与过去63日单日涨跌方向一致性 `>=50%` 时才执行。
  - `xsmom_fip63_tophalf_broker10_guard`：每天只执行方向一致性最高的半数 xsmom 信号。
  - 两者均沿用 Stage103 的 `1.10x` 保证金闸门。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-05-25`，并复用研究线内多起点窗口。
- 账户规模：`615,000`，即 Stage079 的 `50万C3下单 + 11.5万外部现金`。
- 成本口径：沿用真实整数手日度滑点，并补 `1x/2x/3x/5x` 成本压力。
- 样本过滤：无。
- 策略/归因口径：只读重构 Stage079、Stage103、两个 xsmom 趋势质量过滤候选。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 非零日胜率 | 3个月分 | 6个月分 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 | `31,040,650` | `4947.2602%` | `-29.7007%` | `1.3188` | `15.0874` | `1,556,750` | `757` | `48.3478%` | `100.0000` | `100.0000` | baseline |
| Stage103 | `31,730,915` | `5059.4984%` | `-28.9792%` | `1.3681` | `14.3132` | `1,569,265` | `1,217` | `50.3432%` | `121.2041` | `134.4513` | 当前主候选 |
| FIP63 positive | `31,614,185` | `5040.5179%` | `-30.0720%` | `1.3565` | `14.6482` | `1,569,890` | `1,217` | `50.3432%` | `110.9771` | `109.9040` | 硬失败 |
| FIP63 top half | `31,616,485` | `5040.8919%` | `-29.4105%` | `1.3500` | `14.6306` | `1,569,515` | `1,209` | `49.5805%` | `112.8137` | `123.0380` | Stage079目标过线，但不替代Stage103 |

## 3/6个月关键对比

- `FIP63 top half` 相对 Stage079：
  - 3个月体验分 `112.8137`，改善 `12.81%`，改善项 `5/8`。
  - 6个月体验分 `123.0380`，改善 `23.04%`，改善项 `6/8`。
  - 全周期硬约束、rolling252/504、年度/季度冷启动、成本压力均通过。
- 但相对 Stage103：
  - 总收益少约 `18.6065pp`。
  - 最大回撤更深：`-29.4105%` vs `-28.9792%`。
  - Sharpe 更低：`1.3500` vs `1.3681`。
  - Ulcer 更高：`14.6306` vs `14.3132`。
  - 3个月/6个月分更低：`112.8137/123.0380` vs `121.2041/134.4513`。
  - 剔除最大相对 Stage103 正贡献日之前，收益差已为 `-18.6253pp`。

## 关键反证

- `FIP63 positive`：
  - 最大回撤 `-30.0720%`，破 30%。
  - rolling252/504 破30率升至 `0.0976/0.2506`，年度/季度通过率降到 `80.00%/77.27%`。
  - 判定硬失败，禁止继续救 `55%/60%` 方向一致性阈值。
- `FIP63 top half`：
  - 虽然通过 Stage079 目标，但不是 Stage103 升级。
  - `start_2020/start_2021` 的 1.10x 绝对保证金仍有拒单，且所需额外现金 `98,110.70/45,578.30` 高于 Stage103 的 `13,665.70/18,171.91`。
  - 它减少了 xsmom 持仓数量，降低了噪声，也削弱了有效趋势收益。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_report_stage433_xsmom_trend_quality_filter_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_summary_stage433_xsmom_trend_quality_filter_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_horizon_stage433_xsmom_trend_quality_filter_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_score_stage433_xsmom_trend_quality_filter_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_margin_audit_stage433_xsmom_trend_quality_filter_v1.csv`
- topday：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_top_edge_day_ablation_stage433_xsmom_trend_quality_filter_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_quality_panel_stage433_xsmom_trend_quality_filter_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_daily_stage433_xsmom_trend_quality_filter_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_chart_stage433_xsmom_trend_quality_filter_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage433_xsmom_trend_quality_filter_decision_stage433_xsmom_trend_quality_filter_v1.json`

## 结论

- 本阶段结论：决策 `trend_quality_candidate_found`，但只代表 Stage079 目标下有备选；不代表替代 Stage103。
- 是否进入下一步：不作为主候选晋级。可保留为“低持仓、低近期保证金压力”的 paper 对照。
- 下一步：当前主执行相对候选仍是 Stage103；趋势质量过滤不继续扫阈值、窗口或Top比例。后续若继续主动研究，应寻找真正不同收益源，而不是削弱 Stage103 的有效 xsmom 暴露。

## 过拟合反思

- 运行前判断：不是过拟合。方向来自外部动量质量先验和 Stage104 的坏窗口归因，且只测试两个自然形状。
- 运行后判断：不是过拟合。没有因为 `top half` 过线就继续调比例，也没有救 `positive` 的阈值。
- 原因：本阶段主动承认其不如 Stage103，而不是按 Stage079 口径强行晋级。

## 继续价值反思

- 运行前判断：有价值。它直接针对“跳跃型动量/暴涨后反转”这一短持有体验缺口。
- 运行后判断：该子路线继续主动优化价值低；总目标仍有价值。
- 原因：过滤后减少噪声也减少有效趋势收益，无法成为 Stage103 的升级方向。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage133 执行约束。
- 是否更新 `research/registry.md`：否，未产生新主候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；`memory.md` 可不追加，因不是正式候选或关键突破。
