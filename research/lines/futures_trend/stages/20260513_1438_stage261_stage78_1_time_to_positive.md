# Stage261 Stage78-1 多周期转正等待期评测

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-13 14:38
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定正式版本路径评估 / 多周期冷启动体验审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen, *A Century of Evidence on Trend-Following Investing*：长期趋势跟踪在跨资产与跨宏观环境中有正期望证据，但不意味着每个短窗口都平滑。
  - `backtesting.py` 文档/GitHub：主流回测框架会把 `Max. Drawdown Duration` / `_equity_curve` 作为常规路径风险指标。
- 我的判断：
  - 本阶段应重点看“首次转正等待”和“水下期”，而不是只看期末收益。
  - 当前 2026 段更像趋势策略的短期水下体验问题，不应直接通过调参修补；需要和历史冷启动分布比较。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage261_stage78_1_time_to_positive.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；脚本参数 `--analysis-end`、`--capital`、`--ai-eligibility-path`、`--annual`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：季度冷启动窗口从 `2020-01-01` 到 `2026-04-01`，统一评估至 `2026-05-12`
- 账户规模：`500,000`
- 成本口径：沿用 Stage78-1 默认滑点/手续费口径，手续费为 0，滑点按合约配置
- 样本过滤：26 个季度冷启动窗口
- 策略/归因口径：`official_stage78_1_defensive_50w_no_sizing_cap` + Stage182 最新月度 AI 池文件

## 结果

- 期末权益：多窗口不适用；当前 2026Q1 冷启动为 `407,220`
- 总收益：当前 2026Q1 冷启动为 `-18.5560%`
- 最大回撤：当前 2026Q1 冷启动为 `-31.5769%`；全窗口最差为 `-44.0420%`
- Sharpe：当前 2026Q1 冷启动为 `-1.1078`（Stage261日度口径）
- 总滑点：当前 2026Q1 冷启动为 `5,200`
- 总交易次数：当前 2026Q1 冷启动为 `31`
- 胜率：未在本阶段重新统计
- 其他关键指标：
  - 26 个季度冷启动中 25 个曾实现权益高于本金，1 个尚未转正（2026Q2）
  - 已转正窗口最长等待：`256` 个交易日 / `384` 个自然日（2022Q2 启动）
  - 已转正窗口等待中位数：`4` 个交易日
  - 90 分位等待：约 `32.4` 个交易日
  - 全窗口最长水下期：`268` 个交易日
  - 当前 2026Q1 曾于 `2026-01-14` 首次转正，但从 `2026-01-30` 至 `2026-05-12` 持续水下 `63` 个交易日

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage261_stage78_1_time_to_positive_report_stage261_stage78_1_time_to_positive_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage261_stage78_1_time_to_positive_summary_stage261_stage78_1_time_to_positive_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage261_stage78_1_time_to_positive_daily_stage261_stage78_1_time_to_positive_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage261_stage78_1_time_to_positive_summary_stage261_stage78_1_time_to_positive_v1.json`

## 结论

- 本阶段结论：
  - 如果严格按“首次权益超过本金”定义，2026Q1 冷启动并不异常，因为第 8 个交易日已经短暂转正。
  - 如果按用户真正关心的“当前从高点回撤后多久没恢复”定义，2026Q1 当前 `63` 个交易日水下，已经明显长于常见转正等待中位数，但仍低于历史最长水下 `268` 个交易日，也低于 2022Q2 这种 256 个交易日才首次转正的极端冷启动。
  - 当前表现符合趋势策略可能出现的困难窗口，但已经足够进入 `review` 观察，不宜加仓或新增实盘风险。
- 是否进入下一步：是
- 下一步：
  - 每日影子盘继续记录当前水下天数、是否恢复本金、是否恢复 2026-01-29 高水位。
  - 若当前水下期接近 `126` 交易日仍未修复，应升级为专项复盘。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：固定 Stage78-1 与最新 AI 池，只统计不同启动日期的路径指标，没有用结果反向修改品种、参数或风控线。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：当前 2026 亏损体验是实盘心理与风控边界的核心问题；该结果能把“难受”量化为历史分布中的位置。

## 合入建议

- 是否更新本线 `LINE.md`：建议追加 Stage261 摘要
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，当前是路径体验审计，不是正式候选变更
