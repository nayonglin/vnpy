# Stage076：0.5%多手v1实际失败独立审查

时间：2026-10-20 00:40（Asia/Shanghai）；研究线`futures_trend_full_market_noai_one_lot`。源`outputs/run_20261020_contract_weekly_risk05_v1`，源码commit `07254b5c971077d9722cf8f6b991c5016413a6ed`。本代理未参与实现，仅只读冻结资料及运行合成复现，没有金融重跑，未改源目录/工具/LINE/Git。

**结论：FAIL，实际金融回放未完成，存在P1执行计划集成缺陷。** 不能发布完整收益、回撤、Sharpe、胜率或将失败前缀当完整结果。没有最终manifest，JSON顶层`source_manifest_sha256=null`明确表示缺失；以protocol SHA256 `74bf1c2a7003155cbc4369f59ac8e8f245fa45a9eb3456ef0f048e3fc4708184`及失败物料hash绑定事实，绝不伪造最终manifest认证。

## 真实直接事实

失败日**2017-03-13 00:00:00+08:00**，engine.log调用链是native `on_bars → _process_forced_margin_deleverage → _reduce_position_to_target → Stage074._queue_pending_close_lot`，抛`stage074_requested_close_direction_mismatch`，outer报partial_replay并exit1。

341笔实际前缀逐笔符号守恒重建持仓仅：`a201705.DCE short20`、`SR201705.CZCE short18`。末笔BACKTESTING.341是失败当日白糖short18@6774。活动委托明确：SR CLOSE long18，TA OPEN short16，p OPEN short17，v OPEN short29，均为当日收盘意图。没有把待开层当作已成交仓列入上述实际持仓。

failure_snapshot内部`snapshot={}`，没有当时states、targets、pending close或forced迭代事件。SR close活动委托足以证明target曾要求减仓，但不直接给出所有目标数值与原因。因此不能声称某具体合约就是异常触发层。失败日离所涉合约运营deadline尚远（a/SR/TA/v为4/27，p为8/30），不是到期缺价退出错误。

## P1-1：未成交意向被原强减当真实仓

冻结native `_forced_margin_deleverage_candidates`仅看state.layers、active_volume及bar，完全不看actual仓位或entry_price_synced。多手新意向也会占有层；尾部原强减据此记录Close并尝试_reduce，074发现actual0与layer方向不符而硬停。**074方向/实际量检查是正确保护，不能放宽或末端no-op掩盖。**

独立从失败目录加载冻结074，并调用真实native强减函数，以actual0、未同步layer17、target17构造纯合成状态：候选返回17手，随后精确复现同一异常，actual仍0、trades0、pending close为空。未调用run_backtesting或加载历史回放。

用绑定实际3/13收盘及静态规格计算计划保证金：p17=188,768；v29=186,760；a20=156,480；TA16=81,536。SR18=243,684，但如已完全排平/reset就不再有候选层。原priority=largest_margin，故p是首个异常未成交候选的强支持推断；缺运行层快照，不能把它写成直接观测事实。

## P1-2：保留实际保证金后，强减循环会重复排平

关联路径也有独立实证，不能只加actual候选过滤就宣称修完。003实际margin floor在未成交平仓前不释放资金是正确的；native强减while却每轮重新读该实际占用，queue减量后ratio不降，遂对remaining layers再次减量，直到全平。

冻结代码合成真实actual5手、close110、size10、margin0.1、权益750，原trigger0.95/target0.8/broker1.65：实际margin550，首次只需`ceil((550−750×0.8/1.65)/110)=2`手；实际排平却为**[2,2,1]共5手**、3轮、target0，actual仍5且0成交。这个差异是计划会计缺陷，不是新阈值优化。

本项在合成中确证；v1真实prefix里SR18的具体多轮来源和迭代次序因事件缺失无法量化，不能直接宣称当日白糖本该只平多少手。

## 数据、资格和置信度

失败起始21个源码快照逐一与code_start_hashes相符，protocol源commit与预审冻结一致；绑定source_inputs/output_files原文件hash全通过。341笔实际前缀全部有绑定真实bar，price=open，冻结bar V>=整单qty，无execution-only OPEN。这支持本次停止是实现集成而非行情缺价；不认证每个未成交意向实际可交易，也没有补生成不存在的收据/账户终值。

日志和前缀实际仓位置信度高；两项因果由冻结代码合成复现支持；具体异常合约与完整强减迭代序列因缺快照有明确上限。预审285合成测试与490独立检查通过的事实保留，但它们遗漏了“当日新OPEN层+尾部强减”和“实际资金floor+重复强减”组合，不能据此维持完整运行通过结论。

## 最小通用修复与回归合同

1. 触发原强减时，未成交OPEN只能按原priority整单撤意向；必须早于任何Close reason/PnL/streak。撤活动OPEN、target、纯未成交layer和相应pending预留，原receipt与取消诊断归档，不能造真实close或提前释放actual资金。
2. 真实减仓候选只含已同步actual尚未承诺余层；actual0和方向不符不得入选，现074硬检查保留。
3. 强减规划另有“已承诺平仓后的投影保证金”，扣除已有效queue的pending CLOSE（本次新增与跨日已有）以防重复排平；真实账户margin floor直到fill仍占用。不能用篡改actual floor来解决loop。
4. 保持原trigger0.95/target0.8/broker1.65/priority/max100及预算、qty、周门、生命周期，不改品种、buffer或日期。不得末端no-op让Close原因或计划Pnl已经污染。
5. 合成回归至少覆盖纯未成交双向意向取消无PnL/Close，混合真实仓及意向，真实5手仅承诺目标2手且重复调用/跨日不再补平，部分平仓已有pending2后只对余3操作，真实margin到fill前保持，足量真实bar成交后才释放；增加strategy-on_bars异常快照。

原失败目录不变；修复应新源码hash、新v2目录和一次完整金融回放，之后再次独立审全部结果。风险预算/数量门不得为救跑通而放宽。本次结果新增状态仅“完整回放失败”；金融期末权益、总收益、回撤、Sharpe、滑点、交易次数业绩统计、胜率均不报告。

过拟合判断：**否**，目标/实际与投影会计的泛化修复，不按收益/品种/时段择优；仍非样本外证据。继续价值：**是**，修正后新冻结验证能建立有效多手研究账本；v1部分结果没有完整绩效研究价值。

资料判断沿用已读[CME仓位与止损风险](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)与[vn.py目标/实际仓位接口](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)：OPEN意向取消和实际CLOSE是不同事实；外部资料不能代替这里的冻结源码与合成证据。全部失败文件hash见同名JSON。
