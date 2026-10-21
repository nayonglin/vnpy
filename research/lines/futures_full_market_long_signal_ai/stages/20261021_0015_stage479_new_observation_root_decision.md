# Stage479：去重后取得FOMC新观测，有限接受来源而非训练资格

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 00:15 CST；非重要突破。上一goal轮为progress（473年度实验真实完成并否决）；本轮也是progress（新作者数据实际取得及独立源审），没有新收益成果。完整全六所98历史产品/95家族高质量long、窄损/加注目标保持active、未达成。

## 当前结论

接受作者同一固定commit的原始事件表及来源/日期/缺失算术，不接受训练/PIT/alpha资格。当前385事件，1987-11-04到2026-09-16；FF4×SP500联合326，2010后141事件中138，2020后59中57。SP500FUT联合329/140/58只是覆盖披露，不自动替换缺失SP500。时间戳重复0，同日双事件8组保持各自事件身份，不能合并成一个或当作市场独立样本。

474排除了旧K标签、log、DOMAIN、annual时钟等换名重训；475说明精确source-day runway只是未显式身份表示、还涉及未来交易日历当时可知性，当前不做大投影/fit。root另核basis-momentum原论文及原GitHubnotebooks：月度滚动两曲线策略不同于本短期全市场目标，本轮不照搬模型或挑窗口。唯一优先观测是FOMC公告的利率/权益联合意外，不是旧FX回报或共同宏观veto。

## 实际执行与独立审查

476 JSON协议2922B/SHA7abe9a13…a1225b在真实请求前冻结。477唯一session91694 exit0，5.586753秒，GitHub commit API1次及两immutable raw文件各1次，3/3 HTTP200/0retry；不是下载分钟行情。commit`f788aef7d573f87f28b70ffc3763e73c4886a53f`（2026-10-11更新），原CSV69885B/SHA785cb0ac…443300及README5183B/SHA5b57b02f…35416c2完整保留。最初列名启发式未识别start，输出日期资格null而非伪通过；没有重跑捕获。

478独立三小body各一次，385行start显式解析、6160格=5644finite+516empty、绑定/年度/联合覆盖算术已核，来源及数值剩余问题0/0/0。独审0网络/marketinputs/fit/cash/SQL，没有第二次全市场大表审计。root核最终小收据和绑定，接受此有限对象。[478独审](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0011_stage478_fomc_original_source_independent_review.md)；receipt SHA c61240ddd05bbf8b73d3410c07fff2d7ccf6b7de1490f7836c0aaeacb46aabdf。

480仅两固定官方锚：2025-06-18 14:00 EDT对应上海06-19 02:00，+25h到06-20 03:00；2025-12-10 14:00 EST对应上海12-11 03:00，+25h到12-12 04:00。两个例子支持纽约/DST解释，**不证明全部385行或历史首发时刻**。详见[480锚点记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0010_stage480_fomc_timezone_two_anchors.md)。两锚独立于478来源算术，不重复获取作者原件。

## 未解决项与有限下一步

rawFF4完整单位/正号、全部start时区仍未有明确规范；作者main.m只将FF4列在“Interest rate surprises”中，不能直接把final pc1单位倒推raw或宣称FF4正值就是可交易紧缩。作者post测量窗可额外延24h，因此后继至少t+25h覆盖已知测量风险；它不是供应商接收/作者发布证明。现Github版本只能支持带限制历史研究，不是逐u首发PIT。

下一只做**一次有限主源定义核证**（最多2个作者代码/定义小文件，复用原论文），不换FF4/另一央行/BVAR或缩短延迟。若关键定义仍不明，关闭这个具体规格；不连续微修或扩库。若能支持，才另冻结一个延迟入场后的异质事件质量反证：需事前可观察暴露，继承270共同macro scalar不能区分同日月份/品种的限制；不能把公告至入场前gap记作可赚收益，不从已选/已赢/已闭样本起步。当前没有新fit/cash授权，后继预算与一次独立审查另定。

## 调研与反思

[AEA原论文](https://www.aeaweb.org/articles?id=10.1257/mac.20180090)和[作者数据定义](https://github.com/marekjarocinski/jkshocks_update_fed/blob/f788aef7d573f87f28b70ffc3763e73c4886a53f/README.md)支持该独立观测及窗口边界，不证明中国全市场延迟收益。[原GitHub曲线研究](https://github.com/rolling-panda-san/notebooks)依赖私有vivace，不是可直接拿来复验的全市场引擎。本轮判断：新观测具有一次可否决研究价值，源接收不能当收益突破，不能承诺它必有用。

新增/修改/删除策略参数/模型/止损/资金参数及回测结果均0；收益、权益、DD、Sharpe、滑点、交易数、胜率N/A。累计481fit/258完成cash及1旧partial不变。开始/结束新增按本成绩调参过拟合否；同史长期反复择题风险是；继续救旧annual/目标包否，继续一次新事件信息反证有条件的是。原四前瞻账户未改，只有其真实D仍受外部时钟约束；历史研究无需等今日新日线。无正式/CTP/生产/邮件/launchd/Git操作，不写根memory/back_log。

决策：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage479_new_observation_root_decision/decision.json`；下一范围：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage479_new_observation_root_decision/next_scope.json`。
