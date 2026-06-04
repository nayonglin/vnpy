# Stage304 低单笔风险扩池风险槽 Allocator 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 03:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读结构审计；不重放交易引擎、不修改策略、不生成交易白名单。
- 是否重要突破：否。方向被进一步确认，但未形成可部署候选。
- 是否触发A/B：否。未满足 source/TCA/执行无偏差闸门。

## 外部调研与判断

- 参考资料：
  - Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix
  - Man Group Truth or Trend: https://www.man.com/insights/truth-or-trend
  - skfolio risk budgeting / maximum diversification / HRP: https://github.com/skfolio/skfolio
  - PyPortfolioOpt HRP clustering reference: https://github.com/PyPortfolio/PyPortfolioOpt
- 我的判断：
  - 趋势跟踪的本质优势通常不是单品种高 Sharpe，而是多市场、低相关、低单槽风险的复合。
  - 但“扩大品种池”必须翻译成“扩大独立风险槽”，否则同族品种和压力期相关会让分散失效。
  - 本仓库不能直接套 HRP/最大分散黑箱优化器；当前更适合用产品族、滚动相关、source/TCA 和真实执行闸门做低自由度 allocator。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage604_low_single_risk_slot_allocator_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TARGET_EFFECTIVE_SLOTS = 7`
  - `PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0`
  - `HARD_SINGLE_SLOT_RISK_PCT = 20.0`
  - `MAX_CORE_CORR_PREFERRED = 0.10`
  - `MATERIAL_SLEEVE_PNL = 50000`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：只读合成既有 Stage574/592/602/603 输出；不新增交易回放。
- 账户规模：沿用 Stage526 / Stage574 既有口径。
- 成本口径：沿用 Stage526 / Stage574 正常成本口径；本阶段不新增滑点压力。
- 样本过滤：
  - 当前 P0 结构槽：`y/c` 同族 top1-only、`v`、`ao`、`lu`。
  - P1 新槽线索：`black_ferrous(j/i)`，但 DCE 官方源和 TCA 未闭合。
  - 高相关历史赢家如 `br.SHFE` 必须继续拒绝。
- 策略/归因口径：
  - 将“品种数”改写为“有效独立风险槽数”。
  - 用 Stage574 年度 top6 family 捕获代理检查每年是否有趋势机会。
  - 用 Stage574 可部署宽池壳检查 3/6 个月任意启动持有体验是否改善。

## 结果

- 新增交易回测：无
- 决策：`risk_slot_allocator_direction_valid_not_deployable_need_two_new_slots_and_tca`
- 期末权益：
  - Stage526 参考：`23,369,505`
  - 本阶段 allocator：无新增权益曲线
- 总收益：
  - Stage526 参考：`3699.9195%`
  - `All noncore r020` 参考：`3701.4472%`
- 最大回撤：
  - Stage526 参考：`-36.2670%`
  - `All noncore r020` 参考：`-36.3714%`
- Sharpe：
  - Stage526 参考：`1.6385`
  - `All noncore r020` 参考：`1.6374`
- 总滑点：
  - Stage526 参考：`1,342,190`
  - `All noncore r020` 参考：`1,349,620`
- 总交易次数：
  - Stage526 参考：`905`
  - `All noncore r020` 参考：`1354`
- 胜率：
  - Stage526 非零日胜率参考：`53.6330%`
  - `All noncore r020` 非零日胜率参考：`53.4900%`
- 其他关键指标：
  - 当前结构有效槽：`4`
  - 当前可部署 selector 槽：`0`
  - 当前单槽风险：`25.00%`
  - 目标有效槽：`7`
  - 目标单槽风险：`14.29%`
  - 若 `j/i` 官方源和 TCA 解决：`5` 槽，单槽风险 `20.00%`，仍差 `2` 槽。
  - 年度 top6 非核心趋势机会：`7/7` 年为正。
  - 当前 P0 family 捕获代理：多数年份 `60%-80%`，加入黑色后 2020/2024/2025 明显改善，但仍不能解决 2023/2026 缺口。
  - P0 route/event：`3/5`、`2/5`
  - fresh live context：`0/45`
  - P0 valid live TCA：`0/9`
  - 硬闸门：`2/9`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_report_stage604_low_single_risk_slot_allocator_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_decision_stage604_low_single_risk_slot_allocator_audit_v1.json`
- allocator scenarios：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_allocator_scenarios_stage604_low_single_risk_slot_allocator_audit_v1.csv`
- slot inventory：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_slot_inventory_stage604_low_single_risk_slot_allocator_audit_v1.csv`
- annual capture：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_annual_capture_stage604_low_single_risk_slot_allocator_audit_v1.csv`
- holding boundary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_holding_boundary_stage604_low_single_risk_slot_allocator_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_gates_stage604_low_single_risk_slot_allocator_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage604_low_single_risk_slot_allocator_audit_chart_stage604_low_single_risk_slot_allocator_audit_v1.png`

## 图表视觉复盘

- 左上图显示当前 P0 只有 `4` 个有效槽；即便 `black_ferrous` 解决，也只有 `5` 槽，和 `7` 槽目标仍有明显视觉缺口。
- 右上图显示加入 `black_ferrous` 能改善 2020/2024/2025 的年度 top6 family 捕获，但 2023 和 2026 的缺口来自 `financial_index/livestock/other` 等当前不可用风险源。
- 左下图显示 `br.SHFE` 位于相关性红线右侧，虽然历史收益为正，但不能作为低相关分散槽；`j/i` 在低相关区域但收益材料性和执行证据不足。
- 右下图显示可部署宽池壳 `All noncore r020 / Prev+ r020 / Prev+ r015` 的 63/126 日 p10 delta 均为负，说明没有改善任意启动后的 3/6 个月左尾体验。

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势、避免高相关”方向成立。
  - 当前不能晋级，因为有效槽不足、单槽风险仍高、盲目扩池不改善 3/6 个月体验、真实执行/TCA未闭合。
  - “选对品种”是关键，但不能用历史赢家白名单表达；必须先有 point-in-time 外生源、事件账本、source route 和真实 TCA。
- 是否进入下一步：进入补证/结构设计下一步，不进入收益回测或A/B。
- 下一步：
  1. 优先闭合执行无偏差链路：`fresh live context 45/45`、`vt_orderid` mapping、P0 `9/9` live TCA。
  2. 对 `j/i` 继续 DCE 官方源或授权替代源补证；即便成功也只把槽数从 `4` 提到 `5`。
  3. 另外寻找至少 `2` 个非DCE、低核心相关、source可执行、容量合格的新产品族；只做 forward monitor，不做历史白名单回测。

## 过拟合反思

- 运行前判断：否。因为本阶段不是根据收益挑品种，而是检验结构槽、相关性、source/TCA 和 3/6 个月体验边界。
- 运行后判断：否。`br.SHFE` 这类有收益但高相关品种被拒绝，`j/i` 低相关也因为 source/TCA 不足不能晋级，说明没有用历史赢家救结果。
- 原因：输出是闸门和缺口，不是交易名单。

## 继续价值反思

- 运行前判断：有价值。该方向把低单笔风险、扩池、避高相关和选品统一到一个可审计结构。
- 运行后判断：有价值但必须收敛。年度机会存在，说明值得继续；但继续宽池收益回测没有价值，应该转向补两个独立风险槽来源和真实执行/TCA。
- 原因：当前瓶颈不是想法，而是可部署证据不足。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，更新本线最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选或重要突破。
