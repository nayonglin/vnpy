# Stage027：有序入场的因果特征与准备状态合同

- line_id：futures_trend_triple_screen；2026-10-18 02:14 CST；HEAD 67008605c。
- 用户持续自主迭代授权沿Stage001；本阶段由代理固定设计，不重复申请可逆离线研究许可。只实现新入口必需的纯特征/状态与真实信号上界，不碰正式源码、生产、CTP、邮件、其他研究线或用户脏registry。
- 总目标仍是比A0更高净收益且更低回撤，并通过固定多周期/成本/独立复核；本阶段的软件与数据成功不是策略目标完成。Stage024周硬过滤已失败，不救MACD参数。
- 这是新有序机制的第一个可独立验证组件。它不分资金、不发订单、不产生金融收益。盘中执行的预算分配、成交及会计接合另须冻结合同，不能用此组件通过代替真实B/C回测。

## 调研与选择

本次直接再核[CMT的Elder讲座纪要](https://docs.cmtassociation.org/docs/MTA0405.pdf)、[LEAN ForceIndex](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)、[LEAN EMA](https://github.com/QuantConnect/Lean/blob/master/Indicators/ExponentialMovingAverage.cs)与[Backtrader执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)。方向、逆向波动、以后触发是结构假说，经典名称不是盈利证据。Elder当前/旧官网manual本次未重新取到，不声称重核全部原文或完整复刻。

Stage003是收益前的草稿，曾写EMA2 adjust=False但明确初始化待冻。本合同现在单独选择LEAN的两次raw Force均值seed，随后alpha=2/3；不比较首Force seed的收益。零量、缺真实交易日后的重暖是我们的保守资格规则，LEAN本身零量会算Force=0。

## FI2合同

1. `force_index_rows(rows, calendar)`按输入真实合约分别按日排序，输出原日期/合约、raw_force、fi2、ready、reason、previous_date。输入每行含date、vt_symbol、close、volume；calendar是真实交易日，不用工作日替代。重复合约日期、非calendar日期拒绝。
2. 有效bar须close有限且>0，volume有限且>0。无有效前收盘时只seed close；第二个有效连续bar产生第一个Force但未ready；第三个产生第二个Force，其均值为首个FI2。之后`FI2=(2/3)*Force+(1/3)*prior_FI2`。
3. 非有限/非正volume、无效close、真实calendar缺一日均切段并重新需要3个连续有效close。节假日、周末不算缺日。所有reason仅依据截至本行的信息，未来追加或改动不能改变既有行。
4. 不跨真实合约计算收盘差。主力换月不重算或截断新合约已有自有历史，但不能搬用旧合约的准备状态。

## 纯状态接口

`OrderedSetupMachine(arm)`仅接受`B_TS`或`C_TS`。`on_close`使用显式关键字：product、contract、day、next_day、high、low、tick、weekly_ready、weekly_direction、weekly_asof、fi_ready、fi2、eligible、position_open、native_signal。返回dict含decision、setup_id/setup_day、intent或None、baseline_fallback、cancel_reason；输出均可JSON序列化，无账户或未来PnL。

- 同产品每日只更新一次，day严格递增；next_day必须晚于day，来自调用方真实日历，期末可None。周ready时asof严格早于day所属ISO周，direction只许−1/0/+1；tick正，H/L有效。
- 周方向、目标合约、AI资格只在u收盘这一已知边界观察；本次许可与目标冻结到下一执行交易日D，绝不读取D的最终日线/事后主力去追溯取消D早前成交。D收盘再根据当时观察更新。
- 真实合约active epoch改变、周方向改变/变零/未知、eligible=False、position_open=True会取消旧准备/旧未成交intent。新epoch可以使用截至u的新合约FI暖机历史，但必须在新epoch看到一次新的逆向FI，才能建立新setup。
- 周上且FI2<0、周下且FI2>0时建立准备，FI=0不准备。同许可中保持首次setup_day，不因后续逆向日覆盖已有更早准备；这样C不会丢失已有先后关系。
- B在setup_day<=u时可生成只对D有效的条件intent。C还须native_signal方向与许可相同，且setup_day<u；setup与C9信号同一天不能算C的有序通过。无新C9信号不续用旧C9信号。
- trigger为u的high+tick或low−tick，按不利tick网格取整。intent记录arm、确定性intent_id、product、contract、epoch_id、setup_id/day、signal_day、execution_day、direction、trigger、weekly_asof及native_signal；不含数量、资本、盈亏。C保留真实native标签，B明确使用long_triple_screen/short_triple_screen，不能伪称C9原生信号。
- 每次close使上次未成交的一日intent失效，但尚未消费的setup可保留。B次日可用新bar更新条件单，C只能由新每日native signal生成新intent；不无限续旧信号。
- 只有`on_fill(intent_id, execution_day)`确认当前intent在其唯一D成交后，才消费setup；错误ID、迟到日期或重复fill拒绝。生成intent不代表持仓，未触发没有交易或费用。
- `cancel(product, day, reason)`处理当天无真实target映射/bar等情况：不伪造OHLC，清该产品准备/intent，登记严格递增观察日，返回相同六键，decision=blocked、baseline_fallback=False；没有合法native bar时不能凭unknown强制回退开仓。
- 周或FI未知：B无独立信号，等待；C取消旧setup并返回baseline_fallback=True，调用方仍须走原C9全部限制，不能强制开仓。周ready且中性/反向、没有更早准备则不回退。实际执行分钟缺失绝不能伪装成指标unknown回退。
- 明确已持仓或AI不允许的hard状态优先于指标unknown，必须blocked且不能标C fallback。计算出的非正/不可执行trigger不得生成intent，记invalid_trigger；不以强制一tick价格救活。

## 真实数据组件

使用Stage005已验同源SQLite真实日线、原metadata真实合约及global_engine_calendar；FI输入期2019-06-01—2026-10-14，比较期2020-01-01—2026-10-14。周cache77368行沿原SHA，不重算；原900条C9初始信号只取身份/日期/方向字段，不读取经济结果。AI10非fu＋fu仍以原有效日期资格合同为准。

生成一份不可覆盖的FI2因果缓存及B/C潜在intent上界/原因统计、源manifest。上界按全时假设flat且尚未真实消费setup，仅用于后续必要分钟计划，不能称真实成交或可行账户结果，不对潜在intent连接未来PnL。风险/资金/slots尚未接合前不得运行金融臂。

状态机从交易区间首个close空状态开始；2019日线仅暖FI，不把warmup期间的旧准备或订单带进起点。AI选择精确复用A0的eligibility字节，以signal-day查找严格早于它的eval-date（该参数默认False，不暗改为next-day）：2019-12-31静态18前AI快照和后续10非fu＋fu都保留原样，不补造早期fu资格。

## 后续真实实验边界

A0继续复用独立接受结果，150000、AI10非fu＋固定fu、原成本、0.5R/一次retry；B为有序初始alpha＋原持仓管理，C为C9初始信号＋更早回调＋以后突破，均需独立研究子类/引擎。触发日最终OHLC不可用于盘中量或止损；实际fill才落layer；首触发分钟禁止把pre-entry open当入场后价格，同bar不利先，首次stop下一分钟才retry。Stage025已识别必要接合，不在本纯组件里偷偷替代它。

正式CURRENT与远端master e41a0a01d53b7256001e45e686acad53667ef7bf同m0008；本机stable HEAD6b607203a41a47b1255ac1328dde2dc489bb487c，四项已接受修复源码不变。新研究继续明确production_qualified=false，不把顶层配置一致误当全生产资格。

开始过拟合判断：本阶段否，单一经典周期/初始化及取消规则在新臂收益前固定，不搜索胜者；旧历史研究选择偏差仍保留。继续价值：是，只有因果准备状态与真实执行正确，后续收益比较才有意义；不能无限停留在准备或把该组件通过称策略优势。
