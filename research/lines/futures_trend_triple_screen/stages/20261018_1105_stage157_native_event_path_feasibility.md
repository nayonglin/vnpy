# Stage157：旧19品种原生事件路径的收益盲源码盘点

- line_id=`futures_trend_triple_screen`，2026-10-18 10:59—11:05 CST。先读registry、154/155；155当时待156独审，本文不预称accepted。仅写本文与 `outputs/stage157_native_event_path_feasibility/`，不改tools/LINE/registry/旧材料，不派agent。
- **用户已进一步改为全市场、全品种寻找超高质量做多信号，不限正式AI月池。原“6个去向层×2时段、含short拒绝”的≤12例pilot不再采用；未选样、冻结或运行，不作为新目标实验母体。** 本文只交接旧19品种native hook、1手非线性和账户依赖的跨线参考，不自行新建目录或把旧策略设为新目标限制。
- 开始/结束新增过拟合：**否**，没有读取未来盈亏选择样本、造label、改stop/q/模型。继续价值：**是**，机制与数据边界可复用；继续实施旧12例母体：**否**，目标已改变。

## 结论

旧native机制可以作为未来有界、固定环境事件pilot的起点，**没有现成“给一个未选event即可返回唯一原组合反事实”的适配器**。`stage065_run_pairwise_off.run_profile_once`仍是整账户调用器，不是labeler；005仅枚举原生potential信号，没有账户、订单、退出或费用结果。

固定真实1手能核机制，但不能按比例还原原q或组合收益：原退出含整数部分平仓、实际资金/风险簇反馈及换月缩量，1手与原q的退出路径可不同。未选/q=0在原账户没有实际独立路径，必须先公开定义独立环境与admission政策；不得调用旧 `_open_position` 内部的 `max(1,int(volume))` 偷把q=0变1。

现有accepted A_OFF现金/库存/成本及分钟exact-key接受可继承其原范围，足以支撑**以后只消费现存资格、遇缺即停的小机制pilot**；尚未证明任意未选事件从开仓到最终退出/roll的所有真实键齐全。旧19品种事件、806 metadata和执行session白名单不能外推成新全市场做多数据覆盖。无需无端等B，但也不能以旧19材料已经在本机为由声称新全市场标签已就绪。

## 最小真实hook与适配边界

以下行号对应此次实际读取SHA，完整67项AST定位、签名、自身调用列表见source_inventory.json；未import这些模块、未调用main或financial API。

| 用途 | 真实文件与起始行 | 能复用及仍需接线 |
| --- | --- | --- |
| 原生信号 | `tools/stage005_potential_signal_demand.py:97` enumerate_signals；base `qmt_roll_portfolio_strategy.py:8969/9789` history/signal | 同原metadata真实bar/global engine calendar/AM41生成原u信号；不创建账户、不证明全部eligibility |
| 唯一u事件接线 | base `on_bars:1290`、`_build_flat_entry_candidate_plan:4098` | 需新隔离薄adapter在完整历史更新后，仅认精确u/产品/真实合约/long/原signal；停止无关新初开，不从未来fill猜信号。此adapter未实现 |
| 原止损及估量 | base `_calculate_entry_sizing:5792`；Stage830 `_calculate_entry_sizing:94`；Stage804 `_entry_stop_price:59` | 必须经真实MRO；804做多止损是 `max(u.low,u.close*(1-stop_loss_pct))`，不能错用base止损。取得u时S和原字段后，1手政策另标，不假称原预算q |
| 建层/真实下单 | base `_open_position:6108`、`_apply_state_target:6241`、`rebalance_portfolio:1276` | `_open_position`只建state/layer/诊断，不等于fill；target/rebalance后才有实际order，必须走真实engine |
| 下一真实session执行 | Stage502 `new_bars:112`；Stage827 `_stage827_order_context:312`、`cross_delayed_orders:365`、`_fill_order:403` | cross在on_bars前，u信号单按下一真实批次首分钟执行；strict anchor缺失必须停，不以日线open/legacy proxy替代 |
| 0.5R/retry | Stage847 `stage827_intraday_exit_after_open_trade:157`、`_stage847_stop_retry_event_after_open_trade:164`；827 `_fill_synthetic_intraday_close:485` | 保留真实minute suffix、初止损之后下一bar起才能reclaim、实际adverse tick与同bar冲突顺序；synthetic queue及layer identity必须保留，不直接调用一次hook后拿final_state当完整交易 |
| 持续native退出 | base `on_bars:1477`后退出序列、`_process_prev2day_stop:7583`、`_process_layer_stops:7689`、`_process_rsi_partial_exit:8317` | 必须继续喂真实日线/target mapping并走后续实际order/fill，直到终态；不能固定若干日proxy收益替代 |
| roll | base `_handle_rollover:1965`、`_rollover_shape_reopen_volume:9766` | 原5交易日delay、target-only history、shape许可和shrink_to_allowed；须另记真实old-close→target-open/order边，继承同event，而非按日期/合约粗连 |
| 时钟/身份 | `tools/stage031_run_ordered_checkpoint.py:66/74` actual_trade_identities/build_execution_clock | 可复用真实TradeData与usage一致检查；不能把旧C_TS/A_OFF owner、schema或目录直接借给新pilot |
| 现金/库存审查 | `tools/stage030_independent_ordered_account_review.py:159/91` inventory/episodes；095 `a_mothers:353`；106 `adapt_exports:62/frozen_reader:81` | 可移植独立现金、库存、逐fill费用与日期归一的有限纯组件；095/106整CLI绑定原账户，不能直接签新pilot。旧episode retry同根、roll新根，不能冒充完整经济母链 |

