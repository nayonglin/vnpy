# 第334阶段 残差改善来源归因

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 22:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：读取第333阶段产物做来源归因，不新增交易规则，不触发A/B。
- 是否重要突破：否，但形成关键反证。第333阶段`top8`残差改善是真实的，但主要来自2018大回撤段削弱，年度广度不足，不能升级正式候选。
- 是否触发A/B：否。纯归因，不接paper，不接第78。

## 外部调研与判断

- 参考资料：
  - Short-term residual reversal：残差反转支持用市场/行业残差替代裸收益排序。
  - Residual reversal and liquidity provision：残差收益和流动性提供相关，但交易成本和风险暴露要单独验证。
  - Portfolio performance attribution：组合绩效需要按时间、暴露和持仓来源拆解。
  - Cross-sectional mean reversion implementation：横截面均值回归要看相对弱势替换是否真的提升组合。
- 我的判断：
  - 残差层不能只看最终收益/回撤，需要确认改善是否分散到多个年份和多个回撤窗口。
  - 如果只靠2018年削回撤，则更像风险段线索，不是可以继续加仓的稳定alpha。

## 本次变更

- 新增脚本：
  - `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_residual_source_attribution.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数。本阶段只定义四个归因对照：
  - `top8_industry_vs_simple`
  - `top8_blend_vs_simple`
  - `top5_industry_vs_simple`
  - `top5_blend_vs_simple`
- 修改参数：无。
- 删除参数：无。

## 归因参数

- 数据区间：沿用第333阶段，2018-04-20 到 2026-04-27。
- 账户规模：300,000 CNY。
- 成本口径：沿用第333阶段`min_fee`整手回放。
- 输入文件：
  - 第333阶段`summary`
  - 第333阶段`daily`
  - 第333阶段`selected`
  - 第333阶段`orders`
- 归因维度：
  - 总体delta
  - 年度收益/回撤delta
  - 基准回撤窗口delta
  - 换股重叠率
  - 换股市场状态/行业画像
  - 信号10日持有路径代理
  - 真实成交持仓行业贡献

## 结果

- 质量检查：
  - fail：`0`
  - warn：`3`
  - `stage333_top8_increment_confirmed`：pass
  - `top8_yearly_breadth`：warn，`top8_blend_vs_simple`收益和回撤同向改善年份只有`1`年。
  - `top8_base_drawdown_window_relief`：pass，最坏基准回撤窗口内回撤改善`+5.66pp`。
  - `top5_guard_divergence`：warn，top5护栏最大回撤恶化`-1.13pp`。
  - `selection_change_material`：pass，top8混合排序平均换股重叠率`79.37%`，说明排序确实改变了组合。

### 总体delta

- `top8_industry_vs_simple`：
  - 收益差：`+2.41pp`
  - 最大回撤差：`+4.64pp`
  - 正delta日比例：`46.74%`
  - 平均实际持股数差：`-0.24`
  - 平均zero-lot目标数差：`-0.32`
- `top8_blend_vs_simple`：
  - 收益差：`+3.96pp`
  - 最大回撤差：`+4.61pp`
  - 正delta日比例：`47.30%`
  - 平均实际持股数差：`-0.38`
  - 平均zero-lot目标数差：`-0.35`
- `top5_blend_vs_simple`：
  - 收益差：`+7.58pp`
  - 最大回撤差：`-1.13pp`
  - 说明：收益提升但回撤恶化，不能作为可交易护栏通过。

### 年度归因

- `top8_blend_vs_simple`只有2018年同时改善收益和回撤：
  - 2018：收益差`+6.99pp`，年度回撤改善`+5.65pp`。
  - 2024：收益差`+3.44pp`，但年度回撤恶化`-0.59pp`。
  - 2021：收益差`-3.55pp`，年度回撤恶化`-2.03pp`。
  - 2022：收益差`-2.40pp`，年度回撤恶化`-1.07pp`。
  - 2025：收益差`-1.91pp`，年度回撤恶化`-0.75pp`。
- 判断：
  - 第333阶段看起来漂亮的全样本回撤改善，主要来自2018大风险段，不是多年份均匀改善。

### 基准回撤窗口归因

- `top8_blend_vs_simple`在最坏基准回撤窗口表现很好：
  - 2018-05-09 到 2018-10-18：基准回撤`-23.28%`，混合排序同窗收益改善`+5.65pp`，同窗回撤改善`+5.66pp`。
- 但其他主要窗口不稳：
  - 2022-02-24 到 2022-04-26：收益差`-1.07pp`，回撤差`-1.00pp`。
  - 2024-03-21 到 2024-07-08：收益差`-0.59pp`，回撤差`-0.40pp`。
  - 2020-07-15 到 2021-02-08：收益差`-0.85pp`，回撤差`-1.25pp`。
  - 2025-03-19 到 2025-04-08：收益差`-0.37pp`，回撤差`-0.86pp`。
- 判断：
  - 残差层不是广谱回撤控制器，而是强烈修复了2018型大回撤。

### 换股与路径

- 换股重叠率：
  - `top8_blend_vs_simple`平均重叠率`79.37%`，每日平均剔除`1.09`只，新增`0.53`只。
  - `top8_industry_vs_simple`平均重叠率`75.21%`。
  - `top5_blend_vs_simple`平均重叠率`71.58%`。
  - `top5_industry_vs_simple`平均重叠率`59.78%`。
- 信号持有路径代理：
  - `top8_blend_vs_simple`10日路径改善约`+0.083pp`，MFE改善`+0.090pp`，MAE改善`+0.047pp`。
  - 说明残差替换后的信号路径略好，但幅度很小，不足以证明强alpha。

### 真实持仓行业贡献

- `top8_blend_vs_simple`正向贡献最大的行业/年份：
  - 2018 软件服务：`+5.64pp`
  - 2019 软件服务：`+2.11pp`
  - 2024 半导体：`+1.75pp`
  - 2018 元器件：`+1.39pp`
  - 2024 软件服务：`+1.21pp`
- `top8_blend_vs_simple`负向贡献最大的行业/年份：
  - 2022 电气设备：`-2.42pp`
  - 2019 通信设备：`-2.33pp`
  - 2021 软件服务：`-2.23pp`
  - 2021 通信设备：`-1.37pp`
  - 2025 软件服务：`-0.96pp`
- 判断：
  - 改善不是来自“行业残差普遍更干净”，而是强烈依赖2018软件服务等行业/年份替换收益。
  - 软件服务同时出现在正负贡献中，说明它不是可简单剔除或加仓的稳定标签。

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_report.md`
- pair_overall：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_pair_overall.csv`
- yearly：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_yearly.csv`
- drawdown_windows：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_drawdown_windows.csv`
- selection_overlap_summary：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_selection_overlap_summary.csv`
- swap_by_industry：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_swap_by_industry.csv`
- swap_by_state：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_swap_by_state.csv`
- path_delta：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_path_delta.csv`
- position_contribution：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026/stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1_position_contribution.csv`

