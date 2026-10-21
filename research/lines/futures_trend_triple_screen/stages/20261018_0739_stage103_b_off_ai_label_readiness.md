# Stage103：B_OFF 后续 AI 样本与成本后母交易标签的只读准备

- line_id：`futures_trend_triple_screen`；2026-10-18 07:39 CST。
- 工作区：`/Users/mac/Desktop/fian`；分支 `codex/ai-training-data-expansion`；只读时 HEAD `4f42805c2c71f8492a44a6876a82672f410f44df`。
- 阶段性质：接续 Stage055、057、058 的数据资格准备，非重要突破、非新增实验臂、非执行授权；本阶段不触发正式 A/B 或晋级。先读 `research/registry.md`；本线已有 LINE/阶段合同，按 root 指定只写本文，不更新总索引。
- root 下发背景：099 新族 A_OFF 处于其全局第2次运行，B_OFF 未启动；这是任务背景，不是本 agent 新验真的进程状态。本次未读取099运行目录、账户中间产物、PnL、曲线或成交流水，不能预判两臂成绩。
- 当前 A/B 不因本文新增前置闸门或重跑要求。本文的条件只约束**后续 AI 训练研究**，不修改已冻结金融合同。

## 结论

**未来 B_OFF 的完整、独立接受产物足以审计“固定环境下观察到了哪些 B 状态、哪些候选被预算取舍、哪些已分配 intent 真正成交或失效”；仅凭这些产物，仍不足以直接训练 Stage055 所要求的全机会成本后母交易净 R。**

关键缺口不是是否保留旧 pairwise：未入选机会没有实际反事实持仓路径；现有独立母单表按订单/合约闭环，retry 同根而换月重开另根；没有统一的跨换月母身份、预注册 R 分母及标签最终可知时间。完整导出与会计算术通过不等于监督标签已合格。该判断来自静态接口，不依赖账户输赢。

## 继承的模型资格限制

Stage057/058 对旧固定19维 pairwise 的结论不改：实体拟合统计强烈对应含2022后期候选的50行/25日队列，最晚标签终点复算为2023-01-06，但这不是原作业的精确 trained_at/cutoff 证明。旧全历史结果不能自动取得 PIT/OOS 资格，2023以后也不能只按日期自动认证。真实历史发布与今天重建严格历史信息集是两类证明，不能混同。

099 两臂关闭该固定 pairwise 及其仓位耦合，保留月度 AI。未来应核实际 `effective_off_policy.json`、`actual_strategy_settings.json`、`preflight_used.json`/原始 checkpoint 的 exact settings 与来源绑定；关闭 pairwise 不能替代月池自身资格，也不能提供新训练集。OFF 的 `selection_pairwise_rank/score=0`，pending 中正整数 rank 是原计划插入次序；**不可把 ordinal 冒充 AI rank 或学习目标**。源码依据：`stage095_independent_off_account_review.py:279–309,438–447`。

## 未来可直接读什么，以及证明止于哪里

下表仅列将来的文件接口，未检查它们此刻是否存在。接受入口以 root 的实际 terminal exit0、099 lineage、raw/seal/export 精确 SHA 和095独立会计接受为准，不能消费旧失败 partial。

| 问题 | 未来 B_OFF 文件与关键字段 | 可以直接证明 | 不能由此证明 |
| --- | --- | --- | --- |
| 观察母体与资格 | `ordered_gate_audit.csv`/`ordered_audits.json`：product、contract、signal_day、execution_day、setup_id/setup_day、intent_id、decision、cancel_reason、filter_reason、signal、direction | 035在 planner 之前逐产品观察的 B setup/intent，以及月资格、持仓、未知/取消、通用过滤去向；随后同一行回填 planner 状态，可与候选表连接 | 不等于全市场或关闭月池后的全部机会；ineligible 已清准备，不能从该行还原一个实际存在的可交易 B intent；不能只数有成交行认证母体完整 |
| 真实资源取舍 | `entry_candidates.csv` 与 gate 表：candidate_status/skip_reason、selected_volume、active_positions_before/remaining_position_slots、incremental margin 字段；获原始 admitted 资格者另有 `b_ts_final_budget_volume_before/after`、gross_margin_before、cluster gross、risk/margin/single/broker/cluster 上限、equity_u、T/S、reason | 在同一 u、同一冻结账户路径下，候选是否被 concurrent、incremental margin 或 B final budget 减量/归零；前缀和整数约束的实际取舍 | 同日两机会不等于有竞争；自身risk不足/单笔cap不等于彼此挤占；final budget 字段只给 originally admitted plans，不覆盖所有 preplanner intent；u 预算不等于 D 实际峰值保证金或 fill 时重新钳制 |
| 分配后触发/失效 | `ordered_execution_audit.csv`：intent/epoch/setup、signal_day/D、status、quantity、trigger、forecast risk/margin；`ordered_fill_audit.csv`：order_id、execution_datetime、fill_price、stop_price、actual risk/margin；`ordered_pending_intents.csv` | 已被纳入 conditional_pending 的 intent 是 filled 或 expired_untriggered，真实 gap、fill 时间、u T/S/q 与实际风险；尾部 pending 可单列 | 未入选 intent 的 D 是否触发及其后完整持仓结果；未触发不是亏损标签，也不能随意赋成负类；未结束母交易不是完整收益 |
| 实际成本后账本 | `trades.csv`、`execution_clock.csv`、`execution_proxy_usage.csv`、`actual_trade_identities.csv`、参数/行情来源manifest、`positions.csv`、`rollover_shape_same_volume.csv`；095审计输出 `independent_cycles.csv`、`independent_mother_order_episodes.csv`、retry/rollover links、account_checks | 实际成交身份、现金/库存守恒、成本只扣一次、已闭环订单根的净现金与 retry/roll 关联；仍开仓 MTM 另计 | 对未选机会的可识别反事实净收益；统一跨换月的母交易标签；net R 分母、实际券商全部成本、label_known_at 或严格样本外 |