`passed_initial_filter`也不能当完整资格证明：本机886条此字段均为1，而base `_record_entry_candidate_snapshot:6336`将其字面写成1；同表仍含short规则、月池、预算、并发拒绝。005在 `_generate_signal`内已经过部分基础filter，不等于所有下游规则都允许入场。

## 独立1手、冻结原预算q与原组合反事实

若以后新线采纳独立1手机制pilot，需先冻结：初始资本/现金、空持仓与订单、历史streak/账户高水位、全部市场history与日历、long-only允许范围、admission政策、停止新独立信号、原生退出/roll/retry及整手规则。不能边看结果边补资或关掉风险退出。固定150000是旧账户参考，不是此处已批准的新线资金参数；任何新资金值应由新合同明确，不能称无参数变更。

原AI池阻挡、short规则拒绝或候选缺行事件若被强制开1手，结果只属于明确的 `forced_initial_one_lot` 条件路径，不是原native可交易性。本次旧12例不再实施；新全市场做多目标可自主定义不受旧月池限制的long入口，但必须记录这一母体和资格变化，而不是悄悄绕旧过滤。

三个主要非线性/不可识别点：

1. **整手退出。** base8317以 `int(current_volume*0.5)` 部分平仓；1手会得到0而不退，原多手可能减半后继续。旧setting RSI阈值95、比例0.5。native一般加仓/Donchian加仓关闭，reverse及alignment break也关闭；不应将仓库里存在的所有退出说成此账户启用。
2. **账户生存。** 当前实际 `enable_forced_margin_deleverage=true`，trigger0.95/target0.8；base7866读取equity、全部margin并按持仓排序减仓。risk_cluster_heat_deleverage也开启（base7748），是否作用还取决于适用cluster/layer种类/pressure。普通portfolio margin/DD/volatility/overheat deleverage在base默认关闭，不能声称它们本次已触发。base2226每批重算全部状态；独立空账户与原账户slot、相关持仓、streak、保证金、共同环境不同，未来组合还会被这一新event反向改变。
3. **换月/结束。** base1965真实平旧再视history/shape/预算续新；9766可将续仓缩至allowed，0则不续。roll中间库存为0、retry初止损后暂时为0，都不必然是mother结束。不能把原组合之后的equity/margin轨迹冻结后又称它包含新event的唯一因果结果。

冻结原预算q仅适用于u已存在、正值且语义清楚的q快照；q=0没有可冻结的原已准入手数，不能补成1、使用未来财务或按原盈利放大。即使保留原u正q与S，未知候选加入后未来资金/退出/roll仍依赖新环境；已有selected账本只能作已有观测和机制对照，不强求1手与其等PnL，也不能把独立事件PnL相加为组合绩效。

## 数据、费用与时钟的最低合同

