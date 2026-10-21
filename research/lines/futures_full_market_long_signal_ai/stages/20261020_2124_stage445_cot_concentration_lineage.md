# Stage445：COT集中度既有输入血缘的有界只读审查

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 21:24 CST；工作区`/Users/mac/Desktop/fian`。
- 性质：只读既有字段/源码审查，非重要突破，不触发A/B，不授权新金融。解释器`.py311/bin/python`只执行stdlib静态AST/JSON整理，不导入或执行旧工具。
- 范围绑定：444 scope 4,599B，SHA `b275a60e0210f62520687f39db501418bb1bebd334272f2f9213a3db6c5db64e`。

## 结论及范围

**所核旧014、256、048及本线407—410链条，没有发现4/8大户gross/net long/short集中度被提取成数值、进入实际q、训练矩阵、候选条件或金融实测。** 本线407既存2010 schema确实保存24个集中度header；“原件/表头存储”不是“模型用过”。原ZIP表头真实性及各年header覆盖交446源审查；445不推断原值完整、抑制/缺失/数值分布或PIT资格，不能断言所有历史、其他分支、其他仓库完全未研究。

**PMPU旧048算过并存储过，实际q与候选条件只用MM。** 不能说PMPU是新字段，不能说它已在本线全母域被同输入金融证伪。409依然关闭重复PMPU净标量金融后继；本审查不解除价值NO-GO。

## 旧COT实际用了什么

| 旧路径 | 明确数值读取/计算 | 实际q/条件/审计 | 集中度 |
|---|---|---|---|
| 旧014，Stage313实现 | OI、MM long/short、Change MM long/short；市场名/报告日 | MM净仓/OI和MM周净变化/OI；156周/min52 z，分别clip±2后除2，0.35/0.65合并并按long/short取符号；生成建议倍率/veto后固定分桶审计 | usecols无集中度，未计算或进入q |
| 旧256 | 同五个数值原字段 | 同MM q、supportive/neutral/headwind及已有样本上的条件稳定性审计 | 未进入读取、打分或候选条件 |
| 旧重建048 | 额外PMPU long/short；计算producer_net_oi及producer_net_z | PMPU随signals/joined保存，score与全部候选条件只用MM q及mapping/命中状态 | 未进入显式读取、signals/joined或条件 |
| 本线406—410 | 406拟H增量；407五原数计算H/MM，408/410仅来源/修订核验 | 409取消weekly投影和拟议6fit，不是模型/金融实验 | 全header保存在schema，无集中度数值提取或金融后继 |

准确旧公式：`q=clip(sign(direction)*(0.35*MM_net_component+0.65*MM_flow_component),-1,1)`；各component是其滚动z clip±2再除2，旧代码对不可得component填0是源码事实，不是本轮建议。MM flow只是持仓周净变化，不是资金流入金额。

旧048的`producer_net_oi=(PMPUlong−PMPUshort)/OI`，另有156周/min52 `producer_net_z`，但该两列仅进入信号/附表。407 `H=(PMPUshort−PMPUlong)/OI`是旧净标量取反，并非新信息机制。三个旧入口没有`.fit()`调用；048的`summarize_condition_oos`是固定条件分组/样本外统计。train/valid/test分段不能被写成“完整COT原表训练过ML”，已有MM条件负证据也不能扩成PMPU同域已实测失败。

源码证据：

- [旧014读取与MM计算](/Users/mac/Desktop/fian/examples/portfolio_backtesting/analyze_qmt_roll_stage313_cftc_cot_external_quality_probe.py:87)，[q及建议项](/Users/mac/Desktop/fian/examples/portfolio_backtesting/analyze_qmt_roll_stage313_cftc_cot_external_quality_probe.py:159)，[分桶入口](/Users/mac/Desktop/fian/examples/portfolio_backtesting/analyze_qmt_roll_stage313_cftc_cot_external_quality_probe.py:268)。
- [旧256 usecols](/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/tools/stage256_cftc_cot_cross_market_context_audit.py:150)，[MM q](/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/tools/stage256_cftc_cot_cross_market_context_audit.py:188)，[实际条件审计入口](/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/tools/stage256_cftc_cot_cross_market_context_audit.py:798)。
- [旧048读取/PMPU计算](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:156)，[MM专属合并](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:238)，[PMPU信号存储](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:289)，[PMPU附表](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:396)，[全部候选条件](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:413)，[OOS入口](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage048_cftc_cot_mapping_audit.py:632)。
- [407固定字段](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage407_cot_parse_year.py:22)，[唯一H/MM数值生成](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage407_cot_parse_year.py:215)，[原header仅存schema](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage407_cot_parse_year.py:184)。
- [130 COMMON来源](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:18)，[52列设计](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:69)，[训练显式取26列](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:139)：COMMON26加同26缺失标记，无COT类别/集中度。129和071 COMMON列表静态核对；130不继承071自身的额外scalar槽。

