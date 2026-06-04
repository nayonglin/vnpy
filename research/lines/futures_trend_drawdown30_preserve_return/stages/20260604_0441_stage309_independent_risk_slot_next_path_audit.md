# Stage309 独立风险槽下一路径审计

- 时间：2026-06-04 04:41 CST
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage609_independent_risk_slot_next_path_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage609_independent_risk_slot_next_path_audit_report_stage609_independent_risk_slot_next_path_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage609_independent_risk_slot_next_path_audit_chart_stage609_independent_risk_slot_next_path_audit_v1.png`
- 决策：`breadth_thesis_valid_next_path_source_tca_forward_monitor_no_backtest`
- 是否重要突破：否。属于扩池方向的下一步路径收敛，不是可晋级策略。
- 是否触发 A/B：否。没有新策略候选、没有交易白名单、没有 paper selector。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段不根据历史收益挑产品白名单，只合成既有 Stage597/601/602/604/608 证据，把扩池拆成风险槽、相关性、source、容量、TCA 和执行无偏差缺口。
- 是否有价值继续：有。用户提出的“降低单笔风险、扩大品种池、每年抓部分趋势、避免高相关、选对品种”需要从直觉变成可执行队列；否则容易退化成宽池收益扫描。

## 外部调研判断

- Man Group 趋势组合资料强调市场集合、波动、相关、流动性和成本共同决定趋势组合质量，支持“不是单市场预测，而是多市场独立风险驱动”的方向。
- commodity futures trend-following / risk parity 文献支持趋势本身比单纯 risk parity 更关键，但相关性和组合权重仍影响风险暴露。
- `pysystemtrade`、PyPortfolioOpt/HRP 等工程资料说明 instrument diversification、相关矩阵和风险预算可以作为组合层工具；但本仓库不能直接套黑箱优化器，必须回到 point-in-time source、容量和真实 TCA。
- 本阶段判断：扩池方向成立，但“选对品种”应定义为“选对可实盘识别、低相关、可承载的独立风险族”，不是历史赢家品种。

参考：

- Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix
- Trend Following, Risk Parity and Momentum in Commodity Futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
- pysystemtrade instrument diversification/correlation framework: https://github.com/robcarver17/pysystemtrade
- PyPortfolioOpt HRP/covariance tooling: https://github.com/PyPortfolio/PyPortfolioOpt

## 本阶段做了什么

- 只读合成 Stage597/601/602/604/608，不重放交易引擎。
- 新增 Stage609 独立风险槽下一路径审计脚本。
- 生成 family ladder、action queue、hard gates、decision JSON 和可视化图表。
- 首轮视觉检查发现 capacity/source 合并口径错误：容量字段来自 Stage597 family worklist，而不是 Stage601 family rescreen；已修正并重跑。
- 最终图表视觉复盘：左上显示 `4 -> 5 -> 7` 槽缺口；右上显示 `black_ferrous` 在低相关区但材料性有限，`rubber/br` 在高相关红线右侧；左下显示 capacity/source 多数有线索但 TCA 全红；右下显示下一步不是宽池回测，而是 execution/TCA、`j/i` source/TCA 和 forward monitor。

## 参数与变更

- 新增参数：无策略参数。
- 修改参数：无。
- 删除参数：无。
- 新增输出：
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_family_ladder_stage609_independent_risk_slot_next_path_audit_v1.csv`
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_action_queue_stage609_independent_risk_slot_next_path_audit_v1.csv`
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_gates_stage609_independent_risk_slot_next_path_audit_v1.csv`
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_decision_stage609_independent_risk_slot_next_path_audit_v1.json`
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_report_stage609_independent_risk_slot_next_path_audit_v1.md`
  - `qmt_roll_stage609_independent_risk_slot_next_path_audit_chart_stage609_independent_risk_slot_next_path_audit_v1.png`

## 回测结果

本阶段没有新增回测，因此以下字段不适用：

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 核心结果

