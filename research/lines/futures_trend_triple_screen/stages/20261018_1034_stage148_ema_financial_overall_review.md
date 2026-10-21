# Stage148：固定EMA真实接合唯一整体独立审查

记录时间：2026-10-18 10:34 CST；line_id=`futures_trend_triple_screen`；非重要突破。审查人 `ema_financial_overall_review`；不派子agent。已读registry/LINE、140计划、144采纳、142日线与feature交接、146终态、145最终四方法/六源compile证据，以及 requesting-code-review 的 Senior Code Reviewer 模板。BASE=HEAD=`4f42805c2c71f8492a44a6876a82672f410f44df`；对象是明确路径的真实未提交工作区字节，不以空git diff代表已审查。

## 结论

**当前不能进入真实金融 preflight 接受：With fixes。Critical 0 / Important 4 / Minor 0。** 已接受组件和研究数据资格仍成立；本结论针对新接合。root负责一次RED→GREEN修复pass和最终裁定，不需要第二轮独审或旧suite。本文不签 financial readiness、不生成accepted金融receipt、不恢复失败B。真实累计仍11 attempts / 4完整独立accepted，训练0。

## 已做好的部分与实际证据

- Stage142 `review_and_build.py` 已完整独立阅读：先同源DB无损资格，再调用已接受127两公开函数各一次；日历按真实合约分组且缺口重暖由原模型保持；零V与真实合约末行保留。u已知D的LC tick切换明确；29末日无后继D行不可下单。全部keys仅在manifest存一份，未复制到每特征行。本次没有重hash DB、重建EMA或重认证全部历史价。
- `check_142_handoff.py` 实际chunk `bc9429` exit0：manifest `3edc7569…7c28`、features `d9d8fa95…1245`、handoff `272db526…250b`、127与132绑定一致；116394行/96813 ready、12有限输出样本和29末日行符合交接。不能把这说成全市场独立重新定价。
- 新minute scope源码与tiny实际loader组合覆盖原层→016→两anchor→190→071隔离→159，完成keys未提前借159给旧859资格；分别compose新增物理keys的full/anchor权限，并有finally还原。旧190没有重存。
- `capture_ema`在add_strategy后、首bar前注入run_id，沿真实native TradeData保存mechanism/mother；原0.5R及retry、错侧gap保护、普通held-roll仍走真实native。raw在引擎完整返回后先保存，再核日历/settings/参数/输入，后seal/export。export-only dispatch先于prepare，导出失败从同raw恢复而不是重跑。
- `_algorithms`确实从固定095 AST提取原数学，调用原030库存/母链与033身份/序列化，不靠贴旧B标签冒充独审。held-roll、gap、合法retry越L、现金及成本在同一native fixture中实际覆盖。
- 145最终 `final_combined_command.json`：2026-10-18 10:30:47—10:31:07，4 tests / 0 failures / 0 errors，compile6；tool session59677，chunk33b042→78e21a。146离线三代PID/runtime真实执行，SDK3.10.2及冻结数值路径/endpoint检查到凭证读取前停止。本人没有重复该套测试。最终六源SHA再次核对，chunk `4d30b2` exit0，均与GREEN证据一致。

## Important（一次修复后再由root决定进入）

### I1：真实142 thin-reader与已接受产物合同不兼容

文件：`tools/stage140_run_ema_account.py:61–64,94`。

142资格文件的`source_bindings`实际为 `{absolute_path: sha256_string}`，reader却用`item['sha256']`。真实manifest/receipt调用在首个源检查直接抛 `TypeError: string indices must be integers, not 'str'`，无法进入真实preflight。其次，ready只表示26个有效EMA窗口已满；按127 positive-only约定，某一侧positive count为0时mean为None是合法unknown，不可要求ready两侧mean都非None。实际固定142输出中有1548条这种合法记录，即使修好前项也会在94行继续被拒。

最小修复：严格消费实际142字符串绑定（或显式支持被接受的两种结构），保留未知单侧mean，由原127 `limit_quote`按所选方向返回unknown；对有positive count的一侧才要求合法均值。把这个真实固定feature交接路径加入已有组合方法/有限入口验证，不重建EMA、不改原数据和策略参数。

证据：`actual_reader_probe.json`；chunk `f2a73b` exit0，真实reader错误被捕获，DB reads=0，prepare/model/native/provider=0。例：AP101.CZCE/2020-12-30 ready=True，down_count26/mean276.8735，up_count0/mean空。

### I2：外层终止不能收割真实worker子孙

文件：`tools/stage140_ema_wait.py:420–428,846,988`；同一`_invoke`所有嵌套角色均受影响。

每次Popen均`start_new_session=True`；driver→provider与provider→worker成为不同进程组。外层timeout或KeyboardInterrupt只killpg(provider.pid)，真实worker仍可运行；非零父终态也没有清理残余孙进程。原worker的SDK初始化/`api.close`不能靠570秒采集循环软门保证返回，因此原600硬门及“停止后无残留数据连接”不成立。当前三代probe只证明身份传递，没有覆盖异常树清理。

