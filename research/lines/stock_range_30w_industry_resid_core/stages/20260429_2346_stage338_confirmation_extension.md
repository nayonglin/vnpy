# 第338阶段：早期确认后的续航归因

## 时间

- 运行时间：2026-04-29 23:46 CST
- 当前模式：day

## 本阶段性质

- 本阶段是信号层归因，不是策略回测。
- 不新增交易规则，不修改交易参数，不修改第78，不修改`stock_range_paper_v1`。
- 不触发A/B实验。

## 外部调研与判断

- 短期反转研究常见持有期较短，且交易成本会吞噬一部分反转收益；因此不能默认“反转确认后继续延长持有”有效。
- 公开交易系统资料常提成交量/价格确认，但这些经验规则必须拆成两段验证：确认前已经发生的收益，以及确认后仍能交易的剩余收益。
- 本阶段判断：延长持有必须看第11-15日、第11-20日相对基准超额，而不能只看10日内确认样本表现。

参考资料：

- https://www.sciencedirect.com/science/article/pii/S0378426622000309
- https://www.quantifiedstrategies.com/wp-content/uploads/2023/11/Another-Look-at-Trading-Costs-and-Short-Term-Reversal-Profits.pdf
- https://arxiv.org/abs/1411.5062
- https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf
- https://www.tradebeacon.io/blog/mean-reversion-trading-strategy-guide-rsi-bollinger-bands

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_attribution.py`

## 输入与样本

- 输入目录：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_2018_2026`
- 输入文件：`stock_range_reversion_liquid_q3_30w_simple_mother_early_confirmation_v1_enriched.csv`
- 输入样本：`43,206`
- 样本场景：
  - `top8_gross50_ind2`
  - `top5_gross50_ind2`
  - `top8_gross70_ind2`
  - `top5_gross70_ind2`
- 账户规模：`300,000 CNY`

## 检查对象

- `fast_rebound_3d`
- `volume_repair_3d`
- `confirm_either`
- `confirm_both`
- `fast_only`
- `volume_only`

## 质量检查

- `focus_scenario_count`：pass，固定4个简单母本形状。
- `input_rows`：pass，样本`43,206`。
- `fwd_ret_10_rebuild_diff`：pass，重建10日收益最大误差`0`。
- `extension_columns_not_null`：pass，扩展路径可用比例`0.9922`。
- `primary_extension_candidates`：warn，主母本延长持有候选`0`。
- `guard_extension_candidates`：warn，top5护栏延长持有候选`0`。
- `broad_extension_candidates`：warn，跨场景延长持有候选`0`。
- `no_trade_rule_change`：pass，本阶段只做归因。

## 核心结果

### 主母本：`top8_gross50_ind2`

- `volume_repair_3d`
  - 覆盖率：`24.12%`
  - 10日超额边际：`+5.70pp`
  - 第11-15日超额边际：`-0.01pp`
  - 第11-20日超额边际：`-0.21pp`
  - 第11-20日年度正向比例：`33.33%`
  - 第11-20日坏尾部差：`+5.12pp`
- `fast_rebound_3d`
  - 覆盖率：`33.15%`
  - 10日超额边际：`+5.81pp`
  - 第11-15日超额边际：`-0.16pp`
  - 第11-20日超额边际：`-0.46pp`
  - 第11-20日年度正向比例：`33.33%`
  - 第11-20日坏尾部差：`+3.70pp`
- `confirm_either`
  - 覆盖率：`37.73%`
  - 10日超额边际：`+5.54pp`
  - 第11-15日超额边际：`-0.09pp`
  - 第11-20日超额边际：`-0.41pp`
  - 第11-20日年度正向比例：`33.33%`

### 护栏母本：`top5_gross50_ind2`

- `volume_repair_3d`
  - 覆盖率：`23.34%`
  - 10日超额边际：`+5.69pp`
  - 第11-15日超额边际：`-0.10pp`
  - 第11-20日超额边际：`-0.45pp`
  - 第11-20日年度正向比例：`22.22%`
- `fast_rebound_3d`
  - 覆盖率：`33.12%`
  - 10日超额边际：`+5.66pp`
  - 第11-15日超额边际：`-0.19pp`
  - 第11-20日超额边际：`-0.56pp`
  - 第11-20日年度正向比例：`22.22%`

## 重要反证

- Stage337保留下来的`fast_rebound_3d`和`volume_repair_3d`，在10日持有期内是有效确认标签，但不支持延长到15/20日。
- 主母本和top5护栏都没有通过延长持有候选条件。
- `volume_only`有很弱的第11-20日正边际，但覆盖率只有约`4.58%`，且坏尾部更高，不能作为策略方向。
- 日度分桶显示：确认比例越高，10日超额越强，但第11-20日并不继续增强，说明短反收益窗口有限。

## 产出文件

- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_v1_report.md`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_v1_candidate_status.csv`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_confirmation_extension_v1_daily_bucket_summary.csv`

## 过拟合判断

- 当前阶段过拟合判断：否。
- 理由：本阶段是反证式归因，没有把结果写成交易规则；并且用第11-15/11-20日剩余窗口避免把10日内已实现反弹误读为趋势续航。
- 风险：若后续继续从`volume_only`这种低覆盖尾部样本里找规则，过拟合风险会快速升高，应避免。

## 继续价值判断

- 继续价值判断：是，但不是延长持有方向。
- 理由：确认标签解释10日内收益质量，但不具备10日后的续航；更有价值的是反过来研究“未确认样本是否应在第3/4日减仓或退出”，而不是确认后继续加仓/延长。

## 下一步

- 优先做第339阶段：未确认样本的第4-10日减仓/退出归因。
- 先不直接写真实交易规则；先归因比较：
  - `no_confirm_by_day3`
  - `fast_rebound_3d=False`
  - `volume_repair_3d=False`
  - `confirm_either=False`
  - `confirm_both=False`
- 重点看第4-10日超额、坏尾部、年度广度，再决定是否做真实30万整手回放。