本线自己的Stage048是全机会构建协议，与旧重建线Stage048不是同一阶段；前者无COT字段内容，不混编号。

## 原表/存储与模型使用分开

445只读取407既存`schema_2010.json`头部元数据，33,635B/SHA `98a96551fff29333812e489c691ffd52ae6c621b2a793dde929285d3a76d8d87`，原ZIP/CSV数据行0。其`f_year.txt` original_header含：

- `Conc_Gross_LE_4_TDR_Long_All`、`Conc_Gross_LE_4_TDR_Short_All`、`Conc_Gross_LE_8_TDR_Long_All`、`Conc_Gross_LE_8_TDR_Short_All`；
- `Conc_Net_LE_4_TDR_Long_All`、`Conc_Net_LE_4_TDR_Short_All`、`Conc_Net_LE_8_TDR_Long_All`、`Conc_Net_LE_8_TDR_Short_All`。

All八列zero-based161—168；Old八列169—176，Other八列177—184。24列不代表可任意挑选的24个新因子。原值未读，不宣称合法0/缺失/抑制/覆盖或可用时钟通过。

407流过完整原行并保留原件/行hash、全header，不等于全部列进入模型；其`FIELDS`只选择身份与五个PMPU/MM/OI数值。408集中度提及仅指2018 Legacy更正与Disaggregated不受该次更正影响的范围说明，410为复审，不是集中度收益/训练证据。

本线`tools/*.py`限定stage<=444，按CFTC/COT/Conc_Gross/Conc_Net/producer_net/pmpu_标记检索仅命中407、408、410来源工具；不把该有限搜索扩成全仓库、所有历史不存在的断言。原始资产绑定、完整列清单、源码SHA及行号保存在inventory。

## 调研、判断与继续价值

复用root444已实读的[CFTC官方解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)与[维护者cot_reports](https://github.com/NDelventhal/cot_reports)，445新网络0，不伪称重复查网。定义可说明集中度与MM/PMPU类别净仓不同，不保证long方向alpha；可证伪机制及是否仅反映波动/流动性风险交root综合。

**从血缘角度继续一次有限来源/机制裁决：是。** 所核旧q和COMMON模型没使用集中度，不能直接把它归成已失败MM/PMPU净标量。这不是alpha GO，不授权金融、weekly大投影或窗口/类别/方向扫描。若只是字段存在而无可证伪机制，或实际仍是旧净标量改名/换符号，就停止。

开始/结束过拟合：本轮新增收益择参否；长期重复同一历史择题的适应性风险仍高，字段新不重置检验次数。开始/结束价值：有限血缘审查有价值且已完成；只给root一次机制/来源裁决依据，不授金融GO。

## 变更与账本

仅新增本文与inventory。金融参数、回测结果新增/修改/删除均无；原ZIP/CSV数据行、价格/Y/分数/模型读取、新q/旧金融重跑、下载/网络/API/SQL、fit/cash、账户/生产/CTP/订单/Git修改均0。未回测，期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A，不填0或旧值。

落盘前一次元数据断言失败：并行446新建tool使当前目录命中由4变5，未写任何输出；仅将历史搜索固定stage<=444后静态检查通过。不是数据/模型/金融失败，未改旧物料或收益。

inventory 21,044B，SHA `0585a41e16dfc7fb1d84cd9b7fdbbac6dfe1553afe4d347919265820976938d2`。本agent不改LINE/registry/旧stage/他线/根memory/back_log，交root447统一承接。
