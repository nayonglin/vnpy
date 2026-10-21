# Stage233：固定K单动作收益测量一次完成，待234独审

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 21:15 CST；非重要突破。
- 执行已冻230协议：13,556B SHA `ba46ca70fd2bc6387f0cd89d9c7bb7313283b1de38cc9893442487e7ec754f85`。源码准备阶段只新增工具、四项新tiny验证和小型源码/fixture收据，作者未打开实际动作/母表、NPZ、价格或X；随后由root唯一执行actual，真实结果见下节。没有模型、资金、SQL、下载或旧大文件hash。
- 开始过拟合风险是：同史适应性择题仍在；本轮新增收益调参否。继续价值有条件是：有限测量不同收益对象，不为新模型、加注或资金资格背书。

## 变化与固定接口

新增`tools/stage233_K_payoff_measurement.py`及`test_stage233_K_payoff_measurement.py`。原129动作仅一次49列流读、母表仅一次7身份、日历一次、132 NPZ一次五成员；仅14,254支持行做K点报价，闭合前缀直接复制原Y/PnL/clock token，K源缺行/invalid停止，成本不可报价仅影响对应scenario。原130/218主目标保持窄0.25N R，common2N仅单位核对。

新结果接口固定为68列`labels_K.csv.gz`、96列`K_quote_evidence.csv.gz`、16列`mothers_K.csv.gz`，gzip level1、float64原数值，不删unknown/nochild；小summary含全域/2020后及原year/family/product状态计数、已识别配对差/符号矩阵/绝对差分位、成熟支配覆盖。原unknown变known单列，不能把一手PnL合成账户收益。最多16个机械间隔quote anchors。Stage234已收到确切字段并独立实现，不需实际后适配宽表。

base/stress各自trade known/state/clock，政策0只在非行动或已知取消时使用独立政策clock；有trade结果不放入无cost的policy0字段。新K known phase保守`after_all_source_close`。单次K强平报价保留旧`exit_reason`和Kdue，新的price reason用`K_deadline_open`，不冒称与157资金reason逐字相同。

## 四项新行为RED/GREEN与源码绑定

唯一新tiny命令：`.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage233_K_payoff_measurement.py -v`。RED四项均因功能尚未实现产生断言失败；随后GREEN四项全部通过，exit0，unittest 0.010s。覆盖精确复制/cancel/完整母体及身份冲突、K开盘优先与两腿费用/clock/点映射、base可quote而stress不可quote、unknown-before/on/after与pending/blocked政策。fixturefit=0，旧suite=0；不为此跑全仓库旧测试。

| 源/收据 | bytes | SHA256 |
| --- | ---: | --- |
| `tools/stage233_K_payoff_measurement.py` | 25686 | `cc4bac7a67ca41254ea88a2afb22d665ada6a796ace82d23e204989b1971dfee` |
| `tools/test_stage233_K_payoff_measurement.py` | 7293 | `34aaa417ec7777bd237a05b5bf6be96dfdf5b3c1c40faa2cfcaff62c22d8485a` |
| `outputs/stage233_K_payoff_measurement/implementation/source_bundle.json` | 1459 | `42556b65135e038cc75fb2018de5de2d34ca02a6e05ca46090c6ce609d729902` |
| `outputs/stage233_K_payoff_measurement/implementation/fixture_terminal.json` | 6085 | `07c50419266afd420038d41b688fb47c771882e9ad8dae6afab9615c5cab4139` |

bundle仅233工具/新tests及已接受227/156/042小源码。未修改旧工具。232中容易误解的“模型原common2N目标”已按root指示纠正为“辅助口径，非130/218目标”。

## 后续唯一入口与状态