- 当前有效独立风险槽：`4`
- 目标有效独立风险槽：`7`
- 当前单槽风险：`25.00%`
- 目标单槽风险：约 `14.29%`，偏好 `<=15%`
- `black_ferrous(j/i)` source/TCA 全部解决后的有效槽：`5`
- `black_ferrous` 解决后仍缺口：`2` 个独立槽
- 当前可部署 selector 槽：`0`
- P1 新独立风险槽线索：`1` 个，即 `black_ferrous(j/i)`
- P2 低频 forward monitor 族：`2` 个，即 `soft_agri`、`precious_metals`
- hard gates：`1/4`

## 风险槽判断

| 类型 | 结论 |
| --- | --- |
| 现有 P0 槽 | `grains_oilseeds / petrochem / base_metals / energy_oil` 保留结构槽，但只做 source/TCA 和执行无偏差补证，不增加槽数 |
| P1 新独立槽 | `black_ferrous(j/i)` 是唯一当前可补线索，但 DCE 官方源与真实 TCA 未闭合前不能 paper 或白名单 |
| P2 forward monitor | `soft_agri / precious_metals` 低相关且 source 较好，但历史材料性不足，只能低频观察 |
| 高相关拒绝 | `rubber/br` 有收益也不作为分散槽，核心相关 `0.2783`，压力期可能共振 |

## 行动队列

| 优先级 | 动作 | 增加槽数 | 判断 |
| --- | --- | ---: | --- |
| 0 | 闭合 read-only tick / live context / TCA 执行无偏差 | 0 | 不做这一步，扩池只是纸面可交易 |
| 1 | 修 `j/i` 的 DCE source 和每品种真实/独立分钟 TCA | +1 | 当前唯一能把 `4` 槽推到 `5` 槽的新族 |
| 2 | 对 `soft_agri / precious_metals` 做低频 point-in-time forward monitor | 0 | 不能历史回测硬救 |
| 3 | 寻找两个非 DCE、低相关、source 可执行的新独立驱动 | +2 | Stage602 全57非DCE当前未找到 |
| 4 | 继续拒绝高相关历史赢家 | 0 | `br` 这类不能冒充独立槽 |

## 结论

- 用户的方向成立：年度非核心 top6 趋势机会 `7/7` 年为正，说明“每年抓一部分趋势收益”不是空想。
- 当前不能晋级：有效槽只有 `4`，即便补完 `j/i` 也只有 `5`，离 `7` 仍差 `2` 个独立槽。
- 扩池的下一步不是宽池回测，而是三条并行：
  1. 先闭合 Stage608 后续的 read-only tick snapshot 和 TCA；
  2. 只对 `black_ferrous(j/i)` 补 source/TCA；
  3. 对 `soft_agri/precious_metals` 做 forward monitor，同时寻找两个真正新独立驱动。

## 结束后反思

- 是否过拟合：否。高收益但高相关的 `br.SHFE` 继续拒绝，source好但无材料性的族也不投入 TCA，说明没有用历史赢家救结果。
- 是否有价值继续：有，但要收敛。扩池值得做，但只能沿 source/TCA/forward ledger 推进；未达闸门前禁止宽池收益回测、P0/P1 白名单和 A/B。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage609_independent_risk_slot_next_path_audit.py` 通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage609_independent_risk_slot_next_path_audit.py` 通过。
- 图表已视觉检查；第一次 capacity/source 口径误导已修正，第二次视觉检查通过。

## TODO

- Stage608 方向：用户确认测试环境和 read-only 动作后，用 wrapper 显式 `--connect` 捕获 target tick snapshot，继续保持 `send_order=0`。
- 扩池方向：继续补 `j/i` DCE source/TCA；如果 DCE 官方源仍被 412/400 阻塞，只能转授权数据或替代准官方源。
- forward monitor：为 `soft_agri/precious_metals` 只建 point-in-time 观察账本，不做历史 selector 回测。
- 新槽搜索：下一步重点不在全57已有产品列表，而在非 DCE、低相关、source 可执行的新经济驱动或跨策略/外部承载工具。
