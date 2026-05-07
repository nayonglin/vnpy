# 第330阶段 股票震荡30万中段持仓退出/减仓探针

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 21:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：预注册中段持仓路径规则回放，完整复用30万整手成交/最低佣金/成交约束
- 是否重要突破：否，属于关键反证
- 是否触发A/B：否，独立股票震荡研究，不接第78

## 外部调研与判断

- 参考资料：
  - [A Mean Reversion Strategy from First Principles Thinking](https://www.quantitativo.com/p/a-mean-reversion-strategy-from-first)
  - [Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit](https://arxiv.org/abs/1411.5062)
  - [Mean Reversion Trading with Sequential Deadlines and Transaction Costs](https://arxiv.org/abs/1707.03498)
  - [Short-term reversals, returns to liquidity provision and immediacy costs](https://www.sciencedirect.com/science/article/pii/S0378426622000309)
  - [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)
- 我的判断：均值回归系统确实必须研究退出/时间约束，但传统硬时间止损或简单“未反弹就降仓”很容易把反转策略的收益发动机一起砍掉。第329阶段确认中段既是收益主来源也是亏损主通道，因此本阶段只能做预注册粗规则反证，不能为了命中最差样本继续扫阈值。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `age4_unrecovered_half`
  - `age4_unrecovered_exit`
  - `age6_unrecovered_half`
  - `age6_unrecovered_exit`
  - `age4_no_bounce1pct_half`
  - `age8_no_bounce1pct_exit`
  - `age4_new_low_half`
  - `age_decay4_10_floor70`
  - `age_decay4_10_floor50`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2019-01-15 到 2026-04-27
- 账户规模：30万现金账户
- 成本口径：复用30万整手回放逻辑，最低佣金`5`元，成本/成交约束/涨跌停约束重新计算
- 样本过滤：固定四个代表形状，主观察`industry_resid_core_h10_top8_gross70_ind2`
- 策略/归因口径：不改入场信号、模型分数、top_k、行业上限；只在每日开盘调仓前根据截至前一日可见的episode收益路径缩放目标权重

## 结果

- 期末权益：最佳非基准也未超过基准；本阶段不形成候选
- 总收益：
  - 总收益最高仍是基准`industry_resid_core_h10_top8_gross100_ind2_base_rerun`：`49.27%`
  - 非基准总收益最高为`industry_resid_core_h10_top8_gross100_ind2_age_decay4_10_floor70`：`34.17%`
  - 主低回撤场景基准：`37.04%`
  - 主低回撤场景收益改善最大非基准`age4_no_bounce1pct_half`：`18.50%`，收益变化`-18.55pp`
- 最大回撤：
  - 所有规则中最浅为`industry_resid_core_h10_top5_gross70_ind1_age_decay4_10_floor70`：`-23.00%`，仍未进入20%以内
  - 主低回撤场景基准：`-26.39%`
  - 主低回撤场景`age_decay4_10_floor70`：`-23.13%`，回撤改善`+3.25pp`，但收益下降`-18.89pp`
  - 主低回撤场景`age4_no_bounce1pct_half`：`-24.15%`，回撤改善`+2.24pp`，但收益下降`-18.55pp`
- Sharpe：
  - 主低回撤场景基准：`0.349`
  - 主低回撤场景`age_decay4_10_floor70`：`0.244`
  - 主低回撤场景`age4_no_bounce1pct_half`：`0.243`
- 总滑点：沿用源回放成本口径，不新增滑点参数
- 总交易次数：见`orders`输出，本阶段以订单文件为准
- 胜率：本阶段重点看收益/回撤/年度/滚动同向改善，不单独用胜率作为决策
- 其他关键指标：
  - 质量检查：`0 fail`，`5 warn`
  - 基准复现源30万整手回放误差：`0.0`
  - 同时改善收益和回撤的规则：`0`
  - 年度收益+回撤同向改善过半规则：`0`
  - 252日滚动收益+回撤同向改善过半规则：`0`
  - 最好的年度同向改善率：`25%`
  - 最好的252日滚动同向改善率：`41.10%`
  - 主低回撤场景触发强度过宽：`age4_no_bounce1pct_half`缩放日占`92.86%`，`age_decay4_10_floor70`缩放日占`92.69%`
  - 硬退出规则明显失败：主低回撤`age4_unrecovered_exit`总收益`-76.29%`、最大回撤`-77.96%`；`age6_unrecovered_exit`总收益`-68.23%`、最大回撤`-72.64%`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1_report.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1_summary.csv`
- orders：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1_orders.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1_daily.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：简单中段时间止损、未反弹减仓、年龄衰减都不能升级候选。它们能削一点回撤，但代价是明显降低收益；硬退出更是直接破坏策略。
- 是否进入下一步：是，但不是继续扫时间止损阈值。
- 下一步：转向“中段再确认/信号衰减”而不是“持有天数规则”。具体方向是检查持仓第4-7日时，当前模型分数、行业内排名、残差回归信号是否仍然支持继续持有；如果信号已经消失，再考虑减仓。

## 过拟合反思

- 运行前判断：中等
- 运行后判断：否定简单规则，不升级候选
- 原因：本阶段虽然从第329最差路径出发，存在事后裁剪风险，但规则预注册、粗粒度、并做了年度/252日滚动反证。结果没有出现可升级规则，因此没有过拟合出“漂亮候选”。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是，但方向要收窄
- 原因：中段路径确实是关键，但“时间到了就减仓”不是本质。更本质的问题是中段持仓时原始alpha是否仍然存在；继续研究应围绕信号持续性，而不是围绕持有天数扫参。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非跨线里程碑
