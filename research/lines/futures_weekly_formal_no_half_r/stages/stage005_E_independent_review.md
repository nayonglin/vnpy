# Stage005 E同源19池完整回测独立审查

- 审查时间：2026-10-22 23:27 CST；line_id=futures_weekly_formal_no_half_r。仅独立重算会计与回源，不再执行策略。审查输入为E_attempt009自身input_manifest及实际消费行情闭包；F并行新增、未被E消费的文件不算E输入漂移。
- E有效运行：2026-10-22 23:21:36—23:22:51 CST；terminal completed_pending_independent_review/error=null。前E001—E008失败尝试不合并入绩效；失败完整保留。
- 结论：`PASS_RESEARCH_ACCOUNTING_WITH_LIMITATIONS`；未解决P0/P1/P2阻断0。研究判断`RESEARCH_ONLY_NO_PROMOTION`。机器证据outputs/stage005_independent_review/E_audit.json，SHA256 `ce9355f2992020f47e67a1622a6218b36d580dc421469fd2f0a4f882bd1bd322`；独立审计脚本同目录E_independent_audit.py。

## 资金、成交与闭合统计

| 指标 | D旧19池旧数据 | E同源19池新数据 |
| --- | ---: | ---: |
| 本金 | 150000 | 150000 |
| 期末权益 | 323250 | 335420 |
| 总收益 | 115.5000% | 123.6133% |
| 最大回撤 | -16.340226% | -17.323449% |
| Sharpe（252日样本标准差） | 0.729030 | 0.731551 |
| 总滑点 | 7360 | 8480 |
| 手续费 | 0 | 0 |
| 总成交次数（开平分别计） | 100 | 108 |
| 闭合FIFO匹配段 | 50 | 54 |
| 匹配段胜率（双边滑点后） | 44.0000% | 44.4444% |
| 手数加权胜率 | 40.8654% | 45.9016% |
| 期末未平手数 | 0 | 0 |
| 总赢/总亏Profit Factor | 2.117381 | 2.151034 |

- E闭合净利润185420；平均盈利匹配段14437.9167、平均亏损匹配段绝对值5554.8276。胜率口径为FIFO匹配段，不混同成交次数；终端无开放仓需要排除。
- 实际1647账户日2020-01-02—2026-10-22。逐笔现金流+真实日末库存重建权益最大残差1.17e-10，内部estimated_equity与导出权益最大残差5.83e-11；逐合约日净PnL残差3.64e-12，滑点与signed volume差异0。
- 实际17个成交品种：AP/CF/FG/MA/OI/SA/SH/SM/au/cu/fu/hc/jm/lh/rb/ru/sp。仍只为原19池同数据控制，不是全市场候选F。

## 数据、周线与成交锚

- E的6780个冻结输入逐SHA复核0差，pre/post不变；actual_database_binding PRAGMA实际连接stage005_data/daily.sqlite，和expected一致。新行情DB与映射的完整性另见Stage005数据预审，未改旧D文件或既有行情键。
- 460个实际持仓/成交合约日逐日回SQLite真实close核验0差；均有volume>0。没有用未交易日或缺价日的缓存close替代真实持仓行情。
- 129份proof共358212行，patch SHA/行数、完整task分钟键、原raw SHA/逐值、Tq snapshot/serial bounds、父proof身份和原冻结CSV来源均通过；overlay重复与冲突0。对本run实际108次成交，逐个核order、交易日、canonical session首分钟、实际成交timestamp及price，0差、执行失败0。
- catalog实际消费20个唯一锚，逐个回原CSV及冻结SHA核对0差；没有用daily open合成锚。沿用元数据中的legacy proxy标签不是实际成交来源，真实source/时点/价格以本核验为准。
- 25223根导出周bar逐条回SQLite重聚合0差，要求真实正volume会话集合完整；OI取末、volume求和。41是已接受观察周，不保证连续41自然周。58日无ready目标，ready目标中位3、最高19，809合约中453曾ready；数据准备仍有缺口，不能声称整个19池每天都有完备41周。

## 实际逻辑与D到E差异

- 实际WeeklyIndicatorsStrategy、AM41、5交易日换月、target_contract_only不变，半R/C2/AI三个开关均False。盘中事件、半R事件、C2事件、minute scan均0。89条候选AI enabled均0、allowed均1、月池日期空、分数和排名0；有效run还断言AI load_status=disabled/无eval dates。
- D到E有效参数差只有mapping路径更换；旧19池映射键和全部既有OHLC/量仓值未变，新增的是缺失历史日线。23677个共有周bar逐值0差，新增1546个完整周，减少0；每个新增周都能找到旧DB缺失或零volume的原始会话，非按收益改指标。
- 新增完整周分布2019年385/2020年42/2025年309/2026年810。E和D权益首次差异在2026-08-17；增加12170净利润全部来自后段数据补齐后的不同交易路径，不能把它视为已证明新的策略alpha。
- 品种PnL差E-D：MA +15680、fu +2530、cu -4600、SH -1440，合计+12170。E新增SH实际成交仍亏损，未因负结果删池。
- E相对D回撤略差，Sharpe仅约+0.00252；保证金活跃316日、平均保证金/权益4.466684%。不支持用这一小幅变化宣布稳健优越。后续F需与E同源对照，不能只与旧D比。

## 置信度与决定

- 对本run会计、真实消费行情、配置开关与因果周线内部一致性置信度高；对跨周期alpha、容量、真实券商费用和生产资格未建立证据。原始metrics/spec note中的formal/live/default/deployable历史字样不是研究晋级或生产生效证明。
- 手续费0、产品级规格与静态/默认保证金、固定滑点、供应商快照非逐日PIT以及反复同窗研究等限制保留；数据全91资格也不等于逐日全覆盖。
- 开始与结束过拟合判断：本轮控制仅补真实数据，未按成绩改阈值/资金/品种；无新增调参证据，但同窗与数据选择偏差仍在。继续价值：E作为F的公平同源控制有价值；E本身不是新alpha候选，不追加寻优、不晋级。

- 补充实际成交分钟量核验：108个唯一首分钟均volume>0，最小真实分钟量为136.0手；这证明该分钟有成交，不证明回测手数具有盘口可承载容量。