## 结论

- 本阶段结论：
  - 第333阶段残差改善是真实的，不是统计或管线错误。
  - 但它不是穿越周期的广谱增强：`top8_blend_vs_simple`只有2018年收益和回撤同向改善，其他多个关键窗口反而变差。
  - 残差层更适合作为“2018型大风险段的风险识别线索”，暂不适合作为下一版正式排序核心。
  - `top5`护栏恶化进一步反证：不能直接把`top8`残差版本拿去放大仓位或上线。
- 是否进入下一步：是，但方向调整。
- 下一步：
  1. 不继续扫残差阈值。
  2. 做`residual_stress_validation`：把2018单独留出/剔除，确认残差层离开2018后是否仍有价值。
  3. 如果剔除2018后残差层优势消失，则降级为风险监控特征；若仍能改善部分风险窗口，再把它作为状态预算输入，而不是排序主因子。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只解释既有结果，不新增交易参数。
  - 归因结果没有被用来立即形成新策略，而是反过来限制了残差层继续扫参的冲动。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但继续方式要收敛。
- 原因：
  - 残差层确实能削掉2018型大回撤，这对30万/20%回撤目标有启发。
  - 但多年份不稳，继续价值在压力验证和状态预算输入，不在残差排序本身继续调参。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：否。本阶段仍是线内研究。
- 是否追加根目录`memory.md/back_log.md`：否。不是正式候选或跨线里程碑。
