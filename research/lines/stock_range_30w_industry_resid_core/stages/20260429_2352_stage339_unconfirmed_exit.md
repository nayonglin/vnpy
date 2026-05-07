# 第339阶段：未确认样本第4-10日减仓/退出归因

## 时间

- 运行时间：2026-04-29 23:52 CST
- 当前模式：day

## 本阶段性质

- 本阶段是信号层归因，不是策略回测。
- 不新增交易规则，不修改交易参数，不修改第78，不修改`stock_range_paper_v1`。
- 不触发A/B实验。

## 外部调研与判断

- 均值回归系统常见退出方法包括时间截止、确认失败、止损/止盈，但退出规则很容易误伤反弹。
- 短期反转研究说明收益窗口通常较短，但不等于未确认后就该退到现金；需要看剩余持有期本身是否为负贡献。
- GitHub公开均值回归项目可作工程参考，但多数不会处理A股T+1、整手、涨跌停和30万账户颗粒度，不能直接复制。
- 本阶段判断：只有当未确认样本第4-10日绝对收益和超额收益都为负、坏尾部更高、年度广度足够，才允许进入真实退出回放。

参考资料：

- https://backtestme.com/guides/mean-reversion-strategies
- https://arxiv.org/abs/1707.03498
- https://arxiv.org/abs/1411.5062
- https://www.sciencedirect.com/science/article/pii/S0378426622000309
- https://www.sciencedirect.com/science/article/pii/S1386418112000468
- https://github.com/topics/mean-reversion-trading

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_attribution.py`

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

## 预注册退出旗标

- `no_fast_rebound_3d`
- `no_volume_repair_3d`
- `no_confirm_either`
- `no_confirm_both`
- `no_confirm_either_and_no_bounce`
- `no_confirm_either_and_industry_failure`
- `no_confirm_either_and_volume_failure`
- `no_confirm_either_and_breakdown`
- `no_confirm_either_and_stock_lags_industry`

## 质量检查

- `focus_scenario_count`：pass，固定4个简单母本形状。
- `input_rows`：pass，样本`43,206`。
- `late_ret_4_10_rebuild_diff`：pass，使用`fwd_ret_3/10`复原第4-10日路径，最大误差`0`。
- `exit_flag_count`：pass，预注册9个未确认/风险组合旗标。
- `primary_exit_candidates`：warn，主母本退出候选`0`。
- `guard_exit_candidates`：warn，top5护栏退出候选`0`。
- `broad_exit_candidates`：warn，跨场景退出候选`0`。
- `no_trade_rule_change`：pass，本阶段只做归因。

## 核心结果

### 主母本：`top8_gross50_ind2`

- `no_confirm_either`
  - 覆盖率：`62.27%`
  - 第4-10日绝对收益：`+0.65%`
  - 第4-10日超额收益：`+0.57%`
  - 若第4日退到现金，绝对收益边际：`-0.65pp`
  - 相对确认样本第4-10日收益差：`-0.57pp`
  - 坏尾部差：`-3.35pp`
  - 现金退出正向年度比例：`22.22%`
- `no_volume_repair_3d`
  - 覆盖率：`75.88%`
  - 第4-10日绝对收益：`+0.68%`
  - 第4-10日超额收益：`+0.59%`
  - 若第4日退到现金，绝对收益边际：`-0.68pp`
  - 相对确认样本第4-10日收益差：`-0.77pp`
  - 坏尾部差：`-3.02pp`
  - 现金退出正向年度比例：`11.11%`
- `no_fast_rebound_3d`
  - 覆盖率：`66.85%`
  - 第4-10日绝对收益：`+0.79%`
  - 第4-10日超额收益：`+0.61%`
  - 若第4日退到现金，绝对收益边际：`-0.79pp`
  - 现金退出正向年度比例：`11.11%`

### 护栏母本：`top5_gross50_ind2`

- `no_confirm_either`
  - 覆盖率：`62.42%`
  - 第4-10日绝对收益：`+0.70%`
  - 第4-10日超额收益：`+0.59%`
  - 若第4日退到现金，绝对收益边际：`-0.70pp`
- `no_volume_repair_3d`
  - 覆盖率：`76.66%`
  - 第4-10日绝对收益：`+0.68%`
  - 第4-10日超额收益：`+0.57%`
  - 若第4日退到现金，绝对收益边际：`-0.68pp`

## 重要反证

- 未确认样本确实弱于确认样本，但并不是负收益；它们第4-10日绝对收益和超额收益仍为正。
- 因此第4日退到现金会损失后续反弹，不支持未确认硬退出。
- 更极端的未确认组合，如`no_confirm_either_and_breakdown`、`no_confirm_either_and_volume_failure`，第4-10日绝对收益反而更高，说明它们包含强反弹弹性，硬止损会误伤。
- 日度分桶同样没有支持硬退出：未确认比例高的交易日，10日超额较差，但第4-10日平均绝对收益仍为正。

## 产出文件

- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_v1_report.md`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_v1_candidate_status.csv`
- `examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_2018_2026/stock_range_reversion_liquid_q3_30w_simple_mother_unconfirmed_exit_v1_daily_bucket_summary.csv`

## 过拟合判断

- 当前阶段过拟合判断：否。
- 理由：本阶段是预注册未确认旗标归因，没有写入交易规则；结果是反证而不是挑选新参数。
- 风险：如果继续从小覆盖极端样本中寻找退出规则，过拟合风险会快速升高，应停止这条硬退出方向。

## 继续价值判断

- 继续价值判断：是，但不是持仓管理硬规则方向。
- 理由：第338反证确认后延长持有，第339反证未确认后硬退出，说明10日持有窗口本身可能是简单母本的关键结构。
- 后续价值更可能来自入场质量、组合暴露结构、分散度/行业/日期层控制，而不是继续修改持有期。

## 下一步

- 暂停“确认后延长/未确认退出”这类持仓管理硬规则。
- 优先做第340阶段：简单母本日期层/组合层风险归因，识别最大回撤来自哪些交易日状态、行业集中、候选宽度、零手缺口或市场同步风险。
- 目标是回答：既然10日持有不能轻易改，能否在入场日或组合构造层降低大回撤，而不是中途硬切。
