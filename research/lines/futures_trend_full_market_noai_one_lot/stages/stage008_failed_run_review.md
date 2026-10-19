# Stage008：首轮失败与诊断回放独立审查

- 研究线：`futures_trend_full_market_noai_one_lot`
- 时间：2026-10-18 17:12 CST；独立审查者：`/root/failed_run_review`。
- 性质：执行正确性审查；不是重要突破版本，不是新 alpha 候选。
- 范围：只读研究工具、原生策略、已安装 vn.py 模板/撮合器、冻结 inputs、v1/v2 失败证据；运行人工合成事件测试，没有启动任何金融回测，没有修改正式代码、原工作区、候选实现或参数。
- 本次新增/修改/删除参数：均无。新增有效回测结果：无；未删除任何历史结果。

## 审查结论

**首轮及第二次诊断均失败，完整回测完成数为 0。不得报告有效期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率，也不能据此判断策略好坏。**

已确认的问题是研究日线“缺真实 bar 则暂缓成交”语义与原生“先改策略状态、再异步按合约执行 target”语义之间的缺口。单次选手数为 1 并不保证产品实际总手数为 1。实际持仓事实源 `pos_data` 没有被完整用于持仓发现、并发品种计数和保证金估计，已过期但尚未取得真实平仓价的旧仓被隐去。仅关闭断言、按产品净仓抵消或强行用缓存价平仓都不正确。

## 证据与置信度

1. `outputs/run_20261018_daily_proxy_v1/engine.log` 在 2019 年进度后记录 `more_than_one_lot_per_product`。vn.py 的 `run_backtesting` 捕获异常并退出，外层随后以 `partial_replay` 拒绝后处理。这是正确的 fail-closed；报错不是策略绩效结果。v1 当前只有 log、protocol、失败 runner 备份和 `failure_receipt.json`，不存在有效结果 CSV/summary。
2. `outputs/run_20261018_diagnostic_v2/failure_snapshot.json` 明确记录 `2019-06-25`、`financial_metrics_valid=false`：
   - `fb201801.DCE=+1`，`fb201907.DCE=-1`，产品绝对手数为 2；净仓为 0 无法解除违约。
   - 另外 `IH201812.CFFEX=-1`、`SM201909.CZCE=+1`、`i201909.DCE=+1`、`p201909.DCE=-1`。
   - 共 6 个非零合约、5 个产品；protocol 中 `max_concurrent_positions=4`，旧仓遗漏也使实际并发产品约束被绕过。
   - fb 的 state 仅指 `fb201907.DCE` short/base 1，entry_date `20190624`；旧 fb 与 IH target 均为 0，仍各有一手 close 活动单。最后 60 笔成交包含新 fb 空头开仓：2019-06-25、54.55、volume 1。
3. 独立只读扫描 `outputs/inputs/market_daily.csv`：`fb201801.DCE` 69 根、最后真实 bar 为 `2018-01-02`、close 109.8、volume 4；`IH201812.CFFEX` 165 根、最后真实 bar 为 `2018-12-20`、close 2336.2、volume 14395。新 fb 有 80 根、2019-03-06 至 2019-07-12。全表 volume<=0 和 NaN 数均为 0。可确认旧仓缺平仓数据，不是这两笔旧仓当天零成交量被误判。
4. 输入 manifest 声明六所、93 历史品种、4,328 合约 epoch、809,279 日线、3,056 个“已选主力却缺当日真实 bar”产品日。该边界具有实际规模，不能视为偶发可忽略。

对“实际存在违约”和“旧仓在持仓发现/风险计算中可被漏掉”的置信度高。对“v1 与 v2 是完全相同逐笔路径”的置信度略低：v1 原始异常没有当时日期/持仓快照，v2 是同一冻结策略与输入的诊断再现，因此连贯性强，但不应把 v2 新增快照冒称为 v1 原生证据。没有完整旧仓委托/成交全链导出，因此不能仅凭最后 60 笔成交断言旧 fb 最早是哪一次 close/rollover 导致状态脱钩。

## 已证实逻辑缺口

### P1：产品级总手数缺少撮合前硬闸门

`CleanExecution.cross_delayed_orders` 只把缺真实 bar 的订单暂移；`ConfirmedDailyNextRealOpenEngine.cross_delayed_orders` 独立成交剩余各单，没有按产品将平旧与开新绑定。原生 `_handle_rollover` 同次下达 old target=0 与 new target=1，并在平仓尚未成交前更换 state。旧腿缺 bar、新腿有 bar 时可先开新腿；同方向换月和反方向重新开仓均不能突破每品种总绝对手数上限。

