# Stage016 周线19执行与治理消费者候选

- line_id：`futures_weekly_short_ma_slope_gate`；当前模式：day。
- 记录时间：2026-10-31 16:41（北京时间）。工作区：`/Users/mac/.codex/worktrees/weekly19-official-20261031/fian`；分支 `codex/weekly19-official-20261031`。
- 阶段性质：固定 Stage014 C_R150 的工程迁移，不运行金融回测。是否重要突破：否；是否触发A/B：否，未调整alpha或风险参数。
- 状态：`EXECUTION_CANDIDATE_FOR_INDEPENDENT_REVIEW`，`production_qualified=false`。用户部署授权不代替经济门或真实生产资格。

## 外部调研与判断

已读取执行SOP、冻结发行Skill、实施计划和runtime设计。检索并打开了 VeighNa 官方 GitHub 的 [OffsetConverter](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/converter.py) 与 [Portfolio StrategyTemplate](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py)。判断：继续复用现有物理订单、SHFE/INE offset转换、幂等账本、锁、水位、FAK开仓/GFD平仓、撤单和真实成交回报链；不用网上当前版本替换本机已冻结依赖，不重写简化sender。周信号与执行时MD quote的identity必须分别保存。

## 本次变更与消费者清单

1. `qmt_roll_official_execution_profile.py` 注册 `weekly19-15w-r150k`，version/ruleset为manifest所列，交易初资150000、label15w、严格sources仅 `weekly19_pending_order` / `weekly19_risk_reduce`。`decision_mode=weekly19` 显式分流；C9/Stage372保持显式历史兼容。正式默认最后由root统一切换，当前本阶段不修改top formal config。
2. 新 `qmt_roll_weekly19_execution.py`：全部open必须有原资金模块确认、fresh account/positions/orders同generation、E>0、当前原规则risk proof、真实Available与broker margin、fresh quote/session/metadata。原规则重算只向下cap计划手数。缺资金不阻断真实仓位的close/reduce；close仍验证实际仓位/可用手数、报价、会话和未终结委托。旧release/profile/C9 retry/intraday metadata拒绝。roll新仓须旧仓实际完整成交raw SHA证明、唯一trade ID和晚于fill的旧仓flat查询，不能凭target=0释放资金。
3. Stage905 weekly分支不读取Stage904/Stage260/C9历史CSV；产标准OrderRequest并绑定周信号/资金revision/receipt/release。Stage931明确weekly metadata合同，普通once路径拒绝weekly，warm复用原可靠性栈，process-local fresh provider和durable event consumer缺失时在任何CTP创建前拒绝。API-slot/native-child前再闸门；仅同真实lease、payload、token的无native reservation可继续，send/fill/unknown不能豁免。实际回报必须获得周线durable consumer回执，否则transport/readiness失效。
4. 新 `qmt_roll_weekly19_quote_spool.py`：从真实framed MD journal读取并验证header/hash-chain/commit/cursor，保留Friday `signal_identity`，用当前session真实quote构造25s执行trace；新增 `weekly19_quote_admitted`，不伪造 `stage904_detected`。`planned_intent_id`与 `W19EXEC-*` delivery ID分离，原CAS事务内阻止同native信号跨quote重复发送；真实无native过期或known-zero close才能重新交付。未知/发送/成交状态保持阻断。原SQL schema不变，仅旧timestamp列按weekly source解释为新stage，公开trace/observation不冒称C9 detector。
5. Spool新增显式weekly snapshot authority，必须consumer_id=weekly19，拒绝旧profile intent/cursor；原C9默认合同保持。读回重新校验原MD字节。跨feed须真实 `feed_rollover_evidence`，不伪造旧feed闭止证明。
6. Stage930 weekly显式转发独立CLI，禁止旧tick detector/AI startup；Stage945/947复用原7个Stage948-owned控制面label，实际转发root新CLI与profile/context/release/qualification。945精确透传day/night、原duration与授权session角色，持续service/heartbeat由root CLI执行，不能一次cycle成功退出。Stage946/948及production qualification/manifest身份按受控轻量配置解析；支持weekly但缺真实qualification仍阻断。
7. `PRODUCTION_REQUIRED_TEST_SUITES`与critical files加入weekly执行、资金、quote/spool测试与源码。root负责的真实pipeline、邮件、轻量正式身份、weekly独立daily receipt、最终不可变release未在此组件内冒充完成。

