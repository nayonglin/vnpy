# Stage322 平滑风险预算/分段反证

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 17:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：第321阶段后续反证；把硬阈值清仓改成连续风险预算，并做分段稳定性检查。
- 是否重要突破：否；属于重要风控线索确认，但不是正式候选。
- 是否触发A/B：否；股票震荡独立研究线，不接入第78。

## 外部调研与判断

- 参考资料：
  - Volatility Managed Portfolios：`https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf`
  - Smoothing volatility targeting：`https://arxiv.org/abs/2212.07288`
  - Volatility Targeting - Risk Management in Python：`https://hypercode.alexisbouchez.com/risk-management/lessons/volatility-targeting`
  - Backtesting a Cross-Sectional Mean Reversion Strategy in Python：`https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/`
  - GitHub risk-parity topic：`https://github.com/topics/risk-parity`
- 我的判断：业界风险预算/波动目标更偏连续暴露和组合层 overlay，不应把第320阶段的`60日/5%/清仓`直接升级。平滑规则能降低过拟合疑虑，但必须用分段结果证明不是单一压力段偶然。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `smooth60_soft0to10_floor50`：自身60日收益`<=0%`满预算，`0%-10%`线性降到`50%`。
  - `smooth60_soft0to10_floor30`：自身60日收益`<=0%`满预算，`0%-10%`线性降到`30%`。
  - `smooth80_soft0to12_floor50`：自身80日收益`<=0%`满预算，`0%-12%`线性降到`50%`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2019-01-15 到 2026-04-27，交易日`1764`天。
- 账户规模：`300,000`元。
- 成本口径：复用30万整手成交回放、涨跌停/停牌阻断、ADV参与率约束、最低佣金压力。
- 样本过滤：固定第316-321阶段四个代表形状，不扩散扫参。
- 策略/归因口径：只调整目标暴露，不改变alpha、持有期、top_k、行业上限和成交约束；分段为`2018_2022_pre_drawdown`、`2022_2024_drawdown_stress`、`2024_2026_recovery_recent`。

## 结果

- 全部平滑变体同向改善收益和回撤：`12/12`。
- 第320候选形状同向改善收益和回撤：`3/3`。
- 第320候选形状进入20%以内回撤：`0/3`。
- 回撤最浅平滑变体：
  - 场景：`industry_resid_core_h10_top8_gross70_ind2_smooth80_soft0to12_floor50`
  - 期末权益：`455,208`
  - 总收益：`51.74%`
  - 最大回撤：`-19.23%`
  - Sharpe：`0.480`
  - 总成本折算：约`139,542`元
  - 总交易次数：`22,060`
  - 胜率：`51.02%`
- 收益最高平滑变体：
  - 场景：`industry_resid_core_h10_top5_gross100_ind1_smooth60_soft0to10_floor30`
  - 期末权益：`632,370`
  - 总收益：`110.79%`
  - 最大回撤：`-35.22%`
  - Sharpe：`0.615`
  - 总成本折算：约`201,527`元
  - 总交易次数：`20,953`
  - 胜率：`50.81%`
- 第320候选形状的最佳平滑结果：
  - 场景：`industry_resid_core_h10_top5_gross70_ind1_smooth80_soft0to12_floor50`
  - 期末权益：`469,495`
  - 总收益：`56.50%`
  - 最大回撤：`-22.38%`
  - Sharpe：`0.486`
  - 总成本折算：约`145,395`元
  - 总交易次数：`18,110`
  - 胜率：`50.96%`
- 质量检查：fail `0`项，warn `1`项；warn 是候选形状平滑版本未进入20%以内回撤。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1_report.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1_summary.csv`
- orders：本阶段未落盘订单明细；完整成交约束已在回放中执行，关键订单统计写入 summary。
- daily：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1_daily.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：慢节奏风险预算是真线索，平滑暴露在四个代表形状上全部同时改善收益和回撤；但平滑版本不能复现第320硬清仓候选的`收益过百且回撤20%以内`。
- 是否进入下一步：进入，但不作为正式候选进入 paper。
- 下一步：不要继续围绕单一收益阈值扫参；应做滚动窗口/训练前后段反证，判断平滑 overlay 是否能作为组合风险预算模块，或退回为监控指标。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但不能升级正式候选。
- 原因：本阶段只运行三个预注册连续函数，且`12/12`同向改善说明不是单点硬阈值；但候选形状未达20%回撤目标，说明第320硬清仓仍有明显样本点依赖。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但价值从“直接候选”降为“风险预算 overlay/监控状态”。
- 原因：连续缩放能在压力段改善回撤，特别是候选形状2022-2024压力段`3/3`改善；但收益-回撤组合还不够强，不能直接进入实盘或paper候选。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，当前状态未变成正式候选或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内日常研究记录，不属于跨线合入或正式候选。
