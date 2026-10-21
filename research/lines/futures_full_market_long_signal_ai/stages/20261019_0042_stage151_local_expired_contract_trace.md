# Stage151：两只过期合约长期挂账的有界本地链路核查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 00:42 CST。
- 性质：只读事实核查，非策略实验、非重要突破。唯一新增为本文件；不改LINE、registry、源代码、旧输出或其他研究线。
- 新增模型fit、资金回放、SQL、行情下载、大库hash均为0；累计仍为 **397 fit / 206 cash**。不运行旧矩阵或全套测试。
- 先读registry、本线LINE顶部及Stage150；精确检索本线全部stage中的`FU2110/fu2110/FU202110/FU.202110`与`LU2209/lu2209/LU202209/LU.202209`，此前只有Stage150点名这两条长期开放仓，未发现已有的逐环节解释，故本次不重复旧stale总量审查。

## 核查结论

两个末日的**原始观察并未完全消失**：Stage266排除账本记录RQAlpha与旧Tq两源当日都有OHLC和OI，但成交量均为0，因此按收益前既定清洗合同`no_trade`被排除，未进入clean `daily_bars`，也就没有进入132 native缓存的该日行。FU的metadata边界为2021-09-23，LU为2022-08-31，生命周期请求分别在前一源交易日收盘正确产生。执行日没有可用交易bar，131固定资金kernel先走缺价分支，保留数量、旧mark和风险，等待未来同epoch有效open；该epoch之后再无有效行，故持续未决到报告期末。

这条链路已经定位。它**不是已证明的日期日历错误、canonical误换月、132缓存漏存零量有效行或FX特有实现错误**；也不能由零量OHLC填造成可平仓价格。当前更准确的判断是：既定非零成交观察合同与允许持有到最后交易日的研究生命周期合同相遇后，产生了保守但长期的未决仓；未证明违反原合同的代码bug。研究未固定自然人/法人、可否交割及券商强平身份，因此不能把交易所最后交易日等同于所有账户的最后可持仓日。

调研判断：本子任务只核本地接受链路；交易所历史末日及个人账户退出约束由root并行的官方来源核验承担，不以当前通则替代当时规则。本地metadata的9/23和8/31已经明确，不能再用“名义合约月份首日/日历错误”解释。若继续，只值得审视**全市场一致、在当时可知且与账户身份对应的退出边界**，不能对这两只事后已知stale合约加补丁。

## 精确身份、进入与退出时钟

下文CSV行号均含第1行表头；native的local/flat/k均为0起索引。两个action为129原始行，不重新计算标签。

| 字段 | FU长期仓 | LU长期仓 |
| --- | --- | --- |
| epoch | SHFE.FU.202110 | INE.LU.202209 |
| action_id后缀 | 9c849a10afd89b7f224ee6e1e0a0532ba5577b71b8314a1939149df91a4d9eba | 2e7e13910069ae375ccfe83070952632acc7fb79d7286165c11cc6b872658b7c |
| 完整action前缀 | stage129_contract_choice_action_v1_ | stage129_contract_choice_action_v1_ |
| action_sequence_index / actions CSV行 | 1248870 / 1248872 | 968882 / 968884 |
| mother_event_id后缀（前缀stage004_product_day_long_v1_） | f5e5df66dcc89ba36837189a4fc2aa0503bb1f92de0118173e3c3ff2ce97d679 | da6d5b8ad95b6770bc20dcb384ca2ef105e8dd3e35148b00056d9d257576a3ad |
| u日期 / k | 2021-09-15 / 4061 | 2022-08-15 / 4280 |
| D入场 / k | 2021-09-16 / 4062 | 2022-08-16 / 4281 |
| immutable anchor | SHFE.FU.202201 | INE.LU.202210 |
| u N / low20 | 77.04052691644141 / 2371 | 250.97694750315844 / 4763 |
| expiry / 对应源日 | 4065 / 2021-09-23 | 4292 / 2022-08-31 |
| 首次请求日/原因 | 2021-09-22 / lifecycle_exit | 2022-08-30 / lifecycle_exit |
| 129首个unknown日/索引 | 2021-09-23 / 4065 | 2022-08-31 / 4292 |
| 129最后已观察路径索引/持有源日 | 4064 / 3 | 4291 / 11 |

