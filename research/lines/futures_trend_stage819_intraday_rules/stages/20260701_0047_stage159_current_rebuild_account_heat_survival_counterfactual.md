# Stage159 当前重建版账户层 heat/survival 反事实

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读日级代理反事实；读取 Stage157 日级输出，不重跑策略、不连接 CTP、不调用订单 API
- 是否重要突破：否；本阶段反证了几个简单账户层 heat/high-water 代理形状
- 是否触发A/B：否，没有出现可进入订单级正式复测的候选

## 外部调研与判断

- 参考资料：按用户约束不再搜索外部资料；本阶段只使用本地 Stage157 daily delta、Stage158 回撤压力归因和历史正式路线判断。
- 我的判断：Stage158 显示 C9 风险不像 stop/retry 失败，更像峰值回吐和局部保证金热度。延续历史 Stage372/C4 的治理思路，应该先测账户层 heat/survival，而不是继续扫 AI、品种、方向、月份、`0.5R` 或重试次数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `c9_heat90_nextday_soft_scale`：上一日模拟 broker10 heat 超过 `90%` 时，次日 C9 PnL 与估算保证金按 `90/previous_heat` 缩放
  - `c9_heat80_nextday_soft_scale`：上一日模拟 broker10 heat 超过 `80%` 时，次日 C9 PnL 与估算保证金按 `80/previous_heat` 缩放
  - `c9_heat90_peak_dd10_scale70`：heat90 加高水位回撤保护；权益峰值超过 `2x` 资金且当前回撤低于 `-10%` 时，次日缩放不高于 `70%`
- 修改参数：无正式策略参数；以上均为日级代理反事实参数
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01` 至 `2026-01`，终点沿用 Stage157 输出到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 Stage157 日级 `net_pnl/slippage/trade_count`，不新增成本假设
- 样本过滤：9 个年度起点
- 策略/归因口径：
  - 基线：`c4_reference_broker10_cap`、`c9_baseline_stop_retry`
  - 代理：`c9_heat90_nextday_soft_scale`、`c9_heat80_nextday_soft_scale`、`c9_heat90_peak_dd10_scale70`
  - 先校验 `net_pnl_c9` 与 `account_equity_c9.diff()` 一致，最大误差仅浮点级别，再做日级缩放
  - 该阶段只能判断是否值得订单级复测，不能替代真实订单级回测

## 结果

- 期末权益：
  - C9 baseline 2018 起点：`12,857,153.7`
  - heat90 2018 起点：`12,858,429.7`
  - heat80 2018 起点：`12,854,868.7`
  - heat90+高水位保护 2018 起点：`8,816,469.9`
- 总收益：
  - C9 baseline 中位：`126.1993%`
  - heat90 中位：`126.1993%`
  - heat80 中位：`126.1993%`
  - heat90+高水位保护 中位：`116.2017%`
- 最大回撤：
  - C9 baseline 最差：`-56.2069%`，中位：`-39.9820%`
  - heat90 最差：`-56.1874%`，中位：`-39.9820%`
  - heat80 最差：`-56.0126%`，中位：`-39.9820%`
  - heat90+高水位保护 最差：`-51.5741%`，中位：`-39.9820%`
- Sharpe：
  - C9 baseline 中位：`1.2246`
  - heat90 中位：`1.2246`
  - heat80 中位：`1.2246`
  - heat90+高水位保护 中位：`1.1678`
- 总滑点：代理口径输出 `total_slippage_proxy`；不作为正式滑点
- 总交易次数：代理口径输出 `total_trade_count_proxy`；不作为正式交易次数
- 胜率：不适用
- 其他关键指标：
  - heat90：回撤胜出 `1/9`、收益胜出 `1/9`、Sharpe 胜出 `1/9`，触发仅 `4` 天
  - heat80：回撤胜出 `3/9`、收益胜出 `0/9`、Sharpe 胜出 `1/9`，触发 `30` 天
  - heat90+高水位保护：回撤胜出 `5/9`、收益胜出 `0/9`、Sharpe 胜出 `0/9`，中位利润保留 `91.3107%`，但代理 broker10 峰值升至 `101.8654%`
  - 没有任何代理形状满足 `dd_win>=6/9`、中位利润保留 `>=85%`、Sharpe 胜出 `>=4/9`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_report_stage159_current_rebuild_account_heat_survival_counterfactual_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_summary_stage159_current_rebuild_account_heat_survival_counterfactual_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_aggregate_stage159_current_rebuild_account_heat_survival_counterfactual_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_comparison_stage159_current_rebuild_account_heat_survival_counterfactual_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_daily_stage159_current_rebuild_account_heat_survival_counterfactual_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual_decision_stage159_current_rebuild_account_heat_survival_counterfactual_v1.json`

## 结论

- 本阶段结论：
  - 简单 heat90/heat80 次日缩放触发太少，不能稳定改善 C9 回撤；这说明当前 C9 的主要回撤不只是 broker10 超阈值当天的问题。
  - 高水位回撤保护能改善部分旧起点最差回撤，但代价是收益和 Sharpe 普遍变差，并且代理 broker10 峰值反而超过 `100%`；不适合作为当前重建版直接优化方向。
  - Stage159 不产生可推广候选，不进入订单级正式回测，不更新正式配置。
  - 历史里有价值的是“保证金/恢复治理要和订单级持仓、开仓闸门、资金口径绑定”，不是在日级权益曲线上事后缩放 PnL。
- 是否进入下一步：是，但不是继续这个 heat/high-water 代理形状
- 下一步：
  - 回到订单级/逻辑级 review：检查当前 C9/C4/Stage372 的正式构造、AI PIT、broker10 cap 与 stop/retry 的状态依赖，列出真正可能导致执行差错的工程 bug。
  - 若继续优化，优先考虑“订单级开仓前闸门/持仓态风险”而不是日级权益曲线缩放。

## 过拟合反思

- 运行前判断：否。预声明少数账户层形状，只测 heat/high-water 机制，不按品种、日期或方向筛选。
- 运行后判断：否。本阶段没有从局部好窗口倒推规则；结果不稳即记录反证。
- 原因：heat/high-water 是机制级假设；但当前代理结果没有足够稳定性，所以不能继续细扫阈值救参。

## 继续价值反思

- 运行前判断：是。Stage158 指向保证金热度和峰值回吐，账户层反事实是延续 Stage372/C4 治理思路的低过拟合方向。
- 运行后判断：是，但价值转向“停止错误形状”和“回到订单级 bug/闸门 review”。
- 原因：简单日级代理已经证明不应继续追这个方向；接下来要看真实订单级状态，尤其是当前正式构造是否存在全局状态、PIT、闸门触发、报告口径上的执行差错风险。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待订单级/逻辑级 review 后一起整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；本阶段是反证记录，不是正式候选或重要合入
