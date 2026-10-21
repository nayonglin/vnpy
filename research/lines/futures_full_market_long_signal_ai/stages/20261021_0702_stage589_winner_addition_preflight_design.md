# Stage589 原额度内重复赢家加仓：必要上界 preflight 设计与最小IO

- line_id：`futures_full_market_long_signal_ai`
- 时间：2026-10-21 07:02 CST
- 模式：只读小manifest/4 summary、CSV表头与预算/fee源码；仅设计，等root的592冻结后才实施小probe。
- 是否重要突破：否。不是新alpha、不是加仓收益结果。
- 范围：98品种/95家族，157四个OWN A账户；不触碰正式C9。
- 新fit/cash/A重放/SQL/native下载：0/0/0/0/0。累计仍547fit/282完成cash及1旧partial。

## 要验证的唯一问题

原A路径上，是否存在至少一个原u有效信号与已有持仓同actual epoch、已有持仓u时净假设SELL盈利>0且无force/stale/reduce，按原家族/组合/保证金剩余额度及原lot/cap，单候选乐观整数上界至少一手？

**q_upper>0只证明可能；不代表联合批量分配、D成交、实际新增持仓或收益。** 忽略其他普通请求竞争和旧仓同epoch共享gross容量，故是必要条件的宽上界。无任何D数据，不把u.close当已知D价。

## 已核实的最小输入

157 manifest：`stage157_voluntary_cash_v1`、`completed_with_metadata_continuation`，SHA `0c27edef98e636032404272dda9e067e2794d7b7cf49e4ca5401b8b3ea34c7a4`。4 summary均指向独立OWN账户；2020 base/stress有历史stale，四者都有execution_unknown（2023属于容量unknown等），这些限制仍保留。

| 输入 | 用途 | 本轮读取 | actual建议 |
| --- | --- | --- | --- |
| 157 manifest及4 summary | 绑定、账户身份、已有unknown | 小JSON | 仅小元数据核验 |
| 157 signals缓存，583,263B | 已接受原signal、epoch/N/u close/原capacity/原有效K | 仅首行表头 | 单次全表，免重建129/156 |
| 4×daily | 每个u的E、F0all、buffered Mall、空仓/破产/stale状态 | 各表仅表头 | 各单次 |
| 4×positions | 每u逐root/家族占用、entry fill/qty、mark/force/reduce | 各表仅表头 | 各单次 |
| 052绑定041 economic_projection.json，8,146,494B | epoch乘数、lot、tick、vendor margin、qualified status | **只读binding并stat，未读正文** | 单次解析只留必要字段 |
| 042/070/131小源码 | 精确原fee/不利填价、预算与capacity cap语义 | 定向小函数 | source hash绑定 |

4×fills与reservations也各看过首行确认schema，**不进入实际读取预算**。原BUYfee每手恰为`fee_at(entry_fill)`，partial exit不会改变此密度，故positions足够计算剩余持仓按比例入场费，不必读fills。经济投影当前不是严格历史PIT材料，仍只继承原accepted模型事实。

不需要129 actions(334MB)/mothers、156全choices/boundaries、110MB native cache、训练/COMMON52重算、SQL或新行情。最小实际内容约9.3MB（经济JSON为主）；本轮没有读取这些数据行。

## 时钟、资格与准确公式

u范围为各A daily首日至倒数第二日；最后一行不prepare。冷启动前一u为本OWN空仓，不从其他A回填持仓。positions.date=u；缺日期不可当空仓。signals用`potential=1`，沿原qualified economics及family winner排序`(_F suffix, product_id, reference_epoch)`；winner必须与持仓epoch相同，不能向次优同家族合约补选。

原slot处于stale、force_next、reduce_to_next、破产/超原上限或K到期时不新增；未知缺失不能补成无force。原经济source允许缺tick时按fraction滑点，必须沿原模型说明，不把它升级为真实报价证据。

原费用：`fee_at(price)=max(s.fee_min, abs(price)*M*s.fee_bps)`；base为每侧min2/bps0.0001/slip1tick或0.0001price/marginfloor0.20，stress为6/0.0003/3tick或0.0003price/marginfloor0.40。不利BUY向上、SELL向下按tick取整，逐值沿042 Decimal规则。

净假设SELL浮盈：
`Pnet_u = q*[M*(adverse_SELL(mark_u).fill-entry_fill) - fee_at(entry_fill) - fee_at(adverse_SELL(mark_u).fill)]`。

