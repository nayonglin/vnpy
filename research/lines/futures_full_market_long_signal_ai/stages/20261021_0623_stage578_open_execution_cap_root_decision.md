# Stage578 根决策：关闭固定开盘价格上限，历史研究无需等待当日日线

- line_id：futures_full_market_long_signal_ai；模式day；时间2026-10-21 06:23 CST。
- 分支codex/ai-training-data-expansion；非重要突破；独立全市场研究，不是正式C9月池对比或上线A/B。
- 结论：接受576独审的研究算术，否决577冻结的精确价格上限。原目标active，没有稳定高质量AI信号、极窄损加注或真实执行资格的新增证明。

## 为什么不需要等今天日线

只有原独立前向账需要在锁定信号之后，等待对应D交易日完成，再读取真实完整日线评价全天路径；未完成D不能当全天结果。当前575历史对比固定截至2026-10-16的既有样本，不依赖2026-10-21日线。不能把前向账外部时钟表述为全市场研究阻塞，也不为继续研究提前结算前向账。

## 调研与判断

本轮先核旧015/018突破等待、079预算过滤和299历史reopening负结论。参考[原作者Foucault的限价选择研究](https://www.sciencedirect.com/science/article/pii/S1386418198000123)与[vn.py维护者bar撮合实现](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)：限制成交可能交换价格与不成交成本，不能先验认定‘不追高’有alpha。本次没有使用D.low等待成交，也没有把原填价截到上限。实证四组胜率均提高而收益均下降，说明胜率不是账户机会质量的充分指标；不能用节省滑点或少数被挡亏单代替完整账户比较。

相邻资料570—573也已关闭：期权price-skew不是新源，普通VWAP与旧settlement路线重合，CFFEX金额/V字段已在066考虑并约定失败后不追加turnover救参。没有为其新增全量下载/大H5扫描/拟合。

## 变更与固定参数

新增575隔离runner、kernel、7个必要合成fixture；原131/157策略源码不改。唯一策略变更：原执行报价有效且qty>0之后，仅原BUY含不利滑点和tick舍入填价<=同选中epoch的u.close才能进入。超价当日取消；旧unknown/qty0优先，同D不重分，未来按C自己的权益与仓位使用原预算公式。通过者成交价、原raw Dopen−0.25N初损、退出、K、选月和信号不改。

新增参数：无数值调优；固定比较关系<=u.close是一项结构选择，并非无过拟合豁免。修改参数：无；删除参数：无。窗口2020-01-01起、2023-01-01冷启动，各到2026-10-16、base/stress；本金100万、单family风险0.25%、总风险2%、缓冲保证金上限25%、buffer1.10、成交量参与1%，其余原157。

四本A是157自身VOLUNTARY_RESELECT账，直接复用；不是157内的旧baseline_books，也不是正式生产业绩。新C恰4cash/0fit/0SQL/0下载/0A回放。actual共2启动1完成：run1在已验收157的metadata续接状态断言处退出，0账户；仅适配该已知状态后run2 3.984267秒完成，失败证据保留。

## 完整指标

闭合交易次数与BUY/SELL成交记录数分开；胜率按已闭合净损益。

| 窗口 | 成本 | 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点CNY | 闭合交易 | 胜率 | 成交记录 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020起点 | base | A原研究账复用 | 2,229,270.22 | 122.927022% | -15.627420% | 0.978453 | 140,259.04 | 1295 | 12.2008% | 2592 |
| 2020起点 | base | C价格上限 | 1,592,408.39 | 59.240839% | -13.998160% | 0.777480 | 65,053.27 | 716 | 14.9441% | 1433 |
| 2020起点 | stress | A原研究账复用 | 1,528,419.71 | 52.841971% | -11.359301% | 0.787447 | 167,960.05 | 952 | 12.0798% | 1912 |
| 2020起点 | stress | C价格上限 | 1,421,955.12 | 42.195512% | -14.910754% | 0.792839 | 89,632.22 | 528 | 13.2576% | 1057 |
| 2023冷启动 | base | A原研究账复用 | 1,825,436.55 | 82.543655% | -9.902149% | 1.320956 | 53,623.57 | 494 | 12.9555% | 990 |
| 2023冷启动 | base | C价格上限 | 1,637,474.19 | 63.747419% | -6.079820% | 1.422460 | 30,541.07 | 289 | 15.5709% | 579 |
| 2023冷启动 | stress | A原研究账复用 | 1,526,645.82 | 52.664582% | -6.422761% | 1.223020 | 83,952.08 | 422 | 13.0332% | 849 |
| 2023冷启动 | stress | C价格上限 | 1,525,384.58 | 52.538458% | -5.585914% | 1.507496 | 49,403.63 | 247 | 15.3846% | 495 |

## 配对比较与事前门

DD差为C−A，正值表示更浅；CI是配对日log增长差，不是账户总收益的置信区间。沿用原固定252源日块、2000draw/组，共8000draw，不重抽indices。

| 窗口 | 成本 | 收益差 | DD差 | 日log差95%CI | C超价取消 |
| --- | --- | ---: | ---: | --- | ---: |
| primary_2020 | base | -63.686183pp | +1.629259pp | [-0.0003820593, -0.0000355691] | 953 |
| primary_2020 | stress | -10.646459pp | -3.551453pp | [-0.0001375825, 0.0000541394] | 761 |
| cold_2023 | base | -18.796237pp | +3.822329pp | [-0.0002868879, 0.0000673991] | 384 |
| cold_2023 | stress | -0.126124pp | +0.836848pp | [-0.0000979792, 0.0001010703] | 341 |

四C自身正收益，但四收益全低A；primary2020stress收益少10.646459pp且DD更深3.551453pp，主CI跨0。primary2020base CI全部为负。事前收益、回撤、主CI门均false，continuation_gate=unsupported。不得改裸open、反符号、close±ATR、窗口、品种、stop或risk救本规则。

参与路径不是静态删单：2020base A-only/common/C-only=804/493/224，stress590/364/165；2023base293/203/87，stress254/170/78。C-only源于后续自己的现金/持仓路径；不是同D取消后重新分配。没有将A-only事后PnL直接相加归因。base/stress滑点不同，因此通过集合可以不同。

## 独审与置信边界

576独立审查全部4新账、预算与原生报价/cap、fills/positions/closed/open/daily/capacity、BUY身份重叠和固定比较/CI。research_arithmetic_accepted=true，Critical0/Important0/Minor1。唯一minor是四summary未单列unknown_capacity_fills，完整capacity审计与unknown标志已经存在，不为此微调作者或重跑。

独审首次因自身event_id索引适配未完成，恢复run2核完四本；其后Categorical/比较字段适配在同RAM续尾段，未重核四本。原始cache/mothers/signals累计各读2次，无第三次全读，0策略/A/模型重放。详细恢复见acceptance/review receipt，不隐藏失败，也不把审查器失败说成策略数据错误。

四C期末各1开放仓，虽然期末stale0，2020base/stress历史stale仍6/5日，四账执行/容量unknown均保留。静态经济规格、日线条件报价与收盘估值不是券商真实结算；按Dopen+slip研究报价决定是否买入，也未证明观察开盘BBO后仍能按同拍成交。因此接受研究算术不等于真实交易、生产或加注资格。

## 输出与下一步

- [四组比较](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/comparisons.csv.gz)、[八组汇总](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/account_summaries.csv.gz)、[全年切片](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/annual_slices.csv.gz)。年度切片不是逐年独立冷启动。
- [全family-year含零](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/family_year_including_zero.csv.gz)、[cap审计](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/cap_audit.csv.gz)、[参与身份](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage575_open_execution_cap/actual_run2/BUY_identity_overlap.csv.gz)。四C完整账户账本见actual manifest。
- [独审接受摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage576_open_cap_independent_review/actual_run2/acceptance_summary.json)、[独审receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage576_open_cap_independent_review/actual_run2/review_receipt.json)、[机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage578_open_execution_cap_root_decision/decision.json)。

关闭这个精确cap，不再调阈值。下一轮仍围绕全市场机会区分的新信息或实质不同机制，先查已有负结论再冻结小对照；不立即扫另一个cap。新的前向样本自然积累，与历史研究并行，历史研究无需等待今天日线。本day版本到此结案，目标保持active。

## 前后反思

运行前是否存在过拟合风险：是，同一历史上持续择题；新增收益后调参：否。运行后风险仍是，没有因四组胜率好看挑一组宣称突破；预先冻结失败门用于停止该cap，不提供新泛化证明。

运行前有价值继续一次：是，单项执行干预可证伪且无需新数据/模型。运行后继续该cap：否；继续原全市场高质量long目标：是。累计535实际fit/282完成cash及1旧partial；本轮新增0fit/4cash。LINE/registry更新，普通失败不追加根memory.md/back_log.md，不动正式代码/生产/CTP/邮件/调度，不commit/push。
