# Stage130：EMA限价扫描与共同heap组件

- 时间：2026-10-18 09:30 CST；line_id=`futures_trend_triple_screen`；是否重要突破：否。
- 严格限于Stage127 Task3。已先读registry、Stage124/125/126/127、128实施ledger、TDD及必要028/native源码。只新增本文、两个127 engine源码/测试文件及本stage证据；不改旧组件、LINE、registry、ledger、其他线、根总账或Git。
- 调研判断：沿Stage124/125已核作者官网、原著及GitHub限价实现资料；本任务依root边界未重复联网。现有公开资料能支持透明限价近似，不能证明真实queue或唯一Elder算法；本组件固定124定义，不改变参数求盈利。
- 开始新增过拟合判断：**否**，未知B收益下只实现已冻结的单一口径，不读取真实金融结果、不扫参数。开始继续价值：**是**，有限反例可直接证伪价格、DAY、量与首bar因果，不证明alpha。

## 实际变更

新增`tools/stage127_ema_limit_engine.py`：`limit_context(item,frame,*,tick,policy='primary')`、`entry_minute_view(frame,*,entry_time,fill_price,direction,intrabar)`及`build_ema_engine(native_engine,*,qualify,policy='primary')`。没有金融入口、模型、runner或PnL实现。

扫描先验证传入D全部分钟OHLC及有限非负volume，再按严格一tick和`floor(V)>=q`选第一个主口径分钟。触L或量不足继续等；非法量即使位于早期合格分钟之后也失败。open改善使用十进制合法tick向不利侧舍入，仍须在原OHLC可达且不超L，不能clamp造价，不调用stop_fill决定初开。执行tick必须等于u冻结值且L为合法tick。

固定悲观口径只让首合格分钟成为观察，再看紧接下一真实分钟；失败不找第三次，DAY末不延到下一D。下一分钟以限价内最不利合法可达tick成交，多取`floor(min(L,high)/tick)*tick`，空镜像。悲观入场统一按intrabar屏蔽有利极值；不声称其保护极值真实发生在fill之后。

私有view只改唯一入场分钟：多open/high=F、close=min(raw close,F)，low保留；空镜像。原始DataFrame保持不变，开盘改善时保留完整bar。Task4必须把同一view接即时风险与holding两个consumer，本Task未替其宣告接合。

factory先调用完整D资格callback，沿原session grid/entry_session检查全session后scan；复用827共同heap的ordinary/EMA/synthetic稳定serial及真实`_fill_order`/物理时钟。只有pop时激活和建初开单，未成只审计DAY机会/冻结资源，不建layer/费用或回收预算。signed风险合法才计算R；错侧保留signed距离、R=None和实际margin元数据，后续紧急保护由Task4承担。没有在此另造stop或retry。

## RED→GREEN与有限证据

仅一个具名组合测试`test_limit_scan_volume_day_end_and_private_view`。RED真实命令：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage127_ema_limit_engine.py -k test_limit_scan_volume_day_end_and_private_view -v`，chunk `ecd140`、exit1：新limit_context尚不存在，明确断言`Stage127 EMA limit scan is not implemented`失败，非依赖环境错误。

相同命令GREEN：chunk `7e2ee9`、exit0，`Ran 1 test ... OK`。真实反例断言：触L无fill、V<q无fill、D后段非法V仍fail、长/短open改善F=99/101且限价100、无法到达合法tick则fail、0.1 tick严格边界、多空悲观最不利价、下一分钟失败不救第三次、D最后minute不跨D、长view `[100,100,99,100]`与空view `[100,101,100,100]`及raw逐表不变。测试仅tiny内存fixture；独立测试进程将原configure_runtime的OUTPUT临时改到TemporaryDirectory后配置冻结数值环境，无旧输出写入。

必要compile一次：`PYTHONPYCACHEPREFIX=/private/tmp/stage130_ema_limit_pycache .py311/bin/python -m py_compile research/lines/futures_trend_triple_screen/tools/stage127_ema_limit_engine.py research/lines/futures_trend_triple_screen/tools/test_stage127_ema_limit_engine.py`，chunk `f572cc`、exit0。按root任务边界未运行旧suite、旧prepare、真实native财务或Task4两组测试。完整真实输出保留`outputs/stage130_ema_limit_engine_component/{red,green,compile}.log`及`implementation_receipt.json`。

源码SHA：engine `1a8bc7412e4fd954591890b2ce0c9b2efd9e823c8e2bdc7a0bd22862356414f6`；test `85576d74a4825bbee239707729cc3a1e1261cde203a4d140b61c0a4a4ce0202b`。

## Task4交接契约与限制

- engine消费`strategy.ts_pending_intents`，调用`ts_activate_intent(item,F)`、`ts_commit_fill(item,D,order_id,context)`；这些方法由Task2/4实现，不由engine偷换状态/身份。
- 真实`_fill_order`之前，以真实native order ID为键向`strategy.ema_limit_order_contexts`和`strategy.ts_conditional_orders`注入同一context，并向临时`engine._stage827_order_contexts`放context。诊断在update_trade内部发生，因此Task4可在任何abs之前读取`stop_side_valid/invalid_stop_side_gap/signed_risk_price`；错侧`actual_risk_price/per_contract/amount=None`。
- context还含mechanism/epoch/setup/intent、signal_day=u、trading_date/physical execution=D、policy、L/F/tick/q、原`entry_minute`及`raw_minute_close`、预测/实际margin与合法侧风险。`run_id`取item.run_id或strategy.ema_limit_run_id；若无真实独立run_id，`economic_mother_id=None`，绝不借B owner。绑定存在时母ID为`mechanism/run_id/intent_id/native_order_id`。
- Task4的fill commit持久化entry metadata供当日holding consumer，并用本view同时处理两个consumer；临时minute映射必须由其hook的try/finally恢复。engine自身不改minute/cache，异常finally恢复共同heap/context，不删除已填的真实成交证据。
- 资格callback必须确认完整D来源及volume单边手数口径；本scanner不是来源资格自授工具。V>=q只是总量必要条件，全量成交/排队均为研究假设。真实来源、queue、native成本/母链、错侧保护、retry、双consumer实际接合均待Task4/后续独立审查。

新增/修改/删除策略参数均0；新增/修改/删除回测结果均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。`fixture_only=true, financial_replays=0, model_calls=0, provider_calls=0, network_calls=0, real_order_api_calls=0, production_qualified=false`。不读B目录/PnL，不触碰session47648、credentials、provider、进程或全历史数据。

结束新增过拟合判断：**否**，全部反例为已冻结语义，未选择历史路径或收益；历史研究选择偏差仍存在。继续价值：**是，限Task4真实接合及root一次整体独立审查**；Task3通过不等于金融readiness、真实流动性证明或目标完成。