人工合成测试直接使用实际研究引擎和已安装 `StrategyTemplate`：old=+1、old target=0、new target=+1。旧 bar 缺失时，撮合后 old=+1/new=+1、总手数 2、成交 1 笔、旧平仓单仍活动；两腿都有真实 bar 的对照为 old=0/new=+1、总手数 1、成交 2 笔。全部断言通过。该测试证明缺口可达，不代表已复现 v2 的所有历史前因。

### P1：持仓发现只看 state/target/当日 bars，遗漏缺行情真实旧仓

原生 `_resolve_actual_position` 候选仅含 state.contract、target 和当日 bars 中该产品合约，不扫描其他 `pos_data` 实际非零仓。当旧仓缺真实 bar，而 state 已切新合约或被清理后，可能返回 current_pos=0，继续按空仓信号开仓。

人工合成测试：pos_data old=+1/new=0、state.contract=new、当日 bars 只有 new；调用原生方法返回 `(new, 0, new_bar)`，与实际产品仍有一手不符。v2 旧 fb 长期缺 bar、state 指新、又新开一手，符合此缺口。没有证据证明 fixed_size 被放大：v2 新成交 volume=1；fixed_size/max_position_size 均为 1，pairwise volume tilt 和三类加仓均关闭。

### P1：实际持仓计数与保证金可能低估

原生 `_count_active_positions` 仅检查每个 state.contract 的实际仓位；原生 `_estimate_margin_usage` / `_estimate_margin_usage_by_cluster` 遍历 state.layers 且要求该 state.contract 在传入 bars 内。缺 bar 或 state 换新都会使真实旧仓的并发占用及保证金消失。v2 实际 5 产品已经超过保留的 4 产品限制，不能只修“每产品一手”就视为全部执行约束恢复。

此外 `_apply_rollover_released_risk_snapshot` 在旧仓真实 close 尚未成交时可扣除风险占用。异步研究撮合中，保证金修复必须覆盖该路径；只在某个日末重算 margin，不足以保证同日开仓风险判断正确。

### 不支持首要归因为“同合约重复挂单积累”

已安装模板 `rebalance_portfolio` 首先 `cancel_all()`，`cancel_order` 会移除 engine active order 并更新 strategy active IDs。合成连续 3 次 rebalance 得到历史 6 单、活动始终 2 单（每个合约各一单）。正常模板路径不会因反复 target 直接堆积同合约活动单。仍应在新闸门测试重复 rebalance，不能因此免除防重约束。

## 最小正确修复建议与验收

1. **保留失败证据，先补快照再诊断。** 快照至少包含日期、实际仓位、产品 gross、state、target、活动单、最后成交和行情最后可用日期；金融指标继续标无效。当前 v2 已提供关键证据。
2. **仅在研究候选中补实际持仓发现。** 由 source map + 全部非零 pos_data 找该产品真实仓，优先处理真实仓；出现多个真实合约应 fail-closed 诊断，不能悄悄选一个覆盖另一个。
3. **撮合前产品级平旧后开新。** 先执行当日有真实 bar 的 close，再基于更新后的实际 gross 判断 open；同产品任何旧实际仓未平，拒绝/延后新开。拒绝记录必须区别“缺旧 bar”与“产品手数超限”。同合约反向也必须先平后开，不依赖订单字典顺序。开仓 volume 必须恰为 1，不能部分夹断违规多手单再掩盖上游 bug。
4. **并发产品数用真实持仓事实。** 所有非零 pos_data 对应产品 + 尚未成交且有效的新产品预留均要计数；注意用集合去重，不能同一个已持有产品和其 pending 预留重复算两次。只修计数而遗漏同日多个预留仍不完整。
5. **保留实际保证金下界。** 至少由全部非零实际仓、合约乘数、保证金率、最后可靠价构建 total/cluster 下界，覆盖缺 bar 和 state 脱钩。缓存价只能用于估值与占用，不可授权成交；无可靠价格则保证金未知并禁止新开。应同时保留尚未成交目标/预留的风险含义，避免用 actual 替换 state 后漏算计划新仓；旧仓真实未平前不得在 rollover release 路径把实际占用释放掉。最小修复可在研究子类做 floor/reconciliation，无需改正式策略。
6. **补有限合成验收后再完整跑。** 覆盖旧腿缺 bar/恢复、活动订单反序、同产品相反方向、多个同品种开仓单、重复 rebalance、缺 bar 旧仓 state 被清空/换新、真实4产品占满、同日两笔预留、总与cluster保证金未释放、行情无缓存。通过后以新 run_id 跑一次，禁止覆盖 v1/v2。
7. **过期残仓的结果资格单独判断。** 若无到期结算或真实成交价，只能明确标记残仓和估值冻结，不能假平仓、品种黑名单或从结果删除。计算流程即使走到2026年，也不等于2015—2026完整可交易绩效合格；老仓长期过期未结算可能使权益、保证金和后续机会都缺乏可执行含义。应恢复可靠结算证据或如实报告数据/结果资格不足。不能用“保守carry”把不完整市场数据升级成有效金融结论。

