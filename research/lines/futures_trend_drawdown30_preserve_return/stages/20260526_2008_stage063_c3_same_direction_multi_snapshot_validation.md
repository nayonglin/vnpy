# Stage063 C3同簇同向多品种热度快照验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 20:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：A/C引擎验证
- 是否重要突破：否
- 是否触发A/B：是

## 外部调研与判断

- 参考资料：趋势跟踪风险管理应避免单品种事后归因，优先处理可泛化的集中暴露。
- 我的判断：Stage362全簇快照过粗；Stage063只验证同簇同向多品种暴露这个结构性状态，避免单品种黑名单。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage363_c3_same_direction_multi_snapshot_validation.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：C3当前低频滑点口径
- 样本过滤：无
- 策略/归因口径：
  - A：`C3_supply_headwind`
  - C：同风险簇、同方向、至少两个品种同时持仓时使用热度快照；其他情形保持C3原语义

## 结果

- A期末权益：30,925,650
- A总收益：6085.13%
- A最大回撤：-31.0767%
- A Sharpe：1.3663
- A总滑点：1,556,750
- A总交易次数：757
- A胜率：45.3826%
- C期末权益：32,937,605
- C总收益：6487.52%
- C最大回撤：-32.2987%
- C Sharpe：1.36
- C总滑点：1,695,840
- C总交易次数：764
- C胜率：45.9530%
- 其他关键指标：
  - C相对A收益保留：106.6127%
  - C回撤改善：-1.2220个百分点，实际恶化
  - C热度降仓成交事件数：47

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage363_c3_same_direction_multi_snapshot_validation_report_stage363_c3_same_direction_multi_snapshot_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage363_c3_same_direction_multi_snapshot_validation_summary_stage363_c3_same_direction_multi_snapshot_validation_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage363_c3_same_direction_multi_snapshot_validation_decision_stage363_c3_same_direction_multi_snapshot_validation_v1.json`

## 结论

- 本阶段结论：同簇同向多品种热度快照仍未过硬闸门，最大回撤恶化到 -32.2987%。虽然收益提高，但目标是回撤30以内，不可晋级。
- 是否进入下一步：否，停止热度快照降仓语义路线
- 下一步：回到账户部署现金边界或寻找真正低相关收益源；不再围绕热度快照、同簇多品种或相邻阈值做小数救援。

## 过拟合反思

- 运行前判断：否。结构条件来自Stage061归因，不是单品种删除。
- 运行后判断：否，但失败。
- 原因：该规则没有拟合历史胜点，反而显示结构性降仓无法稳定压低最大回撤。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：对本路线没有继续价值。
- 原因：全簇快照和结构性快照都失败，继续微调只会变成阈值/路径拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
