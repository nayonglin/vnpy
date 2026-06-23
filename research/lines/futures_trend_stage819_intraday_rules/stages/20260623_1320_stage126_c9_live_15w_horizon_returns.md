# Stage126 C9 当前实盘15万半年起点收益分布

> 修正说明（2026-06-23 13:53 CST）：本记录中的数值已被 Stage128 作废。原因是 Stage901 `_run_live_c9()` 当时未注入 Stage861 全量分钟K，导致 C9 分钟级 stop/retry 没有参与回放。修正后的半年/一年分布见 `20260623_1353_stage128_stage901_minute_bar_injection_fix.md`。

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 13:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前实盘版本的启动时点敏感性回测统计
- 是否重要突破：否。它不改变策略，只把当前 live 口径的半年/一年启动收益分布量化。
- 是否触发A/B：否。本阶段不引入新策略、不替换实盘版本、不调整参数。

## 外部调研与判断

- 参考资料：
  - VeighNa/vn.py GitHub README：vn.py/VeighNa 是 Python 量化交易开发框架，适合继续使用本仓库既有 vn.py 回测/实盘一体化引擎，而不是切换外部 backtester。
  - Interactive Brokers Campus walk-forward analysis 文章：滚动/步进验证用于检查策略是否依赖单一起点路径。
  - QuantInsti walk-forward optimization 资料：walk-forward 的价值在于按时间推进做分段验证，但验证窗口本身不能被反复调优。
- 我的判断：本次应该用本仓库 Stage901 当前 live profile 重放，而不能复用 Stage928 旧曲线直接下结论；原因是 Stage109 后当前实盘已合并 `build_official_live_strategy_overrides()`，实际接入 Stage182 月更 AI 池。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns.py`
  - `examples/portfolio_backtesting/visualize_qmt_roll_stage936_c9_live_15w_horizon_returns.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增分析常量 `REQUESTED_START=2020-01-01`、`START_MONTHS=(1,7)`、`HORIZONS=(6,12)`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：每个起点独立冷启动，最多跑到启动后一年；最新完整数据日固定 `2026-06-15`。
- 账户规模：`150,000`
- 成本口径：1x 原始成本/滑点；本阶段只统计 horizon 收益分布。
- 样本过滤：从 `2020-01-01` 起，每年 `1月1日` 和 `7月1日` 为起点；只统计完整 horizon。半年样本 `12` 个，一年样本 `11` 个；`2026-01` 因未满完整半年被排除。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`，通过 Stage901 `_run_live_c9()` 构造 live profile；实际 AI 池路径为 Stage182 月更文件，覆盖 `2019-12-31` 到 `2026-05-29` 共 `52` 个 eval_date，最新池品种为 `SA/si/FG/MA/OI/jm/AP/rb/fu`。
- horizon 取点规则：周年日当天若非交易日，取周年日之前或当天的最后一个交易日，不向后看。

## 结果

- 期末权益：
  - 半年：最小 `110,370`，中位 `170,370`，最大 `386,790`
  - 一年：最小 `101,730`，中位 `203,985`，最大 `792,765`
- 总收益：
  - 半年：最低 `-26.42%`，中位 `13.58%`，最高 `157.86%`
  - 一年：最低 `-32.18%`，中位 `35.99%`，最高 `428.51%`
- 最大回撤：
  - 半年 horizon 内最差 `-35.1231%`
  - 一年 horizon 内最差 `-40.7369%`
- Sharpe：不适用。本阶段统计的是多个固定 horizon 的启动收益分布，不计算单一连续路径 Sharpe。
- 总滑点：
  - 半年样本合计 `35,770`
  - 一年样本合计 `83,160`
- 总交易次数：
  - 半年样本合计 `435`
  - 一年样本合计 `833`
- 胜率：
  - 半年正收益 `11/12 = 91.67%`
  - 一年正收益 `10/11 = 90.91%`
- 其他关键指标：
  - 半年最差起点：`2022-01`，实际取点 `2022-07-01`，收益 `-26.42%`
  - 半年最好起点：`2021-01`，实际取点 `2021-07-01`，收益 `157.86%`
  - 一年最差起点：`2022-01`，实际取点 `2022-12-30`，收益 `-32.18%`
  - 一年最好起点：`2021-01`，实际取点 `2021-12-31`，收益 `428.51%`
  - 半年 horizon broker10 峰值 `78.2210%`，一年 horizon broker10 峰值 `80.0860%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_report_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_stats_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- orders：不适用；本阶段不生成订单、不连接 CTP、不调用下单 API。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_curves_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_decision_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.json`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_dashboard_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.png`

## 结论

- 本阶段结论：当前 live 口径下，2020 起每半年启动的半年/一年收益中位数仍为正，说明不是只能靠单一起点；但 2022-01 启动无论半年还是一年都明显亏损，实盘心理预期不能按右尾年份理解。
- 是否进入下一步：是，但下一步应继续真实成交、TCA、保证金和自动化闸门监控，不应根据这组窗口调整 C9 参数。
- 下一步：把该分布作为实盘沟通的基线；如果后续真实路径落入最差半年的附近，应优先核对成交偏差、保证金和 AI 池更新，而不是直接改策略。

## 过拟合反思

- 运行前判断：否。起点计划、资金、当前 live override 和半年/一年 horizon 都是预先固定，未调任何策略参数。
- 运行后判断：否。本次只是对固定 live 口径做启动时点敏感性统计；但样本数量有限，不能用结果反向优化 C9 参数。
- 原因：固定起点分布可以检验路径依赖，但不能作为选择新参数的依据。

## 继续价值反思

- 运行前判断：是。这个统计直接衡量 15万实盘账户在不同启动时点的短中期路径分布。
- 运行后判断：是。半年/一年分布能辅助实盘心理预期和风控沟通；后续应继续观察真实成交/TCA，而不是按这些窗口救参。
- 原因：当前实盘真正的剩余问题在执行与风险承受，不在用短样本继续寻找更好参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加当前 live 口径半年/一年启动收益分布摘要。
- 是否更新 `research/registry.md`：否。未改变正式版本或路线状态。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式版本切换或重要突破。
