# Stage037：2024年三笔股指集中亏损的信号与退出审查

时间：2026-10-19 15:27（Asia/Shanghai）。所属线：`futures_trend_full_market_noai_one_lot`。冻结源：`run_20261018_lifecycle_unlimited_v2`，manifest SHA256 `b0893921b612ed284458625bd6405fef5a994a36beb9214839a8a4a7b27be983`。本代理只读交易、候选、风险诊断、事件、日行情、协议、冻结入口及manifest绑定的native代码。没有金融重跑、参数回放或改动源数据/代码/LINE。

**判断：账本及三笔信号/退出可解释，但研究配置存在P1合同语义偏差，不能一概称实现正确。** 用户批准的是“每品种最多1手、不加仓，保留其余正式/日线风控”；研究配置fixed_size=1切走原risk_budget。原生固定分支没有算错，不等于研究工具正确保留了授权风险预算。三笔没有可证的错单、漏平或错误成交价，但“账户PASS”不认证全部原风险预算已保留。同批相关风险还有明确覆盖边界。不能把“保证金够用”“每产品最多1手”理解成三笔合计损失有小额上限，也不能据此断言完整版C9必会避免亏损。

## 同时入场的信号

三笔原始signal_datetime和委托日期均为2024-09-30；10/08是冻结交易日历的下一session，并非10/08临时看到上涨追发信号。9/30三合约的MA20均从MA40下方上穿其上，同时MA5>MA10>MA20>MA40，候选记long_case2、bullish_alignment=1、MACD允许做多、breakout=1。MA10/20在前一天已经是10>20，具体交叉是20/40，不是三笔随机同名。

| 合约 | 9/27 MA20 / MA40 | 9/30 MA20 / MA40 | 信号close→10/8真实open | 跳空幅度 |
|---|---|---|---|---:|
| IC202412 | 4555.14 / 4566.32 | 4625.01 / 4594.50 | 5889→6476.2 | +9.9711% |
| IF202412 | 3274.97 / 3297.46 | 3319.94 / 3316.405 | 4167.6→4549 | +9.1516% |
| IM202412 | 4482.35 / 4489.495 | 4549.19 / 4515.695 | 5769.6→6339.2 | +9.8724% |

原始accepted日线独立计算的MA与candidate记录一致。RSI分别约97.04/97.95/96.38，但协议enable_rsi_filter=false；高RSI并非入场否决。RSI partial-exit对1手乘0.5再取整为0，也不能凭此推断有半手保护。

在线调研核对了[上交所2024国庆休市公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20240919_10762012.shtml)，仅作为标的股票市场长假背景；股指期货本次委托的下一session以冻结RQ交易日历和实际源bar为证，不把其他交易所公告冒充中金所成交证明。

## 为什么风险门允许三笔

协议fixed_size=min=max=1。native `_calculate_entry_sizing` 的fixed分支没有用risk_ratio计算contracts_by_risk：risk_ratio/target_risk_amount/contracts_by_risk为空。它仍检查单笔资金、各自cluster cap、heat、环境门及真实填单时的总broker保证金，但没有对下一开盘跳空后的入场价再施加货币止损风险上限或跳空否决。

9/30初始stop在信号close基础上收紧至2%：IC5771.22、IF4084.248、IM5654.208。实际fill同步entry_price，**不把既定stop重置为实际fill的2%**。entry_risk的行日期仍为原信号日，filled_entry_price/actual_risk_amount是在10/8成交后回写，不能当作9/30已知信息。三笔原计划价到stop的风险合计71,640元，实际fill到原stop的距离诊断升至417,420元，约信号日权益1,363,491.56的30.614%；它只是距离风险，不是保证能在stop价成交的最大损失上限。

risk_cluster_map显式把IC.CFFEX、IF.CFFEX、IM.CFFEX分别映射到同名独立cluster，并没有统一“股指”簇。每个25%资金cap在本案均能容纳1手。相关性门虽开启，但 `_same_direction_correlation_gate_snapshot` 仅遍历已有实际pos非0的同向仓位，排除尚未成交的同批候选。因此记录active_count=5、max_corr约0.340/0.328/0.321、weight=1，并不表示IC/IF/IM彼此低相关；该快照没有比较三者同批待开关系。