## 外部调研与判断

已查阅官方 [vn.py 组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py) 和 [回测引擎](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)，并以本机已安装版本源码为具体证据。判断：复用事件驱动模板是合理的，但“原实现按合约 target”不自动满足本研究新增的跨合约产品总一手约束；需要研究适配层给出硬约束，不能宣称原生框架已经保证。没有引入其他策略代码或参数。

## 运行前后反思与后续 TODO

- 开始过拟合判断：否。只审查固定合同执行，未搜索收益更优参数。
- 结束过拟合判断：否。建议对所有产品统一按实际持仓修复，不按 fb/IH、年份、方向添加特例。正式信号既有历史选择偏差仍存在，本次审查未消除它。
- 开始继续价值判断：是。产品一手与实际持仓约束是任何绩效的前提。
- 结束继续价值判断：是，先完成通用执行/风险事实源修复及有限合成验收；若数据仍无法结清过期合约，继续补数据或披露失败有价值，继续输出有效绩效没有依据。
- TODO：root 完成修复与验收；新完整回测每次仍须独立 review，核对逐笔仓位守恒、总一手、并发4产品、total/cluster保证金、闭合账本/残仓、实际交易可用日及权益双账本。此 Stage 不构成修复通过或策略晋级批准。


## 第二轮：研究修复只读复审补记（2026-10-18 17:19 CST）

主代理已增加：候选 actual pos_data 补回、实际与pending并发计数、total/cluster actual-margin floor；撮合平仓优先、同产品已有仓阻止开新、实际并发4产品和broker保证金闸门。本轮只读这些修复和新增单元测试，并使用人工事件验证，没有金融重跑。本补记不覆盖后续主代理尚未写入的修复。

判断：这些修复方向正确，解决了首轮暴露的实际持仓事实遗漏及开新硬约束；**仅凭当前broker填单guard还不足以认定全部执行正确性恢复**。以下三项有独立合成实证：

1. **P1，开盘撮合闸门读取当日close，产生前视。** ConfirmedDaily `new_bars` 在撮合前把当日完整OHLC写入engine.bars，新guard按该close估计已持仓保证金。且native update_trade会以这些当日close重估estimated_equity，使后续同批open决策读取未来收盘信息。合成保持所有open=100、estimated_equity=1000不变，仅把旧仓当日close由100改1000，新产品开盘订单由成交1手变为 `actual_broker_margin_cap` 拒绝。必须用独立开盘时点风险账本：有真实当日bar的旧仓按open，否则最后可靠价；权益由昨日结算与持仓开盘MTM、当批已发生费用/滑点更新，不读当日close。验收应要求保持open不变、只改high/low/close时开盘guard结果不变。
2. **P1，次日fill缺signal_datetime导致entry_price未同步。** 现有Stage827本来有按signal_datetime匹配pending layer与诊断的能力；ConfirmedDaily创建TradeData未附该字段，落回base按成交日匹配。合成layer signal_date=20190402、entry_price=100，2019-04-03 fill=120：当前路径仍100且entry_price_synced=False；补signal_datetime=2019-04-02后既有Stage827路径同步为120且True。建议研究FeeStrategy.update_trade由engine原订单绑定signal_datetime/signal_order_id，再复用已有同步器。未修复时不能声称以实际成交价管理持仓层。
3. **P1/P2，未成交close意图不幂等。** 同一真实旧仓一手，在缺目标bar情形连续调用两次 `_close_position_when_target_unavailable`，会reconcile重建layer并再次close：pending_close_lots累计两手、streak更新调用两次，实际仍一手。真实close之后可留下错误队列，未来同合约重入/退出可能错配，重复登记结果也可能影响失败记忆。应按未成交实际量保存唯一close intent，只维持target=0，避免重入重复 `_close_layers`、输赢和理由登记；检查普通stop、缺mapping和rollover三类入口。不是用总一手guard即可消除的问题。

