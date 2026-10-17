# Stage028：有序条件入场的最小真实执行合同

- line_id：futures_trend_triple_screen；2026-10-18 02:34 CST；来源HEAD67008605c。
- 上一goal轮分类：方法解释未改变权威研究状态，属于无进展；本轮已重验Stage027独立收据和实际引擎，进入代码与真实金融实验接合。总体目标仍为更高扣成本收益且更低最大回撤，组件完成不是目标完成。
- Stage027独立审查P0/P1/P2=0/0/0；116394真实日线、900原生身份全部匹配，B13600/C295均只是无账户上界，不能当实际交易。
- 用户沿Stage001授权持续离线自主研究；不新建工作树，不改正式源码/配置/生产/CTP/其他研究线或脏registry。本合同由root在新金融收益前固定，未请求重复许可。

## 研究选择与低复杂度约束

沿本线已核的[CMT Elder讲座](https://docs.cmtassociation.org/docs/MTA0405.pdf)、[LEAN FI](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)和[Backtrader执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)。原结构提供可反证的入场假说，不是收益保证。Stage024周硬过滤形状已失败，不回头扫描周/FI参数。

Stage025提出了风险预算重分配/只缩量的可行方案，但尚未冻结。root现在选择更小且更干净的单一比较：**保留u收盘原native planner实际入选手数q、保护止损S和排序/slot分配；只改变初始入场条件与时刻。** 不另添触发价风险重算、gap额度或日内再分配。Stage830 broker gate仍只在u估算；这不是实际成交风险/保证金的硬上限。actual fill相对原S的实际R和保证金可高于u预测，必须输出并受原七门检验，不能声称成交时重新过了原gate。这一选择在收益前固定，不比较两套执行预算挑赢家。

## 实验与参数

- A0：复用已独立接受的A0_attempt2，不重复回放。
- C_TS：本研究账户的真实C9 native初始信号，完成周许可→更早FI2逆向准备→新native信号→仅下一真实交易日D的high(u)+tick/low(u)-tick条件触发。unknown沿Stage027合同回到原C9普通次open；明确不合格/无合法bar不能回退。
- B_TS：后续独立三重滤网alpha，明确新signal标签并披露原模型类别域；不能冒充C9。先完成最小有效C_TS金融闭环，再推进B，不能把C失败当完整框架已反证。
- 共同2020-01-01—2026-10-14、150000、实际历史AI资格字节/严格signal-day prior eval、原成本、0.5R ON/一次retry、固定周/FI定义。禁止月份/品种/窗口/阈值调参。
- C_TS保留native allocator结果后再过滤，不重新分配被删或未触发名额；u收盘原产品处理顺序处只预留同一q的intrabar资源，不建立layer、target或订单。D内不回收止损/未触发预算给另一intent。

## 真实执行接口与因果规则

1. 新研究策略factory仅覆写本线子类。`ts_pending_intents`保存独立一日intent和deepcopy的u bar/sizing/history/signal字段；`ts_decision_audit`逐候选；`ts_activate_intent(item, fill_price)`只由引擎触发事件调用，调用原_open_position的冻结sizing路径、保留signal-day年龄与身份，并把新layer初始高低种子设为actual fill。quantity必须>0，不依D的estimated_equity、最终H/L/C或事后mapping重新决定。
2. 每个u close恰好更新一次产品状态；无C9信号的日子也必须观察FI准备。无entry gate/AM warmup日可更新准备但不能发native金融单。D先执行u的旧intent，D收盘才观察D的mapping/资格/周状态，不能追溯取消早前成交。
3. 新研究引擎的单一heap包含原ordinary/roll、conditional initial和synthetic事件；ordinary照原canonical context，conditional先经Stage021完整session资格（包括未触发日），然后扫描第一处真实突破。分钟缺失阻塞同一engine，不降级为indicator unknown、不用日线触发价替代。
4. 条件市场事件可以离线预排，但只有pop时才激活layer、建立实际OPEN订单并复用原_fill_order/成本/账户记账。订单signal_datetime保留u，execution_datetime为真实触发分钟；未触发没有position、target、order、费用。仅真实fill后调用machine.on_fill消费准备。
5. actual fill使用原stop_fill的跳空open/门槛不利tick，不能把午间突破填成session首open。相同timestamp按冻结排序/稳定serial；母entry必须早于自己的samebar stop；不按未来PnL排队。
6. 条件在bar内触发时，pre-entry open不得作入场后stop/progress或退出价格。仅在该conditional after-open hook的临时独立分钟视图中把首bar.open设为actual fill，原始分钟不可修改；同bar不利优先，原第一stop下一分钟才retry。触发方向超过fill的有利极值必经首次门槛后发生，可按原first_stop规则；同时触及不利和有利仍按不利先。bar.open即触发的gap不改原open。
7. 0.5R与retry沿原实际fill减冻结S重算；普通单/已有仓/roll不经过新条件首bar处理。所有class/module/cache方法作用域异常后恢复，原冻结021/022/023与正式文件不修改。

## 有限验证与金融闸

只做必要因果hook测试：未触发无layer/order；D未来收盘/账户毒化不改变冻结q；实际pop才激活且signal/fill日期分离；两方向gap与首分钟保守stop/retry；ordinary+conditional+synthetic稳定同队列；normal ordinary无intent保持原路径；数据资格在scan之前。先观察缺实现RED，再实现GREEN，不重复已通过Stage027/FI全流或旧全市场资格。

新runner显式C_TS provenance与独立feature SHA，不篡改022的C0名称；沿已接受stack与同engine bounded wait。新实际请求只取必要精确分钟并独立验收。回测有完整exit/全日期/零吞错后才可报告；之后另派独立agent审查现金、成本、母单胜率、实际R/保证金、参数、时间因果及置信度。原七门与多周期晋升条件不放宽。

开始过拟合判断：新增规则本阶段否，单一结构与执行口径在新收益前固定；既有多轮历史选择偏差仍在。继续价值：是，真实有序入场尚未得到金融证据；应尽快完成一次有效对照，不把文档或准备组件当收益结论。

本合同无新金融结果；权益/收益/DD/Sharpe/滑点/成交/胜率均N/A。金融累计仍5attempt/2完成，模型训练0，生产资格false。
