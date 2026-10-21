# Stage152：新目标下AI信号入口盘点与去重

- line_id=`futures_trend_triple_screen`；时间：2026-10-18 10:51—10:52 CST；性质：有界只读盘点，不是第二套大计划、模型/标签实现或新回测。已先读registry和当前LINE，本线存在但未入registry；本次不修索引。
- 用户新目标不限三重滤网：持续寻求更高成本后收益、更低回撤，重点AI识别高质量信号，再审慎研究窄止损与增加投注。本次不把目标继续锁在B或EMA；055/103里“等B完成”的旧条件只属于当时B-specific提案，不是现在的总前提。
- 只新增本文与 `outputs/stage152_goal_broadening_ai_signal_readiness/` 两份有限JSON；不改LINE/registry/旧线/源码/数据，不派agent，不联网、训练、回测、建模型或造label。

## 结论与最短下一步

**现有材料够做原生C9事件的数据接合试验，尚不够直接训练“全机会、成本后、跨retry/roll同母”的高质量识别器。无需永远等B。** 最短入口是现有accepted A0/A_OFF和005的19产品原生信号，先固定原生入口/止损/退出/风险政策，做一个有界的事件去向与路径可识别性小样本。先把下列缺项具体接通，不换模型、阈值或标签配方去寻找高分胜者；若接不通，就明确数据先行/负结论。

可在现有授权下自主推进的最小工作，是将005事件与A_OFF候选、真实成交时钟和已审成本账本按u/产品/合约/方向/原信号精确连接，先保留“候选缺失、未选、未成、已成未结束”等状态，**不填收益标签**。随后只对包含普通闭合、retry、roll、未选、未成和尾部未成熟等必要形状的有限样本，另做一个冻结原生规则的独立事件路径adapter：保留每个事前事件，无共享slot竞争筛选；用真实native fill/退出和严格已资格分钟数据，给未选机会明确的独立事件基准路径，不能用原账户q=0当其收益0。

该adapter目前**不存在**；它定义的是明确披露的独立事件反事实，不等于“原组合若换选它本来会赚多少”。若原退出依赖账户状态，必须事前固定事件基准环境并披露区别；无法定义时标记不可识别，不借未来组合选择还原。先证明有限样本因果时钟/成本/母链，再决定是否扩展完整机会集；本次不声称数量足够，也不新造监督标签。实际组合收益最后仍须真实账户检验，不能相加独立事件PnL。

真实可复用API：`stage005_potential_signal_demand.enumerate_signals(daily,mapping,metadata,strategy,*,start,end,weekly=None,progress=None)`已存在，调用原 `_build_history_df/_generate_signal` 并给出全部纯初开信号；它没有构造账户，返回的是potential events，不是全体实际可交易/全市场标签。真实经济入口可复用无arm门的 `stage065_run_pairwise_off.run_profile_once(s901,profile,metadata,*,engine_class,start,end,minute_audit)` 及原native847路径；未来需要新增薄事件接线，不能假称此API已内置全机会label。数据来源仍是绑定真实合约DB/日历/映射/参数、已接受分钟层和原生C9配置；不以产品连续日线替代分钟触发/止损/retry顺序。

## 本机实测材料与样本单位

实际只读统计chunk `078df3` **exit0**；两候选精确键去重chunk `b7612f` **exit0**。没有加载模型或raw pickle，没有运行原脚本main/prepare/native。CSV统计与有限source SHA存于 `inventory.json`；这不是重新资格认证。

