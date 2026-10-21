# Stage352：元数据接纳、名义交割身份与新样本时钟结论

- 时间：2026-10-20 04:10 CST；研究线 `futures_full_market_long_signal_ai`，分支 `codex/ai-training-data-expansion`。
- 上一goal turn为progress（345新日增量已接纳）；本轮也是progress（新增9字段实证/80当前身份/具体日期候选改变下一行动）。原全市场超高质量做多、高收益低回撤及窄损加注目标active、尚未达成；本次不是alpha突破。

## 改动和实际接收

沿345/347，仅新增348quote元数据接收、353纯日期展开及354最薄离线调用；模型、52维设计、scaler、选约、K、止损、风险及预算公式均没有新增/修改/删除参数。没有重新训练或运行资金回测。

351唯一实际session10097，连接显式TqSim、public coroutine内一次get_quote_list取得874 refs，35秒元数据窗口、总网络43.1025秒、关闭成功，无重试。原终态exit1/partial如实保留。874合约的身份、日夜时段、delivery年月、expiry、tick共9字段均known；只有volume_multiple全部unknown，故all-fields-ready为0。保存文件没有被拒原乘数值/type，不能断言具体是float或默认0，亦不能宣称账号权限失败。所需子集已足够日期展开，不为无关字段修源/重连。现有已接受经济参数继续按原来源，未知乘数不替换它们。

新增参数仅操作超时（critical82、connect40、metadata35、close8、网络最多90秒）与固定日期解释；无alpha参数改动。新增金融结果、修改和删除旧金融结果均为0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数和胜率均N/A。累计453fit/246cash及1此前金融partial不变；这次metadata partial不是新增金融尝试。

## 数据准确性与身份

349独审一次新metadata、小794显式map与journal来源：874返回身份匹配，794旧名义交割年月全部一致、0冲突。FU2611名义202611而expiry为2026-10-30，证明不能用到期年月代替合约名义月。乘数unknown及partial状态保留。

354只在离线使用该9字段子集，按delivery年月、原symbol数字后缀与既有身份交叉建立874条**当前身份观察**，含80条新增年月证据、0冲突。18条F后缀仍为L_F/PP_F/V_F独立域。新80只在本次实际接收时刻2026-10-20 04:01:37 CST以后被观察，不回写旧历史known、不自动取得价格、单位、经济或模型资格；model_input_eligible=False。

## 日期规则和窗口候选

调研依据[Tq业务对象文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html#tqsdk.objs.TradingTime)、[维护者源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/objs.py)、[上期所交易时间](https://www.shfe.com.cn/services/calenderandholidays/tradinghours/)及350有限原文。quote是周期模板，结合已接calendar与普通日锚形成operational_regular_schedule；不是穷举排除临时例外的交易所担保。25:00按夜盘锚日加25小时，19日夜盘锚16日、20日锚19日、21日锚20日。集合竞价另列，未改原执行open约定。

347建议中的国债09:15已过时。[T修订细则原文](https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf)与本次实际T模板相符：普通日09:30开、15:15收，股指同为09:30开而15:00收；最后交易日另有例外，未沿用错误硬编码。

354唯一离线执行exit0/0.16683秒，共2622条（874×3）。19/20日各870常规候选+4已到期；21日840常规+4已到期+30最后日未知。对原全部726评分输入汇总：

| u→D | 当前全部输入的最晚收盘 | 已知D最早执行open | 全域状态 |
|---|---|---|---|
| 19→20 | 19日15:15 | 19日21:00 | 726全常规候选 |
| 20→21 | 20日15:15 | 20日21:00 | D有13个最后日未知，strict=False |

这些是运营时钟候选；未把metadata receipt当价格完成或首次发布，也未接收新的已完成20日日线。当前source_completed_at/D_open_at正式输入仍未赋值，T0=None、forward0、activeFalse、账户未建。

349复用已留RAM，对2622日期字段与874身份独立算术核对全部0差；不二读原metadata，不重读旧价格/cache/经济，不导入作者函数复算。原partial、30/13未知和严格False均保留。

## 13个到期合约与未来时钟域

355独立只读344 compact一次确认：13在19日原资格全部为0，其中8先被生命周期挡、5先被历史不足/缺口挡；13的原生命周期边界均早于原D20。它们之中还有正分，故不能按正分或最终2赢家来裁剪时钟域。427只是19日原合格数，不是尚未取得的20日资格。

判断：源完成依赖全部实际评分/参考输入；未来D执行截止应在T0前显式规范为原事前合格全集加已有position/pending执行依赖，并在每个新u重算。这个规范可影响运行准入，不宣称所有执行路径等价。当前354按授权全726的strict=False保持原状，不偷偷改通过、不补造最后日时段。

## 反思和下一步

开始/结束均无收益反馈调参，不新增该类过拟合；长期同史适应性择题风险仍有。继续真实新样本有价值，来源工程本身没有证明稳定alpha或窄损加注。原目标保持完整，不以本次小范围通过宣告完成。

按[下一有限范围](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage352_metadata_and_clock_decision/next_scope.json)：核固定原模型运行依赖，T0前冻结上述时钟规范与真实UTC研究参考；准备一个能直接恢复精确日线日期并续checkpoint的薄接收流程，未来用3根日线区分重叠/新日/形成中，不再每天重复当前失败修复流程。20日完成前不抓形成中行情；普通日候选窗口为15:15以后、21:00以前，须按新u实际依赖确认，迟到保持迟到。不启动资金、生产、CTP或定时任务。

- [351原始终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage351_quote_metadata_actual/actual_batch001/terminal.json)
- [349来源子集接纳](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage349_quote_metadata_review/actual_receipt.json)
- [354独立日期/身份核对](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage349_quote_metadata_review/session_actual_receipt.json)
- [355独立时钟域判断](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_0408_stage355_input_and_execution_clock_domains.md)
- [结构化决定](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage352_metadata_and_clock_decision/decision.json)
