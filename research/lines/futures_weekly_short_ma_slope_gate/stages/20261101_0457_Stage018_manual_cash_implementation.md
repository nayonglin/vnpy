# Stage018 人工核验资金模式实施交接

记录时间：2026-11-01 04:57，北京时间；line_id=futures_weekly_short_ma_slope_gate。

本阶段按Stage017实现用户人工核验，不继续开发已取消的自动final statement parser或银行流水/到账producer。所有代码为新m0002候选；未改m0001/历史证据，未操作Git/index、生产、CTP、SMTP、委托或资金。真实CTP仅能在2026-11-02 09:00后由root按授权检查，不能用本记录或条件fixture冒称已安装/激活。

## 实施结果

1. funding公开apply_operator_cash_review(state, envelope, current_broker, now, trading_calendar=...)，保留external-funding.v2与旧自动历史格式。新增可选append-only manual_cash_reviews审计账；receipt/day_roll均明确operator_manual，不生成bank source、HMAC或source_qualified=true。实际Balance/Available不写入或虚增，T只在人工明确确认且gross Deposit守恒/原request/admission绑定时增加，R同步扣减。R+T固定15000000分，strict integer，无提现回补R/冲减T或虚拟Profit。
2. 同次review可覆盖全部已闭交易日及当前已实际到账款。原自动来源仍要求原零现金opening规则；人工分支保存当前真实非零Deposit/Withdraw checkpoint，闭日gross及中间日账目由人工明确核对，不伪造closing CTP callback。每个交易日窗口、gross单调和Deposit/T覆盖同时在apply及持久化validate_state中复核，不能只靠自洽SHA。
3. 30分钟是首次受理窗口，不是长期交易许可。记录绑定原funding revision/SHA/checkpoint/R/T、operator/OS身份、已读CTP raw及原request/全部admission/source；当前真实CTP仍fresh，同现金计数的后续真实generation可以消费。已消费事实永久保留，重复相同bytes不二次扣R；同id异bytes、跨review重复receipt、过期/retired request、当前现金变化或父资金状态改变均拒绝/待重新核验。
4. 新qmt_roll_weekly19_manual_cash.py提供status/prepare/write-and-publish/load-private-record API；root实现专用CLI及runbook。输入字段、容器大小、金额/日期/身份先验，坏JSON不先展开或读source。记录位于checkout外0700目录/0600 owner单链接文件，O_NOFOLLOW；immutable原子落盘后仅CAS追加cash_sources.manual_reviews引用，保留其他并发cashrefs。
5. 私有context必须显式operator_manual_v1且匹配不可变EXECUTION_POLICY，不能用JSON切掉实际账户/持仓/报价/metadata/session/原风险门。旧auto仅历史/preview兼容。Backend先装载验证全部引用，最多一个新review由同actor消费；坏后续ref、null/int/缺path/坏容器均返回原资金和manual_cash_review_pending，不部分入账，也不吞错假ready。
6. CLI不写active bundle。真实既有session bridge调用Backend.reconcile_cash，原runtime actor与funds在PipelineStateStore一CAS提交，原decision/decision_state与AM不重跑不改。缺人审仍保留实际仓位close/reduce独立检查。纯“现金计数已对账”状态不是订单授权，未付建议非债务，E恢复15万不强迫补旧offer；Friday同原始portfolio batch不因另一个native ID重复T。
7. FundingStore真实commit/recover与PipelineStateStore.transact硬编码strict_manual_parent=True，核exact父fundstate且一次最多一个新review。immutable decision-origin→latest只做历史前向验证，可跨两个合法人工部分到账commit；没有把历史检查误当单次CAS，也没有放宽实际写入口。

具体输入/操作顺序见20261101_Stage018_manual_cash_design.md与root的Stage018_operator_manual_cash_runbook.md。prepare/write/status均只读已保存的真实CTP证据，不自行连接查询或转账。

## 独审与补修

- pure资金独审发现“重算SHA后闭日Deposit与T矛盾仍可持久化”，已用共同gross/day-window语义验证器修复；又发现persisted applied_at可越原request expiry，已按实际应用时点重核。旧纯接受证据只属于相应SHA，后续store/history边界另交独审。
- I/O独审发现坏嵌套输入TypeError、record父目录在link后移走仍报published，均保留RED并修输入早验、visible parent/record SHA写前写后复验。root另外修CLI安全兜底，不回显raw/notes或凭证。
- root启动完整90suite attempt001后，独审发现context replace后目录fsync失败的重试分支少了context dir fsync。作者保持LOCK，root精确终止pytest、保存exit -15/无XML/288 critical前后无漂移；该attempt中断且出现未展开F，不得称全绿。收到root许可后仅改existing-ref分支，重做context目录barrier、visible parent和record复验才报published。
- writer首次目录barrier失败明确publication_unconfirmed；重试不续期/不改原bytes、不二次append引用，也不声称资金已由actor消费。funding_consumed=false含义是此CLI未做资金提交，实际消费状态仍由原actor/state查询确认。

## 验证与当前锁源

作者首次最终定向：13套件278项通过/19.032秒，覆盖manual+旧fund/store/pipeline、Backend/CLI、实际warm reader/bridge/同actor原子日切、Friday原批次、执行gate及原native source evidence，均条件fixtures，不是真实生产证明。

最后existing-ref barrier补修：对应case先1 RED；4个受影响套件51项通过/2.254秒。它与原278覆盖重叠，不相加，不宣称原13套件已在新SHA完整重跑。root将对最终源跑新的完整90suite；独审对其独立I/O反例增量复验。

当前owned锁：fund419b8c31…、store07cb5c33…、pipeline7ac40956…、manual bda2ed87…、backend a4b66c5c…、test_manual65bc68e2…。精确SHA、6文件编译/空白检查、日志与原版本关系见20261101_Stage018_manual_cash_author_manifest_v2.json。原manifest保留f6b/278当时快照，不改写。

没有策略参数新增/修改/删除或金融回测结果。期末权益、收益、回撤、Sharpe、滑点、交易数、胜率全部N/A。开始/结束过拟合判断均否，alpha与MRO不变；继续价值为是，人审职责、真实现金守恒和可恢复记录是固定策略可操作部署的必要条件。全局policy/Skill/90suite/new release/资格/Stage948由root接管，真实外部资金核验仍是operator责任，不能称自动broker资格已通过。
