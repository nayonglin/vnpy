# Stage612：限价等待与原报价、初损的相容合同建议

- line_id=`futures_full_market_long_signal_ai`；2026-10-21 08:33 CST；day；独立于正式C9。
- 只读设计：先读当前registry、610，再定向读取原042/070/131相关源码；没有读取新收益、缓存或大native，没有导入或运行策略。
- 结论：**有一个低自由度的条件模型可冻结；但必须纠正“原初损按含滑点actual fill计算”的表述。原实现按raw reference F计算。** 若坚持同时改成actual fill−0.25N，应否决本次单项入场实验的合同，不能称只变限价等待。
- 本阶段新增fit/cash/SQL/行情下载/实现均0；财务指标全部N/A；不修改旧源、LINE/registry、正式版或生产。

## 已验证源码事实

| 来源 | 精确事实 |
| --- | --- |
| 042:158—169 | BUY先加max(bps滑点, n个tick)，有合法tick再向上取整；实际fee按最终fill算；slippage=(fill−reference)×乘数，已体现在填价，不再从现金扣第二次 |
| 070:42—52 | unit risk=0.25N×乘数+原双边fee reserve+同reference原BUY/SELL滑点；没有按实际含滑点填价重新定义0.25N |
| 070:55—78 | u时共同reserve；D仅在自己的qty_cap、allocated risk与margin+fee预算内减量/取消，不获取其他订单余款 |
| 131:152—164 | F=D.open；SL0=F−0.25N；F<=low20_u取消；ledger.entry_reference=F而entry_fill=Qbuy(F)；boundary=max(SL0,low20_u)，SELL继续走原adverse_quote |
| 042:126—130 | stop先检查参考open是否已在boundary下，再检查low触达；SL0本身不做新tick取整，最终SELL报价才按原tick方法向下取整 |

因此报价、原始风险参考、实际填价是三个应分开的概念。把SL0改为Qbuy(F)−0.25N，通常会上移止损一个BUY滑点，属于第二个策略变化；再把SL0另作tick取整同样不是原行为。保留原规则才使入场变化可辨识。

## 唯一建议模型：原不利报价可接受时首触成交

L固定为同一原选中epoch的u.close；在u完整收盘后、D开始前假定订单有效，只到D结束，不追价、不跨日。L是研究BUY填价的最高上限，手续费仍单独付，不能把手续费挤入L或减免滑点。

定义Q(p)=原042 `adverse_quote(p,'BUY',econ,scenario).fill_price`，p>0。原b=slip_bps、n=slip_ticks均为正。合法tick t>0时：

`Q(p) = t * ceil(max((1+b)*p, p+n*t)/t)`。

两个内项随p单调增加，向上取整保留单调非降；Q是阶梯函数，非一一可逆，但可精确反解可接受集合的上边界，不需要扫描价格或试阈值。

1. **开盘即满足**：若原Q(D.open)<=L，F=D.open，填价仍为原Q(F)，保留原开盘改善和全部原成本。不能强制填到L。
2. **否则仅等D内一个固定触发价**：有tick时采用合法raw tick格的唯一最大可接受参考价。令`j=floor(L/t)`、`k*=min(floor(j/(1+b)),j−n)`、`P=k* t`。P>0且D.low<=P时，假定在P首次向下触达成交，F=P，实际BUY仍调用原Q(F)。否则D结束未成交。`j`只用于求最大合法报价，不改写保存的u.close；若原L本身不合法tick格，须记录这一元数据/直接报单未知，不能宣称原L已可合法报单。
3. `Q(P)<=L`必须是实际原函数返回值的断言；不得先计算Q再clip到L。P由原b/n/t/L机械确定，不构成另一limit/窗口/滑点臂。反解整数用Decimal的精确十进制或等价有理数，避免除法舍入后向上多一个tick；不加epsilon修复触边。连续raw集合的上确界为`min(j*t/(1+b),j*t−n*t)`，本合同只取其下方合法raw tick格，不另跑连续阈值版本。
4. **原tick缺失/零/非法时**：沿原042数值回退，Q(p)=(1+b)p，触发参考P=L/(1+b)；它是未tick化的条件报价，不是猜测tick=0或捏造最小价位。保留tickized=false与新增审计说明，不把它升级为真实合法报单证据。需以原Q(P)<=L检验浮点边界；实现时应使用可接受侧的可表示参考数并记录精确反解值，不通过clip改填价。若无法满足原函数断言，保留quote/inverse unknown，不当作“已知不成交”。

此处不是通常的“last price触到L就满额填L”，而是**原含不利成本的研究报价首次不高于L才允许买**。例如低价商品受n*t约束，raw参考须比L更低才满足；这是保留旧成本，而非给被动单新的alpha优惠。首触全量、连续路径、无队列/冲击是公开的条件假设，不是官方交易保证。

### 收益前唯一数值编码补充

2026-10-21 08:38 CST按root611拟冻结口径明确：以上语义触发P记为T，与送入旧float接口的F分别保存。

