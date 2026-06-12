# Stage813 Stage804 RSI 半平显式开关年度 A/B 纠错

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-12 00:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage812 口径 bug 修复；年度多起点显式 A/B
- 是否重要突破：否，但属于重要纠错
- 是否触发A/B：是。B=`Stage804 + enable_rsi_partial_exit=False`，C=`Stage804 + enable_rsi_partial_exit=True`

## 外部调研与判断

- 参考资料：本阶段不新增外部 alpha 资料；核心依据为本地代码审计和复现实验。定位到 `examples/portfolio_backtesting/run_qmt_roll_backtest.py` 中 `build_roll_setting()` 默认设置 `enable_rsi_partial_exit=True`，而 Stage804 profile 未显式覆盖为 `False`。
- 我的判断：用户质疑“0 差异不合理”是正确的。Stage812 不是交易半平无效，而是对照口径被默认 setting 污染；修正后 RSI 半平确实改变成交和权益路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无新策略参数
- 修改参数：纠错 A/B 中明确把 B 的 `enable_rsi_partial_exit=False`，C 的 `enable_rsi_partial_exit=True`、`rsi_partial_exit_threshold=95.0`、`rsi_partial_exit_ratio=0.5`
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01` 到 `2026-01`，统一终点 `2026-05-29`
- 账户规模：50万
- 成本口径：沿用 Stage804/Stage777 组合回测成本口径
- 样本过滤：全部年度起点 9 个；成熟样本排除 `2026-01` 后 8 个
- 策略/归因口径：Stage804 多头更紧初始止损，AM41、旧正式 AI 老师、OI 命中恢复风险资金到 `0.8`、基础等效 `0.4`、maxpos4、关闭连败缩放和 recovery sleeve 均不变；唯一变量为 RSI 半平显式开/关

## 结果

- 期末权益：代表 `2020-01` OFF `26,426,250` vs ON `27,577,760`；`2018-01` OFF `24,007,140` vs ON `26,293,495`；`2021-01` OFF `6,659,315` vs ON `6,393,110`
- 总收益：代表 `2020-01` OFF `5185.250%` vs ON `5415.552%`，ON `+230.302pp`；`2018-01` ON `+457.271pp`；`2021-01` ON `-53.241pp`
- 最大回撤：代表 `2020-01` OFF `-55.7666%` vs ON `-56.0975%`，ON `-0.3308pp`；`2018-01` ON `-3.1652pp`；`2025-01` ON `+6.2811pp`
- Sharpe：代表 `2020-01` OFF `1.5129` vs ON `1.5525`；`2018-01` OFF `1.3163` vs ON `1.3618`
- 总滑点：聚合中位差 `0`
- 总交易次数：成熟样本中位 ON-OFF `+3.5`
- 胜率：本脚本未汇总输出胜率；以收益、回撤、Sharpe、交易次数、RSI 事件作为本轮主判据
- 其他关键指标：全部 9 个起点 ON 收益胜出 `5/9`、回撤胜出 `3/9`、Sharpe 胜出 `6/9`、收益+回撤双胜 `2/9`；成熟 8 个起点 ON 收益胜出 `5/8`、回撤胜出 `3/8`、Sharpe 胜出 `6/8`。成熟样本收益中位差 `+13.692pp`、回撤中位差 `0`、Sharpe 中位差 `+0.0311`。DD40 失败 OFF `4`、ON `4`；DD50 失败 OFF `2`、ON `2`。ON 触发 RSI 半平 `31` 次、合计 `1520` 手；OFF 为 `0`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_report_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_summary_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv` 与 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_off_summary_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv`
- orders：无单独 orders 文件
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_curves_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv` 与 OFF curves
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_decision_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.json`

## 结论

- 本阶段结论：`stage813_stage804_rsi_partial_exit_not_promoted`。RSI 半平开关不是无效，它确实改变交易路径；但它不是稳健风控升级，因为 DD40/DD50 失败数量没有改善，且早期强右尾起点有回撤恶化。
- 是否进入下一步：不进入候选合入，不继续扫 RSI 阈值。
- 下一步：修正我们对 Stage804/812 的口径表述；若继续，只能做“默认 setting 污染防呆”和回测 profile 显式参数审计，不做 RSI 阈值优化。

## 过拟合反思

- 运行前判断：不是过拟合，是用户质疑触发的口径 bug 排查。
- 运行后判断：修正版本身不是过拟合；但若看到 ON 收益中位略好就继续扫 RSI 阈值或方向，会过拟合。
- 原因：ON 的收益提升来自少数早期右尾路径，风险失败数量并未改善。

## 继续价值反思

- 运行前判断：有价值，因为 `0` 差异与事件触发矛盾，必须排除研究口径 bug。
- 运行后判断：法证价值高，策略推进价值低。
- 原因：Stage812 被纠错，Stage813 给出真实 A/B；但结果不足以升级为正式候选。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 纠错摘要，不追加 `memory.md`。
