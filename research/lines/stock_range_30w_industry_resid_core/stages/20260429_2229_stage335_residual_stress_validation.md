# 第335阶段 残差层2018留出/剔除压力验证

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 22:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：归因压力验证；不新增交易信号，不改参数，不重新跑交易引擎
- 是否重要突破：否；但属于重要降级确认
- 是否触发A/B：否。残差层未成为正式候选，不接第78，不改`stock_range_paper_v1`

## 外部调研与判断

- 参考资料：
  - Short-term residual reversal：https://www.sciencedirect.com/science/article/pii/S1386418112000468
  - Residual reversal and liquidity provision：https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf
  - Portfolio performance attribution overview：https://en.wikipedia.org/wiki/Performance_attribution
  - Cross-sectional mean reversion implementation：https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/
  - GitHub mean-reversion-trading topics：https://github.com/topics/mean-reversion-trading
- 我的判断：残差/特质收益可以作为横截面短反信息源，但不能只因全样本改善就升级。业界更可信的做法是做留出、分段、压力窗口和归因验证；如果收益主要来自单一危机年份，应降级为风险监控或状态预算线索。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_residual_stress_validation.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增压力验证桶`full_sample`、`holdout_2018`、`exclude_2018`、`post_2019`、`post_2020`、`recent_2024_2026`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-04-20到2026-04-27
- 账户规模：300,000 CNY
- 成本口径：沿用第333/334阶段`strategy_daily_ret_min_fee`
- 样本过滤：只读取第334阶段`pair_daily/yearly/drawdown_windows`，不重新选股、不重新成交回放
- 策略/归因口径：比较`top8/top5_gross50_ind2`下`simple_ret20`与`industry_resid20`/`blend_simple_industry_resid20`

## 结果

- 期末权益：全样本`top8_blend_vs_simple`变体`1.5355`，简单母本`1.4958`
- 总收益：全样本`top8_blend_vs_simple`变体`53.55%`，简单母本`49.58%`，差值`+3.96pp`
- 最大回撤：全样本`top8_blend_vs_simple`变体`-18.68%`，简单母本`-23.28%`，差值`+4.61pp`
- Sharpe：全样本`top8_blend_vs_simple`变体`0.4711`，简单母本`0.4480`，差值`+0.0232`
- 总滑点：本阶段未重新跑订单回测，不适用
- 总交易次数：本阶段未重新跑订单回测，不适用
- 胜率：本阶段为组合日度/年度/窗口归因，不计算交易胜率
- 其他关键指标：
  - 质量检查：`pass=2`、`fail=4`、`warn=2`
  - `top8_blend_vs_simple` 2018留出：收益差`+6.99pp`，回撤差`+5.65pp`
  - `top8_blend_vs_simple`剔除2018：收益差`-9.78pp`，回撤差`-3.74pp`
  - `top8_blend_vs_simple`2019年至今：收益差`-9.78pp`，回撤差`-3.74pp`
  - 剔除2018年度广度：收益和回撤同向改善`0/8`
  - 非2018主要回撤窗口：收益和回撤同向改善`1/6`，平均收益差`-0.42pp`，平均回撤差`-0.50pp`
  - `top5_blend_vs_simple`剔除2018：收益差`-4.89pp`，回撤差`-5.84pp`

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_stress_validation_2018_2026/stock_range_reversion_liquid_q3_30w_residual_stress_validation_v1_report.md`
- summary：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_stress_validation_2018_2026/stock_range_reversion_liquid_q3_30w_residual_stress_validation_v1_period_stress.csv`
- orders：无
- daily：沿用第334阶段输入；本阶段输出`stock_range_reversion_liquid_q3_30w_residual_stress_validation_v1_period_stress.csv`
- quality：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_stress_validation_2018_2026/stock_range_reversion_liquid_q3_30w_residual_stress_validation_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：残差层全样本改善是真实存在的，但核心贡献高度集中在2018型大风险段；剔除2018后，`top8`和`top5`护栏均不支持继续把残差排序作为广谱增强因子。
- 是否进入下一步：进入，但不继续扫残差排序参数。
- 下一步：把残差层降级为风险监控/状态预算候选输入；下一阶段应回到简单20日超跌母本，做“连续风险预算/暴露函数”的预注册反证，而不是围绕残差因子调参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有新增交易规则，没有搜索阈值，也没有根据结果反向改策略；它是对既有结果做2018留出/剔除和非2018压力窗口反证。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但方向要收窄。
- 原因：继续研究股票震荡30万策略仍有价值；但残差排序这条分支已经被降级，后续价值在于把它作为连续风险预算或监控变量，而不是继续直接加到排序核心。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录第335阶段降级结论。
- 是否更新 `research/registry.md`：否，未发生跨线状态迁移。
- 是否追加根目录 `memory.md/back_log.md`：否，属于本线日常研究降级确认，不是正式候选或跨线合入。
