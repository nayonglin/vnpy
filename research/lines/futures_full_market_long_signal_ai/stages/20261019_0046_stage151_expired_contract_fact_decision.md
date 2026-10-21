# Stage151：长期挂账事实结案与研究边界决策

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 00:46 CST；非重要突破。
- 前置已读registry/本线LINE与150；两个独立分工分别核本地链路与官方历史/GitHub资料，root已读两份最终记录。不是新增金融实验，不额外签全面资金独审。
- 本次参数/代码/回测结果新增、修改、删除均0；新fit/cash/SQL/下载/标签/大库hash均0。累计397实际fit/206资金账户不变。新期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均N/A；原八本成绩见[Stage150](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0037_stage150_fx_fixed_comparison_decision.md)，没有重跑或重解释为实盘兑现。

## 结论

**未证明实现bug，不做代码修补或金融重跑。** 两合约末日原始观察存在、成交量为0，按原清洗合同no_trade排除；精确到期边界正确，回测已在前一日请求退出。执行日无同合约可交易bar，保留数量和旧mark，记录未决。原129标签也早已是unknown，未被填0或纳入成熟闭合标签。该路径符合原协议，不能拿零量OHLC、别的主力合约价格或未来最后有效bar补造平仓。

这也不意味着名义资金结果可以当可实现收益：过期后实际强平/交割经济了结未建模，长期旧mark只是研究未决状态。统计计算被接受；经济可执行资格仍未知。原CONTROL也有同一FU挂账，因此不能把此现象归因FX引入，亦不能简单扣掉浮盈就创造完整反事实资金曲线。

| 合约 | 入场 | 已知末日/原始成交量 | 首退出请求 | 末日零量OHLC/OI | 末端连续stale源日 |
| --- | --- | --- | --- | --- | ---: |
| SHFE.FU.202110 | 2021-09-16，7手 | 2021-09-23 / 0 | 2021-09-22收盘 | 3300 / 336 | 1224 |
| INE.LU.202209 | 2022-08-16，1手，仅FX基础本 | 2022-08-31 / 0 | 2022-08-30收盘 | 5994 / 7333 | 997 |

Stage150的1227是账户中任一stale仓存在的**源交易日日期数**，不是FU连续天数或自然日，也不能与LU997相加。两个末日零量由Stage266排除账本RQAlpha/旧Tq记录交叉支持，本次没有重读原H5或取得交易所成交回报。数据语义解释置信度高，真实平仓/交割现金流仍未知。

## 调研判断

[INE2022-03-01生效标准合约](https://www.ine.cn/upload/20211018/1634548472970.pdf)支持LU前月末最后交易日；[官方历史LU手册](https://www.shfe.com.cn/content/2020_LU_DERIVATIVES/manual.pdf)记载不能交付/接收规定发票的个人客户T−8清零，同期日历对应LU2209的8/19。FU的历史个人T−3规则与同期日历对应9/16；其9/23末日还有官方年报和同期调整通知转发印证。FU原调整通知页、LU2022全部版本沿革未完整取得，不能冒称逐版资格证明。今日LU已改T−5，不能倒套2022。完整来源强弱见[官方资料分工](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0042_stage151_official_contract_lifecycle_facts.md)。

[vn.py官方组合回测实现](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)有缺bar按旧close构造同步OHLC并参与撮合的逻辑；否决照搬它给过期仓“补平仓”。基础引擎行为不能代替成交量、到期制度和交割义务。

判断：本次不是需要继续补整库数据的小错误，**是研究账户身份与经济退出合同尚不完整**。最后交易日、个人最晚持仓日、最后有成交观察日、交割日必须区分。研究没有明确交割资格，不能默认为有资格法人，也不把本次个人规则直接追溯应用于旧账本并删除亏盈。

## 下一步的有限范围

当前完整目标仍是全市场高质量long、提高成本后收益并降低回撤，随后才有条件谈窄损和增加投注。为使后续结果与可执行交易相符，后续研究默认选用**不参与实物交割的投机账户**作为经济目标；这是一项明确的新研究口径，不声称用户真实券商资格或改写旧实验。

先有界核现有元数据/历史规则是否足以给六所全市场统一的最晚持仓与退出边界，并保留规则适用期、来源、当时可知性及unknown。现金结算品种等按自身制度区分，不机械套实物交割。只在覆盖与时钟足够时，另冻结共同政策、必要重算范围与独审预算；不先建设全品种全版本规则工程，不立即增加fit/cash。若缺规则无法检验，就保留具体缺项并决定其他方向，不无限搜网页。

禁止只修FU/LU、按未来stale与否准入、以未来最后有效bar提前出场、填造结算成交或把未决仓改名后清除资金义务。不按本轮收益调退出提前几天、容量比例、模型/止损/加注参数，也不恢复失败FX包。

开始/结束反思：新增按收益救参过拟合，**否**，核的是已有异常的事实链；若用后见stale筛样本则会造成前视，故拒绝。继续本轮核查，**已足够，应结束**；继续统一经济合同的有限可行性判断，**有价值**；全面旧资格再审、立即重训或重跑，**无价值**。目标仍active，稳定优势、极窄损上界与加注资格均未证明。

## 证据

- [本地逐环节核查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0042_stage151_local_expired_contract_trace.md)：双源排除物理行、原129动作、132缓存及131/148请求分支、旧B同FU与口径界定。
- [官方历史规则与GitHub取舍](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0042_stage151_official_contract_lifecycle_facts.md)：原始URL、时点差异与未取得证据的边界。
- [本阶段结构化决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage151_expired_contract_fact_decision/decision.json)：包含两份记录的字节数和SHA，只绑定必要小型文档，不重hash大库。

不修改根memory/back_log或外线，不Git提交/推送/建分支/worktree，不触正式/生产/CTP/订单/邮件/定时任务。