源码证据：`stage035_b_ts_strategy.py:44–116`先观察全部配置产品；`:118–159`调用原planner后回填决策，只把opened且正q的计划送入pending；`:161–177`给候选补 T/S/风险字段。原planner `qmt_roll_portfolio_strategy.py:4670–4759`记录slot与共享margin顺序；`stage035_b_ts_pricing.py:127–220`只钳制 originally admitted B 计划并按原a累加gross、非q回收。执行状态来自 `stage028_ordered_engine.py:49–66,165–205`。`stage065_account_checkpoint.py:384–416`只导出账户frames及四种ordered审计，不能额外想象一个全机会标签表。

完整观察母体的后续只读验收应检查：固定产品/实际日历下 gate 行覆盖、每产品每日唯一、所有 intent 的候选或明确过滤去向、pending 到执行/尾部pending闭环、setup/epoch消费及取消一致；不能仅凭文件非空或行数多声称完成。全机会集合的定义严格条件于原月资格、通用/OI及账户可执行环境，不扩大到所有基础池反事实。

真实竞争的最小证据应是同u至少两个原资格可开、可相互比较的机会，且共同slot/可分配margin/cluster约束确实binding，并能区分共同挤占与各自零手数。`candidate_status`相异或同日多信号只是线索；本次没有计数、没有判定竞争样本足够，不能提前给训练可行性绿灯。

## 现有“母单”与训练母交易的精确差异

`stage030_independent_ordered_account_review.py:91–156`是095 B分支继承的经济重建：普通初开以实际 trade_id 建root；同日retry追溯parent并继承root；换月重开只验证真实旧合约平仓及数量/时间，再以新开trade_id建新root。`:154–155`仅汇总不再活跃root的 `net_cash/costs`。095在`:450–453`调用该函数，在`:469–473`导出结果。

因此该表可以叫“实际已闭环订单根/合约episode成本后净贡献”，**不能直接叫055所需的同一B机会跨retry、加仓、换月直到最终退出的完整母交易标签**。roll links是构造未来经济母身份的证据，尚不是已经实现的全链合并。净现金与成本可由095复核，不代表已选好净R的分母。现有cycles有 entry/exit日期，但 episodes汇总未携带完整标签时钟；应从原真实执行时钟追出最终退出/最终费用可知时刻。

原接受账户手续费参数可能为0，只能声称“按继承成本配置后”；不能称含真实券商全部费用。未来标签需要保留成本口径与逐笔扣费来源，后续压力成本不能混成原样本标签或事后挑最优口径。标签尾部不得截短或用期末MTM冒充已成熟退出结果。

## 最小合法训练入口条件

以下只允许作为未来独立提案的准入清单，尚未全部满足，也不授权当前新增代码、训练或金融运行。