经济投影`instruments[epoch]`中，两约`known_lifecycle_exit_boundary`、`maturity_date`、`de_listed_date`均分别为9/23和8/31；`nominal_month_first_date`则为10/1、9/1。`stage042_cross_session_experiment.py:100`取这些已给定边界的最小日期、映射至源日历；本次未出现取名义月份晚于精确边界的问题。

129两行均为`u_action_eligible=1`、`participation_state=filled`、`filled=1`，最终`label_state=path_or_execution_unknown`、`unknown_reason=missing_or_invalid_held_old_epoch_bar`、`trade_label_known=0`；`exit_date/exit_reason/label_known_date/net_R_stress/net_R_base`均空。即原标签从未把缺失平仓填0、负类或已成熟闭合交易；现金仍尝试下个合法旧epoch open的处理不等于标签恢复已知。

129 mothers中，FU的9/15至9/23 canonical一直是FU202201（CSV353212—353216），LU的8/15至8/31一直是LU202210（CSV308617—308629）。持仓月与初始anchor不同在128合同中允许；持仓不等于anchor本身不会触发退出。请求前没有canonical变化或缺失，首次请求是生命周期边界。`stage129_contract_choice_dataset.py:75`与`stage131_contract_choice_kernel.py:39`均可核对。

## native最后有效行与原始零量末日

132缓存是`cash_only1/native_store_cache.npz`，`epochs.npy/offsets.npy`确定epoch切片；只读取四个epoch（两held及两anchor）的必要列，未恢复全部store、未重hash缓存或数据库。缓存有9520 epoch、1552456行，这些总量沿已接受缓存元数据引用，未全表复核。

| held epoch | epoch序号 / flat切片 | 最后有效local/flat/k | 日期 | O/H/L/C | V | accepted/valid |
| --- | --- | --- | --- | --- | ---: | --- |
| SHFE.FU.202110 | 7793 / [1247454,1247692) | 237 / 1247691 / 4064 | 2021-09-22 | 3300/3300/3300/3300 | 1 | true/true |
| INE.LU.202209 | 6296 / [968321,968467) | 145 / 968466 / 4291 | 2022-08-30 | 5861/6095/5815/5815 | 37 | true/true |

这两条均为该epoch缓存最后行；退出日及之后无该epoch缓存行，不是有一行但`valid=false`。anchor在对应退出日仍有有效行情：FU202201于9/23的O=2839、C=2916、V=1510761；LU202210于8/31的O=5175、C=5091、V=99525。它们属于不同合约，不能拿来平旧epoch仓。

`stage266_clean_daily/excluded_observations.csv.gz`已保存末日原始观察的排除证据，本次读取的精确两约两日为：

| CSV行 | source_id / source_locator | epoch / trade_date | raw O/H/L/C | raw V / close_oi | reason |
| --- | --- | --- | --- | --- | --- |
| 252883 | rqalpha / key FU2110,row241 | SHFE.FU.202110 / 2021-09-23 | 3300/3300/3300/3300 | 0 / 336 | no_trade |
| 1119590 | old_tq:SHFE.fu2110 / row243 | 同上 | 同上 | 0 / 336 | no_trade |
| 366039 | rqalpha / key LU2209,row241 | INE.LU.202209 / 2022-08-31 | 5994/5994/5994/5994 | 0 / 7333 | no_trade |
| 1095628 | old_tq:INE.lu2209 / row243 | 同上 | 同上 | 0 / 7333 | no_trade |

RQAlpha原文件定位为`research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5`，上述key与0起row即排除账本保存的source_locator。本轮复用已接受排除账本中的raw_values，**没有再次读取H5或声称独立重验原文件内容**。两源数值相同提高了对本地清洗链路解释的把握，但不构成当年首发PIT或真实委托可成交证明。

