# Stage321 低单笔风险扩池风险槽缺口优先级板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 06:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读结构审计；不新增交易规则、不重放策略引擎、不生成交易白名单、不连接 CTP。
- 是否重要突破：否。方向继续成立，但没有形成可部署候选。
- 是否触发A/B：否。新增风险预算、paper selector、交易白名单均为 `0`。

## 外部调研与判断

- 参考资料：
  - AQR risk-mitigating portfolio / trend following 组合构建：https://www.aqr.com/Insights/Research/Alternative-Thinking/Key-Design-Choices-when-Building-a-Risk-Mitigating-Portfolio
  - Man Group trend following market mix：https://www.man.com/insights/trend-following-optimal-market-mix
  - Graham Capital trend-following primer / portfolio construction：https://www.grahamcapital.com/blog/trend-following-primer-2026/
  - Riskfolio-Lib / risk budgeting 工程参考：https://github.com/dcajasn/Riskfolio-Lib
- 我的判断：
  - 多市场趋势跟踪的专业做法支持“扩大机会集合 + 风险预算 + 相关性治理”。
  - 但本仓库不能直接套 HRP / risk parity 黑箱优化器；当前更适合用低自由度的独立风险槽、产品族、point-in-time source、TCA 和执行无偏差闸门。
  - “选对品种”不能表达为历史收益榜 topN，必须表达为可实盘验证的 source/TCA/执行闭环。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage621_risk_slot_gap_priority_board.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `TARGET_EFFECTIVE_SLOTS = 7`
  - `CURRENT_EFFECTIVE_SLOTS = 4`
  - `IF_BLACK_FERROUS_RESOLVED_SLOTS = 5`
  - `PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0`
  - `HARD_SINGLE_SLOT_RISK_PCT = 20.0`
  - `MAX_CORE_CORR_PREFERRED = 0.10`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 新增交易回测：无。
- 数据区间：只读 Stage604/611/620 冻结输出。
- 账户规模：沿用 Stage526/Stage604 结构口径；本阶段不产生新权益曲线。
- 成本口径：不新增成本压力；引用 Stage604 对 Stage526 与宽池壳的既有审计。
- 样本过滤：
  - 当前结构槽：`grains_oilseeds`、`petrochem`、`base_metals`、`energy_oil`，其中 `y/c` 同族同向必须 top1。
  - P1 新槽：仅 `black_ferrous(j/i)`，但 source/TCA/live context 未闭合。
  - P2 forward monitor：`precious_metals(ag)`、`soft_agri(CY/SR)`。
  - 高相关拒绝：`rubber(br)`、`other(PR)` 不得因历史收益转成分散槽。

## 结果

- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
  - All noncore r020 参考：`23,378,900`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
  - All noncore r020 参考：`3701.4472%`
- 最大回撤：
  - Stage526 参考：`-36.2670%`
  - All noncore r020 参考：`-36.3714%`
- Sharpe：
  - Stage526 参考：`1.6385`
  - All noncore r020 参考：`1.6374`
- 总滑点：
  - Stage526 参考：`1,342,190`
  - All noncore r020 参考：`1,349,620`
- 总交易次数：
  - Stage526 参考：`905`
  - All noncore r020 参考：`1354`
- 胜率：
  - Stage526 非零日胜率参考：`53.6330%`
  - All noncore r020 非零日胜率参考：`53.4900%`
- 本阶段关键指标：
  - 决策：`risk_slot_gap_priority_board_direction_valid_no_promotion_need_two_new_independent_slots`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`
  - 当前有效结构槽：`4`
  - 当前单槽风险：`25.00%`
  - 目标有效槽：`7`
  - 目标单槽风险：`14.2857%`
  - `black_ferrous(j/i)` 闭合后：`5` 槽，单槽风险 `20.00%`
  - `black_ferrous` 闭合后仍差：`2` 个独立槽
  - P1 新槽家族：`black_ferrous`
  - P2 forward monitor 家族：`precious_metals`、`soft_agri`
  - 年度 top6 在 P0+black 后仍缺口家族：`financial_index`、`livestock`、`other`、`rubber`、`soft_agri`
  - Stage620 source products：`5`
  - Stage620 selector ready count：`0`
  - 硬闸门：`3/9`

## 图表视觉复盘

- 左上图：`deployable_today=0`、`current_structural_p0=4`、`after_black_ferrous_closed=5`、`target=7`，槽位缺口很直接；`j/i` 不是终点，只能把单槽风险从 `25%` 降到 `20%`。
- 右上图：`black_ferrous` 位于低相关且有正材料性的区域，是唯一 P1；`rubber` 与 `other` 位于高相关侧，不能因为历史收益正就加入。
- 左下图：年度缺口在 `2020/2024/2025` 反复指向 `rubber`，但该家族高相关被拒绝；`2023/2026` 指向 `financial_index/livestock`，当前缺材料性或 source/TCA 闭环。
- 右下图：绿灯只来自 fail-closed 纪律和高相关赢家拒绝；目标槽数、3/6个月持有体验、Stage620 selector source、两个新独立槽均失败。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_report_stage621_risk_slot_gap_priority_board_v1.md`
- family priority：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_family_priority_stage621_risk_slot_gap_priority_board_v1.csv`
- slot ladder：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_slot_ladder_stage621_risk_slot_gap_priority_board_v1.csv`
- annual miss：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_annual_miss_stage621_risk_slot_gap_priority_board_v1.csv`
- source contract summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_source_contract_summary_stage621_risk_slot_gap_priority_board_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_gates_stage621_risk_slot_gap_priority_board_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_decision_stage621_risk_slot_gap_priority_board_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_chart_stage621_risk_slot_gap_priority_board_v1.png`

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分趋势、避免高相关”方向继续成立。
  - 但当前不是“加更多品种就能解决”，而是有效独立风险槽不足。
  - 当前只有 `4` 个结构槽，`black_ferrous` 全闭合也只有 `5` 个，距离 `7` 个目标仍差 `2` 个。
  - 当前没有任何新增风险预算、paper selector 或交易白名单。
- 是否进入下一步：进入，但只进入补证/forward monitor；不进入收益回测化 selector 或 A/B。
- 下一步：
  1. 优先闭合 `black_ferrous(j/i)` 的官方/授权 source、raw_hash、live TCA 和 live context。
  2. `precious_metals/soft_agri` 只做至少 `12` 个月 point-in-time forward monitor，并要求至少 `3` 个独立趋势 episode 后再谈 TCA 预算。
  3. 继续寻找 `2` 个非高相关、非同族重复、source 可执行、容量合格的新独立经济驱动；不使用历史收益榜白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有重放策略、没有调交易参数、没有根据历史收益新增白名单。
  - 历史正收益但高相关的 `rubber/br` 被拒绝，低相关但材料性不足的 `precious_metals/soft_agri` 也没有晋级。
  - 输出是缺口和工作队列，而不是收益候选。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但必须收敛。
- 原因：
  - 年度 top6 机会证明“每年抓部分品种趋势”不是空想。
  - 但 Stage604 已证明可部署宽池壳不改善 3/6 个月左尾，继续盲目扩池回测没有价值。
  - 后续价值在于新增真实独立风险槽和 source/TCA/执行闭环，而不是继续扫产品名单。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage621_risk_slot_gap_priority_board.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage621_risk_slot_gap_priority_board.py`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage621_risk_slot_gap_priority_board_decision_stage621_risk_slot_gap_priority_board_v1.json`：通过。
- 图表已视觉检查并修正标签/heatmap 可读性。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage321。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破、路线废弃或跨线合并。
