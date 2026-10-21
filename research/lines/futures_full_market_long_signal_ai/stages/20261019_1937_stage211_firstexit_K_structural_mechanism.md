# Stage211：原 first-exit 与固定 K 单信号价值的可识别机制

- line_id：`futures_full_market_long_signal_ai`；记录时间：`2026-10-19 19:37 CST`。
- 起点：已读取 `research/registry.md`、本线 `LINE.md` 和 Stage209。Stage208 对 q/53/Ridge/K 包的关闭保持；本文不重新解释或核算旧财务结果。
- 模式：只读现有规则源码，恰好两个合成手算例，一项最小投影设计；不是实现、历史投影、标签生成、模型或回测。
- 新 fit/cash/SQL/历史 labels/projection/大数据读取/行情下载/接受源改动均为 `0`；累计仍为 `427 fit / 230 cash`。本阶段没有调用现金引擎或新模型。
- 是否重要突破：否。得到的是规则允许的反序反例，尚未测量其历史支持、频度、预测价值或组合现金影响；正式 A/B、生产、加注均未授权。

## 先给判断

**原 first-exit stress R 与同一动作在固定 K 下的单信号价值并不恒等；即使入场、初始止损、成本、anchor 和正分门全部保持，也存在事前可行动域内的排序反转。** 下例不依赖新特征、正分门变化、整数手变化或未来筛样本。

这只反证“原目标的正确条件均值在任何固定 K 政策下都必然维持动作排序”这一普遍命题，**没有证明现有 Ridge 的历史失败由目标错位造成，也没有证明 K 标签能预测、能提高收益或值得立即重标训练**。现有 Stage129 原标签遵循其冻结定义，不据此判为 bug。

## 规则调研与直接证据

本阶段按 root 的只读边界，不重复联网或下载。公开方法背景沿用 [Stage209](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_1924_stage209_objective_alignment_proposal.md) 对 SPO 原论文、作者 GitHub 与 CME stop 说明的取舍：下游决策和预测目标应分开，但论文/代码不证明本线需要 SPO。本次新增判断直接来自以下现有源码：

| 规则 | 源码证据 | 对识别的约束 |
| --- | --- | --- |
| 日内退出和 stress 成本 | [Stage042](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage042_cross_session_experiment.py:126)，`price_exit_reference`、`fee_at/adverse_quote` | force 开盘优先，其次开盘 gap，最后盘中 low 触 stop；tick 向不利方向取整，滑点在成交价内 |
| 原单动作标签 | [Stage129](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:263) | u 资格与未来 participation/label 分开；D 缺价为未知，路径首个缺价停止完整标签，closed 在退出日 after_all_source_close 才成熟 |
| 原训练成熟条件 | [Stage130](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:60) | 原训练要求 eligible、closed、finite stress R、u 和 label_known_date 都严格早于 cutoff；不是完整意图域的自动无偏条件均值 |
| K 与完整池资格 | [Stage156](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage156_voluntary_choices.py:40)，及 [D<K 门](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage156_voluntary_choices.py:116) | 月前月首 source session；先按 D<K 过滤，再 parent 排名；K 不是成交筛选，也不是历史法定交割资格认证 |
| 生效边界 | [Stage157](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage157_voluntary_cash.py:59) | effective lifecycle = min(source lifecycle,K)；after-calendar K 不截到样本最后一天；source/voluntary/effective provenance 都保留 |
| 现金同日顺序与不变 anchor | [Stage131](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:124)，`anchor_request` | forced exit 先于 risk reduction/stop/entry；持有合约本来可以不同于 u 时 canonical anchor，之后按 current reference 与这个不变 anchor 比较 |

## 合成例一：同母、两月、所有目标均正，只有排序反转

这是合成产品 `P.X` 的规则反例，不代表真实品种规格或历史行情。给定 source calendar，`u=2020-02-20`、`D=2020-02-21`；同一 parent 的两个 child 为 A=`P.X.202004` 和 B=`P.X.202005`，共同 u canonical anchor 为 A。两者在 u 都 history-ready、经济信息已知、volume=`2,000`、round lot=`1`，所以 1% gross cap=`20`、entry roundtrip cap=`10`；比较合法最小量1手，没有账户资金竞争。