保证金判断：新增actual floor是必要措施；未成交前释放state风险仍可能改变计划候选，填单guard只能拒绝实际超限成交，无法恢复因计划层低估而排队/候选排序产生的差异。若本研究风险簇是一产品一簇，同产品guard在本范围同时阻止旧仓与新仓重叠；若任何配置把多个产品放入同簇，单一total broker cap不足以保护cluster cap，须增加actual cluster闸门或在计划层reapply actual floor。持仓计数 `max(super_count, len(held|pending))` 仍保留native对pending重复计数的可能，需测同产品同时位于held与pending，避免无意过度收紧。

执行专用到期overlay方案的判断：严格精确maturity日、双源OHLCV一致、仅OI冲突且官方OI=0，作为隔离的只读成交/估值旁路是合理的；FB的V0/OI0不能成交，继续残仓披露。当前尚未见实现，因此没有通过声明。至少需双闸门：

- 在传入策略super.on_bars的signal bars中剔除execution-only行，防止虽entry_sizing禁开却污染AM、signal、市场环境/相关性；只保留engine报价/估值用途。
- _fill_order直接拒绝execution-only bar上的Offset.OPEN，包括来自前一正常日的pending open；仅在当日entry_sizing禁开无法覆盖此路径。close还应校验实际可平量，不能让旧close挂单造成裸反向。
- provenance、原值/补值及规则命中理由单独冻结，clean store与训练合同保持原样；不得从一次IH事件反推随意日期范围或OI阈值。

本轮仍无alpha调参，不增加过拟合；继续修复有价值。新增合成揭示的是时钟与订单状态事实问题，须修复后再跑金融，不能借修复选择有利绩效。


## 第三轮：修复独立 GREEN 复核（2026-10-18 17:25 CST）

已按主代理授权新增并维护独立 `tools/test_stage009_execution_regressions.py`，只修改该测试与本报告，未修改执行实现、正式代码、数据或启动金融回测。测试首次运行的原3项均观察到预期RED断言：entry100!=fill120；同open只改close改变开仓结果；真实一手产生pending close两手。主代理修复后，独立再次运行全部本线测试，命令为：

`.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test*.py' -v`

执行环境设置 `PYTHONDONTWRITEBYTECODE=1`、临时MPLCONFIGDIR与本工作树PYTHONPATH；结果 **Ran 35 tests，OK**，耗时1.517秒（不含导入），没有金融回放。除第三方导入免责声明外，无测试错误或失败。

独立新增7项回归全部GREEN：

- 开盘风险闸门只改当日close而不改open，结果不变，排除已证实的前视路径。
- FeeStrategy真实update_trade绑定signal订单并经Stage827同步次日实际成交价，layer.entry_price从100正确改为120，synced=True。
- 重复未成交close只保留一个pending lot、一次输赢状态登记，实际仓与target不伪造改变。
- execution-only报价直接拒绝前一正常日产生的OPEN委托；仅在entry_sizing阻止无法覆盖的漏洞已闭合。
- overlay与正常报价混合批次：旧持仓100→110、size10、初始1000，真实native会计结算为1100，次日仍1100；overlay合约AM count保持0。
- overlay真实平仓：open105/close110、此前持仓基准100，平仓后权益/settled=1050，次日仍1050，持仓腿与交易腿相抵正确。
- 整批只有overlay报价：此前super.on_bars空signal早return导致1000不变、却推进last_close而永久漏+100，本测试曾RED；主代理新增显式EOD估值、settled、positions/date边界后GREEN。

同时只读核对：实际持仓发现覆盖缺bar旧仓；并发实际产品与pending集合去重；产品级开新闸门、close优先且实际可平方向/数量校验；opening_equity/open_risk_prices来自当日open与昨日结算，仅扣真实执行成本；rollover释放后重新施加actual total/cluster保证金下界。overlay加载验证CSV哈希、execution_only/allow_new_open标记、clean键不重叠，绑定133条映射到本次合约的记录；信号bars剔overlay，估值报价独立补持仓腿，EOD再推进overlay last_close，语义一致。

**当前意见：未发现需要阻塞 v3 独立研究回放的已证实执行缺陷，可在冻结代码与新run_id下启动。** 这是对研究回放前置条件的限定结论，不是所有潜在bug已消除的证明，不是有效绩效或实盘资格认证。v1/v2继续保留失败身份与metrics invalid；FB等缺真实平仓/到期结算证据的残仓继续显式冻结估值与占用，不可伪造成交、删除或用净仓抵消。v3若计算走完整区间，仍要另行独立复核结果、数据、逐笔守恒与残仓对有效性/置信度的影响。

结束反思：本轮不涉及alpha调参，未增加过拟合；通用执行与会计修复仍有继续价值。不要把修复结果当作策略优化或收益改善证据。


## 第四轮：v3 金融回放失败独立审查（2026-10-18 17:29 CST）

