# Stage016 周线19品种正式迁移合同

## 用户决定与授权

用户已明确替换当前正式实盘策略、推进master及生产安装；找到本机生产目录后替换，保留已有历史；15万备用金真正场外，每周五下午信号邮件计算说明需补资金额。目标候选稳定目录/Users/mac/Desktop/person/vnpy_production_live；原HEAD d55887e1def72629fbfa310e439dc3a879969a14，ahead远端8提交，完整保留。原Stage014冻结树只读；新源分支codex/weekly19-official-20261031。本合同执行既有授权，不重复询问同一风险/发布权限。真实委托、银行/期货资金划转未在本次授权内；安装后的既有交易时段/账户/持仓闸门仍生效。

## 不变的策略与材料

对象Stage014 C_R150，交易初资150000、外部备用上限150000，动态风险按交易权益，unused R不计净值/风险/保证金。原19池、无加仓、short同物理epoch available全历史bottom20门，所有MA斜率/long顶部/AI/MACD/0.5R/C2关闭；完整actual settings而非只摘OI比例，原风险1.8%/6%/6%/2.5%、floor1000、其他原风险/换月规则保留。原MRO和逐方法AST/hash保存，不简化重写。原经济判定NO_PROMOTION与51/54盈利、5耗尽、37margin压力、手续费0原样保留；用户要求属于部署决定，不写自然经济门通过。

价格技术保护只在fresh完成周close确认，下一交易日open模型；实盘只依真实成交，不能以模型open伪造价格。每日账户风险、5日换月delay及收缩容量继续运行。0权益不得经or base_capital回退恢复开仓。完整ProductState/PositionLayer、AM、risk、pending ownership与signal identity必须持久化；无历史层的外来实仓只可对账/减仓，不能以今日close重建成本/stop。

## 真实资金和周五邮件

场外R绝不能通过settled_balance+=T进入真实E。有效native flat/reverse候选通过周stop与short range门、父sizing之前才推荐T=min(max(150000-E,0),R)。不要求最终selected_volume>0才推荐（遵原门时点）；无新候选不请求，R用完可按剩余正E继续原规则。邮件分列真实E/浮盈亏/未用R/建议T/拟补资后条件手数；发送不代表入金，未到账不增加E、Available或新仓容量，平仓/减风险继续。

资金组件仅接受原始账户/银行现金流证据字节SHA、account fingerprint、active release、交易日、请求前Deposit/Withdraw基线。上升余额或浮盈不是现金流。部分/重复/超额/跨账户/缺链/乱序/restart必须可判断，失败不部分落地。跨名义交易日（Friday21:00已是Monday）须有完整day-close和零现金流起点/后续真实流水守恒，缺证据阻断，不凭自然日日期臆造。

默认沿本机生产修复的15:10收盘后链路，周五在全部日线/周线就绪且账户读数可核实时发送一份signal/funding邮件；周内仍更新每日风控和换月，但不把C9 AI月更或intraday stop混进候选。权威日历延伸下一ISO周识别节假日完成周，行情严格截至target。每次发送前资格/数据回执/幂等outbox校验；闭市数据或账户不足发明确blocked提示，不发假0补资建议。场外资金若未及时到账，下一可交易session新开保持阻断；夜盘不一律写周一9点。

## 接口和文件边界

资金：qmt_roll_weekly19_funding.py + funding_store.py；initial_state、recommend_topup返回state/recommendation envelope（不修改输入）、confirm_topup返回新state、assert_open_funding_ready、reconcile_trading_day强证据。全部JSON含release/account/source proof，整数分，标准库，无网络。private 0600、lock/CAS/WAL/atomic，failclosed。

策略：qmt_roll_weekly19_runtime.py + weekly19_frozen/；build_weekly19_runtime(settings_asset,metadata,session_calendar,physical_epoch_daily,broker_snapshot,durable_state,confirmed_cash_state)。Runtime.process_completed_day(trading_date,bars,data_receipt,broker_snapshot,confirmed_cash_state)->decision，apply_order_update、apply_broker_fill(fill,signal_identity)、reconcile_broker_snapshot。decision含targets/intents/protection/funding_admitted_ids/state hashes；send/cancel仅生成intent，真实fill才更新pos，broker E唯一权威避免MTM/现金双记账。

执行：新profile key weekly19-15w-r150k；拟官方version official_live_weekly19_base15w_reserve15w_stage014；ruleset stage014_week_close_19_short_bottom20_original_risk_external_reserve_v1。C9/Stage372保留为显式历史profile。new weekly intent sources严格allowlist，旧C9 halfR/retry/AI intents/旧release ledger拒绝。Stage905/927/931/930/945/947/948、qualification、daily receipt/health所有consumer必须声明新profile；不能用intraday_stop_retry_enabled=False误路由Stage372。现有7个Stage948-owned label保留控制面名称，实际profile/argv/material必须精确绑定新策略；不存在第8个手写launchd或Codex心跳替代生产邮件。

发行：prepare仅在干净source；新不可变release、全部decision source/assets/deps与manifest、fresh clone、source-bound selected suite/formal_ctp_readonly/独立review、activation、controlled promote-master/readback/freshclone、Stage948原子安装及六身份一致后才称完成。不得伪造qualified、复用m0008资格给新规则、手改CURRENT绕开工具、force push/reset/stash现有生产8commits或把ignored/private状态提交Git。新的cold-start只接受新激活边界之后的信号，不追历史理论仓；真实broker非空但无同策略完整保护层则保持只减仓/对账。

## 本轮判断与依赖

过拟合：迁移不寻优，但原历史选择风险仍是；继续价值是，资金/stop/重启/执行接线正确性值得完成。当前没有新finance，技术测试只证明对应边界；真实provider、资金/pos/成交恢复、release与CTP只读资格缺失仍须阻断安装。使用现有Python/vn.py版本，不随网上最新版升级。
