# Stage028 入场前账户状态/候选排序归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：2026-07-01 16:22 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；基于 Stage024/Stage027 已有产物，不重跑交易引擎
- 是否重要突破：否；但给出下一步真实引擎候选方向
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Concretum position sizing in trend following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - pysystemtrade futures backtesting: https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - CFA trend following with managed futures: https://rpc.cfainstitute.org/research/financial-analysts-journal/2015/trend-following-with-managed-futures
  - Return Stacked managed futures trend following review: https://www.returnstacked.com/managed-futures-trend-following/
- 我的判断：趋势跟随优化不应该按某个亏损窗口做品种/方向黑名单。更合理的是在组合风险框架里看入场前账户状态、风险预算释放、保证金压力和排序质量是否有跨 source/date 的稳定解释力。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage028_entry_state_candidate_order_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `BROKER_MARGIN_MULTIPLIER = 1.10`
  - `MIN_CANDIDATE_COUNT = 50`
  - `MIN_CANDIDATE_SOURCE_COUNT = 3`
  - `MIN_CANDIDATE_BAD_DATE_COUNT = 15`
  - `MIN_CANDIDATE_LIFT = 1.25`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage027 代表坏窗口 source 的 opened `flat_entry`，日期不晚于代表坏窗口最大结束日 `2023-10-23`；实际开仓日期 `2021-01-05` 到 `2023-10-23`
- 账户规模：沿用 Stage024 当前重建 C9/15w 输出；本阶段不新建账户、不重放组合引擎
- 成本口径：沿用 Stage024 输出；本阶段只读，不新增滑点或手续费计算
- 样本过滤：
  - 只取 Stage027 代表坏窗口涉及的 `3` 个 source：`2021-01`、`2021-07`、`2022-07`
  - 只取 opened `flat_entry`
  - 若开仓日期严格晚于 selected window start 且不晚于 window end，标记为 `inside_selected_worst_window=True`
- 策略/归因口径：用入场前可见字段做坏窗口重合归因，字段包括账户回撤、loss_streak、AI rank、pairwise rank、保证金、活跃持仓、相关性和 selected_volume

## 结果

- 期末权益：N/A，只读归因
- 总收益：N/A，只读归因
- 最大回撤：N/A，只读归因
- Sharpe：N/A，只读归因
- 总滑点：N/A，只读归因
- 总交易次数：N/A，只读归因
- 胜率：N/A，只读归因
- 其他关键指标：
  - selected window 数：`50`
  - selected source 数：`3`
  - opened flat_entry 样本：`250`
  - 落入代表坏窗口的新开仓：`137`
  - 基准坏窗口开仓率：`54.8000%`
  - exposure 次数合计：`1996`
  - Stage027 背景：代表窗口 opened-after-start loss share 均值 `93.0731%`，opened-after-start loss abs 合计 `5,754,720`
  - 稳定候选条件：
    - `drawdown_abs_ge30`：`84` 笔，坏窗口率 `98.8095%`，lift `1.8031`，bad source `3`，bad date `32`，中位手数 `1`
    - `drawdown_abs_ge20`：`124` 笔，坏窗口率 `95.1613%`，lift `1.7365`，bad source `3`，bad date `43`
    - `loss_streak_ge3`：`58` 笔，坏窗口率 `93.1034%`，lift `1.6990`，bad source `3`，bad date `19`
    - `drawdown_ge20_and_volume_gt1`：`51` 笔，坏窗口率 `90.1961%`，lift `1.6459`，bad source `3`，bad date `22`
    - `loss_streak_ge2`：`96` 笔，坏窗口率 `78.1250%`，lift `1.4256`
    - `drawdown_abs_ge10`：`174` 笔，坏窗口率 `77.0115%`，lift `1.4053`
  - 反证点：
    - 单看 `selected_volume > 1` 并不更坏：`158` 笔，坏窗口率 `37.9747%`，lift `0.6930`
    - `AI rank <=4` 不够：`101` 笔，坏窗口率 `59.4059%`，lift `1.0841`
    - `AI rank <=8` 不够：`174` 笔，坏窗口率 `59.1954%`，lift `1.0802`
    - `pairwise rank <=2` 在该样本中基本等同全体，lift `1.0`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_report_stage028_entry_state_candidate_order_attribution_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_condition_summary_stage028_entry_state_candidate_order_attribution_v1.csv`
- orders：N/A
- daily：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_source_summary_stage028_entry_state_candidate_order_attribution_v1.csv`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_numeric_feature_summary_stage028_entry_state_candidate_order_attribution_v1.csv`
- entry exposure：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_entry_exposure_stage028_entry_state_candidate_order_attribution_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_condition_lift_chart_stage028_entry_state_candidate_order_attribution_v1.png`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage028_entry_state_candidate_order_attribution/rebuilt_c9_stage028_entry_state_candidate_order_attribution_decision_stage028_entry_state_candidate_order_attribution_v1.json`

## 结论

- 本阶段结论：Stage027 剩余左尾的新开/交易仓位，最强入场前可见解释不是 AI rank 或 pairwise rank，而是账户已经受伤后的状态：组合回撤 `>=20%/30%`、`loss_streak >=2/3`。单看正常释放到 `>1` 手并不危险，危险的是“回撤已经 `>=20%` 以后仍释放到 `>1` 手”。
- 是否进入下一步：可以进入真实引擎验证，但只能冻结一个低自由度版本，不能扫阈值。
- 下一步：Stage029 写真实组合引擎候选，预声明一个版本：当入场前 `portfolio_drawdown_abs >=20%` 或 `loss_streak >=3` 时，新的 `flat_entry` 不直接正常释放；优先验证“保持 1 手/暂停新开仓/等待恢复确认”三者里最符合第一性原理的一种，但不得扫手数、阈值、品种、方向或日期。

## 过拟合反思

- 运行前判断：有过拟合风险，因为标签来自 Stage027 已知最差代表窗口。
- 运行后判断：仍有过拟合风险，但比按品种/方向/日期反推要低；候选只来自入场前可见账户状态，并要求 `3` 个 source、`15` 个以上坏日期、`50` 笔以上样本。
- 原因：账户回撤和 loss_streak 本身是路径状态，和坏窗口天然相关，可能只是“已经亏了”的反应而非可避免亏损的前兆；必须通过真实引擎验证它是否减少后续亏损，同时不切断恢复段右尾。

## 继续价值反思

- 运行前判断：有价值；Stage027 已证明剩余左尾由窗口后新开/交易仓位主导。
- 运行后判断：有价值继续做一步真实引擎验证；因为 Stage028 找到了跨 source/date 的入场前状态线索，且明确排除了 AI rank/pairwise rank 和粗暴压正常仓这两条浅层路线。
- 原因：下一步可以在不改 AI 池、不接实盘、不引入新数据的情况下验证一个低自由度账户状态风险释放规则，符合“先账户层生存，再谈高质量加风险”的方向。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是研究线内部归因和候选方向，不是正式候选或重要突破