共有输入为：D.open=`100`，`N_u=4`，`low20_u=98`，初始 `SL0=100−0.25×4=99`，multiplier=`10`，tick=`0.1`。u 前至少20根 O/H/L/C=`100/102/98/100` 可以同时满足 N=4 与 low20=98；D 至原退出前少于20个 source session，保留旧98低点、每日 held low 大于99，可使期间没有 stop。后续 N 的改变不重设原始 SL0。

原 stress 规则为每侧 fee `max(6,fill×10×0.0003)=6`；slip=`max(reference×0.0003,3×0.1)=0.3`，且本例都落在 tick 上。共有 BUY fill=`100.3`、单侧 fee=`6`。R 分母仍是原 `0.25×N_u×multiplier=10` 元，未把预算中含费滑的 unit-risk 误作训练 R 分母。

规定 A 的 K 为 `2020-03-02`，B 的 K 为 `2020-04-01`，两者 **D<K**。u 的当前 calendar/名义月份已给定；这是反例的事前资格假设，不是本研究新增的真实 PIT 日历认证。anchor 到 `2020-03-09` 收盘才从 A 变为 B，故在原政策中两个动作均于 `2020-03-10` 开盘按同一 anchor-change 请求退出。初始持有 B≠anchor 不会立即退出，这是原131/129允许的规则。源 lifecycle 均晚于该日。

| child/目标 | 退出日与参考价 | SELL fill | 现金净 PnL/手 | stress R |
| --- | --- | ---: | ---: | ---: |
| A 原 first-exit | 03-10 anchor forced，O=110 | 109.7 | `(109.7−100.3)×10−12=82` | **8.2** |
| B 原 first-exit | 03-10 anchor forced，O=104 | 103.7 | `(103.7−100.3)×10−12=22` | **2.2** |
| A 固定 K | 03-02 voluntary forced，O=102 | 101.7 | `(101.7−100.3)×10−12=2` | **0.2** |
| B 固定 K | 原03-10退出早于自身04-01 K，因此仍O=104 | 103.7 | `22` | **2.2** |

原排序 `A>B`，同 K 政策价值排序 `B>A`；**四个值都严格正**，不靠更换 score>0 门制造反转。同一动作的 entry、SL0、low20 更新、经济参数、cost/rounding、anchor 和 R 分母在两政策间都相同，唯一不同是预声明 K 的额外退出。

这些未来值不是 u 可观测特征，也不能在真实选择时直接排序。逻辑上，给定这条完整价格路径的退化条件分布，潜在值即条件均值；因此连“原目标的完美条件均值预测器必然保序”也不是一般定理。但真实历史是否接近此分布、X 是否有预测力都没有被测量。实际 Ridge 还受到有限样本、成熟闭合条件和线性投影限制，不能将合成完美预测器当作130实际能力。

## 合成例二：同一退出/成熟日也可能有不同数值

仍用共有 entry=100、BUY fill=100.3、N=4、SL0=99、R分母10、stress每侧6元与0.3滑点。令 prev(K) 收盘后的 next boundary=`103`；K 日 `O=104,L=102`。这与20low真实更新规则相容：D 的 low=99.5，随后20个 source session 的 low 都为103；直到 prev(K) D 才移出20根窗口，boundary在其收盘更新为103，之前不会因103低点提前触103止损。

| 政策 | 同日优先分支 | 参考价/SELL fill | 净 PnL | stress R |
| --- | --- | --- | ---: | ---: |
| 原 first-exit | 无 force，O>103 且 L≤103，stop_boundary | 103 / 102.7 | 12元 | 1.2 |
| 固定 K | prev(K) 已请求 lifecycle/voluntary force，先按K开盘退出 | 104 / 103.7 | 22元 | 2.2 |

两者都在 K，沿标签约定都在 K 的 `after_all_source_close` 才视作 known；数值却不同。因此不能只改 `exit_index=min(old_exit_index,K)` 然后沿用旧 exit price、旧R或旧原因，也不能取 `min(old_R,K收盘R)`。K的真实模拟参考价是开盘，受缺价状态和既定优先级约束。

## K、gap、stop、boundary 的同日优先级

