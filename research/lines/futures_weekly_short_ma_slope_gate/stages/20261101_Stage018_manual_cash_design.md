# Stage018 人工核验资金模式设计

时间：2026-11-01；line_id=futures_weekly_short_ma_slope_gate。根据Stage017及本轮授权，取消自动final statement解析、自动银行流水/到账producer作为前置，核验责任由operator承担。本阶段不CTP连接、不SMTP、不转资/委托、不Git/index；11月2日09:00前不试真实CTP。没有策略参数优化或金融回测，过拟合判断为否，继续价值为是：把用户人工职责接入可操作且诚实的现金账。

## 身份、模式与范围

保留external-funding.v2和旧自动来源历史兼容，不改m0001或历史证据。新m0002必须显式配置cash_verification_mode=operator_manual_v1；该字段和manual_cash_review_root属于immutable context，仅cash_sources引用列表可变。自动兼容模式另名broker_automatic_v1；缺mode在新生产现金流程给出清楚pending，不能靠preview/qualified布尔值开门。profile/version/ruleset/alpha/MRO暂不变，root负责新release、critical/suite/controller required闭包和全局SOP。

实际E、Available、持仓、订单、报价、metadata/session仍来自原有source-qualified fresh CTP链。人工记录仅确认外部现金事实，不生成broker自动HMAC，不设置source_qualified/production_qualified=true，不从Balance差推Transfer，不改原生broker envelope/权益/Profit。Manual review不授权订单。

## 单一原子人工review

新增funding纯API apply_operator_cash_review(state, review_envelope, current_broker, now, *, trading_calendar)。只返回新资金state，仍由原PipelineStateStore+runtime actor一CAS持久化；私有CLI不直接改活跃bundle或孤立FundingStore，从而避免actor/store分叉。

review schema=weekly19.operator-cash-review.v1，source_kind=operator_manual。包含：

- record_id、operator_id、OS uid/user、明确人工确认文本、notes、created_at/expires_at（受理窗口最多30分钟；不是长期开仓许可）。
- account_key/material_release_id、原funding revision、原cashflow_checkpoint及其SHA、原confirmed_topup_fen/reserve_remaining_fen。
- reviewed_account：当时实际读取的CTP账户raw SHA envelope；实际E/Available不用此记录覆盖。消费时当前CTP仍须fresh，同账号release、同TradingDay、Deposit/Withdraw与人审原快照一致，observed_at不早于原快照；允许现金计数未变的后续真实查询generation，不要求人每30秒重复确认。
- topups：每笔唯一receipt_id、原request_id、integer amount_fen、实际occurred_at和名义TradingDay；原request的Friday/全部admission IDs/data source SHA由CLI从真实state复制并精确绑定，不让人填另一个信号冒充原批次。
- closed_days：从现有checkpoint TradingDay到当前CTP TradingDay之间，按已验交易日历恰好覆盖的所有已闭日；每项人工确认final Deposit/Withdraw（integer fen）、closed_at、statement_reference（人工可读核对参考）。它们标记为operator_manual，不伪造closing CTP callback或vendor finality。
- expected_reserve_remaining_fen：用户核对的扣减后真正场外余额，必须等于原R减本次确认的真实到账T；no_unlisted_cashflows=true明确完整人工审核责任。

同一day可只有topups/明确提现核对；跨day可一次review同时核对闭日和当前已经到账的款，不强求自动final statement或曾抓到零Deposit的新日opening callback。闭日Deposit必须等于该日起点已知Deposit加本review明确归属该日的topups；跨过的中间日从0起，当前实际Deposit也须等于本review该日的topups；任何多出/少掉的Deposit不自动推T。Withdraw按用户明确审核的gross数记录，但绝不补回R、冲减T或标为Profit。

closed_at需在相应历史checkpoint后、当前实际账户观测前；人工记录created_at是今天的审核时间，不冒充历史券商callback时点。跨日day_roll留独立operator_manual provenance以及完整review SHA；following checkpoint保留当前真实CTP实际Deposit/Withdraw，可为已明确核对的非零值。原broker自动分支仍保持零现金流opening原约束，不放宽旧来源。

## 现金守恒与幂等

所有金额strict integer fen。0<=T<=15000000，R+T=15000000；每笔>0、不得超原request未确认余额/R，账户/release/request/admission/source/nom义日/时序必须精确绑定。仍拒retired或过期原request的late cashflow，提示专门人工对账，不静默重归另一offer。建议非欠款；E已恢复15万不强迫补旧建议；Friday同source全原始信号批已有确认T后不创建额外offer，沿用既有helper。

新state新增可选manual_cash_reviews append-only audit ledger。manual receipts/day_roll明示operator_manual并回链该review；旧自动receipt格式不重写。Funding.validate_state与FundingStore._forward_ledger检查review/hash/总额/receipt/dayroll相互覆盖、旧记录不可删改、R/T不可回滚。提现不回补R，纯日切不改变T。

record_id重复且原bytes相同只重读，不二次扣R；同id不同bytes拒绝。已消费记录不因30分钟受理窗口过去而抹掉历史事实，但仍需当前fresh CTP和cashflow_match；任何新Deposit/Withdraw/新TradingDay需要新review。未消费记录过期、原现金baseline改变、原R/T改变或当前现金计数变化均可读pending要求重新核验；绝不silent renew或假ready。

## 最小私有CLI/记录入口

新增qmt_roll_weekly19_manual_cash.py和run_qmt_roll_weekly19_manual_cash.py。CLI仅使用本地已保存的真实CTP证据，不connect/query、不加载银行凭证、不调用SMTP/order。

- status：读取原生产链、private context、PipelineStateStore、现有source-qualified broker snapshot，输出当前checkpoint/actual TradingDay、待核对原因、原request/剩余R（不打印凭证/raw账号）。
- confirm：--review-input指向owner0600的人工输入JSON；--operator-id/--review-id/--confirm固定人工确认文本。先读取/验证真实state与broker，再复制原request/source绑定并运行纯apply验证。通过后将完整review原子写到配置的checkout外700目录下600 immutable文件；最后按原context CAS锁只追加cash_sources.manual_reviews的path+sha256，保留并发其他cashrefs。写文件不等于资金已经更新；输出record_written_pending_actor_consumption。
- 重复同review_id不得改bytes或续期；发现已存在记录则核对原语义后复用，不能重复到账。CLI不生成新的原生信号，不修改AM或原decision_snapshot。

Backend显式manual分支按refs顺序装载private记录，调用纯API。缺review且cash已变化/日切时返回原资金及可读manual_cash_review_pending:<reason>；同actor其余实际仓位/减风险处理继续，资金等待不得伪造自动完成。无现金变化的已对账账户不要求每个poll再人工确认。

## 实施/测试边界

先TDD：同日部分/全额到账、未知Deposit/withdraw、无Balance变化推T、R/T守恒/150k上限、重复/冲突/跨账号release/request/admission、过期/未来/stale/late retired、现金计数未变后续generation、Friday→Monday正常/假日多闭日与当日已到账、完整日历/闭日缺项、原自动历史不放宽、E恢复/整批不重复T、FundingStore CAS/前向保护、Backend人工pending/sourcequalified门、CLI private/atomic/ref-CAS及活跃actor不直接写。均为条件fixtures，无真实CTP/SMTP/转资。完成交root独审和全局新release，不以作者单测冒充真实生产资格。
