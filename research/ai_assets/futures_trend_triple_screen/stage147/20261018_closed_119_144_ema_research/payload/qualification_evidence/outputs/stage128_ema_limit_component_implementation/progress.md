# SDD ledger — plan: /Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0919_stage127_ema_limit_isolated_implementation_plan.md

时间：2026-10-18 09:25 CST；line_id=futures_trend_triple_screen。

Ruling: 用户已授权root自主离线持续迭代、同分支且可决定多agent；采用root掌握接合、两个独立纯组件并行、完成后一次整体独立审查。仅组件编码/有限fixture，不创建runner/真实臂/readiness或金融启动。
Ruling: scratch/ledger放本研究线outputs内，遵守用户研究线记录位置，不创建worktree或改其他线。B活跃期间HEAD保持4f42805，不git add/commit/push。
Ruling: Stage124/126定义优先，Stage127为实施论证。127定义之外的实质问题先在本ledger记Ruling，不通过看收益选择；不因Minor问题重复旧suite或无限审查。

Pre-flight: Task1产生feature/quote/独立state，Task2消费，字段和签名按127。Task3产生limit context/私有首bar/engine工厂，Task2 lazy接线且Task4消费。Task4同时接Task2/3，以两个真实native组合验证成本/母链/双consumer。Task1/3文件互不共享，可并行。
Pre-flight: 当前B owner.verify仅逐项核其已冻结source_fingerprints和实际PID/argv，不枚举新未引用模块；只新增127文件不改B绑定源。新组件不接入B，不触碰现B运行目录或金融handle。

- Task 1: component_pass — ema_limit_model_impl；Stage129 receipt记录RED925044、边界REDe5af7a、最终GREENa500e1（2方法）、compile76444f。model SHA6568f87ec74bebdb9afa730b3347c5eb52cdf31bd8f3ca3cc9208b1c55c2f7d6。root只读收据，不重复测试。
- Task 2: author_pass_pending_independent_review — ema_limit_model_impl；真实planner GREEN100590，最后与Task4同六方法GREENcc88d0。作者封存Stage131；root不重复测试。
- Task 3: component_pass — ema_limit_engine_impl；Stage130 receipt SHA6de93ed86f434239d405b7684600a7552c510d0d9613281c66db9520edbcba3a，REDecd140→GREEN7e2ee9（1方法）、compilef572cc。engine SHA1a8bc7412e4fd954591890b2ce0c9b2efd9e823c8e2bdc7a0bd22862356414f6；作者已交回engine/test写入权。
- Task 4: author_pass_pending_independent_review — 两个真实RED084b31（错侧进入abs）/8ce5fc（lifetime high泄漏）；最终六方法GREENcc88d0（6 tests/0.289s）/compile9670c0。中间7110e4手算oracle错误已保留，不算实现RED。原engine.py未改，new strategy SHA3aa45d2dba1495dc443d232c58aee8954f5858361516a7a3818270d1a0205ed0。
- Overall review: component_accepted — 新独立ema_limit_overall_review，Stage132 receipt SHA bb4d79bd77a40475e98e0631737bc8b937d64ff609fc6d4771c48e06fd0e640b，P0/P1/P2=0/0/0，六源SHA无漂移。另一次有限独立脚本81bad8 exit0验证完整拒单schema及空方真实holding consumer。作者131 receipt SHA d19e1fd0e2ec539ee50d6fe4d5a36141070b732824632f698883ed081f386ddc。仅组件接受；无金融runner/readiness/alpha或生产资格，当前任务收束，不再重复旧suite/新六方法。

09:31 Ruling：engine以ts_pending_intents/ts_activate_intent/ts_commit_fill兼容原共同heap；pre-fill同时向ema_limit_order_contexts[orderID]和ts_conditional_orders[orderID]写同一context，native接合作者消费此约定。包含signed_risk_price、stop_side_valid、invalid_stop_side_gap、actual_risk_price（错侧None）、raw_minute_close/entry_minute；母ID没有run_id时保持None，不借B身份。Task3作者已封存，Task4取得engine测试追加权限；任何实质撮合/风险定义矛盾先报告root，不按收益选择。

任何任务完成须保留实际RED→GREEN命令/终态与SHA；unit/fixture标financial_replays=0、fixture_only=true。真实全历史特征/数据下载/模型/账户均不运行。当前B由root独占session47648，provider仅原operator管理。

09:33 Ruling：native synthetic CLOSE TradeData不复制context母ID，而原_sync_entry_risk_diagnostic只在OPEN调用；允许Task4新增极窄update_trade override，仅为真实初开/保护/retry TradeData绑定新机制context/母身份审计字段，然后恰调用一次原super经济记账。普通held/roll保持原路径；不得改F、q/R、cash/fee。此为真实母链合同的必要接口补充，不改124撮合与保护定义，不按收益选择；由计划原有两组native组合及一次整体独立审查验证。