1. prev(K) 收盘若头寸仍有有效估值，先用该日 low20 设置下一日 boundary，再由 `next_day>=effective_lifecycle` 请求 `lifecycle_exit`；voluntary来源由157 sidecar说明。若前一日已经止损退出，K不会将其重新持有。
2. K 日 held quote 缺失先进入 stale/deferred，**不能虚构 K 开盘成交**。原现金引擎在以后观察到的开盘进行理想 deferred liquidation 并保留 unknown；原完整标签在首个路径缺价处停止known标签。这两种对象不得混称为真实已识别的同一个收益。
3. K 日有有效 quote 且已 force，则全量开盘退出，早于 risk/margin reduction 与 gap/stop。若 `O<=boundary`，无K时会是gap_stop，但同样参考O；K时的原因是forced。若 `O>boundary` 且 `L<=boundary`，无K时为盘中boundary，K时已在O退出，如例二。K不能被后出现的更有利或更不利 low 覆写。
4. 无 force 时，原顺序为先既定账户减仓，再 gap（O≤boundary），再 intraday stop（L≤boundary），最后收盘 mark 与下日请求。账户减仓属于组合现金状态，不能偷偷引入独立单动作价值。
5. D=K 或 D>K 的新动作已在 u 的K门被排除；在现金层再有 lifecycle gate。不能一边声称 D<K，一边在K开盘开新仓再退出；已有family当日退出后的重入也由原现金规则取消。

## 原标签较早、较晚与成熟训练域

在**同entry、完整有效日线、无账户反馈、K已知且能按K开盘建模退出**的严格子域内，额外K不会延长原退出日期；但这只是日期关系，不是收益单调关系。

| 情况 | 固定 K 的成熟关系 | 必须保留的区别 |
| --- | --- | --- |
| 原 first-exit 在 K 之前 | 同一个原退出和成熟日，不必等K | 若entry/cost/anchor相同，其trade R应相同；不是所有样本都需要重算路径 |
| 原 first-exit 正好在 K | 退出日与标签known日可相同 | force-open可替代盘中stop reference，数值/原因不可直接复制 |
| 原 first-exit 在 K 之后 | K更早成熟 | 原标签未成熟时K标签可能已知；不能使用原target较晚结果补K值 |
| 原到样本末仍open，但K在样本内且前缀完整 | K可闭合而原仍right-censored | 原closed-only训练缺少这类K已成熟样本；不能为了复用旧训练index而删除它们 |
| K在样本/完整calendar之后 | 不发明终点清算 | 原若早已闭合仍可相同；否则保持open/pending，不能把K clip到最后bar |
| D缺价、路径在K前缺价，或K开盘缺价 | 无法凭以后bar补成完整known路径 | cash理想defer后来可有成交日期，不证明未知区间真实未触stop；不得给真实target编造晚成熟日 |
| u可知D不满足K | u已知policy不参与，不是filled trade标签 | no-exposure诊断0与trade R null分开，不能把unknown/open也填0 |

Stage130 原条件明确要求 `label_known_date < cutoff`。如果未来另定义K target，则每个target的成熟时钟要独立判断；从原标签切到K可能增加已成熟事件并改变训练域、区间并集权重与scaler。这些变化会破坏“沿用130全部模型/训练表就只是换一个Y”的简单说法，必须在另一个尚未授权的协议里定义可比控制。当前不重标、不重算权重、不重训。

排序能得到保证的一项充分条件是：同parent全部可行动作具有共同 `a_u>0,b_u`，使 `E[Y_K(a)|F_u]=a_u E[Y_0(a)|F_u]+b_u`，且admission相同；完全相等是特例。单凭“两个目标都除同一个正R分母”，或笼统“做某个单调变换”，不能推出任意条件分布的均值排序相同。例一违反这种共同保序结构，并非旧083单位替换或103单事件log代理的改名。

## 完整域可识别性与唯一最小投影设计

**候选对象仅是固定K下的独立最小合法量、日线理想执行的动作价值与状态；不是组合现金、不是队列真实成交。** 完整可行动域不能由是否已选、是否正分、是否实际成交或事后是否closed来定义。

