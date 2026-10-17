# Stage267 日PNL/信号源接入语义独立审查

研究线`futures_trend_rollover_shape_same_volume`；2026-10-17。已先读registry确认归属。本审查仅静态读代码、现成模型summary及152行pairwise训练样本日期，不运行金融回放、测试、模型或下载；不改Stage266、LINE、registry、正式代码或生产。

结论：root最新的**每epoch独立六位年月研究symbol＋私有mapping＋显式复制原metadata＋全历史按日推送＋精确asof pairwise读取**方案可以实施。以下是实施验收条件，不是对尚未完成代码的通过结论。特别不能把数据与标签完整性写成整个固定策略历史都是PIT/OOS。

## 已核定的接入方法

1. **身份：私有研究symbol是正确选择。** 旧`main_contract_mapping.py:121–126`按裸`main_contract_vt`去重，策略`qmt_roll_portfolio_strategy.py:834–838`按裸VT建AM，引擎`backtesting.py:191–193`按`(date,vt)`存历史。2015/2025同名SM501若用同一AM，会跨十年保留旧计数和数组。采用如`SM201501.CZCE`、`SM202501.CZCE`，与`CZCE.SM.201501/.202501`一一对应；不再需要按时间间隔reset。BarData.symbol、engine.vt_symbols、mapping目标、元数据各字典、source_symbol_by_contract必须同步使用同一研究VT，source原代码另存。
2. **数字长度：核心消费者可接受六位。** 策略`9409–9415`以去数字得到产品；月度`analyze_qmt_roll_ai_product_suitability_walkforward.py:88–95`、旧市场特征`build_qmt_roll_ai_position_training_samples.py:79–86`取字母前缀；导出`run_qmt_alignment_backtest.py:214–217`去数字后缀。上述路径未发现3/4位月码限定。要保留原产品大小写（如jm/au与SM），否则18池的`continuous_symbol_vt`及配置键不匹配。原contract metadata resolver不能自动解析六位研究名，root按原native VT复制size/cost/margin并注入两个import引用的方案必要，不能让默认resolver再猜。
3. **历史：给映射涉及的每个epoch载入全部真实clean日线，包括它成为主力以前。** 只载“当日主力条”会让换入的新主力永远缺真实AM预热。引擎132–199加载完整历史后，201–239仅依时间排序逐日推；未来记录留在history_data本身不构成泄露，前提是策略和pairwise只能看到当前批次/明确asof切片，不能预先把未来历史塞入AM。
4. **AM门槛按实际setting绑定。** `on_init:1230–1232`的load_bars(warmup_days)只令引擎`self.days=days`（vendor671–678），不是逐合约读够N根。策略1296–1298只更新真实传入bars，再在1373–1380检查AM.inited。当前策略`array_manager_size_floor=120`（404行），实际`am_size=max(ma_extra_long+donchian_entry_period+20,floor)`（834–835）；默认是120，`or140`仅floor为0时回退。若固定140，应显式冻结该设置；若只把coverage门槛设140，这是额外保守资格诊断，不能称策略实际AM140。2010之前clean没有历史，起点不足不可降低门槛或补平价。
5. **数量语义：BarData.open_interest必须等于clean.close_oi单边收盘持仓。** 策略历史8969–8978及9905–9942使用的是收盘OI序列；不需要拿缺失open_oi挡住策略/月度108源生成。不能误取开盘持仓，不能再次除2。pairwise私有frame保留缺open_oi为NaN；19项选中输入主要用closeOI差分，未选择feature_open_oi。通用提取器内部将未选中缺项转默认值，不应被导出为“真实开盘持仓”。
6. **注入范围：替换被import的引用。** `run_qmt_roll_backtest.py:112–121`默认工厂会核主库sentinels再调用原metadata；应替换`roll.build_backtest_engine`与`strategy_module.build_contract_metadata`为隔离接口。替换真正已加载的`vendor_engine.load_bar_data`；pairwise模块14行已from-import旧loader，必须替换`pairwise.load_contract_bars`，只改其定义模块不生效。按回放当前日过滤exact epoch全历史，校验末条date正是当前候选日；空/过期切片应显式阻断评分，不能落回runtime61–71的伪日历与shift开盘OI路径。

