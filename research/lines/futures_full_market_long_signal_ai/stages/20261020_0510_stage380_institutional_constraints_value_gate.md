# Stage380 制度约束新观测的有界价值审查

- line_id：`futures_full_market_long_signal_ai`；整理：2026-10-20 05:10 CST。非重要突破、非正式C9 A/B；没有新策略实现或回测。
- 上一goal turn为progress：单次373训练、375冻结、378独立空态确已完成。本阶段先实读registry/378 scope及当前UTC时钟；20日05:05仍早于15:15完整日线窗口。没有已确认运行中的市场采集句柄，因此不能把当前状况称为verified wait或启动另一采集进程。
- 本阶段只审一个尚未实际测试的经济对象：**交易所发布的保证金、涨跌停和交易限额调整通知**。它不是更改研究风险小数，也不把旧静态vendor margin当新信息。最终裁决：**当前不为“制度调整→高质量做多/加注”直接包投入actual；0fit/0cash。** 这不是历史回测证伪，更不否定所有制度信息的价值。

## 网上与GitHub核验

1. [Abruzzo与Park原研究，Federal Reserve公开版](https://www.federalreserve.gov/econresdata/feds/2014/files/201486pap.pdf)及[作者摘要页](https://www.federalreserve.gov/econres/feds/an-empirical-analysis-of-futures-margin-changes-determinants-and-policy-implications.htm)：研究CME保证金的决定因素，发现保证金对波动上升的反应与对波动下降的反应不对称，并讨论顺周期/竞争因素。它不是中国期货long信号研究，也没有证明保证金提高就该做空、降低就该做多。
2. [上期所2026-01-15锡通知](https://www.shfe.com.cn/publicnotice/notice/202601/t20260115_830107.html)：同一通知同时调整涨跌停、套保/一般持仓保证金及日内开仓限额；前两类从当日收盘结算生效，限额针对次交易日、含当晚夜盘。网页显示发布日期，不能仅据日期断言本策略某个日内时刻已经收到。该单例证明制度约束确实发生变化，不证明全史覆盖、同一影响方向或价格未吸收。
3. [AKShare维护者期货文档](https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md)：`futures_settle`列出按交易所/日期取得结算参数，含保证金、费用和限制字段，当前文档明确不含DCE。它提供潜在线索，未证明六所连续历史、原公告可知时刻、交易所与券商标准相等或按次日适用的精确单位。没有安装/执行SDK或调用该数据接口。

共核4个正文对象（同论文摘要与PDF分别读取），另有限搜索/定位；没有将搜索结果摘要当作已验证历史数据。没有下载交易原表、批量公告或行情，没有探多个年月来找能跑的样本。

## 为什么本轮不直接训练

**新增观测成立，新增可利用预测尚不成立。** 官方规则变化不由当前52列唯一确定；但其发生常响应既有市场波动、假期和合约生命周期。用变动后的保证金解释随后价格，必须区分已知波动、制度反应、真正未预期约束以及同时生效的限价/限量，不能把它们合成一个带固定long符号的scalar。

资金压力可迫使多头或空头缩仓，价格方向还依赖双方杠杆与持仓、其他合约替代和流动性。原研究提醒内生性，但不能据此证明中国市场永无增量。当前尚没有一项低自由度、事前可得且能与旧52/共同K比较的参与者暴露或“非预期制度冲击”定义；直接选方向、窗口、notice类别或品种会再增加研究员选择。

保证金与费用历史可能提高承载估算的真实性，这与识别超高质量多头是两个不同命题。当前359/375共同观察成本/风险已固定；没有核到一个足以推翻其已声明研究假设的具体错误，不为此重跑原资金曲线、改新旧模型比较口径或展开六所参数补齐工程。若以后出现一份可用的明确对象，应独立说明其用途、来源覆盖与因果时间，再决定是否值得研究，不永久封禁。

## 当前下一行动与未达成事项

378原范围不变：今天15:15后且21:00前唯一361完整日线批次，随后362独审/363接受。实际文件出来后才能最小恢复同一composed与旧baseline自身context，两个模型分别产生新的完整资金proposal；当前没有真实future评分、金融结果或E2E ready声明。未到窗口不轮询形成中日线，不重训、不跑旧史、不新增接线工程。

本阶段不将普通“等待某个时刻”称为已运行采集任务，也不以一份价值报告替代目标收益证明。完整全市场long高收益/低回撤、极窄损与加注仍未达到；现有资本状态为空、模型身份和小接口正确并不能满足这些要求。

## 记录与反思

- 实现/科学参数/回测结果新增、修改、删除均0；新fit/cash/市场API/SQL/分钟/大数据/测试/Git均0。累计454完整fit/246cash及1旧金融partial不变。
- 本阶段期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全N/A；没有新alpha、执行、加注或生产资格。
- 开始与结束新增收益调参过拟合：否；同史适应性择题风险仍是。继续本直接制度long包：否，有限资料未形成足够强的可实施命题；继续完整目标及真正新证据评价：是。
- 研究线由root更新LINE/registry；不追加根memory/back_log，不改正式版、生产、CTP、订单、邮件、调度或分支。

## 独立新机制审查与当前边界

379独立核了[NOAA业务GEFS登记](https://registry.opendata.aws/noaa-gefs/)、维护者格式文档及reforecast/版本说明，共4个正文。唯一对象是当时发布的农业产区降水预报更新，属于新观测；其当前NO-GO主要因为没有事前固定作物—产区—生育期/暴露及明确决策增量，不是因为必须让98产品都有天气值或强制严格vintage。实际业务预报历史覆盖/发布时间未查为unknown；后生成reforecast不能冒充当年发布。没有下载或调用数据接口，也没有因四页资料不足而宣称历史业务预报不存在。

[379全文](20261020_0508_stage379_new_observation_value_decision.md)和[小收据](../outputs/stage379_new_observation_value_decision/receipt.json)已由root实读。对制度对象的独立边界判断也不支持直接long符号；不把该意见写成金融反证。两项有限审查现在结束，不能靠不断制造低价值命题维持忙碌。

[root裁决](../outputs/stage380_institutional_constraints_value_gate/decision.json)与[下一范围](../outputs/stage380_institutional_constraints_value_gate/next_scope.json)保存本轮0actual及原378范围。到本轮结束，当前可实施下一步受真实市场时间约束：20日完整u输入尚未完成，另一个有支持的actual问题尚无。此前一轮有实际训练/初始化进展，故这是**首次在goal turn结束时到达该外部时间阻塞**，不是三次连续阻塞；goal保持active，不提前标blocked，也不假称已验证某个后台采集在运行。后续须实查当前时钟，15:15—21:00窗口打开即可推进原361；如果相同impasse连续出现三轮且无有价值替代，应按goal规则标blocked，不能无限状态复述。

后继状态，2026-10-20 05:12 CST：连续第二/第三轮均实查时钟仍早于完整日线窗口，0新实验证据、无已确认live采集句柄，不称verified wait；同一外部条件已满足3轮阻塞审计。`update_goal(status=blocked)`实际返回blocked，原返回保存在[goal_blocked_status.json](../outputs/stage380_institutional_constraints_value_gate/goal_blocked_status.json)，[连续审计](../outputs/stage380_institutional_constraints_value_gate/blocked_audit.json)保留3轮。该更新不代表目标完成、目标缩小或证明策略不可能；等待真实市场时间/新实物改变后再恢复。没有设置自动唤醒或后台采集，不继续制造状态报告/弱实验来维持active。