逐笔重建10/8开盘权益1,368,846.56，先真实平掉cs，再依序开IC/IF/IM；含真实既有持仓、当前open估值及已发生费用的broker保证金/权益分别约0.280742/0.478169/0.661616，均低于1.0闸门。所以三笔被放行符合现用资金规则。固定一手是数量约束，保证金闸门是资金承载约束；二者都不是共同股指亏损预算。上述同批相关性和cluster分桶是现行覆盖限制；它们不改变fixed_size切换已构成研究合同语义偏差的独立结论。不得回改本轮结果。

## P1：最多1手与强制固定手数并不等价

`run_qmt_roll_backtest.build_roll_setting` 默认fixed_size=0，走risk_budget分支：先计算risk_amount、contracts_by_risk、contracts_by_margin等，再取数量上限。研究Stage003显式写fixed_size=1、min=max=1，因而进入native另一个固定数量分支。这不是修改calculate_volume_by_risk，也不是已经算出0后再篡改为1，而是**通过研究配置跳过了该计算路径**。三笔诊断均sizing_method=fixed_size、target_risk_amount/contracts_by_risk/contracts_by_margin空，且各实际成交1手，证据一致。

用户已批准“最多1手”和保留其余风险，不包含单独关闭风险预算的授权。按此实际合同，配置存在语义偏差：正确的一手上限不能自动推导为fixed_size>0。既有v2应降级标注“原生固定手数分支研究结果”，不得继续称为只封顶1手并完整保留原风险预算。Stage027账户与成交一致性PASS仍成立，但不能扩张为预算保留资格PASS。

本审查没有计算替代risk_budget结果，因此**不能无证据断言这三笔原本一定会被拒**。风险预算是否允许某笔、允许手数及整体路径须另有明确任务和受控验证；本轮只记录偏差，不修改、回放或暗中更新收益。

## IC/IF退出与IM晚一天

native在当日收盘刷新风险状态，依次更新动态stop、检查prev2day/layer stop，再检查heat减仓。`_stop_triggered` 以close比较stop，而非low触及就盘中成交；被触发的target0下一真实开盘填单。trade_events里的price是触发日provisional close，不是最终成交价。

10/8三者收盘为6060、4265、6184.8，对实际entry的浮亏为83,240、85,200、30,880元。用冻结日末权益1,160,493.86、此前高点1,525,997.45与native公式重建：portfolio drawdown约23.9518%，drawdown pressure约0.930119；cluster loss pressure分别约0.862135、0.890284、0.110156；heat=drawdown_pressure×max(margin_pressure,loss_pressure)，本例margin pressure为0，因此heat约0.801888/0.828070/0.102458。阈值0.4：IC、IF越过，IM未越过。实际事件恰为10/8 IC与IF `long_risk_cluster_heat_deleverage`，10/9开盘分别5960.2/4212成交。

IM另有精确的动态stop路径。10/8 close较9/30增加415.2，14日ATR=205.542857，415.2≥2ATR=411.085714，于是ATR大波动中点规则把base stop从5654.208抬到当日(high+low)/2=6117.2。10/8 close6184.8>6117.2，日线基础止损没有触发。虽然当日low5895.2低于这个中点，它不是一个在当日开始前已存在、可按日lowย้อนหลัง执行的盘中委托。

10/9 IM close5715.8≤6117.2，触发`long_base_stop`，10/10真实open5844成交。10/9 abs(close change)=469<2ATR=471.942857，没有再次抬高stop。此路径解释IM比IC/IF晚一个session，不是“其他都平了但IM忘记平”。热度数值和ATR是从冻结账本/行情按源码公式独立计算，历史运行没有逐产品heat快照；实际触发原因由trade_events与最终trade的exit_reason直接证实。

| 合约 | 入场 / 实际退出 | 触发日及原因 | gross / 费用滑点 / net |
|---|---|---|---:|
| IC | 10/8 6476.2 → 10/9 5960.2 | 10/8 heat | -103200 / 142.928184 / -103342.928184 |
| IF | 10/8 4549 → 10/9 4212 | 10/8 heat | -101100 / 186.495990 / -101286.495990 |
| IM | 10/8 6339.2 → 10/10 5844 | 10/9 base_stop | -99040 / 141.646992 / -99181.646992 |

