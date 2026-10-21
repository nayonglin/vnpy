# Stage411—417：网络执行修正后，首个双模型真实前瞻提案完成

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 15:34 CST；分支`codex/ai-training-data-expansion`，未切分支或Git写操作。
- 本轮是执行与新观察的实际进展，**不是alpha重要突破**；不改正式C9/月池，不触发正式版本晋升。完整目标仍active、未完成。

## 为什么等待日线，以及本轮执行修正

今天完整日线只用于已冻结模型生成D21研究提案，历史研究并未等待bar。407—410已完成16年COT原档与有限发布事实归档，同时纠正重复路线承接并关闭其金融后继；不再重复旧回测或来源工程。

原360单批于15:15后启动，33703真实exit1/no_raw。原362一次独审确认0raw/0score/0funded，保留空输入无资金research seal，不是“没有交易信号”。认证域名与对照CFTC域名在沙箱内均gaierror8，获准外沙箱DNS诊断均成功，未读凭证或行情，原因是启动环境网络隔离。

root411在07:18:43Z明确一次操作修正：原失败证据保留，外沙箱运行同一冻结357、874×3日线、相同模型/输入/时钟/风险及原15:15—21:00窗口，freshbatch002；合计2次API尝试，第1次零行情；无第3次授权。**原“一次采集/no-retry”承诺有偏差，strict original single-acquisition adherence=False，不能冒称原计划无偏差一次成功。** 412独立核12原账户/journal/envelope及4model/scaler字节未变，初态/空仓未重置，接受因无数据/无评分的单次环境修正，不自动授资金资格。

新9175真实exit0，15:19:59完成。874raw/2622行；737新u20接纳，128无效排除、27日期未知保留，726精确u19见证/0冲突；779warmup/9526inventory保留。414一次1.716秒独核raw/单步N/low20/母98族95/双域，最大差0；26特征仅冻结core一致性，未冒称另一套独立公式。13无当前观察产品仍在母域，不把737合约或85有源产品说成全98产品全部有数据。

源完成15:15、接收15:19:57，D21已知最早开盘20日晚21:00；源域737、D执行域448，未知时钟0。vendor finality/原first-publication及外部clock认证仍unknown/False，属于本地可追溯因果研究而非交易所最终性认证。363接受actual_batch002/run2，旧run1不覆盖。

## 两模型原账户的实际一步

415只调用原382实际恢复一次、原370/378context各一次、原376 process_pair一次，21166 exit0/6.785秒；两模型接受完全相同restored对象，前后identity不变。基准真实训练cutoff2023-01-01/T0=2026-10-19T20:21:56.703789Z；更新模型cutoff2026-10-20/T1=20:48:38.399842Z。各自原T_init保持，不新建账户，不复用旧无资金封签。

新完整资金提案分别在15:25:13.196838/15:25:14.678247封存，均晚于新源、早于Dopen21:00。四个原模拟账户均100万元，phase=awaiting_D、last_u5290/last_D=null；各自新state另存，原初始化文件保持历史证据。

| 模型 | 事前候选 | 基础成本待评估提案 | 压力成本待评估提案 |
|---|---:|---:|---:|
| 原2023基准 | 7 | 6 | 5 |
| 更新成熟训练数据 | 2 | 2 | 2 |

基准候选为BZ、EB、JM、PP、LU、BU、FU；更新模型为LU、FU。共同LU/FU在基准base的qty_cap各2、stress各1，更新模型两情景各4，来自同一固定预算规则对不同候选集合的分配联动，**不是加大风险参数，也不能把未来资金收益差纯归因于信号质量**。选得少目前不证明选得好。

| 账户 | 已承诺风险预留 | 缓冲保证金预留 | 费用预留（未实际支付） |
|---|---:|---:|---:|
| 基准/base | 7,912.53 | 210,662.38 | 191.51 |
| 基准/stress | 3,739.19 | 180,419.04 | 246.03 |
| 更新/base | 5,000.00 | 118,759.67 | 107.96 |
| 更新/stress | 5,000.00 | 211,876.47 | 288.92 |

单笔risk0.0025、total0.02、margin0.25、buffer1.10、0.25N止损、原费用/滑点不变。模型均原52/Ridge(alpha1)与原scaler，不新训或调整。

416独立107项只读核验及一次原定义对照完成，remainingP0/P1/P2=0。原初审3项元数据/哈希假设失败保留：321规范串含尾换行；376更新engine_view实际仅改cutoff并附真实cutoff/sourceSHA/兼容说明，scope并未改，root先前“scope也改”旁注不成立。没有重跑107项、415或737整套数值，更没有重跑金融回测。

## 结果边界和后续

本轮新完整cash回测0、fit0、financialD0、new_state0；累计454fit/246cash及1旧partial不变。新增真实源日1、配对u步1、4个原账户的新资金提案封存；这些不是4本新回测。尚无D21事实，0position/0fill/0closed/0daily，实际费滑和realizedPnL均0；期末已观察权益仅初始100万元，收益、DD、Sharpe、胜率均N/A，不能制造0日绩效或宣称稳定高质量/极窄损加注资格。订单API/CTP/正式策略/邮件/launchd/Git均0改动。

已保存当前415四state、两原journal与真实T0/Tinit、模型/源779checkpoint等续接指针。下一步只补真正需要的u21/D22操作范围与当前状态续接，不能再次使用旧空态、重跑415或重新取u20。后续D21必须用真实观察的D事实结算，今晚不生成未来成交；下一日期collector/clock范围尚未完成，不声称永久日更或调度已安装。评价仍遵守375已固定同起点/双成本计划，不凭首日差异换模型或重训。

运行前及结束过拟合反思：历史多轮择题风险是；本步无按收益择参，加入的是冻结后新数据，操作偏差明确保留，不能抹掉历史选择风险。继续价值：固定两政策的真实新证据和结果有价值；旧史重复、COT净标量救参、当前加注无价值或无资格。完整高收益/低回撤/全市场高质量long/极窄损加注目标未达成。

[实际摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage417_first_forward_pair_decision/proposal_summary.json)；[最终root裁决](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage417_first_forward_pair_decision/decision.json)；[416独审](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage416_actual_pair_review/final_review_receipt.json)；[续接指针](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage417_first_forward_pair_decision/continuation_pointers.json)；[下一范围](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage417_first_forward_pair_decision/next_scope.json)。只更新本线LINE/registry，不追加根总账。
