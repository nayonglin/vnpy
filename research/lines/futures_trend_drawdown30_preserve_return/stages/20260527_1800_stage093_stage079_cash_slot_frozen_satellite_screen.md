# Stage093 Stage079现金槽位冻结卫星筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 18:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；不修改 C3 交易规则，不增加 `61.5万` 账户资金，不扫小数权重。
- 是否重要突破：否。现金槽位冻结卫星没有可晋级候选。
- 是否触发A/B：是。A 为 Stage079，C 为 Stage079 的 `11.5万` 现金槽位替换为已有冻结卫星曲线。

## 外部调研与判断

- 参考资料：
  - trend following / time-series momentum volatility scaling 文献：波动缩放和多市场分散可能改善尾部，但短期路径痛苦仍需滚动窗口验证。
  - commodity futures trend/carry/value 组合研究与 GitHub `futuresbacktest` 代码片段：实践上常把 trend、carry、value 或横截面动量拆成不同因子，而不是在同一趋势阈值上反复调小数。
  - backtesting.py / finmarketpy 等开源框架：强调多指标、滚动窗口、成本和路径验证。
- 我的判断：
  - 暴涨冷却路线已在 Stage091/092 真实引擎反证，本阶段不继续修补坏窗口。
  - 若要在不劣化 Stage079 核心指标下改善 3个月/6个月体验，最自然的下一步是用 `11.5万` 现金槽位寻找独立收益源；但期货卫星缩放到 `11.5万` 必须先标为诊断，不能绕过整数手数和保证金约束。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `cashslot_fu_sn_satellite_scaled`：`11.5万` 现金槽位缩放既有 `fu/sn` 趋势卫星。
  - `cashslot_xsmom_12m_cost20`：`11.5万` 现金槽位承载 Stage045 `12-1月` 横截面动量净值层卫星，成本 `20bps`。
  - `cashslot_range100_scaled`：`11.5万` 现金槽位缩放既有震荡卫星。
  - `cashslot_equal_fu_xsmom`：`11.5万` 现金槽位等分 `fu/sn` 趋势卫星与 `12-1月` 横截面动量。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage079 公共区间。
- 账户规模：固定 `61.5万`，即 `50万C3 + 11.5万现金槽位`。
- 成本口径：
  - C3 沿用 Stage079 正常成本与 `2x/3x/5x` 滑点压力重构。
  - 有真实日滑点的卫星按缩放滑点同步做压力。
  - xsmom 净值层以 `20bps` 成本为 1x，压力用 `cost0 - cost20` 差额近似放大。
- 样本过滤：无新增过滤。
- 策略/归因口径：只读合成，不改 C3、不改卫星策略、不改品种池。

## 结果

