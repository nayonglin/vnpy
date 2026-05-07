# 第336阶段 简单超跌母本连续风险预算回放

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 22:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：30万整手账户回放；固定简单20日超跌母本，只测试预注册连续风险预算
- 是否重要突破：否；但属于重要反证
- 是否触发A/B：否。未形成正式候选，不接第78，不改`stock_range_paper_v1`

## 外部调研与判断

- 参考资料：
  - Volatility Managed Portfolios：https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf
  - Smoothing volatility targeting：https://arxiv.org/abs/2212.07288
  - Volatility Targeting - Risk Management in Python：https://hypercode.alexisbouchez.com/risk-management/lessons/volatility-targeting
  - Target volatility strategies：https://www.pfolio.io/academy/target-volatility-strategy
  - Backtesting a Cross-Sectional Mean Reversion Strategy in Python：https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/
  - GitHub volatility topics：https://github.com/topics/volatility
- 我的判断：业界风险预算/波动目标更适合作为连续、低频、可解释的组合层overlay，而不是硬阈值清仓。当前线要避免为了压回撤而扫阈值，所以本阶段只设置5个预注册预算函数，并重新经过30万整手账户回放。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `hot60_0to10_floor70`
  - `hot60_0to10_floor50`
  - `hot80_0to12_floor70`
  - `repair60_m8_boost115_hot10_floor70`
  - `repair80_m10_boost110_hot12_floor75`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-04-20到2026-04-27
- 账户规模：300,000 CNY
- 成本口径：沿用30万整手账户最低佣金压力口径`strategy_daily_ret_min_fee`
- 样本过滤：固定四个简单母本形状`top8_gross50_ind2`、`top5_gross50_ind2`、`top8_gross70_ind2`、`top5_gross70_ind2`
- 策略/归因口径：不改变选股、top_k、行业上限、持有期、成交约束；每天只按截至前一日的变体自身权益曲线计算预算缩放，再重新经过整手取整和交易成本回放

## 结果

- 期末权益：最佳收益变体`top8_gross70_ind2_repair80_m10_boost110_hot12_floor75`为`1.7162`
- 总收益：最佳收益变体`71.62%`
- 最大回撤：最佳收益变体`-32.82%`
- Sharpe：最佳收益变体`0.4605`
- 总滑点：未单独统计滑点；沿用最低佣金/交易成本口径
- 总交易次数：输出`orders.csv`，本阶段摘要未单独列总次数
- 胜率：本阶段为组合日度回放，不统计单笔胜率
- 其他关键指标：
  - 质量检查：`pass=6`、`warn=5`、`fail=0`
  - 全部预算变体收益和回撤同向改善`0/20`
  - 高收益且20%以内回撤候选`0`
  - 主母本`top8_gross50_ind2`回撤最浅：`hot60_0to10_floor50`，总收益`43.15%`，最大回撤`-23.23%`，相对母本收益`-6.43pp`，回撤`+0.06pp`
  - 主母本收益最高：`repair60_m8_boost115_hot10_floor70`，总收益`52.16%`，最大回撤`-24.70%`，相对母本收益`+2.57pp`，回撤`-1.42pp`
  - 高暴露`top8_gross70_ind2`收益最高：`repair80_m10_boost110_hot12_floor75`，总收益`71.62%`，最大回撤`-32.82%`，相对母本收益`+10.47pp`，回撤`-1.17pp`
  - 主母本非2018主要回撤窗口有局部改善：`hot60_0to10_floor50`同向改善`6/6`，平均收益差`+1.49pp`，平均回撤差`+1.22pp`
  - 但主母本年度广度不足：最佳年度收益和回撤同向改善比例`44.44%`

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1_report.md`
- summary：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1_summary.csv`
- orders：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1_orders.csv`
- daily：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1_daily.csv`
- quality：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：连续预算确实识别了非2018主要回撤窗口，尤其是主母本`top8_gross50_ind2`的hot-only规则；但它没有解决全局最大回撤，也没有把收益推近100%。带修复加仓的规则能提高收益，却稳定恶化最大回撤。
- 是否进入下一步：进入，但不继续做组合层预算扫参。
- 下一步：转向信号层“反转兑现/失败”识别。组合层预算最多保留为非2018窗口缓冲线索，不能作为当前30万高收益低回撤主引擎。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但预算状态仍需谨慎。
- 原因：本阶段没有改变alpha，也没有搜索大量阈值；5个规则为预注册函数并重新过整手回放。风险在于“策略自身热度”来自样本内归因，结果显示并不能全局达标，因此不升级。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但方向要转。
- 原因：股票震荡30万路线仍有alpha和风险窗口可解释性；但组合层预算已经证明不能独立达到目标，下一步应研究信号层如何识别好反转和坏反转，而不是继续加仓/降仓函数。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录第336阶段反证结论。
- 是否更新 `research/registry.md`：否，未发生跨线状态迁移。
- 是否追加根目录 `memory.md/back_log.md`：否，属于本线日常研究反证，不是正式候选或跨线合入。
