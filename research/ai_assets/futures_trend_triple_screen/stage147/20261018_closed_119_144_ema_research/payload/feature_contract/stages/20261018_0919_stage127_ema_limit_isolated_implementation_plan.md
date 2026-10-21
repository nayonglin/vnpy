# EMA 穿透限价隔离组件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Stage124/126 已固定的 EMA 限价隔离组件，并用六个有限组合反例证明真实 native 接合；本计划不创建金融入口或启动账户。

**Architecture:** 新增纯 EMA/独立状态、初开定价/策略工厂、限价执行三个模块，保留原035风险 recipe、028共同heap与827/847真实经济记账。工厂输出与065相同形状，但不借用 A_OFF/B_OFF 身份；只复用原无arm限制的 `run_profile_once` 接口形状，不复制 runner/PnL。

**Tech Stack:** `.py311/bin/python`、stdlib/unittest、已冻结 pandas/vn.py/native827/847；无新依赖、训练、网络或provider。

**Spec:** [Stage124](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0902_stage124_ema_penetration_limit_proposed_design.md)，SHA `28b584b28fab94f36dfb0368dea04980b1b26a9b7123abcab2103128d7070d33`；[Stage125](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0911_stage125_ema_penetration_design_independent_review.md) receipt `b449d89db5dc7b5c85b68a72be72331d8a9e51af39c4a794ed2b012dd3f7d43d`；[Stage126裁决](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0914_stage126_root_ema_limit_definition_decision.md)。执行者先读三份，不以本计划替换定义。

## Global Constraints

- line_id=`futures_trend_triple_screen`；2026-10-18 09:19 CST；当前分支/HEAD保持，不建worktree。本轮仅新增此计划；下面所有代码、测试和命令均是未来步骤，当前未执行。
- 只新增本线 `tools/` 文件；不改027/028/035/065、native源、模型、行情、正式材料、LINE、registry或别线。B活跃期间不commit、不git add；后续root仅exact add选定文件，不使用 `git add -A`。
- EMA13/SMA13 seed、26有效bar positive-only均值、至少38根连续真实bar、只用u及以前、方向tick舍入、DAY、严格穿透一tick且V≥q；主参数仅这一组。真实目标合约自身未拼接日线，缺口重暖、epoch改变不继承旧价。
- 月度AI10非fu+固定fu、OFF八键、普通filters、原OI/连败风险recipe、slot/margin/gross只缩量/no refill、原持仓/退出/换月不改。初开L/S须 `d*(L-S)>0`；实际F错侧仍真实初开→同母保护close、R=N/A、两边成本各一次、不retry；合法R原retry可越L。
- 收益/DD/Sharpe/生存门和原A0/A_OFF/B_OFF限制沿124。当前唯一B必须先真实终态及完整独立审计；本组件计划、fixture或工厂均不是新金融readiness，不创建正式A/B/C臂或生产资格。

## Review Focus

1. 日线缺口、同一key冲突或hash后重开：拒绝错源/未来泄漏，38bar重新暖机（Task1 `test_formula_source_and_future_poison`）。
2. epoch变更、EMA unknown及过期fill：保留正确准备语义，独立ID且不借B身份（Task1 `test_state_epoch_unknown_and_identity`）。
3. L错误侧、q=0及未成资源：在abs前拒绝、不补位，原gross前缀与reserve次数不漂移（Task2及Task4）。
4. intrabar之前有利H/L/close进入两个consumer：即时0.5R和lifetime均用同一私有保守视图（Task3及Task4）。
5. gap越S、retry越L及DAY末stress：真实native母链/成本，不伪造R、不跨日确认（Task3及Task4）。

---

## 文件与接口地图

所有下列路径均位于 `research/lines/futures_trend_triple_screen/tools/`；仅规划新增：

| 新文件 | 单一责任 |
| --- | --- |
| `stage127_ema_limit_model.py` | 同合约EMA/穿透、日线源绑定、纯准备状态与机制ID |
| `stage127_ema_limit_strategy.py` | L定价/最终预算、初开策略、diagnostic/保护与双consumer接合、无运行工厂 |
| `stage127_ema_limit_engine.py` | 主/固定悲观撮合、私有首分钟视图、028 heap上的limit事件 |
| `test_stage127_ema_limit_model.py` | Task1两个纯组合测试 |
| `test_stage127_ema_limit_strategy.py` | Task2一个真实planner/预算测试 |
| `test_stage127_ema_limit_engine.py` | Task3一个扫描测试，Task4再加两个真实native组合测试 |

