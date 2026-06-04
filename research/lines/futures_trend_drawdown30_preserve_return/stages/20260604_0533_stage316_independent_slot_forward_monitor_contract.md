# Stage316 独立风险槽 forward monitor 合同

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：低单笔风险扩池方向的只读监控合同；把“选对品种”定义为有效独立经济驱动槽的 forward monitor，而不是历史收益 topN。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage616_independent_slot_forward_monitor_contract.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_report_stage616_independent_slot_forward_monitor_contract_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_chart_stage616_independent_slot_forward_monitor_contract_v1.png`
- 决策：`forward_monitor_contract_ready_no_new_slot_budget`
- 是否重要突破：否。它给出下一步监控合同，但没有新增可部署风险预算。
- 是否触发 A/B：否。没有 paper selector、交易白名单或正式候选。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段不做宽池收益扫描、不按历史收益 topN 选品、不调相关阈值小数，只读取 Stage601/602/611/615 的冻结证据。
- 是否有价值继续：有。当前目标第4点要求减少单笔风险和扩大品种池，但现有结果显示瓶颈不是产品数量，而是有效独立风险槽不足；需要把后续观察标准固化下来。

## 外部调研与判断

- 商品趋势跟随研究支持跨市场分散，但风险平价或等风险权重本身不是 alpha，不能用权重工程替代趋势机会。
- Managed futures 资料强调新增低相关市场能改善分散，但相关性会随环境变化抬升，所以必须做家族/压力期相关性检查。
- `pysystemtrade`、HRP/风险聚类等开源实现都指向同一个工程原则：组合分散要按 instrument/family/risk budget 管理，而不是用历史收益榜扩名单。
- 本阶段判断：用户提出的方向成立，但正确表达是“新增有效独立经济驱动槽”；当前没有新增预算的证据。

参考：

- Trend Following, Risk Parity and Momentum in Commodity Futures：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813`
- CME Managed Futures Research Digest：`https://www.cmegroup.com/education/files/research-digest.pdf`
- Rob Carver `pysystemtrade`：`https://github.com/robcarver17/pysystemtrade`
- PyPortfolioOpt HRP reference：`https://github.com/PyPortfolio/PyPortfolioOpt`

## 本阶段做了什么

- 读取 Stage611 family admission protocol。
- 读取 Stage602 full57 non-DCE scout，确认没有遗漏可部署非DCE新族。
- 读取 Stage615 live evidence 决策，继承 live context `0/45`、P0 live TCA `0/9` 的执行阻塞状态。
- 新增 Stage616 脚本，生成：
  - slot ladder；
  - monitor plan；
  - promotion gates；
  - hard gates；
  - decision JSON；
  - markdown report；
  - 可视化图表。
- 不回放收益，不改策略，不生成白名单。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage616_independent_slot_forward_monitor_contract.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `TARGET_EFFECTIVE_SLOTS = 7`
  - `CURRENT_EFFECTIVE_SLOTS = 4`
  - `IF_BLACK_FERROUS_RESOLVED_SLOTS = 5`
  - `MAX_CORE_CORR_PREFERRED = 0.10`
  - `MAX_CORE_CORR_WATCH = 0.20`
  - P2 forward monitor 最低观察期：`12` 个月。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- 当前有效独立结构槽：`4`
- 目标有效独立槽：`7`
- 当前单槽风险约：`25.00%`
- 目标单槽风险约：`14.29%`
- 如果 `black_ferrous(j/i)` source/TCA 全部闭合：`5` 槽，单槽风险仍约 `20.00%`
- 当前新增预算：`0%`
- 当前 paper selector：`0`
- 当前交易白名单：`0`
- P1 source/TCA worklist：`black_ferrous`
- P2 forward monitor only：`precious_metals`、`soft_agri`
- 高相关拒绝：`rubber`、`other`
- live context：`0/45`
- P0 valid live TCA：`0/9`

## 监控合同

| 层级 | 家族 | 动作 | 晋级前证据 |
| --- | --- | --- | --- |
| P0 reference | `grains_oilseeds`、`petrochem`、`base_metals`、`energy_oil` | 只补执行/source/TCA，不增加槽数 | read-only snapshot、exact `vt_orderid`、P0 live TCA `9/9` |
| P1 source/TCA worklist | `black_ferrous(j/i)` | 每周 source probe、每月点时化 ledger | DCE官方源或可授权替代源、`received_at/source_url/raw_hash`、live context/TCA |
| P2 forward monitor | `precious_metals`、`soft_agri` | 每月点时化快照，不投入TCA预算 | 连续12个月、至少3个独立趋势 episode、3/6个月左尾不劣化 |
| Reject/recheck | `rubber`、`other` | 只做季度相关性复查 | 相关性长期回到 watch 线内且经济驱动可重新定义 |