1. **接受账户与来源闭合。** B_OFF真实exit0、099修复族/attempt谱系、原始account checkpoint、validation seal、完整导出及095独立经济审计同一run_id/SHA闭合；策略、月池、OFF开关、成本与数据资格均明确。生产部署资格不作为本离线样本设计的前置，但离线接受也不等于生产资格。
2. **全机会和去向可验。** 冻结分析母体为原资格允许、pairwise/slot/组合预算取舍前的全部 B intent；保留未选、预算归零、未触发、取消、成交、未成熟去向，不按未来盈利或已成交筛样本。每行至少有 product/contract/epoch/setup/intent、u/D、原资格与原预算快照及来源hash；同setup重复intent只能作为同一组的关联观测。
3. **排序确有作用空间。** 核实真实共享预算竞争，报告独立日期/setup/母交易/产品组数及有效pair数，预先冻结可识别样本充分性的标准；没有足够竞争组则否，不因名义pair多继续训练。本阶段未指定或扫描数值门槛。
4. **目标可识别并预注册。** 对未入选机会，先证明可以不借未来组合取舍构造与原 D触发、gap、0.5R、retry、持仓、换月、真实退出一致的路径；若不能识别就停止，不以已成交-only或旧5/10/20日代理代替。统一经济mother ID、净R分母、成本、未触发监督编码、右删失与label_known_at；不能把原账户未分配的q=0解释成机会零收益。标签构建本身若需要新回放，须另获root冻结的有限实施授权，不从当前账户自动追加运行。
5. **信息集与切分可复验。** 每预测u只使用u之前已完全成熟标签；同setup、跨换月母交易与相互重叠标签区间按真实结果结束时点purge，embargo按依赖约定冻结；标准化仅拟合训练侧，按u选择模型版本并绑定训练样本/标签manifest、特征可用时刻及拟合政策。严格历史模拟可今天重建，不能反称当年已部署。
6. **唯一配对与作用隔离。** 继承055：同一B样本/标签/分割/学习器/权重，M0重学19维，M1仅加固定两context的pair差分；旧serialized模型仅历史参照。先核旧19维在全机会上的可得性，OFF下部分pairwise派生快照为0不能直接当真实特征。新priority与风险/预算/原分数用途须另冻结隔离合同，不能覆盖score/rank顺带改仓位。标签检验通过也仅是另行账户试验必要条件。

目前1等待未来B_OFF完成；2/3未做全表验收和计数；4缺全机会真实规则标签及统一母身份/分母；5/6尚未实施。**所以当前答案是：足以准备只读审计，尚不足以直接合法训练。** 不因数据不足换模型、加字段清单、扫时间窗或缩为已成交样本。

## 唯一优先保留的信息假说

继续055原来的一个问题：**在同u真实竞争资源的B机会中，原生准备持续时间与FI修复程度，是否提供旧19维之外的成本后母交易质量信息。** 只继承两变量：`setup_age`=同epoch/setup从setup_day到u的真实交易日间隔；`fi_repair_r = direction × FI2(u) / [volume(u) × abs(T(u)−S(u))]`。分母不合法使样本不可用，不用D回填，不新增阈值、窗口、交互、品种或模型路线。

gate表能给setup_day/u并用绑定真实日历算age；FI2本身没有被035 decision逐行保存，需要从095/065已绑定的 `stage027_ordered_features/fi2_daily.csv`精确(day,contract)连接；`stage031_run_ordered_checkpoint.py:256–307`约束该缓存与真实日历。volume/T/S也必须来自u真快照；同根重置与换月边界需保留，不能从赢家fill反填。该信息有状态机机制依据，但尚无新OOS增量证据，样本/标签不足时明确不训练。

## 外部调研与判断

本次有限复核055已引用的两个主源，未下载/执行外部代码或行情：

- [QuantConnect Lean官方 ForceIndex 源码](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)：价差乘量再平滑，支持FI的变量语义；不证明本仓库EMA种子逐值相同，更不证明该比率有预测力。判断仍需同母体配对反证。
- [Bailey等《The Probability of Backtest Overfitting》作者原文](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)：重复挑历史赢家会引入研究选择偏差；支持保持一次配对、完整披露失败谱系，不支持把已反复看过的2020—2026重切后称全新未来OOS。本次没有计算PBO或显著性。

## 变更、指标、反思与边界

本次仅新增本文。脚本、模型、策略、参数、数据、来源pin/收据、LINE、registry、根日志新增/修改/删除均0；无fit/predict、无金融回放、无行情/DB扫描、无账户中间PnL读取、无订单或生产操作。外部访问只为上述两份原始主源。

新增/修改/删除回测结果0；本阶段期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A（未运行）。不改变099账户沿革、七门、审计与终态判断，不占用或阻挡当前金融流程。

开始/结束新增过拟合判断：**否**，只把旧假说映射到真实可读字段和无法识别的标签，不按途中盈亏选方向、不拟合、不扩候选。未来过拟合风险仍高，重复历史/相关pair/结果筛选都需约束。

开始/结束继续价值判断：**只读样本与标签资格审计有价值，立即训练价值未成立**。唯一下一步是未来已接受B_OFF完整产物的有限资格清点；不新增运行或把“账本全了”误当“训练样本全了”。合入时仅由root整理本线状态，本文不修改LINE或registry。