仅对剩余数量q计算，不混入已实现部分；entry和SELL slip已进入填价，**不再扣一遍slippage**。同epoch native mark应与signal u_close一致，否则保留不一致/unknown而非择价。

令C=u_close，N=N_u，L=原round_lot：

- `r_u=.25*N*M + 2*fee_at(C) + BUY_slippage_CNY(C)+SELL_slippage_CNY(C)`；
- `m_u=1.1*C*M*margin_rate(e,scenario)`；`f_u=2*fee_at(C)`只单列披露；
- `Hf=max(0,.0025*E-F0_family)`，`Hr=max(0,.02*E-F0_all)`，`Hm=max(0,.25*E-buffered_margin_all)`；
- `target_upper=min(Hf/r_u, Hr/r_u, Hm/m_u)`；
- `q_upper=min(floor_lot(target_upper,L), 原entry_capacity_qty)`，原cap必须整数、非负，沿原lot语义。

**margin分母是m，不是m+f。** 070约束的是buffered margin；fee另列，且r已含双边fee。用m+f会产生错误偏紧的“零上界”。D的margin+entryfee只可削减原u qty_cap；不能凭假设D=u价对必要上界再加更紧的约束。

positions的`Σq*risk_per_lot`、`Σ1.1*q*mark*M*margin_rate`与daily原F0/M对齐；同日期的account/scenario/epoch、持仓数也须核对。不是重新计算现金收益或回放A。任何可能影响该候选上界的缺失、非有限、重复key、stale估值、未解析状态或一手边界数值歧义均unknown/输入失败，不强行归零。

## root已接受的关键合同：零数量不得先抢reserve

原070先用实数target参与共同scale，再floor手数；131 entry-cap又在共同scale之后。因此，**即使新增单最终0手，也可能先改变普通单的scale/reserve**。若不管这一点，全部0手不足以证明C与A相同。

root已确认592将冻结：**仅新增add在本单候选必要整数上界<L时，在进入共同batch、任何reserve或其他副作用前完全剔除。** 原A普通请求的顺序/预算不变。此规定不重新开启082的普通单一手预过滤。

由此前提，首次分歧归纳才成立：分歧前C=A，故u状态为A；若每个新增请求都是已知原资格拒绝或上界0，则均无副作用，下一步原普通单与旧仓路径不变。四个完整窗口所有候选均已知0/拒绝时，可免4次C现金重放，**仅在原accepted A模型路径内**签“无首次分歧”，不签真实成交/PIT/生产资格。

只要存在正上界，或可能相关unknown，证明就保持开放；不准把正上界当C成交，也不准用本preflight决定提高risk/调整stop。真cash需要另冻joint分配、跨root容量和开盘/日内时序，589不设计引擎。

## 小schema与实施边界

`design.json`已给完整path/bytes/SHA绑定、4账户、最小列集合。待592冻结后，小probe拟输出：

- `candidate_bounds.csv.gz`：账户/u/event/family/epoch/root、资格状态、净假设浮盈、E/F0/M、Hf/Hr/Hm、r/m/f、lot/cap/q_upper/reason；unknown的q留空，不填0。
- `support_summary.json`：每账户正/零/unknown支持计数及月份/家族；不产生C收益/交易记录。
- `manifest.json`与真实start/attempt/terminal：本轮不先造actual回执；输入内容单次read并hash同一raw，避免hash后又全读一次。

本轮未写probe脚本、策略引擎或测试套件；未运行actual。已有小schema不是592最终授权，输入白名单/公式/hash仍由root冻结。

## 调研判断、反思与后续

本轮新查[vn.py维护方backtesting源码](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)，沿579原作者Turtle材料，仅用于提醒u/开盘/日内成交是不同对象；不从开源回测实现推导alpha。本次结论主要依据已接受本地070/042精确源码，外部资料不替代它。

- 是否过拟合：本次**否**，只算必要可行性上界、不看新候选收益、不扫参数；反复同历史选择机制的长期风险仍存在。
- 是否值得继续：**是，但只值得此最小support probe**。若全域0且无相关unknown，省去4C；若正值则只说明下阶段有必要讨论，不能预签有效。
- 结果字段：新权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A。
- 不改LINE/registry、正式C9、Git、生产；等592再实施，root统一研究账本。

输出：`outputs/stage589_winner_addition_preflight/design.json`。