合计净亏 **-303,811.071166元**，与三个closed_episode逐笔独立计算相符。所有六次成交均为accepted clean真实正成交量bar的open，不涉及execution-only或生命周期截止问题。

## 日内停用能确证什么

协议明确 enable_stage827_intraday_c2_stop=false、enable_stage847_half_r_stop_retry=false；当前engine是daily next real open。可确证没有执行C2分钟路径或C9半R止损/重试，不能把本案称完整C9的实际交易表现，也不能把信号价2%止损描述成实际fill后的盘中2%限亏。不能仅凭日OHLC推出分钟事件先后、盘口成交、完整C9是否止损/重试及其最终损益。本审查不计算任何替代止损、禁止股指或完整版C9的反事实收益。

## 范围与后续

本记录绑定九项冻结账本/输入hash及manifest列举的native/入口代码hash，均与源一致；完整JSON保存本案六笔交易、三候选、三风险诊断、事件与公式重算。未新增/修改/删除策略参数或金融结果。重要突破：否，是解释性法证。root的2024逐笔逐日MTM归因已另作下列独立核验，不能把这三笔episode损失直接替代整年账户变动。

开始与结束反思：本次只解释已发生交易，不按三笔亏损筛选规则、阈值或剔除品种，未见过拟合操作。仍有继续价值，因为它厘清“1手/资金承载/止损风险”三者差异；不足以据一次集中亏损宣布参数应怎样改，或声称某未回放版本可以免亏。


## 补充：2024日历MTM归因独立复核（15:31）

归因对象：`outputs/attribution_2024_20261019_v1`；summary SHA256 `30c91650aa6a042dc75341a1373937b01ad496c6ef705cb3c5dc8a941bbd0f62`，与上述源manifest双绑定。9个归因产物hash及全部源文件/生成器hash通过。没有调用Stage035生成器，而以源trades/market重新重建每个entry ID的每日holding/trading/commission/slippage/net与期末active IDs。

独立复核2024共242个日账户边界、2229条episode-day行、340个有当年敞口的episode。逐日/逐episode分项与归因detail一致（最大holding误差1.46e-11元，trading1.82e-12、net3.64e-12，费用与滑点0）；全部每日期末实际仓位一致。episodes、products、signals、asset_classes、monthly、daily_reconciliation、closed_exit_2024_lifetime等全部CSV汇总均核验，无差错。

- 2024账户净损益 **-340,705.679413元**，年初权益1,361,718.777524至年末1,021,013.098111，年度回报约-25.0203%。
- Index：24个episode，-521,828.475558；Commodity：298个，+89,317.796145；Government：18个，+91,805。
- 2024退出334笔的完整持有期净损益-351,363.271913；年末未平净浮14,653.71825，年初3,996.12575，两者差10,657.5925。桥接：-351,363.271913+10,657.5925=-340,705.679413。此处未平净浮包含各自入场成本，用于与完整episode净口径一致。
- 三笔贡献-303,811.071166，占当年净亏89.1711%；其它episode算术合计-36,894.608247。比例与算术剔除不是策略可交易反事实，尤其不能据此说“删三笔以后策略就怎样”。

整日分项抽核（元）：

| 日期 | holding | trading | commission | slippage | net |
|---|---:|---:|---:|---:|---:|
| 10/8 | -1725 | -200995 | 102.695534 | 175 | -202997.695534 |
| 10/9 | -257365 | +126010 | 69.963692 | 125 | -131549.963692 |
| 10/10 | -21895 | +43040 | 29.570640 | 40 | +21075.429360 |

10/8末active entry IDs为4994/5012/5016/5018/5020/5022/5023/5024/5025；10/9末为4994/5012/5018/5024/5025；10/10末为4994/5012/5018/5025（均BACKTESTING前缀）。同时核验当天全部敞口ID和fills列表，不仅比较金额总数；详见伴随JSON。归因产物在其“既有固定手数账本”的口径下PASS，不消除本记录P1合同语义偏差。