v3路径：`outputs/run_20261018_daily_proxy_v3/`；已只读核对protocol、code-start hash文件、engine.log与failure_snapshot。失败日 `2015-07-30`，完整回测仍为0，financial_metrics_valid=false；本审查未金融重跑。

`engine.log` 的精确异常为 `intraday_unmatched_open_fill:BACKTESTING.134`，命中Stage827 `_sync_open_trade` **line199**，条件为state缺失或state.direction与真实fill方向不符，**不是line205的层日期/可同步数量不足**。上次补signal身份后严格同步暴露了原先被静默跳过的无效开仓意图；不应通过恢复静默跳过或伪造layer来消除报错。

`failure_snapshot.json` 日期正确但snapshot为空，只保存了金融无效标记。现有artifact不足以确认具体品种/原始信号/当时target以及哪一次重挂产生该实际订单，不能把推断当作完整历史法证。通用代码路径已确认：native `_reconcile_state_with_position(current_pos=0)` 可reset state.layers，却不清target_data；随后rebalance仍可能按残留target重发open。最新fill路径会先修改pos_data/费用再被严格sync拒绝，因此失败进程内还可能存在半完成成交状态，绝不能计算绩效。

独立在 `test_stage009_execution_regressions.py` 新增2类行为回归并观察RED：

- 无匹配有效pending layer（空state、方向错、已同步layer）时，旧实现均先把实际pos从0改1；预期应撮合前拒绝、target归0、活动订单取消且无交易记录。严格唯一层的歧义也作为拒绝边界加入。
- 有效一手layer原始信号为2019-04-01，重挂order.datetime为2019-04-02，2019-04-03次日fill120：旧实现按重挂日期同步失败，layer仍100；预期使用唯一未同步layer.entry_date作为signal_datetime，同时保留order_reissue_datetime=2019-04-02，不任意挑多个候选层。

首次新增RED执行结果：原7项PASS，新增失效意图3个subcase和重挂身份1项为预期断言FAIL（Ran9，failures4，无fixture error）。在此之后补入严格唯一歧义与撤活动单断言，等待root修实现后统一GREEN验证。本审查只修改独立测试与本报告。

修复边界：应在真实候选撮合前验证state.contract、direction及唯一未同步一手layer，拒绝标记stale_open_intent并清target/取消订单，不能重建假layer；有效重挂需保留原signal与重挂时间两个身份。随后重新运行全部本线人工回归，使用新run_id才可再金融回放。建议通用异常快照增加current_fill_order、其产品state/target与实际仓，避免下次仍空snapshot。此项是证据质量建议，不授权新的金融重跑。

本轮开始/结束过拟合判断均为否：处理订单状态守恒，不优化收益或筛选品种。继续价值为是：严格同步暴露新的执行缺陷必须闭合；在该缺口修复和GREEN前，应阻塞下一次金融回放。


## 第五轮：v3 后开仓意图修复独立复核（2026-10-18 17:31 CST）

独立再次执行本线完整人工测试发现命令，结果 **Ran 37 tests in 1.535s，OK**，没有金融回放。此前RED的两类新增回归现在GREEN：失效open四个subcase（空state、方向不匹配、已同步layer、多个未同步layer歧义）全部在实际仓位变更前阻止、清残留target且移除活动订单；有效一手重挂保留原layer信号日期与order_reissue_datetime两个身份，实际entry_price同步为fill120。

只读实现核验：`pending_open_layer` 要求state合约匹配、方向匹配、且恰有一个未同步一手layer；真实研究候选的撮合器在调用parent fill前校验，失效者记stale_open_intent、set_target=0并调用cancel_order，不重建假layer。FeeStrategy.update_trade对有效open从该唯一层绑定signal_datetime，保留重挂时间并复用Stage827严格同步。generic fill异常快照新增order（身份/合约/方向/offset/手数/日期）、实际positions与states/layers，避免v3同类异常只留下空snapshot。

**当前限定结论：此前已证实的v3开仓意图缺口已被人工回归覆盖并通过，当前未发现需要阻塞v4独立研究回放的已证实剩余缺陷；可以冻结新代码，以新run_id继续。** v1/v2/v3继续保留失败身份，不应被新代码或新结果覆盖。该结论仅允许研究回放，不宣称已完成金融回测、已证明有效收益或生产资格。v4完成后须由新的独立结果审查者核对真实数据、逐笔路径、双账本、约束与残仓边界。

开始/结束反思：无alpha调参，无新增过拟合；修复跨时点订单意图身份与实际仓位守恒仍有继续价值。本轮只运行合成/契约测试并追加本记录，未修改实现、冻结数据或金融结果。
