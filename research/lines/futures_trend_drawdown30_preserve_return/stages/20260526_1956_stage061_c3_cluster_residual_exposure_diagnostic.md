# Stage061 C3风险簇剩余暴露诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 19:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：归因诊断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：趋势跟踪长期研究强调跨市场分散和风险分配，而不是删除历史亏损品种。
- 我的判断：Stage060 的单品种删除不能合入；下一步应看风险暴露结构，尤其是同一风险簇内多品种同步亏损。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage361_c3_cluster_residual_exposure_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：C3当前低频滑点口径
- 样本过滤：无
- 策略/归因口径：`C3_supply_headwind`，归因最大回撤窗口内风险簇、多品种暴露、热度降仓事件

## 结果

- 期末权益：30,925,650
- 总收益：6085.13%
- 最大回撤：-31.0767%
- Sharpe：1.3663
- 总滑点：1,556,750
- 总交易次数：757
- 胜率：45.3826%
- 其他关键指标：
  - 最大回撤窗口：2021-05-12 到 2021-07-02
  - 回撤金额：555,670
  - 黑色建材簇亏损占回撤：99.1488%
  - 同风险簇多品种亏损占回撤：63.4189%
  - 最大回撤窗口内热度降仓成交次数：2

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage361_c3_cluster_residual_exposure_diagnostic_report_stage361_c3_cluster_residual_exposure_diagnostic_v1.md`
- summary：无
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage361_c3_cluster_residual_exposure_diagnostic_decision_stage361_c3_cluster_residual_exposure_diagnostic_v1.json`

## 结论

- 本阶段结论：C3剩余最大回撤确实集中在黑色建材同簇多品种同步亏损；但当前热度降仓已经在该窗口触发过，不能简单声称“没有风控”。
- 是否进入下一步：是
- 下一步：验证热度降仓执行语义是否存在同日顺序依赖。

## 过拟合反思

- 运行前判断：否。本阶段是归因，不改变参数。
- 运行后判断：否。
- 原因：没有删除品种、没有搜索阈值，只定位剩余回撤结构。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：归因显示风险簇多品种暴露贡献明显，值得做一个低自由度引擎语义验证。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为路线反证上下文
