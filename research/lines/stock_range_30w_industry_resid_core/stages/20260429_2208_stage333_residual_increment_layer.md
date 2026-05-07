# 第333阶段 残差增量层同形状验证

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 22:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：layer1残差增量验证；固定第332阶段母本形态，只替换排序口径，不触发A/B。
- 是否重要突破：阶段性突破，但不是正式候选。`top8_gross50_ind2`在行业残差/混合排序下首次同时提升收益并把最大回撤压进20%以内；但`top5_gross50_ind2`可交易性护栏没有同步改善，且总收益仍未达到100%目标。
- 是否触发A/B：否。没有正式候选，不接paper，不接第78。

## 外部调研与判断

- 参考资料：
  - Short-term residual reversal：残差短反强调剥离共同因子暴露后再做短期反转。
  - Short-Term Residual Reversal PDF：残差反转的核心是用残差收益替代裸收益排序，并关注交易成本后的可行性。
  - Cross-sectional mean reversion implementation note：横截面均值回归的基本形态是买相对落后者，而不是只看绝对跌幅。
  - Short-term reversals, turnover, and news-driven trading：高换手/新闻驱动样本可能延续而非反转，不能默认所有残差超跌都更好。
- 我的判断：
  - 残差层有理论和业界形态支撑，值得验证。
  - 但当前只能作为同形态归因，不应扩大参数网格。
  - 市场残差在同日减常数后应与裸20日超跌等价，本阶段把它作为管线校验项。

## 本次变更

- 新增脚本：
  - `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_residual_increment_layer.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 固定形态：`top8_gross50_ind2`、`top5_gross50_ind2`。
  - 排序口径：`simple_ret20`、`market_resid20`、`industry_resid20`、`blend_simple_industry_resid20`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2018-04-20 到 2026-04-27。
- 账户规模：300,000 CNY。
- 成本口径：`min_fee`，沿用30万整手回放最低佣金压力口径。
- 源候选：`weak_market60_q1q2_reallocated`。
- 源信号：第332阶段简单20日超跌母本候选池。
- 固定形态：
  - `top8_gross50_ind2`：研究母本。
  - `top5_gross50_ind2`：可交易性护栏。
- 排序设计：
  - `simple_ret20`：裸20日超跌，复现第332母本。
  - `market_resid20`：20日收益减同日候选池中位数，理论上与裸20日排序等价，用于校验。
  - `industry_resid20`：20日收益减同行业候选池同日均值，买行业内相对短期更弱者。
  - `blend_simple_industry_resid20`：裸20日超跌分位与行业残差超跌分位等权混合。

## 结果

- 正式目标命中数：`0`。
- 管线校验：
  - `market_resid20`与`simple_ret20`结果完全一致，说明残差排序回放管线没有破坏母本。
- `top8_gross50_ind2`研究母本：
  - 简单母本：期末权益`1.4958`，总收益`49.58%`，最大回撤`-23.28%`，Sharpe`0.4480`，zero-lot`26.52%`。
  - 行业残差：期末权益`1.5199`，总收益`51.99%`，最大回撤`-18.64%`，Sharpe`0.4619`，zero-lot`25.79%`。
  - 混合排序：期末权益`1.5355`，总收益`53.55%`，最大回撤`-18.68%`，Sharpe`0.4711`，zero-lot`25.85%`。
  - 混合排序相对简单母本：总收益`+3.96pp`，最大回撤改善`+4.61pp`，Sharpe`+0.0232`，收益/回撤比`+0.7375`，zero-lot下降`-0.67pp`。
  - 行业残差相对简单母本：总收益`+2.41pp`，最大回撤改善`+4.64pp`，Sharpe`+0.0140`。
- `top5_gross50_ind2`可交易性护栏：
  - 简单母本：期末权益`1.4041`，总收益`40.41%`，最大回撤`-22.68%`，Sharpe`0.3684`，zero-lot`18.38%`。
  - 行业残差：期末权益`1.4799`，总收益`47.99%`，最大回撤`-24.10%`，Sharpe`0.4155`，zero-lot`17.67%`。
  - 混合排序：期末权益`1.4799`，总收益`47.99%`，最大回撤`-23.82%`，Sharpe`0.4149`，zero-lot`17.93%`。
  - 判断：top5上残差提高收益和Sharpe，但回撤更深，不能算同向改善。
- 252日滚动：
  - `top8`简单母本滚动正收益窗口比例`84.77%`，最差滚动回撤`-23.28%`。
  - `top8`行业残差滚动正收益窗口比例`72.67%`，最差滚动回撤`-17.64%`。
  - `top8`混合排序滚动正收益窗口比例`76.56%`，最差滚动回撤`-17.64%`。
  - 解释：残差层明显削掉最坏回撤，但牺牲滚动正收益覆盖率；它更像风险结构改善，不是全面增强。
- 最佳场景订单统计：
  - 场景：`blend_simple_industry_resid20__top8_gross50_ind2`
  - 订单行数：`16,478`
  - 成交订单行数：`16,478`
  - 阻断订单行数：`0`
  - 未成交权重：最新目标日`0.00`
  - 日度活跃胜率：`51.57%`
  - 总滑点：本股票整手回放无独立滑点字段，使用`min_fee`成本压力口径。

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_report.md`
- summary：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_summary.csv`
- delta：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_delta_vs_simple.csv`
- quality：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_quality_checkpoints.csv`
- yearly：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_yearly.csv`
- rolling：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026/stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1_rolling_aggregate.csv`

## 结论

- 本阶段结论：
  - 行业残差层不是噪声，至少在`top8_gross50_ind2`研究母本上提供了真实增量：收益更高、回撤进入20%以内、Sharpe更高。
  - 但它不是正式候选：收益离`100%`目标仍远，`top5_gross50_ind2`护栏没有同向改善，滚动正收益覆盖率下降。
  - 因此不能沿着行业残差继续扫更多阈值；更合理的下一步是做“残差层的收益/回撤来源归因”，确认改善来自2018/2022风险段被削弱，还是来自行业/样本覆盖变化。
- 是否进入下一步：是。
- 下一步：
  1. 对`top8`残差改善做来源归因：年份、回撤段、行业、市场状态、候选数量、zero-lot和持仓路径。
  2. 判断残差层是否可以作为`top8`风险结构模块保留。
  3. 若改善集中在少数行业或少数年份，则降级为监控特征；若改善来自多段风险削弱，再进入连续状态预算层。

## 过拟合反思

- 运行前判断：否，风险可控。
- 运行后判断：否，但不能升级正式候选。
- 原因：
  - 本阶段只验证第332预注册的两个固定形态，没有扩topK/gross/行业上限网格。
  - 排序口径只有四个，其中`market_resid20`是等价校验项。
  - 结果不是按收益最高继续追参数，而是发现`top8`和`top5`分歧，必须做归因反证。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：
  - `top8`残差层把最大回撤从`-23.28%`改善到约`-18.6%`，这是贴近用户30万/20%回撤目标的结构性线索。
  - 但收益和可交易性护栏仍不够，所以继续价值在“归因和稳健性验证”，不是继续扫参数。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：否。本阶段仍是线内研究，不改变总索引状态。
- 是否追加根目录`memory.md/back_log.md`：否。尚非正式候选或跨线里程碑。