## P0：缺行情时缓存价可估值，但不能被伪装成真实可成交K

`SameDayCloseBacktestingEngine.new_bars`（run_qmt_roll_backtest.py:34–63）把真实bar加入传给策略的`bars`；缺bar时又把旧close构成当日平价bar放入`engine.bars`（45–57）。因此**目前合成bar不会直接推进AM**，这是可保留的边界；不能把engine.bars整包传给策略。

但策略缺mapping/targetbar会走1309/1363的关闭路径；2185–2215可回退engine缓存bar关闭层与设target=0；1276–1287 rebalance也可使用缓存bar。same-day-close撮合65–87未验证订单合约是否有真实当日bar，存在缺真实K仍成交的路径。仅把当天coverage=false不能消除伪成交改变随后持仓、连败、权益、margin及其它产品排序的影响。

实施验收应记录每笔fill对应的真实clean epoch/date键，`stale_or_synthetic_fill_count=0`；若发生，不能把受污染路径当成观测充分的训练源。不能仅删除表面缺日后就声称后续账户路径已恢复准确。若研究适配要禁止这类fill，还须同步考虑策略层已提前reset的layers/targets，不能单独丢订单造成状态不同步。缺日carry仅能作为明确的估值约定，不能提高观察覆盖。

对于root已放弃的bare-VT quiescent reset方案：vendor holdingPnL为`start_pos*(close-preclose)*size`（814），零持仓不会因旧preclose产生收益跳变；但这不能保护AM、非零遗留仓位或其它状态。独立六位VT更直接，也使vendor每日ledger天然隔离。

### root补充的撮合guard：设计有条件接受

root拟在研究engine的`cross_limit_order_on_close`调用原撮合前，暂移今日无真实历史键的active orders，记录deferred attempt，finally恢复仍活动的未成交单。该方案可以作为本次**conditional clean retrospective source**的数据缺口保护，不改生产或alpha参数。实施应满足：

- 真实依据是`(self.datetime, order.vt_symbol) in history_data`，不是engine.bars的datetime（合成bar也改成今日）。
- 不恢复已经撤销/成交的单；遮蔽期间若有取消回调，不能被finally复活。vendor715–722的cancel_order在active字典找不到单时直接返回，需确认实际回调路径不会丢取消意图。
- 下个真实bar日，不能直接按缺日旧order.price伪装成当日close成交。原SameDayClose撮合直接使用order.price；正常template.rebalance_portfolio:190–195会先cancel_all再重建当天单，应验证实际运行遵循此时序，或显式阻断过期单。
- `stale_fill_count=0`是必要验收，仍须记录gap前后pos、target、layers和pending close。`_close_all_layers:8454–8472`会在未成交前清layers；`_reconcile_state_with_position:7542–7559`又可用当前bar价重建层。故guard可能改变缺口后的策略内部状态，不能只由stale_fill=0宣称无条件真实策略轨迹或PIT；缺口传播限制保留在source manifest及资格报告。

本审查者未实现runner，可在root单次生成后独立只读核查真实fill键、过期订单、asof、AM观察计数、双账本与月度60日标签；此处不预先给运行结果PASS。

## P0：固定pairwise模型的历史可得性不能靠严格60日标签修复

Floor35原入口`run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest.py:22–39`明确启用pairwise_v2、long tilt0.15、VolRef30与corr20的0.60/0.80/floor0.35。不能为了早期数据完整而悄悄关闭pairwise，这会改变固定策略。

只读当前`qmt_roll_ai_candidate_selection_pairwise_classifier_summary_selection_pairwise_v2_risk_weighted.json`：train50/25天，valid_start2023-01-01、test_start2024-01-01。相同源`qmt_roll_ai_candidate_selection_pairwise_samples_v2.csv`共152行、73候选日；按该split的50训练行日期为**2020-09-17—2022-12-08**。将这一已训模型用于2010–2022历史，只能称**事后固定策略反事实回放**，不能称当时可得/PIT/OOS；即使回放价格严格asof，也不改变模型权重来自较晚标签这一事实。