共享契约：`MECHANISM_ID='stage124_ema_limit_v1'` 仅为未来代码命名空间，不是现有注册臂。feature含`asof,contract,ready,reason,ema,ema_prev,mean_down,mean_up,positive_down_count,positive_up_count,valid_ema_count,segment_start,source_bindings`；quote再含`direction,limit_price,execution_tick`。intent包含独立`mechanism_id,epoch_id,setup_id,setup_day,intent_id,signal_day,execution_day,product,contract,direction,limit_price,execution_tick,weekly_asof,native_signal,rank`，其中signal_day=u、execution_day=D；另以`trigger=limit_price`兼容031资格callback的既有入参，明确`order_type='limit'`，不能因此调用stop-entry初开撮合。冻结plan沿028原`target_bar/history/sizing/signal_data/volume/rank`结构，新增预测字段统一`ema_limit_*`。经济母ID以`MECHANISM_ID/run_id/intent_id/native_order_id`绑定，native局部trade/order号保留，不能作为跨账户全局身份或借用B owner。

### Task 1：同合约原始特征与独立纯状态

**Files:** Create `stage127_ema_limit_model.py`、`test_stage127_ema_limit_model.py`。

**Interfaces:** `load_bound_daily_csv(path: Path, *, sha256: str, qualified_keys: frozenset[tuple[str,str]], qualifier_sha256: str) -> tuple[list[dict], dict]`；`build_ema_rows(rows: Sequence[Mapping], calendar: Sequence[str], *, source_bindings: Mapping) -> list[dict]`；`limit_quote(feature: Mapping, *, direction: int, execution_tick: float) -> dict | None`；`EmaLimitSetupMachine.on_close(observation: Mapping, quote: Mapping | None) -> dict`、`.cancel(product: str, day: str, reason: str) -> dict`、`.on_fill(intent_id: str, execution_day: str) -> dict`。observation必需键与027 `on_close`相同，`native_signal`固定None；下一任务注入lookup键为`(u,contract)`。

- [ ] 写 `test_formula_source_and_future_poison`：37根不ready、38根ready；正穿透只除正数个数；追加/毒化u之后bar不改变u quote；缺一个应有session后须重新38根。临时CSV只读一次bytes并核SHA，再从同bytes解析，改文件不得被旧SHA接受。
- [ ] 写 `test_state_epoch_unknown_and_identity`：同原周/FI输入生成setup，EMA unknown仅无第三层单；换合约取消旧准备、不能继承E/A/L；未成不消费、过期fill拒绝，真实fill消费一次。外部epoch/setup/intent均带新namespace，与同输入原027的B ID不同。
- [ ] Run RED：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage127_ema_limit_model.py -v`。Expected：新模块/函数未定义或上述具体断言失败，不能以数值环境失败冒充RED。
- [ ] 实现上述接口。源CSV规范为`date,vt_symbol,open,high,low,close,volume`，同合约真实日线优先用已有合格本机源；每row绑定原源路径/SHA和精确`(vt_symbol,date)` qualified key。qualifier SHA只是来源引用，不由本工具自授资格。真实来源由root后续交付既有已接受日线/冻结DB资格的规范化绑定；DB必须只读、先形成可绑定快照/导出并反验，禁止边hash边重开活动DB。未获资格、carry、拼接价、冲突key拒绝；未满足38根则unknown，不启动补数。纯状态可私有组合027的B逻辑，但私有分支ID不得外泄；独立ID→私有intent映射仅用于一次on_fill消费，不注册B资产。
- [ ] 同命令GREEN；输出仅六项关键证据：seed/窗口边界、positive计数、u未来毒化零差、源SHA、epoch/独立ID、consume次数。不构建真实全历史特征、不跑旧027 build/main。

### Task 2：L定价、OFF工厂与初开策略边界

**Files:** Create `stage127_ema_limit_strategy.py`、`test_stage127_ema_limit_strategy.py`。

**Interfaces:** Consumes Task1 lookup与状态机；Produces `build_limit_priced_base(native_base: type) -> type`、`finalize_ema_plan_batch(strategy, plans) -> list[dict]`、`build_ema_strategy(native_base: type, *, weekly, fi, next_days, ema_lookup) -> type`；`build_ema_account_profile(formal: Mapping, native_strategy: type, native_engine: type, *, weekly, fi, next_days, ema_lookup, qualify) -> tuple[dict,type]`。后者无arm参数、不读数据/实例化engine，返回`profile,engine_class`，Task3工厂通过lazy import接入。

- [ ] 写 `test_real_limit_budget_off_identity_and_reservation`：独立测试进程仿旧065测试先用原`configure_runtime(temp/shared)`配置冻结数值栈，再import native，finally恢复临时OUTPUT；不调用原测试模块或prepare。真实847 MRO、035原risk recipe、原planner在L输入下产生量；L=100/S=95/size=10时rho=50，L≤S必须在原abs算术前拒绝（空方镜像）。原admitted三项gross只缩量、q=0不补位，真实产品snapshot每项最终正q仅reserve一次；OFF仅八键不同、无模型load/predict/fit。工厂owner不是A_OFF/B_OFF，formal输入不被修改，非flat/已有仓保持原路径。
- [ ] Run RED：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage127_ema_limit_strategy.py -v`。Expected：新工厂/合法S或上述预算断言失败。
- [ ] 实现pricing基类：照035真实MRO把局部估价L送进 `_calculate_trigger_priced_entry(..., entry_estimate=L, ...)`，先signed校验S；不改u bar/history。035 finalizer的小算术可在新namespace薄适配，保留所有原整数cap/gross前缀与recipe，不走其B_TS审计身份。仅保留`long_triple_screen/short_triple_screen`作为既有方向/风险分类标签，真实owner另列。策略按035的planner前观察、原filter、最终q后冻结与snapshot时reserve；`ts_activate_intent`可复用028真实层激活，`ts_commit_fill`自行用新ID记录，不先生成C/B审计再改owner。
- [ ] 工厂只从065导入`OFF_SETTINGS`并用`dataclasses.replace`做八键投影；不调用旧`make_off_profile(...,'B_OFF')`、selector、`prepare_account`或checkpoint。原profile资本/metadata/成本不变，输出`research_mechanism=MECHANISM_ID, financial_ready=False`。旧 `run_profile_once(s901,profile,metadata,*,engine_class,start,end,minute_audit)` 形状可复用，但本任务不得调用真实 `_run_profile`。
- [ ] 同命令GREEN；只保存本方法的有限MRO/八键/q/gross/reserve/ID证据。Task3未交付时，测试可用`patch.dict(sys.modules, ...)`为lazy import注入符合已定签名的sentinel engine factory，验证工厂接线；不能stub实际预算或把新工厂当金融preflight。真实组件组合由Task4覆盖。