## 接口与日名义

- `evaluate_intent(intent, context, now=aware_datetime)` 返回 `weekly19.execution-gate.v1`，allowed仅表示对应纯闸门通过，始终 `production_qualified=false/order_api_called_count=0`。
- context：material_release_id/account_fingerprint/target_cutoff_date（已完成source日）/trading_date（执行名义日）/cold_start_date/data_receipt_sha256/confirmed_cash_state/broker_snapshot/quote/metadata/session/completed_close_intents/execution_ledger_rows；open另需 `open_risk_proof` 和 `durable_state_sha256`。
- broker_snapshot由独立raw SHA envelope的account/positions/orders组成；同generation、完整查询、fresh时点，不把positions包装成account callback。quote允许symbol/vt_symbol兼容名，同时存在必须相同。
- decision.trading_date、intent.target_date/completed_target_date与receipt target_cutoff_date是已完成行情日，例如Friday；intent.trading_date/next_execution_day、broker TradingDay和quote/session可为Friday夜盘归属的Monday。daily风险来源日不得用上周completed_week_end替代。
- 原风险proof必须由 `runtime.revalidate_open_intent(original plannedID, same broker/account/quote)` 产生，匹配真实Equity/Available、account raw SHA、quote SHA/session、资金revision、原行情receipt与durable state。邮件建议/备用余额不增加真实E或Available。
- `prepare_weekly19_quote_intent`、`commit_weekly19_quote_batch` 和 `spool.snapshot_authorizable_intents(... execution_profile='weekly19-15w-r150k')` 提供标准preparedrow/CAS/candidate。root slow_controller签发候选精准授权，不能冒称旧Stage903/927通过。
- warm接口：`run_serve(args, weekly19_context_provider=..., weekly19_event_consumer=...)`；provider可读同连接完成的raw query epochs和真实lease，不应在最终API-slot水位已冻结后自行发新CTP query；event consumer必须raw capture并调用runtime真实fill/update与durable store，返回applied/duplicate和state SHA。

## 验证与证据

测试日志和当前源码SHA见 `20261031_stage016_execution_candidate_manifest.json`。已完成定向回归记录包括467 tests、789 tests；最终准确次数/耗时以各日志 `Ran ... / OK` 为准，另有本轮session参数专项测试。CLI参数拒绝测试会打印usage，这是预期negative fixture；没有真实SMTP、CTP、委托或launchctl操作。

测试发现并修复了：False profile误入Stage372；weekly持仓epoch被当C9拒绝；旧C9 artifact/trace路径；缺原风险重算仍开仓；同原生信号跨quote重复排队；spool读回不验原MD字节；当前无native reservation自阻。全部使用先失败再实现的定向测试。本阶段没有修改原Stage014冻结树、生产树、Git index/commit或远端。最早的缺provider测试曾进入旧无提交prewarm循环，立即终止且新增防重现guard；未连接CTP/发送订单。

## 财务指标与结论

新增/修改/删除回测结果：均无。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。原Stage014 C_R150的NO_PROMOTION、51/54盈利、5耗尽、37 margin压力和手续费0限制保持原样，未提升金融置信度。

本阶段可交给root接入真实pipeline并做独立整分支review，但不代表正式迁移完成。真实provider、source-bound selected suite/readonly capture、独立review、immutable release/qualification/activation、master读回和Stage948原子安装仍由root完成；缺任何一项保持failclosed。当前正式default切换后的selected suite须重新验证，不能把旧C9默认时的绿色测试称为切换后的资格。

## 反思与合入

运行前/后过拟合判断：本工程迁移否，不筛参数、不跑收益寻优；原历史选择/手续费/压力限制仍存在。运行前/后继续价值：是，真实资金、原风险重算、持仓恢复、信号/quote双identity、异步换月与可达spool是固定策略正确执行的必要条件。只写本stage与component manifest，不改同线LINE、registry或根memory/back_log，交root统一合入。
