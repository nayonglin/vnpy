# Stage370 双模拟初态已签入，后续仍需真实及时资金方案

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 04:38 CST；工作区`/Users/mac/Desktop/fian`，沿用研究分支，Git0。非收益突破、非正式A/B或生产动作。
- 用户目标仍是全市场高质量做多、更高成本后收益/更低回撤，继而检验极窄损与加注；不能永久用未出资快照替代连续资金证据。

## 研究判断与改动

- 364查明LINE遗漏315/316/324而误留310“未启动”；root已补齐结案。整数数值包因求解矛盾关闭，经济价值未评估，不重开或误称alpha被否定。
- 365有界核CME/NYMEX CL官方日结算与历史入口：当前对象版本/历史通路未闭合，NO-GO、历史actual0。最终日报23:00/次日00:00北京晚于21:00，不能配初版13:00/14:00时钟；这不构成所有海外价或条件历史重建的永久禁止。来源与推论见365。
- 367提出有限后继；368只建立原政策base/stress两个100万空模拟态，不改变359参考T0或360仅观察批次。正常加载相邻131/070/042纯定义，未导入旧cash runner；359缺的131单独保存在新payload，不写回旧closure。
- [Freqtrade维护者说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)支持区分完整输入、因果时钟和前视偏差；资料不证明本策略alpha。判断：复用原核、保存完整初态与真实新事件，有助未来检验连续预算，不需重写分配算法或重跑旧金融。

## 参数与实际

- 两个场景初资各100万，原NARROW初损0.25N、单family风险0.0025、总risk0.02、margin cap0.25、buffer1.1、原费用/滑点/退出/F0不变；账户ID独立，start_u=5290/2026-10-20，空仓pending0，不带旧利润/仓位。没有新增或删除科学参数。
- 368唯一有意义新fixture作者GREEN1/.267秒，369独跑唯一组GREEN1/.345秒：拒绝SQL/原行情/资金runner/seal/advance，核场景隔离与真实321签名；旧suite0。
- root唯一actual：exit0、0.189960667秒；真实321 `paper_state_initialized` 的 **T_init=2026-10-20 04:34:30.535301 CST**，UTC `2026-10-19T20:34:30.535301+00:00`。
- 原359 T0仍为20日04:21:56.703789；T_init独立于它，不以文件名/整理分钟代替事件。当前status=`initialized_inactive`，active=false、no_funded_proposal=true，两本仍awaiting_u/next_u5290，没有任何资金方案或成交。
- 369最终独审13项全通过/core0，完整状态、source、参数、scope及event/object/policy hash一致。收据`outputs/stage369_paper_initialization_review/actual_receipt.json`，11081B/SHA `ec8a043663e1a82929ea4b7df45f8eca25377c3af7ad50fde842dfd320cc6622`。静审的一个JS键序假阴性在最终按字段纠正，旧收据保留；没有作者bug/改源/金融重跑。
- 新建研究态2次；fit/cash/模型推断/行情API/市场读/SQL/seal/advance/订单/Git均0。累计完整453fit/246cash及此前1金融partial不变，真正新forward样本0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：N/A。100万是初始模拟余额，不是已跑出的收益结果；旧回测不修改或删除。

## 继续范围与反思

- 今天15:15—21:00仍只按360进行一次361新日线观察，随后362独审/363接纳；不提前抓形成中、不重取metadata、不装调度。
- 之后另设薄future范围才可使用同一已接受snapshot生成原325完整资金proposal，必须另核T_init<实际source完成、完整新proposal seal<D_open。不能继承357未出资seal；错过start_u20就留缺口，不能重置/跳u或补认及时。
- 371另识别训练时效问题，372已固定一次latest-mature训练协议，373仅薄实现/新fixture，374独审后root至多1fit；原2023参考与本双态不改，不重跑旧收益择优。
- 开始/结束新增结果调参过拟合：否；历史适应性择题风险仍有。开始/结束继续价值：是，补齐连续研究资金证据并固定一次训练更新能推进完整目标，重复旧包救参无价值。稳定高质量、极窄损安全和加注资格仍未证明，goal active。
- [root裁决](../outputs/stage370_paper_initialization_actual/decision.json)、[下一范围](../outputs/stage370_paper_initialization_actual/next_scope.json)、[实际初态结果](../outputs/stage370_paper_initialization_actual/actual_run1/result.json)。只更新本线LINE/registry；不追加根总账，不改正式版、其他线、生产/CTP/邮件/launchd。