### Task 3：限价扫描、私有首bar视图与共同heap

**Files:** Create `stage127_ema_limit_engine.py`、`test_stage127_ema_limit_engine.py`。

**Interfaces:** `limit_context(item: Mapping, frame, *, tick: float, policy: str='primary') -> dict | None`；`entry_minute_view(frame, *, entry_time, fill_price: float, direction: int, intrabar: bool)`返回独立DataFrame；`build_ema_engine(native_engine: type, *, qualify, policy: str='primary') -> type`。policy仅`primary/pessimistic`，后者精确实现124固定反证，无额外阈值。qualify签名沿028：`qualify(engine,item,actual_bar) -> None`，必须先完整D资格再scan。

- [ ] 写 `test_limit_scan_volume_day_end_and_private_view`：触L不成、穿透1tick但V<q继续等、非法V失败；open改善不超L且在OHLC/tick内；主口径首符合分钟；固定悲观仅紧接下一真实分钟确认，DAY末不跨D/不找第三次；私有view精确等于124的长high=F/close=min(close,F)、空镜像，raw未变。
- [ ] Run RED：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage127_ema_limit_engine.py -k test_limit_scan_volume_day_end_and_private_view -v`。Expected：新扫描/视图未定义或指定断言失败。
- [ ] 实现新limit context，不能调用stop-entry `execution.stop_fill`决定初开。以028 `cross_delayed_orders` 共同heap为最小适配保留ordinary/roll/conditional/synthetic稳定serial；仅pop时调用真实buy/short、native `_fill_order`和新机器on_fill。未成记录DAY机会/资源，无layer/订单/费用，不回收预算。初开context元数据在`_fill_order`之前按order ID注入，供Task4诊断及保护hook识别；异常finally恢复临时视图/cache/context。
- [ ] 同命令GREEN；记录量、tick、F/L、policy、时钟和raw未变证据。V≥q只为必要条件，保留全量近似/queue不可识别限制，不新建参与率或部分成交模型。

### Task 4：两组真实 native 接合与一次整体交接

**Files:** Extend `stage127_ema_limit_strategy.py` 的三个hook与 `test_stage127_ema_limit_engine.py` 两个组合方法；不改旧fixture。

**Interfaces:** Overrides `_sync_entry_risk_diagnostic(self, trade) -> None`、`stage827_intraday_exit_after_open_trade(self, trade) -> dict | None`、`_build_daily_env_gate_snapshot(self, day_contexts) -> dict`。共用Task3 `entry_minute_view`；Task2 `build_ema_account_profile`提供真实847/新engine组合。参考旧 `test_stage065_pairwise_off_integration.py:489` 的tiny构造方式，但不执行旧suite/main、不读其outputs。

- [ ] 写 `test_real_gap_invalid_side_mother_and_cost`：多L100/S95、open90/low88，原生初开F90→保护close88、空方镜像；同u信号/新机制母链，setup仅消费一次、R=N/A、无retry，两个真实TradeData各计一次原成本；spy使错误侧若进入827 diagnostic abs或847/827 R分支立即失败。价格均可达，状态最终flat，禁止CSV伪成交。
- [ ] 写 `test_real_dual_consumer_retry_and_unfilled_resource`：初始F=L100/S96，入场分钟open103/high105/low99是先高后低的可行intrabar路径；此前high105不得成为即时progress或lifetime浮盈。先用持续持仓分支实际调用holding consumer验其高点，再用后续stop98→下一分钟open103 reclaim→第二stop98的分支验retry可越L，仍同q/初始R和stop98，之后终止。另同fixture含DAY未成及V不足候选，真实reserve仍占用且无补位/费用；毒化D最终收盘/权益不改u q/L/S。实际现金/库存与逐fill成本公式相等，原普通held/roll不走EMA首bar分支。
- [ ] Run RED：分别用上一Task命令的`-k`替换为两个方法名；确认是预期的abs、双consumer或母链接合断言失败。
- [ ] 实现三个hook：wrong-side在任何abs之前分流，保留实际fill的margin/母身份但R=N/A，立即排同母保守synthetic保护close、不retry；正确侧保留原minimum-risk guard、0.5R及下一分钟F reclaim（可越L、不重算q/R）。首bar私有视图同时供即时scan和holding聚合；全日技术环境仍读raw。保护指令即时、成交分钟最差价仅是proxy；悲观口径额外不利先后假设照124披露。
- [ ] GREEN命令：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p 'test_stage127_ema_limit_*.py' -v`，Expected六个方法PASS；再用`PYTHONPYCACHEPREFIX=/private/tmp/stage127_ema_limit_pycache .py311/bin/python -m py_compile research/lines/futures_trend_triple_screen/tools/{stage127_ema_limit_model.py,stage127_ema_limit_strategy.py,stage127_ema_limit_engine.py,test_stage127_ema_limit_model.py,test_stage127_ema_limit_strategy.py,test_stage127_ema_limit_engine.py}`，Expected exit0；不重跑旧suite。用真实native `calculate_result`验证fixture成本：`Σfill(成交额*原rate + 手数*size*原slippage)`，原trade_count/现金/库存/母链一致，native/synthetic每笔只一次。保存`fixture_only=True, financial_replays=0, model_calls=0, provider_calls=0`与新源SHA。
- [ ] root组织一次新增组件整体独立审查，重点仅以上六类反例和新接口；通过也只标组件就绪。当前B仍live时保持零git操作；root后续统一exact add源码、三测试、计划和选定有限证据，保留所有RED与限制，不为通过另换撮合/保护口径。