最小修复：让provider及worker在共同可终止的真实进程树约束内，或记录并可靠收割全部后代；保持原570/600/840/1800/7200/4不变。把真实离线父孙进程的timeout/interrupt/nonzero清理反例并入现有owner组合方法；无需凭证/网络。

证据：`process_cleanup_probe.json`；原样提取`_invoke/_environment`，chunk `9184b2` exit0，外层timeout后孙heartbeat仍增加，探针finally已杀掉该测试孙进程。root另有outputs149的三种RED，不属于本人重复review。

### I3：独立EMA证据未闭合决策/数量/风险链

文件：`tools/stage140_independent_ema_review.py:39–92`，相关实际审计入口`:95–145`。

当前检查有效覆盖实际成交价/母ID、穿透/V、负R必须N/A和gross prefix，但不读取decision、不建立setup/intent→budget→execution的完整对应，预算q也未与真实成交q相等；有效R只检查大于0，实际margin不核。140任务4明确要求这些独立证据。它们不是要求重写已接受127或引入排队模型，而是防止一份经济账相等但机制证据缺失/错误的产物被标为EMA独立接受。

最小修复：按真实intent/setup/日期/合约连接原固定决策、budget、fill、execution及实际TradeData，检查唯一消费和DAY边界、冻结L/S/q及各上界、预测与实际risk/margin；复用已固定标量公式和原会计，不产生交易或重算PnL。保留错侧gap R=N/A、合法retry可越L、普通held-roll的现有语义。把下列三种已有fixture反例并入原独审组合方法。

证据：`audit_semantics_probe.json`，chunk `da6f3b` exit0；只读最终已存同一个fixture raw，逐次保持对应export一致并调用现有完整`_audit_payload`：①清空全部decision；②第一budget q改0但仍保留成交3；③合法fill实际risk/margin改999999999。三者均错误接受。没有native/financial/model/network调用。

### I4：账户源码冻结只存SHA，未保存约定的真实源码快照

文件：`tools/stage140_ema_checkpoint.py:104–125,129–139`；140任务2“所有新旧源与测试/协议binding一次freeze并留源快照”。

start_run仅核当前路径并把binding写context，没有原065同类的`source_snapshots`；load_context只能依赖未来仍存在且未变的工作区。当前六源又是未提交新文件，实际金融完成后仅有SHA无法恢复当时源码，削弱已明确要求的失败导出恢复/可复验来源证据。

最小修复：run创建后、首bar前，按预先固定binding复制源码/测试及协议字节到run拥有的快照目录，manifest逐项保存原路径、SHA、bytes、相对快照路径；加载/审计核源快照与binding相等。可以复用原065的有限快照逻辑；不能借旧账户身份。无需复制行情DB、扫描其他研究线或建设通用归档框架。root也可在本轮真实preflight提供等价已绑定不可变源码快照，但须作为实际run/context的可验证资产，不能只写“后续会冻结”。

## Declined to judge（交root逐项裁定，不默默丢弃）

1. 新金融净收益更高且回撤更低、A0/A_OFF双对照、悲观撮合/成本/多起点/生存门：本轮无EMA真实账户，不能判alpha或目标完成。
2. 所有历史OHLCV的外部独立逐值真值、vendor每根bar单边量单位、排队/部分成交：139/143/144已明示仅同源研究资格与V≥q全量近似，不追加全市场重新认证或外搜。
3. 实际凭证之后的SDK鉴权、真实provider网络完成性、实际wait流量及未来sidecar：当前组合测试明确未执行；源码/API审查不冒称网络通过，必须未来真实owner/terminal绑定。
4. 官方production资格、旧机器manifest/activation/CTP/launchd，以及B失败恢复或B2安排：不属于本次新研究接合授权，未操作。
5. 当前固定完整窗口若出现零成交账户的通用导出支持：checkpoint有零成交拒绝，既有任务以固定机制完整证伪为范围；本文不以泛化零成交框架加阻塞，root如认定实际出现时再裁定。

## 变更与反思

本人只新增本Stage148和outputs148脚本/证据，没有改6源、测试、LINE、registry、Git或其他研究线。新增/修改/删除策略参数均0；新增/修改/删除回测结果均0。期末权益/收益/最大回撤/Sharpe/滑点/交易次数/胜率均N/A（本轮未跑金融，fixture经济数字不外推）。

调研沿121/123/138/143已读来源；判断：固定机制值得一次真实证伪，来源与代码通过不等于alpha。开始/结束新增过拟合：**否**，只在收益未知时核固定输入、身份、预算和独立证据，不按PnL救参；既有历史选择偏差仍在。开始/结束继续价值：**是**，四项修复直接决定能否取得完整可复验账户；一次修复到可运行后应进入真实证伪，不继续样式微修或无限审查。