root在234精确源码prepass后签授权，唯一CLI：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage233_K_payoff_measurement.py --actual --authorization <absolute_root_auth.json> --authorization-sha256 <sha> --output <fresh_absolute_actual_run1>
```

授权schema=`stage230_exact_root_authorization_v1`，stage=`measurement`，`authorized_by=root`、`exact_source_authorized=true`、精确230 SHA、绝对output及精确source_bundle。源码不接受无精确授权的actual；fresh目录已存在就拒绝，不自动恢复/重试。作者未启动actual；以下补记root唯一实际运行的终态与小型汇总，独立算术接受仍待234最终收据。

## root唯一actual结果补记（2026-10-19 21:18 CST）

root session80769，21:16:46启动、21:18:29完成，terminal=`completed`，102.757480875秒；root报告进程exit0、实际manifest SHA `f028bdb67d5db85c4202fb92a9fe328ed020e30d7c3ee2707db2fa9ea3a1686e`。本文仅实读actual的737B terminal、611,602B summary、6,753B source_read_receipt补记，没有读取新大输出或重跑actual。234独审root session96437仍运行中，本记录暂不签发独立接受，最终裁决由root235负责。

真实I/O计数：129动作1次49列流、母表1次7身份、calendar1次、132 NPZ打开1次/5成员。旧227投影、经济投影、六traincache、X、模型/分数/选择/现金、SQL、网络下载、旧大输入hash、fit、cash全部0。actions/mothers/cache前后stat逐项相同，accepted大SHA继承且未重hash。

全部1,552,456动作、399,252母体和186,400无child母体完整；2020后966,740动作、161,014母体、44,788无child。primary/timing/calendar计数与227全部一致。全期主域706,910、K新报价14,254；2020后主域483,648、K新报价9,760。两cost全部K支持行均可报价，本次实际未发生单cost不可报价；原unknown-before/on及pending/intent仍保持null。

| 范围 | 每cost新known trade | 每cost未知trade | 政策不行动0 | 原closed-before逐token复制 | 原unknown/open新增known |
| --- | ---: | ---: | ---: | ---: | ---: |
| 全期 | 687732 | 2710 | 862014 | 673478 | 744 |
| 2020后 | 470643 | 2545 | 493552 | 460883 | 691 |

政策0含非主域不行动和主域已知取消，不是tradeY=0；全期主域取消16,468、2020后10,460。新增known全期744=682原unknown-after+62原open-K-reached；2020后691=629+62，不能为这些行捏造旧Y或配对差。

下表只使用原closed-primary且新known的已识别配对，主单位始终原窄0.25N R；分位数覆盖全部该配对域，p50/p90两cost各范围均0，不按非零子集替换分母。changed按冻结相对容差定义，不等于alpha。

| 范围/成本 | 已识别配对 | 数值改变 | 负→正 | 正→负 | abs差p99 R | abs差max R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 全期 base | 686988 | 12908 | 3977 | 31 | 4.4154862454 | 249.2279981275 |
| 全期 stress | 686988 | 12908 | 3787 | 97 | 4.4146030598 | 249.1781475428 |
| 2020后 base | 469952 | 8709 | 2845 | 15 | 4.3943446388 | 150.8895823458 |
| 2020后 stress | 469952 | 8709 | 2721 | 45 | 4.3934656820 | 150.8594014112 |

全期原closed-primary 686,988/686,988两cost均新known，2020后469,952/469,952；两范围/两cost的成本未知和新known-clock晚于旧closed-clock计数均0。该全域stress覆盖可以支持将来讨论旧训练子集的报价/成熟必要条件，不能替代六traincache身份、共同域、原权重或scaler资格，当前没有读六cache或批准新训练。

实际新增的是收益对象/状态差异证据：K单动作目标与旧firstexit确有数值及符号差别，2%支持并非全部数值不变；这仍不证明可预测性、旧模型bug、历史资金亏损根因、策略alpha或账户收益改善。没有重训、重新选择、重放旧现金或直接累加一手PnL。大R差受原窄分母放大，不能拿最大值证明加注资格。

新增/修改/删除策略参数0，实际回测结果新增/修改/删除0。权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A；累计433fit/234cash不变。不改LINE/registry/其他线、正式版、生产或Git。

调研与判断继承本轮232实际核得的SPO原文与作者GitHub：应区分预测对象和下游决策对象，不能将K单动作结果当账户目标或直接上SPO；未装外部库。结束过拟合风险仍是历史适应性择题，本轮未按收益救参；唯一有限测量已有对象差异证据，等待234独审及root235裁决有价值；重复运行本测量或立即训练/资金无授权也无新增资格。