- Stage079 基准：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3182`
  - Ulcer：`15.0931`
  - 252/504日滚动破30回撤率：`0% / 0%`
  - 年度/季度回撤30内通过率：`100% / 100%`
- `cashslot_xsmom_12m_cost20`：
  - 总收益：`4961.0038%`
  - 最大回撤：`-29.4188%`
  - Sharpe：`1.3239`
  - Ulcer：`14.9520`
  - 252/504日滚动破30回撤率：`0% / 0%`
  - 年度/季度回撤30内通过率：`100% / 100%`
  - 3个月体验分：`103.3165`
  - 6个月体验分：`111.0170`
  - 综合短持有体验分：`107.5518`
  - 硬约束若忽略“诊断项”可通过，但仍未达到 3个月 `>=110`，且 6个月改善项仅 `4/8`，不能晋级。
- `cashslot_fu_sn_satellite_scaled`：
  - 总收益：`5372.9140%`
  - 最大回撤：`-32.7764%`
  - Sharpe：`1.3394`
  - Ulcer：`15.1768`
  - 252/504日滚动破30回撤率：`10.1892% / 25.5390%`
  - 年度/季度回撤30内通过率：`66.6667% / 73.9130%`
  - 综合短持有体验分：`105.9344`
  - 结论：高收益不能覆盖路径风险，废弃。
- `cashslot_equal_fu_xsmom`：
  - 总收益：`5166.9589%`
  - 最大回撤：`-31.3155%`
  - Sharpe：`1.3350`
  - Ulcer：`15.0294`
  - 252/504日滚动破30回撤率：`9.9466% / 25.2626%`
  - 综合短持有体验分：`104.2834`
  - 结论：仍被 `fu/sn` 路径拖穿30，废弃。
- `cashslot_range100_scaled`：
  - 总收益：`4947.8585%`
  - 最大回撤：`-29.6861%`
  - Sharpe：`1.3182`
  - Ulcer：`15.0896`
  - 综合短持有体验分：`100.2327`
  - 结论：几乎等同 Stage079，不能解决3个月/6个月体验。

## 3个月/6个月关键指标

- `cashslot_xsmom_12m_cost20` 3个月：
  - 5%分位收益：`-11.3918%`，仍远低于 `>-8%`。
  - 中位收益：`13.4523%`，低于 Stage079 的 `13.5155%`。
  - 正收益率：`73.6274%`，低于 `80%`。
  - 年化低于5%概率：`29.2079%`，高于 `22%`。
  - 最差期内回撤：`-29.4188%`，比 Stage079 略差于 3个月基准 `-29.1988%`。
  - 破20回撤率：`18.2268%`，高于 `12%`。
  - Ulcer P95：`17.5215`，高于 `15`。
  - P95最长水下：`88` 天，高于 `80` 天。
- `cashslot_xsmom_12m_cost20` 6个月：
  - 5%分位收益：`-1.4312%`，比 Stage079 改善，但未转正。
  - 中位收益：`33.6787%`，低于 Stage079 的 `33.9211%`。
  - 正收益率：`93.5741%`，低于 `95%`。
  - 年化低于5%概率：`8.8649%`，高于 `6%`。
  - 最差期内回撤：`-29.4188%`，改善。
  - 破20回撤率：`35.7411%`，未改善。
  - Ulcer P95：`19.7757`，高于 `17`。
  - P95最长水下：`167` 天，高于 `150` 天。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_report_stage393_stage079_cash_slot_frozen_satellite_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_summary_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_horizon_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_score_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_gate_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_cost_stress_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_daily_stage393_stage079_cash_slot_frozen_satellite_screen_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen_decision_stage393_stage079_cash_slot_frozen_satellite_screen_v1.json`

## 结论

- 本阶段结论：`no_promotable_candidate`。
- 是否进入下一步：现金槽位冻结卫星路线暂不晋级；xsmom 可保留为“方向弱线索”，但不能围绕 `11.5万`、`12-1月` 或成本小数继续救。
- 下一步：
  - 不继续救 `fu/sn` 现金槽位缩放，因为破30和滚动破30直接失败。
  - 不继续救既有震荡卫星现金槽位，因为效果近似为零。
  - xsmom 方向若继续，只能换承载方式或作为外生状态/风险温度计，不能继续做小资金期货卫星权重微调。
  - 主目标仍需寻找真正能提升3个月左尾的外生信息源，而不是只提升6个月。

## 过拟合反思

- 运行前判断：不是参数过拟合。
- 运行后判断：不是过拟合，但不能晋级。
- 原因：
  - 本阶段不新增阈值、不按坏窗口调权重、不扫小数；只复用已有冻结曲线。
  - `cashslot_xsmom_12m_cost20` 的结果方向较好但不足，继续在 `11.5万` 现金槽位、成本 bps 或 xsmom 权重上微调会变成过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：总目标仍有价值，但现金槽位冻结卫星继续价值有限。
- 原因：
  - 现金槽位只有 `11.5万`，即使有低相关正收益，也很难把 3个月正收益率、左尾和水下天数推到目标区间。
  - 需要更本质的信息源：能提前识别短期亏损窗口，且不能来自坏窗口归因；或者找到可以在61.5万内真实承载、同时高收益低相关的工具。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
