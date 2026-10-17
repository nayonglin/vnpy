# Stage031：仅修复真实成交身份导出与完整账户checkpoint

- line_id：futures_trend_triple_screen；2026-10-18T03:02:40.632193+08:00。
- Stage028 C_TS attempt1进程67762已真实terminal exit1，失败时间2026-10-18 02:58:52.921424+08:00；error=ValueError('execution_clock_identity_unmapped:signal_datetime')。引擎返回且barfailures为空，随后clock身份检查失败；不能报完整金融结果。总attempt6，accepted完成2，模型0，当前生产false。
- 独立代码/金融失败审查已分别确认两个P1：synthetic usage生产者schema未承诺signal_datetime/signal_order_id；以及导出前无完整raw durable checkpoint。原028前置审查未覆盖该producer/consumer组合，其0P1不覆盖现已证实缺陷；旧receipt不改。
- 失败目录没有combined/frames/capture trades/usage/equity或任何旁路完整账本，只有100条件fill无法恢复金融结果；不从A0或部分信号补造PnL。必要新attempt明确计数，绝不覆盖旧失败或假称原进程恢复。

## 单一修正合同（新收益前）

1. 新runner tools/stage031_run_ordered_checkpoint.py从已冻结028复制，使用独立outputs/stage031_ordered_account/C_TS；实验arm仍C_TS、attempt明确2。旧028/strategy/engine/021—029和失败输出不修改。native q/S、准备/trigger、AI、成本、holding全部不变；新策略/引擎SHA仍d4f870.../f7d745...，不因失败改alpha。
2. 结果身份优先读取实际TradeData显式signal_datetime/signal_order_id，并持久化；usage中存在的身份必须与之相等。合法synthetic usage缺字段不是错误，但其intraday_episode_id必须唯一关联实际母OPEN成交，合约/交易日/时间先后一致；普通缺身份、缺母、重复、冲突仍fail-closed，不用synthetic自身orderid或执行时间伪造signal。
3. _run_live_c9完整返回后、任何导出检查之前，原子保存raw combined、全部frames、完整capture trades/usage/equity/minute/anchor、实际TradeData身份、ordered、actualsettings、effectiveparams、spec/preflight/input指纹及运行上下文。采用本机自生成受SHA绑定的durable checkpoint；无外部pickle，未经身份校验不得反序列化。checkpoint初始只是raw证据，不表示经济合格。
4. 全日期/零吞错/分钟完整/actualparams等固有验证与输入未变检查通过后签engine validation seal，精确绑定checkpoint SHA；然后纯后处理导出。新CLI --export-only只允许本次已sealed自有checkpoint，禁止调用_run_live_c9/建engine/下载，拒覆盖已有成功结果，允许失败后仅重导出到新结果范围并保留原错误记录。这个能力用一个小型持久化后模拟失败的fixture验证，不再重复引擎/FI旧suite。
5. 新attempt复用两项已独立资格anchor：原2026cu2609及本次2020OI009；只授各自一key anchor权利，不扩大fullsession，不重下。OI receipt09444de4ec525a874b5f03caacfe0742836c3a4f8b4d6ba0aec0eea69d1303fa及真实provider terminal16.820751秒保留。
6. 本次必要回放前只补该真实synthetic→runner身份组合反例RED/GREEN与checkpoint失败恢复fixture；独立agent复核仅新delta，无需重跑26旧tests/全FI/所有旧源资格。新run内联原preflight，A0不重跑。actual终态与完整账本后仍需独立经济审查。

本协议无新金融结果，所有绩效N/A。不是重要突破，正式参数新增/修改/删除0。调研沿Backtrader/GitHub真实订单语义与本地827显式producer；此次根因以真实source/失败证据为准，不以收益选择。过拟合前后否，本次不改交易规则；继续价值是，可信完整资金路径仍缺，修正后尽快单次闭环。总体更高收益且更低回撤目标保持active。
