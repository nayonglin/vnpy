# Stage324：前瞻三个组件实现与独立审查结案，尚非端到端ready

- line_id `futures_full_market_long_signal_ai`；2026-10-20 03:03 CST；分支codex/ai-training-data-expansion。非重要收益突破，非正式A/B/C。
- 上一goal turn为progress：数值包失败现场、316路线审查和317318设计改变了本次动作；旧session65606已终态，无重新poll或启动。
- 本次实际改变：实现320因果核、321时钟记录、322连续状态桥；3组tiny GREEN、323独立静审core0。0新fit/真实cash/SQL/大表/真实价格，0旧控制重放；完整累计453fit/246cash及前包1未完成attempt不变。

[机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage324_minimum_forward_component_decision/decision.json)；[独立静审](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_0301_stage323_minimum_forward_static_review.md)；收据SHA `a342319dfe5dc08f407359979d0fb223c512656401e60e97bf8f52e8688ba8bb`。

## 本轮改动与验证

| 组件 | 已有实现 | 本轮验证 |
| --- | --- | --- |
| [320因果核](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage320_causal_forward_core.py) | 原own11/maturity13/2列成本几何、Wilder续接、固定main2023 scaler与26+26推断、原156/157选择及完整状态 | 1组/4子例GREEN，.223秒；未来追加不影响旧u、20/21根语义/缺失、母及pool、K pending原分支 |
| [321时钟记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage321_forward_journal.py) | u完成>T0与及时decision分开；当前UTC receipt、同key幂等、新版本追加、hash对象/链、拒静默修复 | 1组GREEN，.005秒；晚取/迟到/未知/时区、修订与对象/断尾损坏 |
| [322连续状态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage322_continuous_paper_state.py) | 原131 prepare显式closure封存，D前重核自状态预算/econ，原D代码推进；JSON恢复/容量/insolvent连续 | 1组GREEN，.249秒；两session与原小合成路径一致、base/stress独立、缺价/恢复/重复D/到期哨兵 |

全部按新测试先RED再最小实现；根321增加删除对象回归先见RED后修，322有两次本地code身份序列化诊断异常后改稳定字段fingerprint，均已披露，不是实际金融尝试。没有跑旧suite。322的8次真核调用只用合成价格/fixture，不能计为8本真实回测或公布其金额为策略收益。

新增代码/测试6文件，原070/131/129/130/156/157等源码未修改。新增的只有计算/时钟/状态接口，模型、特征、threshold、止损、预算、费滑策略参数0新增/修改/删除；不使用已关闭312整数分配器。

## 三项重要实现边界

1. 原模型是26 raw+26missing flags，raw合法缺失不构成新资格门，推断沿原scaler，无fit。own11 SMA20TR与资金/标签N的Wilder20不混。旧epoch缺u bar不能carry报价；用有原索引的array前缀或明确unknown输入。
2. source lifecycle/K target在entry保留到position；原有限calendar的len哨兵只作pending表示，不能扩历后当真到期而无故一天平仓。322只将已封target按追加calendar重新解析，pending暂存远于nextsession的索引，并明确非真实K；不改已封目标日期或策略。
3. 321给定时钟关系可核，本地recorded_at不是交易所首发证明；320调用者仍须提供当时可得的calendar/经济/数据版本。NaN入journal须显式转null并留mask/状态。322 singleton summary不作连续绩效；真实累计账来自持久state。

323一次读最终6源码/测试、3 tiny终态和小refs，无开放P0/P1/P2，无新测试组/重跑/实际市场读数。它证明静态计算边界和合成证据可接受，**没有验证真实接收、真实warmup、真实时钟、完整generator调用链或收益**。所有最终binding已逐一核过，本报告不再铺旧94依赖/模型训练资格。

## 下一步：一次真实历史日接线演练

[next_scope](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage324_minimum_forward_component_decision/next_scope.json)已由root限定：使用已接受132cache末日2026-10-16及原317模型，做一个真实历史日的最小caller/输入接线；不是新金融实验。cache/经济投影各至多加载一次，必要时只一次本地只读同日数据SELECT补closeOI/quality（schema只读），不读旧训练/score/label/actions巨表，不重跑四控制，不推进真实D收益。完整98父域、缺失及所知新catalog unsupported保留。

先取得current-u全部anchor references再推进既有sealed D状态，自己预算/时钟通过才seal下一D；初次历史演练不初始化真实forward账。真实来源与接收时点、warmup及caller均完成后才另签不可变T0。现在T0=None、forward观察0，真实receiver尚未绑定；晚取2026-10-19也不会变前瞻。

## 调研与开始/结束反思

本轮复核[scikit-learn官方common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)及[Freqtrade维护者GitHub](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)。前者支持固定训练预处理和列语义，后者支持未来追加不改变过去输出的因果检验。未安装框架/升级环境；这些材料不证明本期货AI alpha。

开始：本轮新增寻优否，既有模型历史择题风险仍是；补最小因果和时钟链有价值，因为后续必须能产生新证据。结束：未按实际收益调参，仍未证明高质量long或更高收益更低DD；三个组件实现有价值，下一步一次真实历史接线也有价值，不能将tiny/static绿色当完成目标。

本阶段无真实绩效，期末权益/收益/DD/Sharpe/费用/滑点/交易/净胜率均N/A。原正式策略、真实资本/加注/生产无本轮变动，用户完整目标active未完成。不追加根总账、不commit/push、不建调度。