## 金融交接、真实未决与一次自审

新金融入口不在这四项交付中：旧065 `prepare_account`、readiness和checkpoint写入端绑定旧A/B owner/失败/attempt，不能借B_OFF封装EMA。当前B真实终态与独立财务审计完成后，root才可另绑定：真实日线/分钟scope和源SHA、qualified 38bar覆盖、独立EMA owner、完整新源/fixture审查、固定区间资本限额，以及中性raw→seal→export身份适配；可复用原`run_profile_once`和既有经济表，不复制PnL。上述真实绑定尚未提供，当前不得写readiness、创建实际臂或启动账户。

执行方式由root按既有授权选用：建议native掌握Task2/4，Task1与Task3在本文接口固定后可少量并行，最后一次整体审查；不新增向用户索要执行方式/批准的门槛。

自审一次：124公式/来源/epoch→Task1，风险/OFF/资源→Task2，撮合/时钟/悲观DAY→Task3，gap/成本/原retry/双consumer→Task4；签名引用一致，五项Review Focus均有具名测试。实际源资格及未来金融owner/checkpoint/readiness明确后置，未假称已有API。计划只含三个生产组件、六个测试方法、四个验收任务，比124短，不给完整实现正文，不另派计划审查。

本次仅新增本文；源码、实际参数、数据、测试运行、回测结果新增修改删除均0，所有权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A。开始/结束新增过拟合判断：否，在未知B收益前把已采纳定义映射成有界实现；历史选择偏差仍在。开始/结束继续价值：是，组件级因果和经济接合可直接证伪；不等于alpha、金融就绪或目标完成。`production_qualified=false`。