| 现存入口 | 实测覆盖/身份 | 可直接复用 | 还不能证明 |
| --- | --- | --- | --- |
| accepted A0与A_OFF `entry_candidates.csv` | 各886行、673个候选日期、19产品；各312 opened＋574 skipped，均flat_entry | u时市场/原生信号、原止损/估量和真实预算去向；对照OFF耦合与入场筛选 | 没有未选机会实际持仓结果；还不是排序前全部可交易母体 |
| 两臂事件去重 | `(date,product,contract,direction,signal,entry_context)`各886唯一键，交集/并集均886 | 同一事件跨对照的关联观测 | **不是1,772个独立样本**；已看同一历史的两账户不能充当新增OOS |
| 005 `potential_initial_events.csv` | 900行、682日期、19产品；SHA `47f51b17bea78f52153866af93241bd9cbb1949246967e84125cdf0c594b1e61` | 不依赖B的新入口起点，包含未必进入账户的原生信号 | 不是57品种、不是900个独立已成熟母交易；与886的差异原因尚未逐键验收 |
| A_OFF实际成交/时钟 | 817 fills、439成交日期、214真实合约；不是214产品 | native成交价/物理执行时刻、成本和真实库存 | fills包含初开、平仓、retry、roll，不能一fill一标签 |
| 独立episode/cycle | 318闭合订单根episode＝310 flat＋8 roll；403 cycles、319根，cycle entry日期286 | 已核现金/库存/成本的闭合订单根及retry/roll连接证据 | 403不是403独立机会；318表名虽含mother，源码换月重开另建root，仍缺统一跨roll经济母交易及成熟时钟 |
| 141/142固定真实日线 | 继承本线已接受116,394行/533合约/1,786日及研究级限制；仅原metadata scope | 入场前可得的真实合约历史、已有指标缓存和特征来源绑定 | 日线根数不是独立标签数，不提供未选路径、分钟内先后或新信息优势 |
| 旧全市场57库存 | 当前eligible CSV路径和二期Stage124输出目录均不存在 | 旧124/126/129中文审计摘要是需求/失败清单，源码仍可阅读 | 不能声称本机已有57品种完整候选/训练集；旧126为有保留接受：54/57有分钟缺口、38/57分钟加载0，后续10品种局部overlay不等于57全量接受 |

A0接受receipt及A_OFF Stage110接受记录实际存在；A_OFF run=`7cf2c2bffdc34d8cbd926693aa75dd10`，cash/inventory/cost/identity已独立接受。这里仅继承原接受，不用Stage152重算绩效。原佣金0、日收盘保证金非分钟峰、旧模型/月池PIT限制继续保留。

## 真正缺的标签合同

- **信息与成熟分开。** 特征必须 `feature_known_at<=decision_u`；未来结果只有最终退出及该事件费用/现金最终可知后才有 `label_known_at`。训练时要求标签在拟合截止前完全成熟，不能只有 `eval_end<u`。已检查的候选/成交/episode/cycle表均没有 `label_known_at` 或统一 `economic_mother_id`。
- **全机会去向。** 保存排序、slot、margin取舍前的事件身份与资格；未选不是负类，未触发不是亏损，尾部持仓是右删失，未知行情是缺资格。现有19产品事件能作为起点，但母体覆盖与真实竞争仍须核对，不能从312 opened反填完整训练集。
- **经济母链。** retry、加减仓、roll到最终退出归同一经济mother，再绑定每笔实际成本、初始u冻结风险分母、最终时钟。`stage030...reconstruct_episodes`真实存在，retry继承root但roll重新建root；可复用其会计/连接证据，不能把当前输出直接叫全链净R标签。窄止损不能靠缩小R分母制造“更高质量”。
- **统计独立性。** 报独立决策日期、产品组、经济mother与成熟/删失数；同日候选、同setup反复挂单、同母retry/roll、17个重叠起点不可独立计数。682/673是唯一日期数，也不等于相互独立的有效样本量；分钟/日线根数更不是训练置信度。按真实标签区间做时间purge/embargo与产品组留出，不能把已反复看的2020—2026重切称全新未来OOS。

旧 `build_qmt_roll_ai_candidate_training_samples.build_candidate_market_label_row` 用planned price/止损距离计算5/10/20日前瞻与同日起MFE/MAE，尾部以min截短；`build_training_samples`只给实际selected连接真实交易，未选主要是日线proxy。旧pairwise `filter_rerankable_pool`只取flat_entry且同日有入选和未选的竞争池。它们是特征schema/失败诊断参考，**不能原样用作本目标的成熟、成本后母交易ground truth**；OFF的0 score/rank与ordinal也不能当AI质量标签。

