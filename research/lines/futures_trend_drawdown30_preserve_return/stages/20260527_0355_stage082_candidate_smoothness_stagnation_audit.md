# Stage082 候选平滑度与停滞期审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 03:55 CST
- 阶段性质：候选体验审计；不修改 78-1、C3、Stage079、Stage080 或任何交易规则
- 是否重要突破：否，重要复核。确认当前正常成本部署候选在“多年停滞/持有体验”维度也显著优于78-1。
- 是否触发A/B：否。本阶段只审计既有候选曲线，不产生新策略版本。

## 外部调研与判断

- 参考资料：
  - QuantStats 使用 rolling returns、drawdown、underwater 等指标评价策略体验。
  - PerformanceAnalytics/Ulcer Index 类指标强调回撤深度与持续时间，不只看单点最大回撤。
- 我的判断：
  - 用户关心“78-1有两年几乎没增长”，不能只用最大回撤判断；需要同时看年度收益、滚动252/504日收益、最长水下期和 Ulcer Index。
  - 本阶段应先审计已有候选，不应为了平滑继续扫现金、股票权重或策略小数参数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage382_candidate_smoothness_stagnation_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 目标最大回撤：`-30%`
  - 相对 C3 收益保留闸门：`80%`
  - 低增长年度阈值：`5%`
  - 低增长两年滚动阈值：`10%`
  - 外部现金：`115,000`
  - 股票账户资金：`300,000`
- 修改参数：无
- 删除参数：无

## 审计口径

- 公共样本：`2020-01-01` 至 `2026-04-27`。
- 对照与候选：
  - `official78_50w`
  - `official78_plus_115k_cash`
  - `c3_50w`
  - `stage079_c3_plus_115k_cash`
  - `stage075_c3_plus_300k_stock`
  - `stage075_c3_plus_300k_cash`
  - `stage080_c3_plus_300k_stock_plus_115k_cash`
  - `stage080_c3_plus_415k_cash`
- 指标：
  - 全周期收益、最大回撤、Sharpe、Ulcer Index
  - 最长水下期
  - 年度正收益/非正收益/低增长年份
  - 252日/504日滚动最差收益和低增长持续期
  - 相对78-1最大回撤、Ulcer和水下期改善

## 结果

### 78-1正式基准

- 期末权益：`25,309,885`
- 总收益：`4961.9770%`
- 最大回撤：`-40.1659%`
- Sharpe：`1.1556`
- Ulcer Index：`20.7886`
- 最长水下期：`403` 个自然日
- 年度非正收益年份：`1`
- 年度低增长年份小于5%：`2`
- 最差252日收益：`-35.5420%`
- 最差504日收益：`-7.2903%`

### Stage079：50万C3 + 11.5万现金

- 期末权益：`29,806,800`
- 总收益：`4746.6341%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.3074`
- Ulcer Index：`15.1012`
- 最长水下期：`369` 个自然日
- 年度非正收益年份：`0`
- 年度低增长年份小于5%：`0`
- 最差252日收益：`-15.1776%`
- 最差504日收益：`28.3351%`
- 相对78-1收益保留：`95.6601%`
- 相对C3收益保留：`81.3008%`
- 相对78-1最大回撤改善：`10.4651pp`
- 相对78-1 Ulcer 改善：`27.3585%`
- 决策：主候选，正常成本部署边界，收益保留和回撤目标同时成立。

### Stage080：50万C3 + 30万股票 + 11.5万现金

- 期末权益：`30,308,682.12`
- 总收益：`3212.4243%`
- 最大回撤：`-27.4358%`
- Sharpe：`1.3150`
- Ulcer Index：`12.9998`
- 最长水下期：`369` 个自然日
- 年度非正收益年份：`0`
- 年度低增长年份小于5%：`0`
- 最差252日收益：`-14.1225%`
- 最差504日收益：`28.1775%`
- 相对78-1最大回撤改善：`12.7300pp`
- 相对78-1 Ulcer 改善：`37.4667%`
- 相对C3收益保留：`55.0227%`
- 决策：平滑备选。曲线明显更平滑，但资金占用大且收益率下降，不作为主候选。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_summary_stage382_candidate_smoothness_stagnation_audit_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_annual_stage382_candidate_smoothness_stagnation_audit_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_rolling_stage382_candidate_smoothness_stagnation_audit_v1.csv`
- drawdown_periods：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_drawdown_periods_stage382_candidate_smoothness_stagnation_audit_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_daily_stage382_candidate_smoothness_stagnation_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_decision_stage382_candidate_smoothness_stagnation_audit_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_report_stage382_candidate_smoothness_stagnation_audit_v1.md`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage382_candidate_smoothness_stagnation_audit_dashboard_stage382_candidate_smoothness_stagnation_audit_v1.html`

## 结论

- 本阶段结论：Stage079 是当前最低过拟合、正常成本口径下的主候选；它满足最大回撤30以内、相对C3收益保留80%以上，并且在 Ulcer、最差252/504日收益、年度低增长和水下期上显著优于78-1。
- Stage080 可以回答“如果愿意牺牲收益率和占用更多资金，能不能明显更平滑”：可以。但相对 C3 收益保留只有 `55.0227%`，资金口径升至 `91.5万`，只能作为 paper 体验备选。
- 本阶段不是新 alpha 突破，而是部署/组合账户口径的体验证明；若要求高滑点也稳定保收益，仍未完成。

## 过拟合反思

- 运行前判断：不是过拟合。只审计既有冻结候选，不新增规则、阈值或搜索空间。
- 运行后判断：不是过拟合。结论接受了 Stage079/Stage080 的真实边界，没有为了让候选过线继续调现金或股票权重。
- 原因：所有候选都是前序阶段已冻结结果，本阶段只补充体验指标。

## 继续价值反思

- 运行前判断：有价值。用户关心的是全周期可持有性和停滞期，不只是最大回撤。
- 运行后判断：继续有价值，但方向应分叉：
  - 若接受正常成本和 `61.5万` 账户总资金，Stage079 可进入影子盘/部署边界审计。
  - 若要求高滑点、单策略、不加现金也达标，则仍需寻找真正独立收益源或新承载工具。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，作为目标线当前候选边界摘要。