`stage266_clean_daily.py:32`首先把`volume==0`定为`no_trade`；`:185`至`:188`将其写入excluded并return，故不插入daily_bars。132的`read_native_once`在`:195`只按日期查询daily_bars，**没有按train_eligible、legacy108、positive volume或quality_status额外WHERE过滤**；`:192`保存valid标记，`:199`仍把查询到的全部行加入缓存。因此缺行原因已前移定位为Stage266既定零量清洗，而非132恢复缓存时丢行。

## 148账本、容量和长期未决分支

148 primary_2020 base与stress的FU都是同一action、9/16 BUY 7手；base reference/fill=3112/3113，stress=3112/3115。base的LU为8/16 BUY 1手，reference/fill=5170/5171。FU在base fills/capacity CSV第600行、stress第493行；LU在base第1341行。三个根仅有该次入场fill，之后无SELL。其他同epoch已平仓的LU action不混入本次根。

入场并非容量拒绝：FU的u成交量1426，固定1% gross cap14、往返半额cap7；实际BUY7在上限内。LU的u量22038，gross cap220、半额110；base实际BUY1在上限内。148 signals_FX CSV第2504/2069行、base reservations第837/2401行可以复核。LU在stress的同一信号没有入场，reservations第2403行及rejections第2020行显示`target_qty_prefloor=.4606616731`、`qty_cap=0`、`D_state=risk_margin_or_one_lot_rejected`，不是生命周期或容量判为不合法。

末日退出没有fill，因此也没有新的capacity audit行。kernel的容量检查发生在已有fill之后，是标记未知而非阻断退出的分支；本案直接阻断点为缺bar。仅按既定公式作算术诊断：FU末日前日V1、LU末日前日V37，1% gross cap均为0；即使取得一个价格并假想卖出7/1手，也不能因此宣称通过当前容量合同。这不是实际新增成交/资金模拟，不能补填为某条已验证退出。

资金分支为：

1. `stage148_fx_cash.py:90`调用cache locate，退出日不存在held行即返回None。
2. `stage131_contract_choice_kernel.py:125`至`:128`先检查bar；None时设置`deferred=True`、`force_reason=research_deferred_liquidation`、保留旧mark并记stale，然后continue。原请求没有被忽略或撤销，但当前展示force字段转为缺价后处理；初始`anchor_request_date/reason`仍保留。
3. 只有之后出现合法同epoch bar才可到`:129`至`:133`按旧epoch open退出。由于该epoch缓存最后行已在前一天，此条件始终不成立；这是无限期等待的来源。缺价同样阻止stress后续已请求的减仓，rejections第3050/3222行显示2025-02-11、2026-01-26为`missing_quote_deferred_exit`，不是数量已经减少。
4. `stage042_cross_session_experiment.py:218`在mark=None时不改旧mark。期末2026-10-16，FU仍7手、mark3300，base/stress未实现盈亏分别13090/12950；LU仍1手、mark5815、未实现6440。不能用8/31零量5994替换为可成交或已兑现利润。

148 base positions CSV第792行/795行为FU的9/22生命周期请求/9/23首stale；LU第2097/2108行为8/30请求/8/31首stale。stress对应FU第618/620行。末端base第5767/5768行、stress第3488行显示数量保留。open CSV base第2/3行、stress第2行保留全部初始请求身份与`stale_open_unresolved`。

FU根在期末连续stale **1224个源交易日**，LU为 **997个**。Stage150的**1227是账户中任一stale_positions>0的日期数**，不是单FU的连续天数，更不是自然日数；两本最早stale日期为2020-04-14（本轮不再追该旧根）。`stage102_cash_diagnostics.py:137`是该口径。FU始终stale覆盖后1224日，LU后997日与之重叠，不能把两根天数相加得到账户1227。

旧131B primary_2020 base和stress的open第2行已经是**完全相同的FU action、同样7手、同9/22请求、同3300末mark和1224连续stale日**。故FU长期挂账不是FX新增逻辑独有，也不能拿它证明FX收益增量来自或不来自过期仓；本次没有计算收益归因或删除该仓后的反事实资金路径。旧131B末端未见本次8/16 LU action的长期开放仓。