- **宇宙不删行**：沿用原129的全部 `1,552,456` action身份和全部 `399,252` mother身份；无child母行保留为no-action状态。历史数字沿用既有身份合同，本阶段没有重新读表计数。先按u可知的history/economics/anchor/一手容量与D<K记录资格；score、选择、实际fill和未来closed均不作为母体过滤。
- **最小行字段**：immutable action/parent/sequence/product/family/epoch/anchor/u；u eligibility及原因；D与K_target/K_state/K_index；原target state/value/known clock；K intent state、entry/exit reference与cost lineage；known K trade R、单独的known-no-fill policy诊断0；首个unknown与last observed；open/pending；容量/entry execution unknown；每target独立成熟标记。无child母表只需identity+state。
- **最小一次投影**：仅当另行冻结身份、预算与来源后，才能对完整action域投影。对确证完整且早于K的原闭合路径可复用同值并记录provenance；其余只在同一accepted native cache前缀内识别首次有效退出/K-open/首个unknown，停止于unknown或sample-end；不从已接受现金fills反推未选动作，不以gap插值或终点close补缺。当前只给设计，**没有执行历史投影或生成新标签**。
- **known no-fill**：原规则可确定的D stale-boundary/invalid-stop等不参与，在已识别零暴露前提下可以保存policy diagnostic 0，trade R仍null；u阶段明确D≥K也保留blocked状态。D quote缺失、native未知、open未闭合均不能置0。因为某个旧账户无资金/occupied/四舍五入而未成交，属于账户条件，不是该动作本身的零价值标签。
- **何时可点识别**：给定固定日线模型、完整元数据/calendar、已知参与和退出前有效bar，理想单动作结果可由规则确定；但capacity超限、队列、停板与实际可得成交仍不是日线数据能证明的真实收益。前缀缺失和右删失保留未知，未给普适有限损失界，故不能未经假设给完整真实总体均值精确估计或用“已知子集均值”冒充全域结论。
- **唯一可检验问题**：在完整事前域中有多少状态可识别、是否存在可识别而有实际选月可能性的原/K相反序。当前只证明可能，**历史占比、金额、正分覆盖、是否解释206、是否有预测力全部未测**；未来即使识别反序，也只是进入另行设计的必要条件，不能直接开启模型/现金或宣称alpha。
- **明确否决条件**：如果最终只能从“两臂都选中、都成交且闭合”子样本取值，或无法枚举完整事前域/unknown/no-fill/open，**否决投影/目标替换设计**，在fit/cash前停止。如此筛样本同时条件化资本路径、决策、执行与未来存续，不能识别全域目标代理作用。

本设计没有改变原输入、stop、K、成本、风险、选择政策或模型；也没有授权目标学习、SPO、追加cash。需要新target时连对照都可能要重新定义，而不是机械复用旧文件名；做不到可比控制则停于设计。

## 产物、反思与停止边界

- 唯一小输出：[mechanism_design.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage211_firstexit_K_structural_mechanism/mechanism_design.json)，含两个手算例、现有源函数锚点、完整域/未知合同与设计预算。没有新增实现脚本、test suite或数据扫描。
- 两个例子仅用Decimal做公式核算，验证了原8.2>2.2而K0.2<2.2，以及同日1.2/2.2的不同值；这不是backtest、actual cash或历史标签。期末权益、总收益、DD、Sharpe、总滑点、交易次数和胜率均为N/A；不需要把合成手算交给207当作实际回测审查。
- 开始是否过拟合：**是，历史多轮择题风险仍在**；失败后转向目标解释也有解释选择风险，不能因反例成立就挑一段历史求证。
- 结束是否新增按收益调参：**否**；没有新历史收益或拟合，但上述历史选择风险并未消失。例子是逻辑反例，不是概率估计；没有把两个成功手算例当市场经验累积。
- 开始继续价值：**是**，209要求的结构机制可以在0金融成本下被精确定义，避免把标签差别、成熟差别和现金差别混为一谈。
- 结束继续价值：**有条件的是**，仅限完整域、单对象、保留未知的一次投影资格判断；当前开启重标、训练、现金或复杂优化器：**否**。若只能closed-only取样，直接否决，不扩大研究找支持。
- 待root汇总211机制与其他独立评估后决定是否另开可复验协议。整体目标未达成；q53包关闭保持，不改 `LINE.md`、registry、根账本、其他阶段或任何接受源。
