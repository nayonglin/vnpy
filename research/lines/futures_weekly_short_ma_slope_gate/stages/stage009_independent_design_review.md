# Stage009 独立设计及入口审查（只读，尚未批准金融）

2026-10-30；line_id=futures_weekly_short_ma_slope_gate。基于冻结Stage008 A/C，仅讨论交易桶150000+备用桶150000、同23个独立起点至2026-10-29的固定机制。此记录不改原源、旧产物或生产，不运行金融。代码实现完成后仍须独立预审与逐窗完整会计审查。

## 可用hook和精确定义

推荐在**新Stage009 wrapper的_calculate_entry_sizing**接入；其父级继续为冻结Stage005 range_strategy_class及Stage029v2完整父链。仅canonical long_case1a/long_case2/short_case1a，且entry_context属于flat_entry/reverse_entry。env_probe、rollover_reopen、所有加仓/退出直接super，绝不补资。

顺序：检查金融起点/信号方向与启用权限 → C短门只读RangeHistory.snapshot，would_block则不补 → 原_weekly_initial_stop_qualification，只对valid补 → 用当时真实raw estimated_equity（含未平MTM）判定短缺 → 原子记账补资 → **仅调用一次**正常父级sizing。blocked/invalid分支仍调用原父级，以保留原正常gate/invalid_stop证据，不伪造证书。

不能要求原selected_volume>0再补：资金不足恰可能令其为0。不能在_open_position补：flat计划提前缓存volume，零手数到不了open，非零也已按旧资金定量。也不能先正常super计算一遍再补、再super一遍；原sizing链会记录诊断/计数，并非纯函数。

这里“有效信号”应冻结为通过日期/方向/canonical信号、原周止损方向资格及C价格门，**不等于保证成交**。后续原预算、并发、相关性、环境、热度和其他风险门仍可给0；已转入交易桶的资金留在该桶，不回填备用。如要额外要求所有后续非资金门通过才转账，现有hook不足，不能偷偷用不同规则替代；需先另行冻结全规划/虚拟预算语义。

flat入口由_build_flat_entry_candidate_plan调用，早于最终并发/增量保证金规划。reverse入口在旧仓平仓目标已计划、实际旧仓尚未次日成交时调用；因此不能要求get_pos==0才能补reverse，不能为补资清空真实旧仓、目标或预留，不能将计划平仓提前当已实现盈亏。保持原产品遍历/候选次序；同日多信号按原顺序处理，首次补足后其他信号共享真实交易权益。

## 资金与会计不可破坏的恒等式

设净交易PnL含滑点/手续费，累计内部转账F：

- T=150000+累计净交易PnL+F；R=150000−F；W=T+R=300000+累计净交易PnL。
- 每次x=min(max(150000−T,0),R)，有限且非负；R只减、无利息、无回拨，备用耗尽仍按剩余交易桶运行。T>150000保留全部动态权益，不能偷偷锁定15万尺寸。
- 保持原strategy/base/engine交易初资150000，不把300000赋给sizing/保证金可用余额；总财富初资300000只用于新总账户报告。
- 补资需同步增加settled_balance和estimated_equity，或加settled后用同日完整bar重估；只加estimated会在下一_refresh/日结丢失。不得加realized_pnl、trade_costs、日交易net_pnl或伪成交。
- 原引擎calculate_result按固定capital+交易PnL生成daily，不自动含自定义transfer。保留该原始PnL源，再新增bucket_daily，将交易桶T与internal_equity捕获逐日对上；不能直接给旧replay会计加一个伪收益调整。
- 每个转账记录唯一事件ID、完整signal/方向/context/合约/epoch/信号日、gate/stop资格、T/R/W前后、x和累计F。W转账前后不变，T增x=R减x；重复探测和同一事件重入不可重复消费。

控制组W0=Stage008原交易权益+固定150000闲置金，逐日用300000初资重算收益/DD/Sharpe；不可沿用旧DD/Sharpe或简单除2。候选W为主绩效，交易桶T的现金流调整收益另列，保证金/T与保证金/W分开；R在转入前不参与可用保证金。

## 主要bug风险与必须测试的边界

1. env_probe即使产生有效信号、stop也不能改变T/R/目标/预留/风险历史。C底20%拒绝、无效周止损、未ready/预热、方向禁用、无信号均不转账；同日blocked与allowed并存不能先给blocked补。
2. 只读资格检查不能追加原有诊断两次。Stage029v2资格本身已有抑制Stage804诊断的处理，应使用该函数，不自行重写周止损公式或用日K极值代替。
3. 只刷新必要的当前资金派生状态。完整_refresh_risk_state还会更新/记录波动与冷却状态，不应在sizing中重跑。若刷新drawdown只用原_refresh_portfolio_drawdown_state并保留旧high-water；不清streak、历史PnL/胜负、仓位、target、pending reservation、已有风险历史，不把峰值重置到15万。
4. 波动预算/过热冷却若实际启用，原历史函数使用estimated_equity比值，会把deposit误当盈利；须在preflight记录实际loaded flags。若基准确实关闭则断言继承关闭，不可凭settings缺键声称关闭；若启用，需先冻结现金流中性历史口径，不能重置或自动关掉原风控。
5. T阈值须读raw float，不能用estimated_equity or base_capital。原_sizing_equity_snapshot恰有0值fallback；T==0且R耗尽必须防虚拟15万购买力。测试正好150000、略高、100000/R150000、短缺大于R、R0、T0、负T、非有限输入；不把强制平仓或清理状态当补资。
6. 备用只允许单向转入。转账后无当日交易时，W和净交易PnL仍不变；下一日重估/结算不能丢失或再次加钱。交易桶盈利超过150000后，原动态手数继续增加，不能按15万封顶。
7. C空头门源码/含signalday范围不变；两侧新增MA斜率门/多头价格门继续关闭。A/C各自资金路径独立，禁止共用备用余额或全局class可变容器；每个新窗口新建全部钱包/事件状态。

## 后续独审验收建议

先冻结新合同/源码/数据/成本和上述有效信号定义，再边界测试RED→GREEN、canary独审后放完整23窗。新补资策略会改变真实手数/退出路径，不能拿旧fills后补现金冒充候选；旧Stage008+固定闲置金可以只读派生为同本金控制。每个新回放审核transfer逐事件资格、两桶/总财富守恒、逐笔逐日会计、现金流排除、实际订单锚点、原风控状态及全部来源；保留经济负结果，不救阈值。

判断：固定补资机制有研究价值，但收益与回撤必须按同30万本金公平比较；备用金降低总财富回撤的一部分是结构性现金缓冲，不等于alpha。仍是已见历史内机制选择，23窗重叠，不是新OOS。当前只通过设计入口可行性审查，未批准金融或声称策略有效。
