# 原额度内赢家重复信号加仓：存在技术空间，尚未验证收益

记录时间：2026-10-21 07:17 CST。研究线`futures_full_market_long_signal_ai`，沿用`codex/ai-training-data-expansion`，独立于正式C9。不是重要突破；完整目标仍active。

## 结论

原AI再次选中已持有、按原费用模型净盈利的同一真实合约时，四个原A账户都有至少一手的**单候选乐观预算上界**。因此不能用“完全没有空间”否决机制，值得准备一次固定的资金对照。上界忽略普通订单竞争和旧仓占用成交容量，不能当作真实新增C成交，更不能据此宣称提高收益或降低回撤。

唯一actual用时3.965550秒，0新训练/0新资金账户/0原A重放/0SQL/0行情下载。5项必要合成fixture已通过，root未重跑。独立审查唯一一次3.833194秒，3805项检查全部通过，剩余Critical/Important/Minor=0/0/0；覆盖完整候选集合、原窗口/cutoff、净利润、原F0、预算/费用/手数、未知与所有统计，不只检查摘要。

## 实际核算

| 原A账户窗口 | 成本 | 同epoch重复 | 净盈利有效 | 正一手上界 | 零上界 | 未知 | 正界涉及原持仓root | 月份 | 家族 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020 | base | 1191 | 1095 | 686 | 409 | 8 | 204 | 46 | 39 |
| primary_2020 | stress | 812 | 723 | 479 | 244 | 3 | 142 | 39 | 31 |
| cold_2023 | base | 417 | 379 | 178 | 201 | 0 | 63 | 17 | 16 |
| cold_2023 | stress | 345 | 303 | 137 | 166 | 0 | 52 | 16 | 15 |

总候选4485条，其中正界1480、零界1020、已知排除1974、未知11。四账户跨成本和冷启动会重叠；同一持仓跨多个u也会重复，不能把1480当作独立样本、交易数或可累计加仓手数。distinct root也不是统计独立性的证明。

| 窗口/成本 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026至10月16日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020 / base | 31 | 181 | 265 | 24 | 7 | 9 | 169 |
| primary_2020 / stress | 32 | 130 | 183 | 10 | 7 | 11 | 106 |
| cold_2023 / base | — | — | — | 6 | 7 | 18 | 147 |
| cold_2023 / stress | — | — | — | 13 | 7 | 11 | 106 |

2023冷启动base有147/178=82.58%的正界行位于2026，stress有106/137=77.37%；对应2026原持仓root为50/38。近期集中、重复信号和早期稀疏限制置信度，不能据此称为穿越周期。11条未知均为其他持仓的陈旧估值可能影响权益/预算；不补成零、不修旧账、不把它们当已知拒单。所有原A账户原有execution_unknown/capacity unknown仍保留；cold账户本轮未知0也不等于真实执行已知。

## 固定口径与代码变化

- 输入：原157四个OWN A账本，2020-01-02/2023-01-03各自起到2026-10-16；完整缓存signals和原经济投影。范围98产品ID/95家族，无行情DCE.S不删除。没有重新回放A或扩大分钟工程。
- 原organize及家族winner优先级先执行，再与已持有epoch相交；不先筛同epoch再选次优。2020账户完整跨2020/2023两训练模型，逐u核原cutoff_for；2023账户自然只用2023模型。
- 剩余净利润按剩余qty减原BUY每手费和u不利SELL费，滑点已在fill中，不重复扣或重复加浮盈。F0仍是原入场每手风险×剩余qty，不因盈利或止损上移而释放。
- 原家族风险0.25%权益、组合2%、保证金25%、buffer1.1及窄止损0.25N不变。每个add分别用剩余家族/组合风险和buffered margin计算乐观上界，再按原lot/容量向下取整。保证金分母不误加fee，不用未来D价格或退出回收预算。
- 若以后要用全零上界证明模型路径恒等，新增不足一手请求必须在共同batch/预留/任何状态影响之前剔除，防止零手请求仍挤出普通订单。本次已有正界，不能签恒等或免cash证明。
- 新增589独立脚本和5项必要fixture；原策略源码/参数无修改，无参数扫描、无删除旧结果。592v1的固定cutoff漏域在收益/actual前被源码追踪发现，v2修正；v1保留，唯一actual按v2完成，没有因此重跑。

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易数、胜率：**本轮均N/A**，因为没有新资金回测，未改写原A财务结果。累计仍为547实际模型fit、282完成cash及1旧partial。

## 调研判断与下一步

[原Turtle发布页](https://www.tradingblox.com/originalturtles/originalturtlerules.htm)和[vn.py维护实现](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/strategies/turtle_signal_strategy.py)说明加仓与仓位/止损联动。未声称读完原PDF或照搬其0.5ATR/四单位/2ATR参数包；已有传统机制不是本策略增益证据。我的判断：当前支持一次原额度内新批次机制反证，不支持直接提高风险或倍投。

接下来依据595草案冻结一个C：用C自己的权益/持仓决定加仓；fresh原请求和add剩余额度共享原batch缩放；各批次独立原成本/SL0/F0/退出。D时序固定开盘已知退出→冻结开盘订单→日内止损→收盘，禁止用Dlow取消更早的开盘add，旧新批次共用gross容量。原四A直接复用；至多4个C资金账户，无新模型；保留完整年份和压力成本，不扫描利润R、间隔、次数、年份/品种黑名单、风险或止损救参。实际执行必须另有冻结协议及独立全账审查，本记录未授权cash。

运行前与运行后：新增结果选参过拟合均否；本轮只作原预算必要界，没有借未来盈亏调规则。**同一历史反复择题的过拟合风险仍高**，集中与依赖进一步限制置信度。继续本机制是，理由只是一手空间已存在、值得一次固定反证；继续全市场高质量做多、更高收益更低回撤、窄损与加注完整目标是，收益和生存资格仍未证明。历史研究不等待当日日线，原封存前瞻验证单独等待真实日线结算。

## 可复核输出

- [逐候选上界](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage589_winner_addition_preflight/actual_run1/candidate_bounds.csv.gz)
- [原核算汇总](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage589_winner_addition_preflight/actual_run1/support_summary.json)
- [独立验收摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage593_winner_addition_preflight_review/actual_run1/acceptance_summary.json)
- [独立实际收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage593_winner_addition_preflight_review/actual_run1/review_receipt.json)
- [冻结v2协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage592_winner_addition_upper_bound_protocol/protocol_v2.json)
- [多批次执行草案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0715_stage595_multi_root_implementation_contract_draft.md)
- [root裁决](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage594_winner_addition_upper_bound_root_decision/decision.json)
