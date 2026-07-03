# Stage060 Stage013 account-state pilot vs 正式版多周期对比

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T18:01:07
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读多周期复算；读取 2026-07-01 既有真引擎曲线，不 fresh rerun 策略引擎
- 是否重要突破：否
- 是否触发A/B：是；A=Official C9/15w Stage847，C=Stage013 account-state pilot，但本阶段仅做冻结曲线复核

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、trend-following vol targeting/no free lunch、meta-labeling/候选筛选风险。
- 我的判断：Stage013 属于账户状态风控层，不是增加预测信号；多周期比较有价值，但不能在当前 AI 文件缺口未修复前 fresh rerun 正式版并声称为真实表现。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage060_stage013_vs_official_multiperiod.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读比较口径 `stage013_vs_official_nav_gap_pct`、`drawdown_improvement_pp`、AI 输入完整性审计
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：逐半年起点 `2018-01` 到 `2026-01`，终点统一 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用原曲线成本与滑点，不重新估算
- 样本过滤：同日起点同日期 inner join；只比较已有真引擎曲线
- 策略/归因口径：A=正式 Stage847 C9/15w；C=Stage013 account-state pilot gate

## 结果

- 期末权益：2026-01 起点 Stage013 `152851.60`，正式版 `152851.60`
- 总收益：2026-01 起点 Stage013 `1.9011%`，正式版 `1.9011%`
- 最大回撤：2026-01 起点 Stage013 `-14.7303%`，正式版 `-14.7303%`
- Sharpe：2026-01 起点 Stage013 `0.2860`，正式版 `0.2860`
- 总滑点：2026-01 起点 Stage013 `2360.00`，正式版 `2360.00`
- 总交易次数：2026-01 起点 Stage013 `29`，正式版 `29`
- 胜率：本阶段复用日曲线，未重放 closed lots 计算胜率
- 其他关键指标：Stage013 收益胜正式 `14/17`；最大回撤改善 `14/17`；最小终点权益比例 `0.9075`
- Stage013 收益退化最严重起点：`2018-01`，return_diff `-792.6365pp`
- Stage013 回撤退化最严重起点：`2025-07`，drawdown_improvement `-1.2673pp`
- AI 审计：current 2026 eval_dates `2026-01-30, 2026-02-27, 2026-06-30`；saved Stage013 2026 eval_dates `2026-01-30, 2026-02-27, 2026-05-29`；fresh rerun safe=`False`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_report_stage060_stage013_vs_official_multiperiod_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_per_start_summary_stage060_stage013_vs_official_multiperiod_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_pair_curves_stage060_stage013_vs_official_multiperiod_v1.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_ai_input_audit_stage060_stage013_vs_official_multiperiod_v1.json`
- chart_absolute：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_absolute_equity_grid_stage060_stage013_vs_official_multiperiod_v1.png`
- chart_gap：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_relative_gap_grid_stage060_stage013_vs_official_multiperiod_v1.png`
- chart_drawdown：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_drawdown_grid_stage060_stage013_vs_official_multiperiod_v1.png`
- chart_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage060_stage013_vs_official_multiperiod/rebuilt_c9_v2_stage060_stage013_vs_official_multiperiod_summary_bar_stage060_stage013_vs_official_multiperiod_v1.png`

## 结论

- 本阶段结论：Stage013 有继续价值，但不能直接晋级；它改善多数周期回撤和部分路径收益，同时仍有 3 个起点收益或回撤缺陷。
- 是否进入下一步：是，建议进入更严格的同 AI 文件 fresh rerun/A-B 复验；但前置条件是先修复正式 AI eligibility 月池。
- 下一步：先恢复或重跑完整 PIT 月度 AI eligibility，冻结 hash 后再同时 rerun A=正式版、C=Stage013。

## 过拟合反思

- 运行前判断：否；本阶段只做固定候选 vs 固定正式版对比，没有调参。
- 运行后判断：否；结果暴露了 Stage013 的反例窗口，没有按反例继续拟合。
- 原因：比较对象和终点预先固定，且结论没有把局部优点包装成晋级。

## 继续价值反思

- 运行前判断：有；Stage013 是账户状态层候选，和新增 alpha 不同，可能改善生存曲线。
- 运行后判断：有但有前置条件；必须先修 AI 文件再做 fresh A/B。
- 原因：多数周期改善明确，但当前 AI 输入不完整会污染任何新回测。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，避免与既有并行研究记录冲突。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式突破，只写本线 stage。