## 原因层级、置信度与最小下一步

| 层级 | 已证事实/判断 | 置信度 |
| --- | --- | --- |
| 身份与生命周期 | 精确epoch、u/D、metadata boundary、源日历映射一致；不是用名义月份推错边界 | 高（本地接受证据） |
| 数据语义 | 原末日零量观察存在于排除账本；clean按no_trade排除，132未再次筛掉该行 | 高（代码与双源排除记录相互印证；未重验原H5） |
| 请求逻辑 | canonical稳定；前一日按lifecycle签发；held不同anchor是合同允许行为 | 高 |
| 执行与资金 | 无held可交易bar先进入deferred并保留旧仓；无后继有效行导致长期未决 | 高 |
| 实际市场成交/交割 | 零量OHLC不可作成交证明；实际账户强平/交割/结算与损失未识别 | 未知，不能从研究账本推出 |
| 是否代码bug | 当前路径符合已冻结合同；未证明实现错误。生命周期合同对非交割账户是否恰当另属设计问题 | 高置信度的范围限定结论，不给全库无bug保证 |
| alpha/收益增量 | 本次没有识别FX或策略alpha，也没有证明过期仓造成增量 | 不作归因 |

本地链路已足够，无需为解释此两约再做SQL、下载或大库检查。若root要求进一步独核原始字节，最小读取仅为上述H5两key各row241，另与两个末日官方历史交易/交割资料核对；不是重读全库，也不是重放资金。原始零量观察不能解除成交未知。

可考虑的最小共性改进仅是**另行收益前冻结**：明确研究账户是否可交割，按所有品种当时可知规则与交易日历统一给出非交割账户退出边界，并把`no_trade`、源缺失、到期后交割/结算未决区分记录，保留原生命周期请求原因。任何数值变化都需单独界定最小必要重算范围和独审；不按将来stale与否过滤，不对FU/LU特设例外，不用最后一条未来有效bar回溯“提前平仓”，不把expired状态改名便删除资金/风险义务。本次不实施这些建议。

## 复现路径与执行边界

- 本线输出根：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/`。
- 原动作/母行：`stage129_contract_choice_dataset/actual_run1/actions.csv.gz`与`mothers.csv.gz`；只取上列两action及对应窄日期母行。actions通过已知sequence的物理行读取，读取到第二目标即停止，没有全表标签审查。
- native接受缓存：`stage132_contract_choice_review/cash_only1/native_store_cache.npz`与`.json`；序号及切片见上表。
- 原B开放快照：`stage131_contract_choice_cash/actual_run1/NARROW_B_primary_2020_{base,stress}/open.csv.gz`。
- FX小账本：`stage148_fx_cash/actual_run1/NARROW_FX_primary_2020_{base,stress}/{open,positions,fills,capacity_audit,reservations,rejections,daily}.csv.gz`及`signals_FX.csv.gz`。
- 经济投影：`stage041_minimum_cash_economics_sources/economic_projection.json`的`instruments`双epoch对象。
- 排除与清洗合同：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/excluded_observations.csv.gz`、`dataset_manifest.json`；清洗与kernel代码行号已在正文给出。
- 日历：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/trading_dates.npy`；本轮解释器全部为`.py311/bin/python`。仅读取本报告所需字段/片段，没有调用任何策略、模型或cash运行入口。

新增/修改/删除策略参数、回测结果均为0；本轮期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均为N/A（未跑新回测），不得把上述单仓mark和浮盈当新账户成绩。148原始指标与Stage150结论保持其原有条件解释，未因本次事实核查升级资格。

开始与结束反思：新增按收益救参的过拟合，**否**；这是固定两条已披露异常的事实核查，没有选新阈值/收益样本。若据此只修这两约、未来stale过滤或挑好看的提前退出日，则会产生过拟合与前视，因此拒绝。继续本轮有界核查，**有价值且现已足够**，因为它解释了执行未知来源；继续扩成全库重审或立即重训/资金回放，**否**。继续原全市场高质量做多目标，**是**，但先以全市场一致、账户身份明确的生命周期可行性决定是否需要新协议。
