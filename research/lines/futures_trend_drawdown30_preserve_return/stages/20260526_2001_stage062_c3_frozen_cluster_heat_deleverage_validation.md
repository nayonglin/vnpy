# Stage062 C3风险簇热度快照降仓验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 20:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：A/C引擎验证
- 是否重要突破：否
- 是否触发A/B：是

## 外部调研与判断

- 参考资料：趋势跟踪风险治理应优先处理组合暴露和相关性，不应以单年单品种亏损做黑名单。
- 我的判断：若同日风险簇热度降仓存在顺序依赖，冻结当日热度快照是低自由度实现语义修正；但必须以全样本回撤和收益保留验证。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage362_c3_frozen_cluster_heat_deleverage_validation.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `risk_cluster_heat_deleverage_use_daily_snapshot`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：C3当前低频滑点口径
- 样本过滤：无
- 策略/归因口径：
  - A：`C3_supply_headwind`
  - C：`C3_supply_headwind + risk_cluster_heat_deleverage_use_daily_snapshot=True`

## 结果

- A期末权益：30,925,650
- A总收益：6085.13%
- A最大回撤：-31.0767%
- A Sharpe：1.3663
- A总滑点：1,556,750
- A总交易次数：757
- A胜率：45.3826%
- C期末权益：29,547,175
- C总收益：5809.4350%
- C最大回撤：-33.7689%
- C Sharpe：1.3308
- C总滑点：1,525,580
- C总交易次数：780
- C胜率：46.6837%
- 其他关键指标：
  - C相对A收益保留：95.4694%
  - C回撤改善：-2.6922个百分点，实际恶化
  - C热度降仓成交事件数：49
  - C最差回撤窗口变为 2020-01-02 到 2020-07-16

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage362_c3_frozen_cluster_heat_deleverage_validation_report_stage362_c3_frozen_cluster_heat_deleverage_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage362_c3_frozen_cluster_heat_deleverage_validation_summary_stage362_c3_frozen_cluster_heat_deleverage_validation_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage362_c3_frozen_cluster_heat_deleverage_validation_decision_stage362_c3_frozen_cluster_heat_deleverage_validation_v1.json`

## 结论

- 本阶段结论：全簇热度快照降仓失败。它保留了较高收益，但把最大回撤恶化到 -33.7689%，说明扩大同日降仓语义过粗。
- 是否进入下一步：只允许做一次结构性收窄验证
- 下一步：只在同风险簇、同方向、多品种同时暴露时使用快照；若仍失败，停止热度快照路线。

## 过拟合反思

- 运行前判断：否。没有新增阈值、没有删品种。
- 运行后判断：否，但效果失败。
- 原因：失败不是因为过拟合，而是该风险释放语义本身破坏了有利路径。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有限。
- 原因：全簇快照失败，但失败位置显示规则过粗；仍可做一次基于Stage061结构归因的收窄验证。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
