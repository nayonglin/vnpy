# Stage018 截至10月30日完成周的下周开仓信号范围

时间：2026-11-01T04:28+08:00（Asia/Shanghai）。所属线：futures_weekly_short_ma_slope_gate。重要突破：否，冻结规则的单次技术信号查询；不构成正式晋升/安装/CTP资格。

**结论：假设15万元空仓冷启动，截至2026-10-30完成周，Stage014 C_R150固定19品种全部无新开仓信号。** 全部19主力合约都已有至少21根完整周线、当周fresh完成，原_generate_signal返回空；entry_candidate_snapshots及intent皆空。没有候选进入风险/保证金/资金选量，不是候选因资金不足被压为0。

这仅回答当前完成数据下的新开技术候选，不承诺下周后续行情不会生成新信号。真实账户权益、Available、持仓及source资格未知，无法据此判断实际账户下周是否需平仓/减仓/换月，不能将历史研究仓位移作真实订单。

## 先读规则与调研判断

已读当前SOP、official-shadow skill、registry/work-type/config；registry定位为weekly19工程候选，SOP明确新分支须独立实际来源资格。Skill旧C9查询入口不能覆盖本次明确Stage014 C_R150口径。本次信号使用已冻结本机数据，不启动HTTP服务；本阶段不新增行情下载；部署日历另见Stage018 calendar记录。判断：直接使用锁源Runtime原工厂/原方法，一次完成日决策，优于另写简化信号或搬历史回测仓位。

过拟合：否。未扫描参数/方向/日期/品种，不根据结果改规则；无金融全史回放。继续价值：是，明确当前技术候选并排除缺数据造成的伪“无信号”；之后价值在周一真实账户/来源核验，无需优化救参。

## 假设与禁止事项

- 明确OFFLINE fixture BrokerID/AccountID，Balance=Available=150000、空仓、场外R=150000不计E；不是券商回执/真实账户。
- 为只读本周技术信号，场景cold_start_date=2026-10-30，fixture asof_clock=同日15:15；这是反事实单日信号范围，不替代实际生产cold cohort，也不许可追历史信号。
- 真实账户/Available/旧仓/实际保证金率为unknown；本轮没有可授权订单或正式daily receipt。条件reader receipt只封在离线report，并保留conditional_read/unqualified/production_qualified=false。
- CTP连接、send/cancel API、SMTP、HTTP服务、全历史金融回测均0。未改core源码、原树、44品种线、LINE/registry/index/Git。

## 数据与时点

只读原冻结data_stage014_20261030/data_approved。五来源pin、代码pin在运行前后相同：runtime5a7a911af89a1319fa9b7ed752e6f42aef67bb9fbb5d7faf3678b2c5a76e6d1c；固定actual_settings513ef478b031ad819dd0a81baf11b76f1fee1bad8671de6526966ad68e6b71ab；reader3cf9ab9d1822390dfd32e1d8cb5bdfe7f8dc3bf621d1e05da1b375e6ad730eb5。

标准库SQLite readonly DTO与physical CSV逐条OHLCV+closeOI核验392382行、2015个positive physical、3117日、2093metadata；10/30有185正量合约bar，固定19主力全覆盖，无0填造，真实closeOI无openOI fallback。原始physical epoch/explicit YYYYMM保持。此为原approved有界数据条件读取，不把历史非完整PIT/零成本等研究限制改写为生产资格。

原raw/fresh_calendar.csv明确给10/29、10/30及11/2；reader将真实11/2扩入下一ISO周确认10/30周线完成，bar仍仅截至10/30。11/3以后的完整交易日历此源未提供，不能声称已验证整周；本次下一交易日绑定11/2已足够，完整生产calendar须root另核。

## 执行范围与19品种

严格read16.186s、原工厂build8.908s、纯AM warmup（所有日期<10/30）37.780s、唯一completedDay34.572s。warmup结束intents0/pos0/layers0/funding request0；随后on_bars仅一次，不执行历史风险/资金/开仓回放。原565方法AST/core源无改，MA5/10/20、无MACD、无加仓、空头allhistory bottom20、原OI风险、原周退出保护不变；完整settings已保存在result。

| 品种 | 当前主力 | 完整周计数 | 原规则信号 | 理论手数 |
|---|---|---:|---|---|
| AP.CZCE | AP701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| CF.CZCE | CF701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| FG.CZCE | FG701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| MA.CZCE | MA701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| OI.CZCE | OI701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| SA.CZCE | SA701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| SH.CZCE | SH701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| SM.CZCE | SM701.CZCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| au.SHFE | au2612.SHFE | 48 | 空（未形成开仓信号） | 未进入选量 |
| cu.SHFE | cu2612.SHFE | 44 | 空（未形成开仓信号） | 未进入选量 |
| fu.SHFE | fu2701.SHFE | 42 | 空（未形成开仓信号） | 未进入选量 |
| hc.SHFE | hc2701.SHFE | 40 | 空（未形成开仓信号） | 未进入选量 |
| jm.DCE | jm2701.DCE | 40 | 空（未形成开仓信号） | 未进入选量 |
| lc.GFEX | lc2701.GFEX | 40 | 空（未形成开仓信号） | 未进入选量 |
| lh.DCE | lh2701.DCE | 38 | 空（未形成开仓信号） | 未进入选量 |
| rb.SHFE | rb2701.SHFE | 40 | 空（未形成开仓信号） | 未进入选量 |
| ru.SHFE | ru2701.SHFE | 40 | 空（未形成开仓信号） | 未进入选量 |
| si.GFEX | si2612.GFEX | 45 | 空（未形成开仓信号） | 未进入选量 |
| sp.SHFE | sp2701.SHFE | 40 | 空（未形成开仓信号） | 未进入选量 |

无信号时手数为未评估，不把unknown/未进入选量写作真实0手。底20、初始止损、风险预算与资金等新开门没有收到native candidate，因此没有伪造“通过”证明。实际成交/实盘quote风险重验本轮均未运行。

## 原封输出交叉核

原Stage014_C_20150101_attempt001与Stage014_C_20260601_attempt001的当周19当前主力周OHLCV+OI与approved physical本周5个真实日聚合逐字段完全相同，source_days也完全一致。两路径10/30 entry_candidates/pending_orders均0，与本次技术空信号一致。

不同历史持仓路径严格分开：2015起点10/30模拟空仓；2026-06起点仍模拟持rb2701.SHFE空13手。后者是既有持仓，不是本周新开空13的信号，也不证明真实券商持仓。未把路径资金/层/risk记忆移入本次空仓fixture。

## 失败保留与复验

首attempt strict SQL读取通过后，build在raw_account_mismatch拒绝：工具最初fixture account fingerprint与其明确OFFLINE BrokerID/AccountID不一致。失败日志保留；只修Stage018工具指纹，不放宽资金/策略core，第二次完成。全量source SHA前后与19周bar parity均通过，独立review由root协调，结论单列不冒称已审。

策略参数新增/修改/删除：无；唯一改变是明确标记的反事实账户/单日cold-start场景。新增/修改/删除回测结果：无。期末权益/收益/最大回撤/Sharpe/总滑点/交易次数/胜率：不适用，本轮没有金融回测。所有原研究失败/NO_PROMOTION结论继续保留。

文件：Stage018_signal_scope_20261030_result.json为完整设置/19指标/门控/原始decision/来源pin；Stage018_signal_scope_crosscheck_result.json为两路径封存输出与19周bar逐字段来源核验；Stage018_signal_scope_artifact_hashes.json为脚本与产物SHA。来源qualification/actualbroker仍unknown；production_qualified=false。
