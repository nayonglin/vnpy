# 第331阶段 股票震荡30万架构盘点与路线重置

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 21:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：路线盘点/架构重置，不新增回测参数，不接入实盘，不触发A/B。
- 是否重要突破：否，但属于重要方向纠偏。
- 是否触发A/B：否。当前线没有稳健正式候选。

## 外部调研与判断

- 参考资料：
  - 纽约联储 Staff Report 513：短期反转收益可拆成行业动量、行业内预期收益差、现金流反应不足和残差；残差部分是更关键的正向来源。
  - Short-term residual reversal：残差短反通过剥离动态因子暴露，降低传统短反的因子污染。
  - Connors RSI(2)：业界短期均值回归模板强调顺长期趋势买短期回调，不是猜大底。
  - 在线组合均值回归研究：很多benchmark偏向均值回归，加入真实交易成本后容易失效。
  - GitHub公开均值回归/RSI2/配对交易项目：多为教学或单标的框架，可借鉴流程，不能直接复制为30万A股策略。
- 我的判断：
  - 股市震荡策略的本质仍是横截面短期流动性冲击回归。
  - 但交易系统必须通过30万账户整手、成本、分散度、持有路径和状态稳定性验证。
  - 第322到第330阶段对`industry_resid_core`的亏损归因有价值，但继续小规则修补已经开始偏离“30万高收益、回撤20以内”的初衷。

## 本次变更

- 新增脚本：
  - `examples/alpha_research/analyze_stock_range_reversion_30w_architecture_inventory.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。本阶段只读取既有产物。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：读取既有`2018_2026`与`2019_2026`产物，不新跑策略回测。
- 账户规模：
  - 重点比较30万整手回放产物。
  - paper/300k路线只作为隔离参照。
- 成本口径：
  - 优先使用`min_fee`口径。
  - 市场下跌残差路线排除`strategy_gross`毛收益代表值，优先看净收益/超额/残差。
- 样本过滤：不新增过滤。
- 策略/归因口径：
  - 统一盘点paper线、简单20日超跌、行业残差核心、慢节奏、平滑预算、弱行业过滤、risk-on、强势回踩、ETF卫星、市场下跌残差和信号层证据。

## 结果

- paper监控线：
  - 期末权益：`2.2225`
  - 总收益：`122.25%`
  - 最大回撤：`-15.16%`
  - Sharpe：`0.7373`
  - 状态：`yellow_caution_continue_paper`
- paper/300k参照路线：
  - `base_rerun`期末权益：`2.0177`
  - 总收益：`101.77%`
  - 最大回撤：`-12.38%`
  - Sharpe：`0.8475`
- 当前线直接30万可比路线：
  - 第320慢节奏低回撤候选仍命中目标：总收益`106.98%`，最大回撤`-17.67%`，Sharpe`0.7994`。
  - 但该候选已在第321阶段被邻域反证为参数形状敏感，决策桶为`goal_hit_but_not_robust`。
  - 当前线稳健目标命中数：`0`。
- 简单20日超跌30万基准：
  - 收益最高代表：总收益`61.15%`，最大回撤`-31.66%`，Sharpe`0.4028`。
  - 低回撤代表：总收益`25.83%`，最大回撤`-13.62%`，Sharpe`0.4468`。
- 行业残差基准：
  - 主低回撤形状：总收益`37.04%`，最大回撤`-26.39%`，Sharpe`0.3495`。
  - 高收益形状：总收益`49.27%`，最大回撤`-39.15%`，Sharpe`0.3481`。
- 强势回踩交易化：
  - 最好代表总收益约`39.20%`，最大回撤约`-43.33%`，Sharpe约`0.3087`。
  - 短周期强势回踩最好代表总收益约`7.37%`，最大回撤约`-23.89%`。
- ETF路线：
  - 独立核心没有达到总收益`>=100%`且回撤`<=20%`目标。
  - 适合作为低波动卫星/状态参照，不适合作为主收益引擎。
- 总滑点：本阶段未新跑回测，不新增滑点统计。
- 总交易次数：本阶段未新跑回测，不新增交易次数统计。
- 胜率：本阶段未新跑回测，不新增胜率统计。

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_report.md`
- summary：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_architecture_summary.csv`
- signal：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_signal_evidence.csv`
- decision：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_route_decision.csv`
- quality：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_quality_checkpoints.csv`
- meta：`examples/alpha_research/native_results/stock_range_reversion_30w_architecture_inventory_2018_2026/stock_range_reversion_30w_architecture_inventory_v1_meta.json`

## 结论

- 本阶段结论：
  - 初衷没有错：目标仍是30万A股长侧横截面震荡/短反策略，高收益，最大回撤尽量压在20%以内。
  - 当前研究确实有一点偏离：最近多个阶段越来越像围绕`industry_resid_core`修补尾部，而不是重新审视哪种架构更适合30万账户。
  - 最大正面证据仍在隔离的`stock_range_paper_v1`线；当前线不能拿paper结果冒充自己的稳健候选。
  - 当前线没有通过稳健性反证的30万正式候选。
  - 强势回踩/8点统一因子暂未成为更强交易系统。
  - 简单20日超跌30万基准反而是下一阶段更健康的架构地基。
- 是否进入下一步：是。
- 下一步：
  1. 暂停`industry_resid_core`微修补。
  2. 以简单20日超跌30万基准为母本，做架构级分层验证。
  3. 逐层加入残差增强、状态预算、ETF卫星，每层必须证明真实增益。
  4. `stock_range_paper_v1`继续独立监控，不和当前线混合记账。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做既有结果盘点，不新增参数，不选择最优参数上线。结论反而是暂停微调，避免继续在同一条残差核心线上做事后修补。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：已有paper线说明股票震荡方向有价值；当前线虽然没有稳健候选，但通过盘点明确了下一步应从简单基准重建可解释架构，而不是放弃股票震荡。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：否。研究线归属未变。
- 是否追加根目录`memory.md/back_log.md`：否。本阶段是线内方向纠偏，不是正式候选、跨线合并或根级里程碑。
