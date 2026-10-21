# Stage509 现金政策续持状态最少源与执行语义设计

时间：2026-10-21 02:40 CST，02:44纠正源覆盖规划错误。研究线 futures_full_market_long_signal_ai；非重要突破。

本轮只读代码与小manifest/schema，未读任何大payload、价格、数值Y、原129动作、母表或native数组；0 SQL/API/下载/fit/cash。开始与结束判断：长期历史择题过拟合风险是；本步按收益调参否。继续有条件价值是：检查改善A157 OWN现金政策所需的持仓后决策对象能否因果构造，不据此训练或加注。初稿提出129路径，root明确最终经济对象后修订为131/157 per-unit机会路径；没有运行初稿actual。

最少正确路线为三份大源各一次：466全动作metadata112,644,206B（全1,552,456，仅读身份/u资格字段，不读未来状态/时钟字段）、466全母身份22,524,157B（399,252母、186,400无子及逐日canonical reference）、132 native110,273,488B（9,520 epoch的days/OHLCV/accepted/valid/N/low20/run）。另需既有economic_projection8,146,494B提取精确生命周期、listed-date/roundlot/报价资格。原生命周期取nominal及known boundary/maturity/de-list最早值，不能只按合约年月猜。calendar44,824B显式绑定；不读489 forward causal69MB、505 closed37MB或原129334MB动作。大文件hash继承已存小manifest，本轮没有重hash。

466 metadata仅读全身份/u资格/u不具资格原因，不请求filled/closed/entry/exit/unknown/terminal钟与cutoff-finalstate列；native重算N_u/low20_u/u_close/run及131 Decimal容量，并核原eligible的native资格及u anchor与全母表一致。未来filled/closed/unknown不筛u，129出口不认证现金路径。505成熟闭合区间只能作可比计数锚，不能作新风险集。母域98品种/95族与有子97/94不同；无子、不具资格、未参与、入场未知、持仓未知/删失均保留状态，不能填0。

目标是131/157现金价格机制的独立per-unit机会：原eligible意图在D=u+1执行，effective expiry=min(source_lifecycle,commonK)，D<K。nativeD有效才观察到F=D.open，SL0=F−0.25N_u；F<=low20_u或无效SL取消；D缺价记entryunknown，但它不影响之前u意图存在。进入后B_entry=max(SL0,low20_u)，先处理入场日止损，仅生存close有持仓状态。

关键纠偏：129标签遇缺held bar立即unknown停止；131/157必须保留上次mark/boundary、标记stale、锁research_deferred_liquidation，之后合法旧epoch bar到来时优先open强退。因此不能借129出口认证现金路径终态。正常日先既有force/open gap/low stop，再close；生存close设B_next=max(SL0,旧持有epoch当日low20)，不是前B单调上调。131 force优先级为生命周期、既有force、缺canonical、canonical偏离固定entry anchor。held epoch允许与anchor不同。commonK只加在私有effective expiry上，不改继承source时钟。

state必须由<=t历史逐日生成，包含stale/deferred/forced-only，也包含最终未闭合路径；未来是否有效D、最终是否closed均不能作state存在门。t可知entry/N/SL0/own boundary/mark/age/stale/anchor/canonical/force_next/K。t+1 open及之后退出属于隔离的事后执行观察，不进状态。缺下一bar逐日保持pending，不能在t预知之后第一个有效open。期末open/stale unresolved保留，不能归零收益。

per-unit机会仍不是实际A157账户持仓prefix：真实book还依赖选入动作、占族/同日退出、整数手数、资金/风险/保证金/容量及强减仓。当前不重跑实际book，不把独立路径可共存当事实。132现成restore函数隐式stat旧库并读128/052/calendar；建议新实现显式绑定一读缓存和calendar，不增SQL。cache原purpose是旧恢复用途，root可明确授权一次新研究读取，无需篡改旧manifest。

参数及金融结果新增/修改/删除均无。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A；累计505fit/274完成cash及1旧partial不变。原目标未达成，不改正式/生产/CTP/邮件/任务/Git。

下一步仅由root冻结后一次构造131/157机会状态及小型因果fixture：全1,552,456动作pathsummary、全部postclose持仓state（含stale/force），以及严格隔离的未来open/新机制terminal价格与base/stress SELLquote观察表。后者仅价格/报价，尚不生成数值reward，避免下步为X/Y重读缓存。输出free-vs-mandatory/stale/deferred/未知及因果值一致性计数；不拟合、不做现金，不拿129出口认证。依据为原129/132/156/157与131/042实际源码及既有accepted manifest；503原论文/作者GitHub只说明最优停止方法，不提供alpha证明，本轮未新增网络请求。

机器设计：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage509_continuation_source_design/design.json。

## 02:44 源覆盖规划错误纠正（未发生actual失败）

509此前将489 causal69MB误认全1,552,456动作，是未看producer过滤条件就依据binding大小作全域推断的错误。511静读producer发现后，本轮已实读stage489_fomc_residual_experiment.py第286—300行：第298行只写u_date在2020-01-01至END之间；第300行明确total=1,552,456而forward=966,740。旧建议会漏掉585,716条较早动作，无法提供pre2020训练风险集，现予撤回。

纠正为466 metadata112,644,206B全域源，仅14列事前身份/u资格白名单；完整绑定SHA256 e290400d43d702bf97ba25e3bff1b0f317d9eba443d7465e06b8dfec2d824465。其余466全母22MB、132native110MB、econs8MB与calendar44KB不变。native重算N/low20/uclose/容量，不需要旧未来终态。先前design SHA256 61a0bda8c6fcb8fcf373c58890d3ca3f41895b581493a4788407efd80eb74d66已被本修订替代，规划错误记录保留；修订前后大payload/旧缓存/价格/Y/SQL/fit/cash始终0，不是一次失败回测或数据重跑。