因此可按已授权固定策略一次生成PNL/候选与月度特征，但source manifest需明确`retrospective_fixed_policy=true`及`upstream_model_PIT_certified=false`，绑定模型/summary指纹。未来60日标签完整仅是标签成熟条件，不是上游模型时间有效性证明。本次无需也不得据此重训、扫参或更换策略；后续若要求真实PIT，须另定义获授权的数据与模型版本合同。

## P1：覆盖、账本与产物的可实施验收

- **映射空洞不能填前值。** 私有mapping只改身份，不修补原缺口；10/15–16原18池无映射，不应因行情到10/16而强行延长策略源。回放end取10/14或明确将尾日标invalid。没有真实mappedbar、AM未ready、新上市/旧代码不覆盖均是coverage失败，不是零信号/零PNL。
- **已持仓其它合约也须检查当日真实bar。** 当前mappedbar完整不代表持仓估值完整。root计划把每个missing-held-contract-day标该产品无效是必要条件；发生伪成交/账户路径污染时，还应披露全组合风险状态的传播限制。
- **真实平仓/无信号的0与缺观察分开。** 月度原`_complete_product_frame:98–103`及`build_product_daily:242–243`会fillna(0)；这只能服务已证明有效的无信号/无持仓产品日，不能替代mapping/realbar/AM/heldbar覆盖矩阵。严格标签应要求后续完整60个源交易日，历史特征也应用显式日历覆盖检查，尾部不足保留未成熟状态。18,649旧CSV七列窗口不参与月度108必要性判断。
- **隔离默认输出与隐式数据读取。** 直接提取`run_qmt_alignment_backtest.build_positions_df`（83–115）与candidate snapshots（131起）即可；不要调用整组formal.run_experiments（72–86，包含3个策略和起始年扫描）。同样防止默认save_artifacts的逐笔K线图等分支重新读主库。只生成本线stage267独立输出，调用一次固定runner，`include_start_year_sweep=False`。
- **双账本一致性。** 用vendor daily_result.contract_results导出逐合约PNL、成本与positions，再验证合约和=组合日PNL。另核策略settled_balance/estimated_equity与引擎累计PNL；策略同日close撮合后更新trade_to_close的时序见1259–1269及1804–1816，不能只校总收益而忽略时间对齐。
- **固定metadata不等于历史PIT元数据。** 按原native metadata复制避免6位研究名解析错位，保留既有策略语义；但现代size/tick/margin/cost映射不能被追认为2010所有历史合约都经官方PIT认证。source manifest应明确这是冻结策略成本合同。

## 环境与可重复性

不改sys.path的`.py311`默认find_spec位于`.py311/lib/python3.11/site-packages/vnpy_portfoliostrategy`。Stage263旧runner显式使用外部冻结vendor路径`/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor`（stage263_build_expanded_source.py:124–147），本审查也已实际读取该vendor backtesting；SHA为`543be175773cc6b670f7ba1730e5164708ad8425ed7b80da4bc9cce0862e61e2`。Stage267须在import前确定路径，并把`vnpy_portfoliostrategy.__file__`、backtesting/template、strategy、runner、metadata、mapping、模型和Stage266最终DB/contract指纹写入manifest，不能根据默认环境推断实际vendor身份。

外部只读调研：[vn.py官方portfolio backtesting源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。判断：该上游提供框架参考，当前本地SameDayClose子类与冻结vendor的具体时序才是本次事实源，不把上游当前版本当本机执行证明。

运行前/后过拟合判断：本审查否，没有回放收益、调参或依据表现选数据。但固定已训模型回用于早期历史属于明确的时间可得性限制，应如上记录。继续价值：是，先固定身份、bar真实性、模型时间语义和缺口处理，可以避免对错误源PNL制造看似完整的月度标签。财务回放/模型拟合/参数扫描/市场数据下载次数均0。