- **真实日线/映射。** 需要u前完整warmup、之后直到自然退出/删失的真实合约OHLC/volume/OI语义、原主力mapping/calendar、合约size/margin参数，roll旧/新两边target-only历史。不能单靠141七列CSV重建整个旧C9（其未含OI/turnover等旧输入），不能把native carry当真实行情。缺session不补价；保留原范围/再暖限制。
- **分钟与权利。** OPEN/full_session须完整实际grid与已接受七值/完成证据；CLOSE至少严格qualified首anchor，retry/roll实际触发所需full不能由anchor权利升级。`qmt_roll_intraday_execution.py:30/77` session_minutes/entry_session使用真实映射日历、夜盘所属交易日、actual execution后的suffix；当前硬编码session仅覆盖19产品组，不能静默扩全市场。`stage021_blocking_data_gate.py:136` requirements、`stage045_exact_request_resolver.py:88` qualify_local及061 `load_accepted_delta:385`/`compose_qualification:492`可供后续有限接线；不要通过旧CLI绕owner。022 `inherited_qualification_predicates:643`明确859 anchor-only不能授full。
- **现有接受边界。** 此次只读取022 manifest、061 delta manifest及081独立receipt；081明确full_future_path_coverage_claimed=false。未载入原始分钟、DB或whole stack，也没重新资格。pilot只能先用实际请求的既有accepted exact keys；缺一个必须键就输出missing/unqualified并停该事件，不下载、补0、无限资格或换事件来凑成功率。
- **费用。** base `_trade_cost:3423`逐fill为turnover×rate＋q×size×slippage，必须覆盖初开、每次retry双边、roll双边和最终退出。旧effective rates806项均0、slippages806项均1.0是价格单位，并非已证明每合约一execution tick；新全市场真实费用仍需独立材料。执行tick经 `effective_pricetick:66`，与sizing/cost tick分开；保留LC历史变更等既有规则，不以新条款外推未知合约。
- **完成/成熟。** event→真实order→fill→layer/母链→每笔费用必须闭合。新mother建议从唯一原u事件起，包含同事件retry和roll及所有close；不能新开一个roll root就当新独立标签。必须库存为0、所有相关挂单/retry/roll continuation均明确终止，且最终fill/费用所依赖的行情已完成并可知，才给label_known_at；取这些可知时刻的上界，不用首个stop/逻辑u午夜/最终退出日0点。原始source没有准确known_at时保持未知，不造timestamp；末尾开放、缺分钟、pending、roll身份歧义分别保留删失/缺资格/未识别。

未来若做技术pilot，应按新目标的u时做多资格、固定日期/产品层先定事件，不能看未来盈亏、成熟与是否发生roll/retry后补选。retry/roll是必要状态机覆盖；未自然出现就披露未覆盖，另用事先声明的非效果估计机制案例检验，不从成功事件筛训练集。本次不为新线预选事件或提出第二套大计划。

## 停止条件、产物与终态

遇到原signal/S无法在u重建、强制入场政策不明确、真实session不支持、资金环境未定、required exact key无资格、订单/母链歧义、未平/未成熟或费用known_at不明，即保留对应状态，停止出完整结果标签；不补0、不以PnL救参，不以修完14差集为前提反复扩大任务。

`inventory_sources.py`实际唯一调用工具chunk=`edf89d` **exit0**：stdlib AST解析18个源码、67个真实hook、27项紧凑source绑定；选样0、标签0、financial/prepare/model/training/provider/network均0。source_inventory.json SHA=`35b6955bcdebce8d9115831ad16baeba94566635227d0188993b201ecdcb3db9`。这是一份只读盘点，不是adapter实现、试跑、数据签发或独立审查。早前一个猜测Stage804文件名的只读rg实际exit2，随后按rg --files找到真实文件，未执行源码或以缺文件推断不可用。

沿用154已有primary网页/GitHub判断：Boyd风险约束及分布稳健Kelly只支持把误差/生存约束纳入未来投注，不能提供本仓库优势证明；官方mlfinlab当前多函数pass，仅参考interval/purge合同。未新增网络调用。参数/回测改动均0，权益/收益/DD/Sharpe/滑点/胜率N/A；无新金融，不更新root并行进程计数，production_qualified=false。过拟合新增否；跨线参考有继续价值，旧19品种含short的pilot随目标改变停止。
