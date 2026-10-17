# Stage026：有序FI2准备与止入场的原始资料再核

- 时间：2026-10-18 02:12 CST；line_id=futures_trend_triple_screen；只读源码HEAD `67008605c`。
- 性质：基于C0收益出现前Stage003备忘的资料/合同建议，不是批准实施协议。本次只读资料与源码、只写本备忘，不编写策略、不回测、不训练、不重建特征、不扫参数；金融指标全部N/A。Stage024负结果只针对周许可增量，不能外推完整有序机制失败。

## 原始来源与证据限度

1. **Elder**：[作者官网软件说明](https://www.elder.com/product-page/elder-disk-v3-for-metastock-v15-with-scanners-1)确认作者工具包含Triple Screen、Force Index和周MACD方向，并提供manual。当前官网manual已指向[c709…PDF](https://6e6fa188-f273-4932-86c0-66af721f16a8.usrfiles.com/ugd/6e6fa1_c70983b8ebfa4100945b4c05c5f76c40.pdf)，本次抓取超时；Stage001曾核的[6065…旧manual](https://6e6fa188-f273-4932-86c0-66af721f16a8.usrfiles.com/ugd/6e6fa1_60651ebd50ca4ea0bd0421f83dce9e74.pdf)本次也不可访问。既有主源记录保留：周方向先决、日FI2逆向准备、后续顺大势价格触发；第三屏不必另加一个更小周期指标。**本次没有重新取得原书第三屏逐句正文，不能声称已当次独立复核“每日追踪直到周反向”的所有细节；搜索返回的社区/上传转述不作新增primary依据。**以下一日有效期、精确tick、取消和风险处理均按我们的研究合同标注，不冒称原著唯一实现。
2. **LEAN FI/EMA已直接核到源码**：[ForceIndex.cs](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs#L47-L89)用当日成交量乘同合约收盘变化，首close只保存前值，WarmUpPeriod=period+1；[ExponentialMovingAverage.cs](https://github.com/QuantConnect/Lean/blob/master/Indicators/ExponentialMovingAverage.cs#L79-L116)的首个ready EMA为前N个输入的SMA，其后按alpha=2/(N+1)递推。因此FI2为3根有效close暖机：第二日得到F2但未ready，第三日得到F3并以(F2+F3)/2初始化，之后E_t=(2/3)F_t+(1/3)E_(t-1)。它不同于首Force值seed的pandas adjust=False；Stage003原措辞是draft且初始化已明确留待冻结。建议只选本LEAN初始化，不比较两个seed收益。
3. **Backtrader已直接核到文档/源码**：[订单执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/#stop)规定完成bar形成的订单最早下一bar生效；Buy Stop遇开盘越过触发位用open，否则high触及才用trigger，卖单镜像。[bbroker.py](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py#L840-L903)同样处理gap，并在StopLimit中仅对部分OHLC形状作假定。源码不是tick先后证据，不能因文档模型存在就假设同一分钟入场、止损、止盈有确定顺序；未成交量/排队模型也不能视为真实成交保证。

## 唯一建议合同：C9的一日条件入场改造

**共同边界**：沿用A0正式池、AI时点、费用、C9风险治理/持仓退出；周许可仍为Stage001 cache(u)，在u收盘冻结至下一执行交易session D，不读取D事后主力映射或最终日线。交易合约和所有订单价格来自u时已经可见的信息。只在已知的u收盘决策边界处理周变、换月、AI移除或数据变化，不追溯取消D早前成交。

1. **FI数据与未知**：原始F_t=(C_t−C_(t-1))×V_t；每个真实合约独立连续segment，禁止旧主力末价接新主力首价。仅使用已经完成的日线；真实交易calendar中缺日、非有限/非法close、V≤0切断FI和准备，下一段重新收满3根有效close。周末/节假日不算缺日；V>0而价格不变导致F=0是合法输入，FI2恰为0是ready但不建立逆向准备。**零量/缺日reset是我们的保守资格约定，LEAN会把合法零量算成F=0且不自动reset，原著未规定此门。**
2. **准备与严格顺序**：周许可多且FI2<0（空头镜像>0）在s收盘建立setup；在更晚u>s出现C9原生有效初始信号才可用它安排D条件单，不能同日AND或以“FI又上穿零”追加确认。setup按品种/方向/真实目标合约epoch管理；成交消耗，换月取消旧setup。建议新目标可用u前自身合法连续历史完成FI暖机，但必须在新active epoch重新观察逆向FI并建立setup，不能搬运旧主力准备；这不是允许跨合约收益拼接。无最大准备N天、幅度阈值或失败后加冷却参数。
3. **唯一有效期与触发位**：D为真实交易日历的下一交易日，夜盘按D归属；u收盘将Buy Stop定为H_u＋1有效tick，Sell Stop定为L_u−1tick。只在D有效；D未触发即失效，不能续用旧C9 signal ID。下一日若需新单必须有新的有效C9信号。传统“连续追踪下调买入/上调卖出止单”的长期订单不直接照搬到C9：**一日失效和重发条件是我们的组合约定**，不是声称完整复刻原著。
4. **成交与风险**：逐分钟按真实时戳判断；buy开盘已越位则用不利open，否则真实high触及用trigger，sell镜像，沿原成本/tick规则。保护stop与风险预算只能用u及更早已完成日线，实际fill改变后重算R与整数手；最多保留原C9计划手数，gap导致风险/保证金不足只能减量或拒绝，不借D最终高低/收盘反推更好风险。并列触发的资源优先序须在金融运行前固定。
5. **同分钟保守先后**：open gap成交后，真实open先于极值；分钟内触发则不能把该分钟的pre-entry open当成随后止损/进展或止损成交价，同分钟H/L的先后不能取有利顺序，采用已声明adverse-first。实际C9源码Stage847约205—239行已经规定首次stop后的下一分钟才能retry，retry所在分钟可保守再次stop且use_open=False；初始intrabar entry须获得同样的pre-entry open屏蔽，否则照搬first_stop的open分支会读入场前价格。保持0.5R/一次retry，不加新退出、止盈或补仓规则。这是保守执行约定，不是Elder原著或Backtrader给出的真实tick路径。
6. **unknown不制造收益**：在u决策时周/FI未知，则清除旧准备并明确退回当时A0行为；单列fallback信号/成交覆盖，不能将未知变成反向或隐性空仓。D分钟缺失/数据未资格属于执行阻塞，必须等待已签数据，绝不能冒充指标unknown改按日首open成交。过了原可执行时点也不能倒填一笔所谓A0回退。独立B没有A0信号时则只能等待，不能凭空制造fallback入场。

## 决策与停止边界

这是单一建议，不是参数候选列表：EMA2按LEAN seed、只看符号、严格s<u<D、一日C9信号、既有C9退出与保守分钟模型。原著来源与我们的数据/账户/执行约定必须分别标注；完整实验还需独立B/组合C隔离和实际资源语义，不因C0周门负结果改阈值或挑年份。

开始和结束判断一致：本备忘没有以失败年/品种选择参数，不新增收益驱动过拟合；同一历史被反复研究的选择风险仍在。继续有条件有价值，因为有序时机区别于已经失败的单层许可，但先冻结合同再实施。经典名称、LEAN数学正确或Backtrader执行模型都不证明alpha；本次没有新回测结果或晋升结论，不改LINE/registry。
