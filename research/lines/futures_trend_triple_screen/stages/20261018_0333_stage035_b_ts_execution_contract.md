# Stage035：独立 B_TS 信号与已知触发价预算合同

- line_id：futures_trend_triple_screen；2026-10-18 03:33 CST；来源ed41e3578。上一轮分类为实质进展：C_TS完成并独立接受负结果，不是目标完成。当前无金融进程在跑，B尚无金融或代码。
- 用户沿Stage001/027/028和持续目标授权自主可逆离线迭代、多agent由root决定；继续当前codex/ai-training-data-expansion，不建worktree、不改正式源码/配置/旧C/031/033、脏registry或其他线，不推送/部署/CTP。brainstorming设计与writing-plans由root在此固定，依授权自主实施，不重复请求许可。
- 当前m0008六身份已配置校验，远端master e41a0a01d53b7256001e45e686acad53667ef7bf、稳定生产HEAD6b607203a41a47b1255ac1328dde2dc489bb487c的CURRENT相同。实际采用已接受修复源码离线A0，不冒充生产资格；identity_check.json记录完整六身份。production_qualified=false。

## 单一假说与对照

独立『完成周方向→日线FI2逆向准备→次真实交易日突破』可以比原native交叉信号更早捕捉趋势恢复，而用u已知T估量和最终只缩量预算避免把额外杠杆误当信号增益。资料为[CMT Elder](https://docs.cmtassociation.org/docs/MTA0405.pdf)、[LEAN FI](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)、[Backtrader执行](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)。源码复核Stage034/0330支持可实现性，不支持盈利保证。

A复用完整accepted A0_attempt2：2262595/1408.396667%/DD−48.789850%/Sharpe1.367364。旧组合C_TS为660825/340.55%/DD−32.758963%/Sharpe0.991077，已失败停止，不换预算重跑救参。B_TS为独立首次alpha，仍借同一C9持仓/退出、AI资格和账户框架。即使B胜出，也不是旧C通过；之后须收益前另定义真正首次信号替换组合C_new并证明行为等价或运行，再过固定多周期/成本门。

共同固定2020-01-01—2026-10-14、本金150000、历史AI原字节且strict eval<signal day、原模型字节/19特征、原OI风险recipe、原通用entry filters、成本、0.5R ON/一次retry、既有持仓/加仓/退出/换月。原佣金参数0、原滑点已计，不能称真实券商完整费用。周MACD/FI2/门槛沿027，禁止改窗口、月份/品种名单或阈值救参。最小B全周期只有一版本；失败停止，达标才进入固定Jan/June独立1/2/3年等验证。

## 信号、时序、权限

1. 每u收盘、每产品恰一次OrderedSetupMachine('B_TS').on_close；无context但有真实bar可观察，无真实bar/mapping要cancel，准备从2020空机开始，不借2019准备。B允许setup_day=signal_day，执行D必须晚于u；epoch/周方向/持仓/AI资格等取消逻辑沿027。unknown一律无初始金融信号，不回退native；缺分钟仍同engine阻塞，不能变成indicator unknown。
2. 原planner之前只对真正flat的同一个context复制signal_data，清旧native signal；B intent且原_passes_entry_filters(new_signal, history)通过才写long_triple_screen/short_triple_screen。held context原信号/技术字段不改。generic OI mode按volume-OI→OI→regular重算，不要求native cross/alignment/MACD；short只精确开放short_triple_screen，short_other不泛开。
3. 沿原AI月资格和模型/评分/slot/tilt算法。19数值特征含same_signal，新B标签的分布为域外推；现有catastrophe/recovery白名单不扩、关闭开关不启。保持原算法不意味着分数/rank数值等于旧close版；T风险/margin数值自然进入模型。

## 已知 T 的 sizing 与最终 q

4. 新pricing基类只插入真实MRO的772与qmt之间：新策略→847→830→827→804→772→PricingQmt→qmt。复制SHA绑定的qmt唯一_calculate_entry_sizing方法，除读取(u,contract,direction)合法T的三处估价替换外保持原算法；S仍self._entry_stop_price(direction,原bar,原history,True)，不改bar.close/history，不改804多头S或原空头S。B flat缺T必须拒绝，非B/held/add/reverse/roll走原路径。实际fixed_size=0，其他模式无本次资格。
5. rho_T=max(abs(T-S)*size,原min_risk)，m_T=T*size*原margin_ratio；完整提供risk_per_contract/margin_per_contract，贯穿原830/cluster/heat/env/模型/allocator。新外层sizing只保存与830完全同fallback的E：float(self.estimated_equity or sizing.get('sizing_equity') or self.base_capital or 0)。不从D取值。
6. 原allocator完整返回后，冻结原candidate_status=opened且q>0集合，按原rank/稳定序做一次_b_finalize_admitted_budget。a_i为原allocator量；P_i=sum此前a_j*m_j，同cluster另有P_i,c。用裁剪前gross前缀，不能回收被缩量/归零项的budget或slot给别的初始候选。只允许q_i=min(a_i,floor(R/rho),floor(max(0,L-P)/m),floor(K/m),max_position_size,原830开启时floor(max(0,E*c/b-B-P)/m),原cluster开启时floor(max(0,C-H-Pc)/m))，再max(0,...)；0<q<min_position_size设0。R/L/K/B/C/H及开关/倍率均取0330列的原u sizing字段，不添加阈值。
7. contracts_by_risk/margin/single必须已与T字段一致，不能用最终min掩盖接合错误。原gate/tilt快照不覆盖；新增b_ts_budget_equity_u、b_ts_final_budget_*记录所有原量/最终量、gross前缀、各整数上限、T/S/rho/m和预测风险/保证金。plan.volume与sizing.selected_volume同时更新，q=0改为filtered/b_ts_final_budget_zero，不消费setup、不发单、不补候选。只在原snapshot产品循环处对最终q reserve一次，不在planner提前reserve；gross前缀不记成真实持仓。原已有仓/add产品循环不改。
8. 新q限制是B专属行为，不谎称原C9已有最终硬预算；它不是新的全组合stop-risk总额限制。T/u预算不保证D真实gap时仍不过界。D真实F按原stop_fill及不利tick，q/T/S冻结，不依D最终H/L/C/账户/mapping重算，actual R/margin对T预测差异必须输出。相同分钟保守不利优先/下一分钟retry/持仓entry后suffix及全日技术环境沿028/031，不改原价格。
9. shared条件执行/holding helper可复用028，但真实machine/新标签/所有审计arm/manifest/owned checkpoint必须B_TS，不能伪称C。原snapshot保留signal_close，明确T及冻结预测字段；actual同步可更新实际risk字段但不能丢T预测。最终budget字段进入decision audit及冻结plan，不仅留最终成交表。

## 入口、数据与验收

新035 pricing/strategy两个部件，036独立B runner从冻结031可靠checkpoint入口适配，037仅provider作用域适配。原031/028/所有正式源保持原SHA；engine028复用。周/FI缓存和accepted A0不重建；两项原anchor各精确一key复用，不能扩大full权利；仅真实必要新request走同engine原资格与正规provider并独立签收。--run只内联一次preflight，--export-only只读本B自有sealed snapshot，不重放。

必要验证只覆盖新增价格/MRO/预算/独立信号组合：long close100/low99/high110/T111/size10仍S99、rho120；short镜像；T缺失拒绝；tilt10→12被预算10钳住；三项gross60000后第三归零，前项缩量不回收；无native但B有效可开、unknown无fallback、通用filter拒绝、held不改、单观察/单reserve；一个真实847+028engine B条件成交/合成止损组合；B checkpoint身份与恢复入口。先RED后GREEN，不重复已过26旧suite/FI/全旧行情资格。

完整terminal/1641日/零吞错/分钟资格/原params门后，另派独立金融agent复算现金、成本、库存、母单/retry/roll、T预测/actual、最终预算、因果与七门。仍要求收益>A且DD优于A，Sharpe不低、margin峰及超100日不恶化、生存和非空；没达标不跑多周期救参。promising仍需固定多周期、成本压力、弱段及独立复核，B单次通过不是总体目标完成。

本合同无新金融，权益/收益/DD/Sharpe/滑点/交易/胜率均N/A；正式参数新增/改/删0，研究新增B信号/按T估价/最终预算结构，无新数值旋钮。开始过拟合新增否：单一机制在B收益前固定，不按C损失倍数定阈值；历史多轮选择偏差保留。继续价值是：独立B真实经济证据仍缺，不能把代码或设计完成当收益突破。目标active、production_qualified=false。