## 晋级闸门

| 闸门 | 当前状态 | 结论 |
| --- | --- | --- |
| independent_slot_count | `4`，即使黑色闭合也只有 `5` | 阻塞 |
| same_family_top1_same_direction | 合同通过 | 只允许同族同向 top1 |
| low_core_corr | mixed | `rubber` 等高相关拒绝 |
| point_in_time_source | DCE `j/i` official route blocked | 阻塞 |
| live_execution_tca | `0/45` live context、`0/9` live TCA | 阻塞 |
| forward_materiality_before_tca_budget | P2 只有 source，没有材料性 | 只监控 |
| paper_or_whitelist | `0` | 阻塞 |

## 图表视觉复盘

- 左上图显示当前 `4` 槽对应 `25.0%/slot`，即便 `black_ferrous` 全闭合也只有 `5` 槽、`20.0%/slot`，距离目标 `7` 槽仍差 `2` 个。
- 右上图把横轴设为核心相关性，历史 PnL 只作为诊断纵轴；`rubber` 虽有正 PnL 但在 `0.20` watch 线右侧，继续拒绝。
- 左下图显示 `black_ferrous` 是 0 个月等待但只能做 source/TCA research；`precious_metals/soft_agri` 必须走 12 个月 forward monitor。
- 右下图显示晋级闸门仍以红色为主：独立槽数、point-in-time source、live execution TCA、paper/whitelist 全部阻塞。
- 视觉结论：图表没有把 P2 观察对象误画成候选，也没有把 `black_ferrous` 误画成足以解决目标的新增槽。

## 结论

- “低单笔风险 + 扩池 + 避高相关 + 选对品种”方向仍值得做，但当前只能推进 forward monitor 和 source/TCA closeout。
- 当前不能新增资金预算、不能 paper、不能交易白名单。
- `black_ferrous(j/i)` 仍是唯一 P1 新独立槽线索；但即便它完全解决，也只能把有效槽从 `4` 推到 `5`，不足以让单槽风险降到目标。
- `precious_metals/soft_agri` 低相关且 source 较好，但历史材料性不足；必须点时化观察 12 个月后再谈 TCA 预算。
- 高相关家族即使历史收益好也不晋级，避免压力期伪分散。

## 结束后反思

- 是否过拟合：否。没有新增收益回测，没有按结果挑品种，没有调整阈值去救某个家族；所有结论来自冻结证据和预先定义的实盘准入约束。
- 是否有价值继续：有，但价值方向很窄：执行无偏差、`black_ferrous` source/TCA、P2 点时化 forward monitor，以及寻找至少两个真正低相关、source 可执行的新经济驱动。继续宽池收益扫描价值低且过拟合风险高。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage616_independent_slot_forward_monitor_contract.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage616_independent_slot_forward_monitor_contract.py`：通过。
- 图表视觉检查：已修正标签重叠和边界裁切后通过。
- decision JSON 复读：通过。
- 输出文件存在：通过。

## 输出文件

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_decision_stage616_independent_slot_forward_monitor_contract_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_report_stage616_independent_slot_forward_monitor_contract_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_chart_stage616_independent_slot_forward_monitor_contract_v1.png`
- monitor plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_monitor_plan_stage616_independent_slot_forward_monitor_contract_v1.csv`
- promotion gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_promotion_gates_stage616_independent_slot_forward_monitor_contract_v1.csv`
- slot ladder：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_slot_ladder_stage616_independent_slot_forward_monitor_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage616_independent_slot_forward_monitor_contract_gates_stage616_independent_slot_forward_monitor_contract_v1.csv`

## TODO

- 执行线：用户明确确认测试环境和 read-only 动作后，刷新 Stage608 live snapshot，并输入 Stage612/606/607。
- TCA线：用户明确确认测试环境和 submit 动作后，做 exact `vt_orderid` writer 和真实 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` reducer。
- `black_ferrous`：继续找 DCE 可授权源或稳定替代源；无 source/TCA 前不 paper。
- P2 monitor：为 `precious_metals/soft_agri` 建每月点时化 ledger，记录 source hash、趋势 episode、3/6个月左尾，不投 TCA 预算。
- 新槽搜索：继续寻找至少两个非DCE、低相关、source可执行、不同经济驱动的新家族；禁止宽池收益 topN 扫描。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage316。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入。