## 去重：哪些旧路线不能换名重做

| 既有证据 | 对新目标的约束 |
| --- | --- |
| 信号质量AI Stage236：407样本，路径标签＋purged walk-forward后2022—2025高分质量率持续低于低分，2026相同 | 旧静态AI/RSI/账户桶换更复杂分类器、再换path label，不是新优势 |
| 重建二期Stage015：2,867 panel去重1,995，OOS1,281；高分只3/5年胜低分，高分总PnL反较低 | 不能重做同一meta-label并靠年份/产品/桶阈值挑赢家；panel行/起点不是独立样本 |
| 重建一期058、068—071 | 连续风险预算没有同时保留右尾；“超高质量”composite均值/lift好看，固定+25% proxy仍未解决左尾。不能继续调top8、account阈值、fraction或换兄弟组合 |
| 二期010/013/014 proxy与058真引擎 | closed-lot乘倍率的好看曲线不是成交/整数手/保证金可实现证明；真实质量＋OI cap50仍未晋级，不能floor/ceil/min+1救参 |
| 全市场002risk 001—009 | score-only、veto、guarded tail形状均失败；AP605右尾漏单已有归因，不能品种/年份黑名单或topN/分位救参 |

这些负结论否定的是已见信息与已测形状，不证明AI永远无效。重建全机会标签能修正选择偏差与可识别性，但**数据合同修好并不自动恢复旧特征预测力**。只有明确新的事前信息/不同可识别事件母体及一次冻结比较，才有理由再验证；同组旧字段继续组合、换seed/模型/标签门槛应停止。

## 三因素必须分开

先固定原生S、执行、成本和统一原风险预算，检验AI质量选别本身的留出增量及未选右尾机会成本；不能先加注，让杠杆变化冒充识别能力。数据接线pilot若用一手，仅为核对路径，不可冒称跨止损距离的等风险收益比较。选别没有稳定净增量就结束该形状。

“窄止损”是独立执行/生存假说：可能同时提高整手数、噪声止损、gap和成本/R占比，并不机械产生更高期望。不要同AI模型一起扫stop、窗口或参与率。若有结构理由才冻结一个独立止损形状，与识别增量分开核验。

只有识别增量及其实际执行成立，才研究一次独立、有限的加注形状，明确估计误差、回撤/保证金/相关风险约束；不扫描fraction或在最坏年份救参。root已核[Boyd风险约束Kelly](https://web.stanford.edu/~boyd/papers/kelly.html)、[分布稳健Kelly](https://web.stanford.edu/~boyd/papers/robust_kelly.html)及作者GitHub：可参考不确定性与回撤约束，不证明本仓库有优势或允许直接套最优投注。root已核Hudson&Thames官方 `mlfinlab/cross_validation.py` 当前网页多处函数主体为pass，仅可参考区间purge合同，不应声称可直接依赖完整开源实现；本阶段未下载/运行外部代码。

## 终态与反思

`inventory.json` SHA `2fc856803f6ef1f663c80c2df2aee5a0127a7ab566a5a87688a22a9f7453f123`；`candidate_key_dedup.json` SHA `d598e2618c78d04bac0852ff42e4820f7285dabb9bc61edb98d3adb21328feaf`。只写这两份计数/来源证据和本文，没有生成event scaffold或任何新label。

root当前事实：EMA接合四项修复已集中完成，但actual prepare151因旧InputRecorder未收 `.pickle.gz` 压缩证明而KeyError，root修中性交接；没有新金融，累计11attempt/4accepted。本盘点既不以此失败推断EMA alpha，也不把解决该API当AI质量标签前提。

新增/修改/删除策略参数及回测结果均0；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。开始/结束新增过拟合：**否**，本次只读去重、未选口径；继续用旧高分标签缩止损/加注而忽略失败会是过拟合。开始/结束继续价值：**是**，最小原生事件数据接合有明确现存入口，立即训练/加注暂无依据；目标保持active，允许数据先行与负结论，不承诺已找到可穿越周期优势。
