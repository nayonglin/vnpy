# Stage038 低相关卫星路线审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 02:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：路线审计 / 既有实验证据汇总
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*。
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*。
- 我的判断：
  - 跨风格组合有价值，但卫星腿必须是独立收益源；如果卫星自身收益过低或为负，组合回撤改善多数只是现金缓冲/稀释，不是 alpha 对冲。
  - 当前仓库旧震荡、BOLL、无影线和 range 近邻版本大多属于低收益低波动卫星，不宜继续扫权重。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage338_low_corr_satellite_route_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；读取 Stage306/307/325/326 已冻结结果。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用各阶段既有输出。
- 账户规模：50万真实资金口径用于 Stage325/326；净值层用于 Stage306/307。
- 成本口径：沿用各阶段真实引擎或既有权益曲线成本口径。
- 样本过滤：
  - Stage306 前30个非 `_equity` 重复卫星候选。
  - Stage307 净值层权重前沿。
  - Stage325 真实资金全样本拆分前沿。
  - Stage326 `c3_350_sat_150` 多周期与滑点压力。
- 策略/归因口径：路线层证据汇总，不新增策略信号。

## 结果

- 净值层最优旧卫星：`qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_daily`
  - 配置：`base0.875_sat0.125`
  - 总收益：`4368.8302%`
  - 最大回撤：`-29.9555%`
  - 全样本收益保留：`87.1167%`
  - 多周期严格通过：`3/6`
  - 最低收益保留：约 `71.4360%`
- 真实资金全样本候选：`c3_350_sat_150`
  - 总收益：`5005.0490%`
  - 最大回撤：`-29.2412%`
  - 收益保留：`82.2505%`
  - 但保证金复核天数较多，且需多周期复验。
- 真实资金多周期：
  - 通过：`3/9`
  - 正收益窗口通过：`2/8`
  - 正收益窗口最低收益保留：`35.15%`
  - 最差回撤：`-32.46%`
- 滑点压力：
  - 通过：`1/4`
  - 2x滑点组合收益：`4751.0850%`
  - 2x滑点最大回撤：`-30.8090%`
- 当前卫星集合质量：
  - 前30个非重复卫星中，自身正收益 `8` 个，负收益 `22` 个。
  - 卫星自身最高收益：`5.7650%`
  - 卫星自身中位收益：`-0.9535%`
  - 中位相关性：`0.0079`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage338_low_corr_satellite_route_audit_report_stage338_low_corr_satellite_route_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage338_low_corr_satellite_route_audit_route_summary_stage338_low_corr_satellite_route_audit_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage338_low_corr_satellite_route_audit_candidate_quality_stage338_low_corr_satellite_route_audit_v1.csv`

## 结论

- 本阶段结论：当前旧低相关卫星集合对回撤有帮助，但主要像低波动现金替代；真实资金、多周期和滑点压力下没有稳定通过。
- 是否进入下一步：不在当前 v8/BOLL/无影线旧卫星集合内继续扫权重。
- 下一步：
  - 若继续低相关路线，必须寻找更高收益、真实资金可交易、与C3弱窗口错开的新独立策略。
  - 或转向账户部署层结构，重新评估 C3 自然回撤约 `-31%` 是否是可接受边界。

## 过拟合反思

- 运行前判断：过拟合风险低。
- 运行后判断：否。
- 原因：本阶段只汇总冻结结果，不新增阈值、权重或信号；反而降低了继续过拟合旧卫星集合的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前旧卫星集合继续价值下降，但低相关路线本身仍有价值。
- 原因：当前旧卫星自身收益太弱，继续扫权重容易把现金稀释误判为 alpha；需要换收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录当前旧卫星集合降级。
- 是否更新 `research/registry.md`：是，更新最新关键阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是路线降级，不是正式候选。