- 全程用`Decimal(str(...))`建立L/b/t；known-tick T为反解得到的精确k*t，仍是raw经济tick格。无tick T=L/(1+b)在局部`prec=50, ROUND_FLOOR`计算，公开这是高精度向可接受侧表示，不冒充无限精度商。
- **触达只比较`Decimal(str(D.low))<=T`**，含等号。不能用之后下调一ULP的F比较，否则D.low恰等于合法T会被错误取消。语义T用于触发而不是第二种撮合臂。
- 起始F=float(T)；仅当`Decimal(str(F))>T`时，做**恰一次**`math.nextafter(F,-inf)`。这是机器表示向可接受侧编码，最多一个相邻float，不是另挂更低一tick、增加价差buffer或扫描价格。known-tick T仍合法；调整后的F只叫其保守机器编码，不能声称F本身又是一个新的合法raw tick。
- 随后硬核`finite(F) and F>0 and Decimal(str(F))<=T`，并调用原函数硬核`Q(F)<=L`。失败统一`numeric_inverse_unknown`，保留未知，不进入known no-touch/known qty0；不继续nextafter、不减一个tick、不clip填价、不加epsilon。也不因一个表述误差遍历多个价格找能赚钱的成交。
- 同一次入场的原报价、原数量、fee/slip、`SL0=F−.25N`和后续原风险函数全部使用**同一个最终F**；不能触达用T、报价用F、初损又用另一个L或含滑点fill。审计保存`semantic_trigger_T`十进制字符串、`encoded_F`、`encoding_adjusted`及硬核状态。T/F最多一ULP的差异是公开数值表示误差，不是可宣称的价格改善。

这个固定方法避免无tick连续商在转float后稍微越界就普遍当作未成交；最终仍以原Q硬核守住L。它不认证队列/真实足量成交，也不改变旧131旧仓先记账循环。本补充仅设计、0构造程序/历史probe/actual，没有新模型或行情。

## 初损、数量与同日退出

选出F之后先检查原入场前提：F>low20_u、N_u>0、SL0=F−0.25N_u>0；生命周期、原unknown、qty_cap等原拒绝仍优先。F<=low20_u时取消，不先开仓再造“瞬时gap_stop”。这保留原stale-entry比较在入场参考F上的意义；不能只在D.open检查后允许日内买入到已失效的low20下方。取消仍在共同reserve之后，不给D其他订单让预算。

原`execution_quantity(intent,F,...)`只执行一次，沿自己的u allocated budgets计算qty；入价较低可改变D可执行减量，但永不超过u qty_cap，不重新共同缩放。手续费、margin、risk与BUY/SELL滑点均通过原函数；已知qty=0是已知不成交，不是未知。

保留`SL0=F−0.25N`、`boundary=max(SL0,low20_u)`、`R0=0.25N`，不改初损tick、不改SELL。开盘成交直接沿原same-day stop。日内成交时，因开盘Q(O)>L且Q单调，O>P=F；又因F>low20_u且N>0，boundary<F。连续首触模型下，价格先到F入场，才可能到更低boundary；因此D.low<=boundary可作入场后止损，不需要把D.high/low任意排列成有利顺序。可复用`price_exit_reference(F,D.low,boundary,None)`，该日内分支不会伪造开盘gap_stop；SELL仍按原报价。未触stop则按D.close原估值，再沿原K/low20/anchor退出。

以上顺序只在所声明连续首触模型成立。真实盘中跳空、停牌/涨跌停、部分成交及stop可成交价仍未识别；0.25N不是最大损失保证。不能以条件模型把此unknown变成实盘认证。

## 原时钟与缺失边界

- 131在u选家族时已排除occupied family，pending与旧仓家族不相交；又没有D再分。因此旧仓日内处理在pending前可保留为原账务顺序：不能用其D止损新放出一个fresh机会，也不允许同family当天重开。若未来设计打破这一不相交条件，须另冻时钟，不能沿本合同外推。
- 新单内部必须先判首触/入场，再判自己的stop；不让D.low决定u选择或u reservation。已知未触达只在合法已知D上成立，缺D仍entry_execution_unknown。
- 原Market把非正volume视为无合法bar；不能把这类bar自行恢复为“0量所以已知未成交”。原独立capacity函数的合法0上限与Market.bar缺失须区分。u qty_cap/entry_capacity为已知0时沿原已知拒绝；缺/非法round_lot、乘数或元数据沿原经济资格状态。
- 原capacity审计只用u成交量1%及当日双边gross累计，不观察D量，更不代表到价方向/队列容量。超原cap或缺容量保留unknown；限价触达不把capacity unknown变绿，也不能新用D成交量给自己加量。
- tickized=false、缺报价/反解失败、原stale/容量unknown与静态经济/PIT限制分别报告。数值条件模型能运算与真实可执行资格是不同层；不通过删除这部分样本获得更干净的收益。

## 交付、调研与判断

复用610当天已真读的一手资料：[能源中心细则](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/trade/202609/t20260914_833389.html)、[CME订单类型](https://www.cmegroup.com/education/courses/futures-trading-mechanics-and-regulation/futures-order-types)、[vn.py维护撮合源码](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)、[HftBacktest成交模型](https://hftbacktest.readthedocs.io/en/py-v2.1.0/order_fill.html)。本轮未重复抓取或扩源；资料支持区分限价、价格触达与成交，不证明盈利。612新增结论来自原本机已验收源码的代数相容性，不来自收益挑方法。

源码绑定：042 SHA`ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d`；070 SHA`ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe`；131 SHA`85205ef9bc309a34283fc0082ac09c53d1f156ca788b8efe6bbd9743f5f430b5`。

建议root在611明确采纳raw F初损修正，并只冻这一种报价首触模型后，才决定0fit、最多四C与原A比较；本记录不签actual，也不把touch/strict两曲线叫经济界。若失败，仅关闭精确条件模型；成功仍须保留真实执行未知。本阶段新增/修改/删除策略参数均无。

开始/结束新增收益后选参：否；长期同史反复择题的过拟合风险：是。继续有界相容设计：有价值；继续到一次预声明条件模型有条件价值，但不是已证明更优。若必须同时改初损、减成本或从多个反解/触达模型挑优，继续价值否。不扩分钟工程，不称全市场高质量long目标完成。
