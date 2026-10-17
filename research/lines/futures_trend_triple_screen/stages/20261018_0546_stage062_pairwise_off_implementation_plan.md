# A_OFF / B_OFF 公平资格入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本阶段只交付计划，不实施；沿现分支工作，不建 worktree，不重复向用户索取已有研究授权。

**Goal:** 为全 2020-01-01—2026-10-14、150000 本金的 A_OFF(native) / B_OFF(035 完整 package)建立独立、共同移除 pairwise19/tilt/AI rank 保护的入口，保留月 AI 池及其他原门，并让终态、失败和纯导出有真实身份。

**Architecture:** 新增一个政策/profile 模块、一个中性账户快照/export 模块和一个小 runner，复用原 847 的账户表组装及 022/031 的真实采集/身份函数，不复制 036 的整套 main。A_OFF 使用原 native strategy/engine；B_OFF 使用冻结 028/035。账户 owner 与信号机身份分开，不能把 A_OFF 伪装成没有成交的 B 或通过改旧模块常量借用其 seal。

**Tech Stack:** `.py311/bin/python`；沿 022 冻结 pandas2.3.3 / numpy2.4.4 / sklearn1.8.0 / joblib1.5.3 及既有 vn.py vendor；不安装或升级依赖。有限测试使用 `unittest`，仅三个具名接合测试。

**Spec:** [059 修复设计](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0535_stage059_pairwise_pit_repair_design.md)、[060 决策](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0540_stage060_asof_evidence_registration_and_next_gate.md)、[035 B 合同](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0333_stage035_b_ts_execution_contract.md)、[061 数据复用计划](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0545_stage061_accepted_wait_delta_reuse_plan.md)。line_id=`futures_trend_triple_screen`；2026-10-18 05:46 CST，HEAD `008575e132ea76032d904cbd407aa6f85566b349`；非重要 alpha 突破。

## Global Constraints

- 只新增本线计划指定文件；不改 022/028/031/035/036、模型、原数据、旧协议/收据、LINE、registry 或其他研究线；当前阶段训练、预测、金融、行情/网络、订单均为 0。
- 最新 root 真实观测及已读 [063](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0546_stage063_b_ts_actual_old_value_conflict_failure.md)、[064](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0548_stage064_b_ts_actual_failure_independent_review.md)：原 B session70433 / PID21822 已 exit1，原因 `qualified_delivery_old_value_conflict`，不是 timeout；无完整 B 绩效。191 个 accepted 指针仅 190 个实际 append，末 fu2209 请求未 commit。不得重启 036、覆盖末包、改预算或以部分收益作结论。仍需具体冲突处置闭环和 061 实际 commit 前缀的冻结/独立签收。
- 未来新金融还须有限独立接合接受、数据冲突闭环与 root 单次放行；代码准备不等于金融就绪。原 1800/7200 秒常量不在本计划改动。root 根据真实失败终态判断是否沿用原限额；不因本次非 timeout 自动延时。
- A_OFF 与 B_OFF 保持同一月 AI 池字节/资格时钟、OI/通用过滤、成本、slot/普通 margin、持仓/加仓/退出/换月、0.5R 与一次 retry；B 的 T 估量、真实 u 的 S、最终只缩量 gross 预算和条件执行仍为预声明 package 差异。
- 不实施 055 context、滚动模型、参数搜索或 2023+ 截段。新 A/B 只是 pairwise-free，不宣称整套无 AI 或全历史严格 OOS。原 A0 与原 B 终态必须公开，不能只胜较弱 A_OFF 就宣告总体目标。
- 仅从真实终态及 `data_qualified_appended` 成功证据继承数据；pointer accepted/provider 成功/独立签收不等于 engine commit。061 不纳入冲突末包、不把 anchor 升 full；新缺口仍用同等 021 门。
- 三个新生产模块在 runtime 配置前只允许 stdlib import；数值/native/B 模块延迟导入，export-only 不因顶层 import 误进入数据或引擎路径。

## Review Focus

1. A_OFF 未挂 TS strategy/engine，却被 exporter 伪造 intents、ordered counts 或 B provenance：测试 3 必须检查 `ordered=null` 与真实 native 类。
2. policy False 但 runner 仍调用旧 model smoke，或 MRO/official overrides 把 True 合回来：测试 1 必须覆盖 profile 最终合并、真实构造器和模型禁用前检。
3. fallback 执行序号被当作 AI rank，导致 protected margin 豁免/tilt 或 B gross 顺序改变：测试 2 必须执行真实 planner 与最终预算。
4. synthetic usage 缺 signal 列被误拒绝，或缺母/冲突被放过：测试 3 沿真实 827/847 fill 及 031 身份函数验证。
5. post-engine guard 失败丢 raw、A/B seal 可互换、export-only 偷跑引擎/数据：测试 3 以内联子场景证明先存证、owner 绑定与零重放。

## 文件地图及实际可复用边界

未来仅新增 4 个代码文件；前缀 065 避开 root 的 063 终态与 064 审查记录：

| 新文件（均在本线 `tools/`） | 唯一责任 |
| --- | --- |
| `stage065_pairwise_off_policy.py` | 八项共同 OFF 设置、formal profile 投影、有效属性/设置差异验收与 arm class 选择 |
| `stage065_account_checkpoint.py` | A_OFF/B_OFF owner、account-only raw/manifest/seal、通用成交身份导出和比较表 |
| `stage065_run_pairwise_off.py` | stdlib CLI/bootstrap、必要身份/data/preflight 门、一次原 847 账户执行与失败存证 |
| `test_stage065_pairwise_off_integration.py` | 仅下列三个具名真实接合测试及其共享 tiny fixtures |

独立输出根固定 `outputs/stage065_pairwise_off/`：两账户分别为 `A_OFF/`、`B_OFF/`，每臂仅一次 `attempt=1`；没有自由 `--output`/重试参数。测试输出仅 `outputs/stage065_pairwise_off_implementation/` 下新目录，绝不借用旧金融输出。

可直接调用、不得执行其 main 的真实接口：

- 022：`configure_runtime(shared)`、`capture_formal_profile(s901, metadata, start, end)`、`capture_actual_settings(engine_class)`、`capture_engine(engine_class)`、`canonical_trade_enums(frame)`、`attach_trading_dates(trades, clock)`、`InputRecorder(accepted)` 及其 `record/audit/verify`、`normalize_reference(value, shared, reference_shared)`、`FileWaitResolver(root, recorder, audit, run_began, ...)`、`whole_run_budget(seconds=RUN_SECONDS)`。前两 collector 分别 yield 设置列表与 `{usage,equity,trades,minute_requests,anchor_requests,failures,weekly_gate}`，无 TS 要求。
- 031：`actual_trade_identities(trades)`、`build_execution_clock(capture, identities)->(clock,usage)`、`capture_ordered_engine(engine_class)`、`pending_intent_snapshot(item)`、`read_reused_A0()`、`validate_daily_calendar(actual,reference)`、`bind_input(recorder,path,expected=None)`、`replace_engine_class(module,engine_class)`，以及 B 的已资格条件 stub `build_qualification_callback(holder,Offset,Direction)`。collector 对 native 缺 TS 属性合法返回空数组，仍采真实 identities；A 导出必须把四类空 TS 数组映射为“不适用”，不能当 B 审计。
- native：`s901.s847._run_profile(profile, metadata)->(combined, frames)` 是完整账户表组装接口，内部实例化 `Stage847StopRetryEngine`；`s901._run_live_c9` 另行合入 official overrides，不能在它前面加 OFF 再指望不被覆盖。
- B：`build_b_strategy(native_base, weekly_lookup, fi_lookup, next_days)` 和 `build_ordered_engine(native_engine, qualification_callback)` 原样调用。B_OFF 外层账户名为 `B_OFF`，内部 `OrderedSetupMachine('B_TS')` 及 producer audit 的 `arm='B_TS'` 保留，另记 `signal_machine_arm='B_TS'`；禁止文本替换冻结 B_TS/C_TS 字符串。

不能直接调用 031/036 的 `owned_output/new_run_context/save_raw_checkpoint/seal_checkpoint/load_sealed_checkpoint/export_checkpoint`：它们硬绑定旧路径、arm、attempt、writer/schema、旧 `actual_settings_equal_accepted_A` 和 ordered provenance。故确需一个小型中性快照/export 适配；只迁移其原子写入与检查顺序，并逐项保留身份校验，不能参数篡改旧 globals 后继续声称旧 seal 有效。

## 固定公共接口及输出合同

下列为本计划决定的新接口，**不是虚构的 061 接口**；跨任务只用这些名字：

```python
# stage065_pairwise_off_policy.py
Arm = Literal['A_OFF', 'B_OFF']
OFF_SETTINGS: Mapping[str, bool | int | float]
def make_off_profile(formal_profile: Mapping[str, Any], arm: Arm) -> dict: ...
def expected_off_settings(reference: Mapping[str, Any]) -> dict: ...
def check_settings_delta(reference: Mapping, requested: Mapping, actual: Mapping,
                         *, shared: Path, reference_shared: Path) -> dict: ...
def disabled_pairwise_preflight() -> dict: ...
def check_effective_off_policy(strategy: object) -> dict: ...
def select_account_classes(arm: Arm, native_strategy: type, native_engine: type,
                           *, weekly=None, fi=None, next_days=None, qualify=None) -> tuple[type, type]: ...

# stage065_account_checkpoint.py
def new_run_context(output: Path, *, arm: Arm, preflight: Mapping, started_at: str) -> dict: ...
def save_raw_checkpoint(output: Path, payload: Mapping) -> dict: ...
def seal_checkpoint(output: Path, manifest: Mapping, validation: Mapping) -> dict: ...
def load_sealed_checkpoint(output: Path, *, arm: Arm) -> tuple[dict, dict]: ...
def export_checkpoint(output: Path, destination: Path, *, arm: Arm,
                      metrics_function=None, export_only: bool=False) -> dict: ...
def write_comparison_if_ready(root: Path) -> dict | None: ...

# stage065_run_pairwise_off.py
def prepare_account(args) -> dict: ...
def run_profile_once(s901, profile: Mapping, metadata: Mapping, *,
                     engine_class: type, start, end, minute_audit: Mapping
                     ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]: ...
def execute_account(prepared: Mapping) -> dict: ...
def main(argv: Sequence[str] | None=None) -> int: ...
```

`prepare_account` 返回冻结 policy/profile、metadata、expected settings/parameters、reference calendar、source/data bindings 和 preflight 字典；不创建金融 engine，不加载/预测模型。`run_profile_once` 恰返回 `(combined, frames, profile['spec'])`；上述 pd 类型仅供文档/TYPE_CHECKING，不能为类型注解提前 import pandas。`execute_account` 唯一执行一次金融；不得从 exporter 回调它。DataFrame/BarData 只进入 account-only pickle 或显式 CSV，JSON 不递归序列化 engine/strategy/history/minute cache。

八项唯一 allowed setting delta 为：四个 False：`enable_selection_pairwise_v2`、`enable_selection_pairwise_v2_catastrophic_veto`、`enable_selection_pairwise_v2_catastrophic_hard_filter`、`enable_selection_pairwise_v2_volume_tilt`；三个 0：`selection_pairwise_volume_tilt_strength`、`selection_pairwise_volume_tilt_long_strength`、`selection_pairwise_volume_tilt_short_strength`；一个 0：`incremental_margin_budget_gate_protected_selection_rank`。reference 原缺的设置取**已 pin native 类的声明默认**并纳入有效属性快照，不能用 `dict.get(None)` 放过；`check_settings_delta` 同时验证完整 requested/actual、仅八项可能变化、其余键零差异。路径仅沿原 `normalize_reference` 归一 shared empty-input 根，不能泛化忽略所有 path/未知字段。capital、日期、原费用和 contract metadata 不允许差异。

`make_off_profile` 对 `capture_formal_profile` **已经合入正式 live overrides 后**的 profile 作 dataclass `replace(spec, overrides={原 overrides + OFF_SETTINGS})`，保留资本、风险倍率、原 profile metadata；不调用并修改旧 official assembler。arm 在独立 research 字段记录，不能借改资本/风险 spec 标签掩盖经济字段差异。有效属性还断言 runtime=None、path_damage 等原禁用模型仍禁用、月池开关/路径不变；其他门不能新增或关闭。

`disabled_pairwise_preflight` 固定 schema=`stage065_disabled_pairwise_policy_v1`，status=`disabled_by_shared_pairwise_free_policy`、model_loads/model_predictions/model_fits=0、eight_key_policy_sha256、fallback=`metadata_sorted_product_insertion_order`、rank_protection=False。不能调用 022 model smoke 后填 disabled；不称全系统 model-free。

快照采用新 schema 前缀 `stage065_`：`run_context_v1`、`raw_account_checkpoint_v1`、`raw_checkpoint_manifest_v1`、`engine_validation_seal_v1`。全部绑定 arm/attempt=1/run_id/精确 output/writer SHA/3 个新模块及冻结依赖 SHA/policy SHA/data bindings SHA。raw 包含 `combined,frames,capture,actual_trade_identities,actual,parameters,spec,preflight,input_fingerprints,run_context,engine_elapsed_seconds,wait_audit,resolver_audit,qualification_audit`；另含 `ordered=None`（A）或 `{decision,fill,execution,pending}`（B）。A 不附 weekly/FI/intent 权利声明；B 可另保存原 final-budget 审计。

seal validation 不再谎称等于旧 A 全设置，改为 `actual_settings_match_off_expected=True`、`parameters_match_reference_except_off_policy=True`、`pairwise_decision_dependency_absent=True`；保留 engine_returned、1641 日及 reference calendar 完全相等、bar failures=0、strict missing=0、全部 consumed 输入未变、accepted correctness code 未变、shared input 为空等原门。source/policy/manifest/context/raw 的 SHA、size、run_id、arm 和 writer snapshot 在解压反序列化**之前**全部核验，拒绝 symlink/外部/跨 arm/未 seal；不能为 fixture 关门。

公共导出：原全部 account `frames/*.csv` 对应名称、`daily.csv`、`execution_clock.csv`、`execution_proxy_usage.csv`、`actual_trade_identities.csv`、`internal_equity_daily.csv`、minute/anchor requests、wait audit、actual/effective settings、input manifest、metrics/provenance/summary。A 的 `ordered_applicable=False, ordered_counts=null, signal_machine_arm=null`，不写虚假 ordered CSV；B 保留原 ordered 审计并另加 `research_arm=B_OFF, signal_machine_arm=B_TS`。所有行/summary 的 owner 是新账户，不重写 producer 原始母单/intent 身份。

`summary.json` status 固定 `completed_pending_independent_review`，result_scope=`offline_full_2020_2026_shared_pairwise_off_native_vs_stage035_package`，financial_replays=1；export-only 本进程为 0；production_qualified=False。已成功拒绝再次导出覆盖；失败导出放新 `exports/export_NNN/`，不改 raw/seal 或旧失败。比较表 schema=`stage065_pairwise_off_comparison_v1`，同时列 A0 受限固定模型、原 B 真实终态（本次失败则指标 N/A）、A_OFF、B_OFF，独立结论仍 pending。原 A0 为 2262595 / 1408.396667% / DD−48.789850% / Sharpe1.367364；不能只列新两臂或宣布通过。

## Task 1：冻结共同政策与真实 native/B class 选择

**Files:** Create `tools/stage065_pairwise_off_policy.py`；Create 测试文件中的 `PairwiseOffIntegrationTests.test_disabled_profiles_native_and_b_no_model`。

**Interfaces:** Consumes 原 022 formal-profile、035/028 class factories；Produces 上述 policy 六个函数和唯一八键 OFF_SETTINGS，供 Task 3/4 使用。

- [ ] 写 RED：用已冻结真实 847 native strategy 构造实例（tiny engine），A 返回的 strategy/engine 必须 `is` 原 native 类；B 返回真实 035/028 接合类；formal profile 输入保持未修改、资本与非 OFF settings 零差异。
- [ ] 同一测试用 test-only spy 令 joblib load、runtime 构造/predict、旧 model smoke 一旦被调用就失败；执行 `disabled_pairwise_preflight`、最终 profile 合并和真实实例初始化，确认调用数均 0、runtime=None、long tilt 0、rank protection 0。不得导入/运行旧模型或写模型 bytes。改变一个非白名单风险字段要明确拒绝。
- [ ] Run: `.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage065_pairwise_off_integration.py -k test_disabled_profiles_native_and_b_no_model -v`。Expected RED：新 policy 未定义或实际旧模型依赖被 spy 捕获；不是凭 import/version 失败冒称有效 RED。
- [ ] 实现 policy：A 不造 research subclass，不挂周 gate/B stub；native `stage827_require_complete_minutes` 原默认 True，验属性不改类。B 的内部 B_TS producer 身份原样保留，账户 policy/owner 单列。
- [ ] 同命令 GREEN，留 `outputs/stage065_pairwise_off_implementation/test1.json`：实际类/MRO、八键 delta、有效属性、load/predict/fit=0、无其他设置漂移。独立审查该边界后仅提交新 policy/test 的准确路径，不夹带当前其他并行文件。

## Task 2：联合 slot/margin/gross 反例

**Files:** Extend 同测试文件的 `test_real_planner_fallback_slot_margin_and_b_final_budget`；如 Task 1 政策有缺口，仅改新 policy。

**Interfaces:** Consumes Task 1 policy、真实 qmt `_plan_flat_entry_candidates`、原 035 `finalize_b_plan_batch`；Produces 可检查的候选、q、风险、slot/margin 和 reservation evidence；不新增 allocator。

- [ ] 写 RED：同一 tiny u 状态三个候选，输入按真实 metadata 产品序；保留真实 planner/tilt/margin 方法，只隔离与本反例无关的历史/模型资源。固定每项基础量3、单手margin100、reserved=0：slot=2/budget1000时前两项量3入选、第三项因concurrent_limit未入选；slot=3/budget450/reduce=True时按序量3/1/0，rank=0 无 protected。即使给旧 score 非零残值，也不能改变 fallback 或触发 tilt。这些是反例输入，不是新策略参数。
- [ ] Run: 上述 unittest discover 命令把 `-k` 换成 `test_real_planner_fallback_slot_margin_and_b_final_budget`。Expected RED：缺少新有效政策/证据断言时失败；若原 native off 行为已满足，不为了 RED 修改冻结实现，只以新 policy 未接入的可观测失败作 RED。
- [ ] 接入 Task 1 共同政策，B 继续真 T/真实 u S 与原 finalizer；另在三项原admitted量10、单手margin100、L2500且其他原cap不紧的固定合法plan中验证最终10/10/5、gross前缀0/1000/2000，无补位。检查 pairwise_rank=0 与 intent ordinal 分开、plan.volume 与 selected_volume 一致。让真实产品循环对每个最终可开计划执行恰一次 reservation，不能用手动计数代替。
- [ ] 同命令 GREEN；留 `test2.json` 的每候选原量/最终量/T/S/rho/m、顺序、slot、protected=0、tilt applied=0/multiplier1、gross、reserve 次数。A/B 机制差异如实列出，不要求最终手数人为相等。
- [ ] 审查证据；仅提交新文件的此增量。此反例不升级为全数据或金融结果。

## Task 3：中性 checkpoint/export 及真实成交身份

**Files:** Create `tools/stage065_account_checkpoint.py`；Extend `test_real_fill_identity_checkpoint_and_pure_export`。

**Interfaces:** Consumes Task 1 arm/policy identity、022 account capture、031 actual identities/build clock/enum/date helpers；Produces raw→seal→纯 exporter 和比较表函数，供 Task 4 调用。

- [ ] 写 RED：tiny native A 原 847 与 tiny B 真实 035+028 各产生真实开仓及 synthetic/0.5R 路径；必须调用真实 827 `_fill_order`，不能用手造“已成交”CSV替代。B 只复用已接受 [035 fixture](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage035_independent_review/native_b_composition_fixture.py)的长侧 synthetic bars/种子方式，期望T111/S99及真实成交111/105/111/105、下一分钟retry、成本按实际4笔计一次；不执行旧fixture main或重跑其3case。A 保留原native信号入口且无 ts intent。fixture 不调用完整回测入口、不读研究分钟全集；账户15万参数由test1/新preflight核验，不把tiny fixture资金当金融参数。
- [ ] Run: 同一 unittest discover 的 `-k test_real_fill_identity_checkpoint_and_pure_export`。Expected RED：新 neutral checkpoint/export 未定义，或旧硬编码 arm 导致断言失败。
- [ ] 适配 031 原子 pickle.gz→manifest→validation seal 机制；只移植这组小函数并审 diff，不抄 800 行 main。先持久化所有原始 account tables/capture/actual identities，再跑后处理 guard：设置/calendar/source 等 engine validation 故障保留 raw、无 seal/summary；其后 clock/metrics 导出故障保留 raw 与已有合法 engine seal、无成功 summary。seal 不是经济或独立账户审查通过。引擎未返回/无完整表只写独立 `failure_capture.pkl.gz` 和 `run_failure.json`，标 partial、不 seal，不假称完整 ledger。
- [ ] 使用真实 identities 跑原 031 clock：synthetic usage 缺 signal 列可由真实 actual 母身份一致补齐；缺母、冲突必须拒绝。A 的 ordered=null，B 有真实 counts，二者真实成本只计一次；不得为 A 放松普通母单/订单身份门。
- [ ] 同一测试内加入 owner/恢复子场景：跨 arm、改 raw/manifest/seal/context/source SHA、symlink、未 seal 均在 `pickle.loads` 前拒绝；有效 sealed snapshot 的 export-only 以 sentinel 禁止 engine 构造/load_data/run_backtesting/061 loader/DB/minute reload/模型 load 与 predict，仍能用冻结数值栈完成导出；成功不覆盖，失败只留本次 export 目录。
- [ ] 同命令 GREEN，保存 `test3.json`：实际 fill/mother IDs、价格/量/成本、原字段来源、A/B owner、raw 保存早于故障、拒绝项、export-only finance/data/model 调用数 0。独立审查 snapshot 身份壳及 native 语义后仅提交新模块/test 增量。

## Task 4：小 runner 接线、061 依赖及金融前冻结

**Files:** Create `tools/stage065_run_pairwise_off.py`；Extend 已有三个测试的 runner dispatch 子场景，不新增第四套 suite。

**Interfaces:** Consumes Task 1/3 的确切函数；原 847 `_run_profile`；061 最外层复用接口。Produces 独立 CLI/preflight/执行/失败证据，不调用 036 main 或改其 globals。

- [ ] **执行前 resolve 的唯一未定 API：D061。** 061 目前只计划 `stage061_accepted_wait_delta.py`，没有可调用 loader/context/predicate 的最终签名。由数据 owner/root 提供真实签名、source SHA、manifest/review 的准确位置/SHA与 scope 出参后，固定本 runner 的一个 data 接入点；不能自行发明 `stage061.load_*`、把它塞入旧022 stack第五层或伪称已经实现。Task 1—3 可独立做 tiny fixture；实际 data/preflight/金融接线在 D061 冻结并独立接受前不就绪。
- [ ] CLI 固定 `--arm {A_OFF,B_OFF}`、互斥 `--preflight|--run|--export-only`、原 `--data-stack-manifest/--data-stack-sha256`，并承接061计划的 `--accepted-wait-delta-manifest/--accepted-wait-delta-sha256/--accepted-wait-delta-review-sha256`；review 路径解析随 D061 真实合同定，不猜文件名。`--run` 另必须传 root 的 `--execution-readiness/--execution-readiness-sha256`；无放宽数据/旧值/模型 fallback 参数。
- [ ] stdlib 解析后，export-only 先分支：只装 frozen 数值路径及新 checkpoint exporter，核 owned seal；不调用 `prepare_account`、061、s901、DB/minute loader 或旧 model smoke。其余分支在数值/vn.py import 前调用原 `configure_runtime(shared)`；仅为 runtime 输出临时设置/恢复 022 OUTPUT，禁止改策略/校验全局。shared 固定本输出根的空目录。
- [ ] `prepare_account` 保留 036 已有的 accepted correctness SHA、六身份、vendor、固定原minute/source、月AI资格、settings/参数、空外部signal、source recording 门；将“actual全等A”替换为 Task 1 的**严格八键差异门**，不删除门。B 才读原031的 ordered features；A 的 ordered feature provenance 为 N/A。调用 `select_account_classes` 后把返回 strategy 精确赋给 `profile_off['strategy_cls']`，engine 精确交给 `run_profile_once`；不得留用 formal native class 误跑 B。数据以061固定最外层使用、原层顺序不变，完整新源闭包进入 InputRecorder。
- [ ] `run_profile_once` 复用原 formal profile 捕获结果作 OFF 投影，然后**直接**调用原 `s847._run_profile(profile_off,metadata)`，不再调用会重新合入 official True 的 `_run_live_c9`。调用期间仅用原031 `replace_engine_class` 切换这个构造边界、显式保存/恢复 `s847.START/END` 和 `_GLOBAL_MINUTE_BY_SYMBOL`；finally 必须恢复。原 `_run_profile` 自身复用原设置组装、数据载入和全部 frames builder。补齐 `_run_live_c9` 原有的资本/profile列、四个 forced-margin 0 列及 minute_source/loaded_symbol_count，用原 spec 和 minute_audit 值；不自写第二套 PnL 或持仓计算，不通过字符串替换/全局替换 `_build_setting` 绕门。
- [ ] A 将原 native engine 交 021 ordinary gate，无 TS qualification stub；B 用原028条件 callback holder，在 gate scope 中绑定/清除，full资格含未触发合法 intent。使用 022 通用 collectors 与031身份 collector；仅局部、finally恢复的既有 capture context，不 monkeypatch 旧校验函数返回True或吞异常。
- [ ] `execute_account` 只 reserve 新 owned 目录一次；快照 protocol/新源/旧冻结依赖/政策/数据 manifest、run_context/preflight。原账户返回后立刻 Task 3 raw，随后完整设置/参数/日期/分钟/source验证，再 seal/export。捕获 BaseException（含 WholeRunBudgetExceeded），保留真实 partial capture、待单投影、设置、请求、resolver/gate审计、raw/seal存在性和失败阶段；JSON 不泄露 DataFrame/BarData。A/B 失败互不覆盖，后续只允许 seal 后 export-only 恢复。
- [ ] 在现有 test1/test3 内扩 runner dispatch 子场景：OFF最终合并不被 official True 覆盖、禁用预检不调用旧 smoke；export-only 不进入 prepare/data/engine。只复跑这三个新增方法，compile 仅新四文件，保存实际命令/exit/source SHA和有限证据。
- [ ] root 组织有限独立接合审查（只新四文件与3证据）；通过后 freeze 新源/本计划/数据bindings。提交只含准确四个新代码文件、计划和其独立证据目录，不 `git add -A`、不混入当前其他 agent 改动。

`execution-readiness` 由 root 在真实终态/独立审查后产生，schema=`stage065_pairwise_off_execution_readiness_v1`，必须绑定：063 原B真实 terminal/run_failure SHA、064 冲突审查及已闭环的数据处置依据、061 manifest与独立review SHA、新源/三测试独立review SHA、原 A0受限参照、原B失败/N/A状态及 root 的限额决策。**本计划仅支持 root明确选择继承原1800/7200的情况；若终态审计认为需改限额，先另定合同，不能执行者自行改常量或靠变更预算重跑。** 当前非 timeout 的数据冲突没有提供自动延时理由。readiness 未齐时 `--run` fail closed，preflight只能标 `financial_ready=False`，不能写 passed金融资格。

未来实际运行命令由 root 带冻结 SHA 填入：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage065_run_pairwise_off.py --arm A_OFF --run ...`，B_OFF 同入口另进程/目录；每次只一次内联 preflight、一次 account。现在不得执行。若任一新臂失败，失败保留且无完整比较；不得以另一个单臂或截断年限代替。全部完成后交独立账户审计，比较表与原 A0/B 终态一起公开；只有收益/DD原目标及后续PIT/成本/固定多周期/弱段门全成立，才讨论目标完成。

## 计划自审与阶段反思

- spec coverage：059八项政策/耦合、native/B分离、真实身份、checkpoint/export/failure、061权限及新冲突门、完整区间/资本/旧参照、无context/训练/数值升级均已对应 Task 1—4。
- 接口/步骤：Task 1 定政策，Task 2 验真实预算，Task 3 定中性快照，Task 4 定入口；后续任务函数与上文一致。D061 是唯一未定依赖 API，明确阻塞 data 接入而非虚构签名；终态冲突审查及限额决定是金融 readiness 前置证据，不是工程师可选参数。
- 五个 Review Focus 都落入三个具名测试；未要求重扫旧suite、1590来源或用新金融代代码测试。现有 native/ordered collector可复用，只有硬编码owner/export部分适配，没有800行runner复制方案。
- 本阶段只新增本文，代码/参数/回测新增修改删除均0；权益、收益、DD、Sharpe、滑点、交易次数和胜率均N/A。没有训练/预测/金融/网络或B途中PnL读取。
- 开始和结束新增过拟合判断：否，修复政策和门依已知资格问题固定，不根据收益选择；历史选择偏差仍存在。继续价值：是，有界工程准备可消除明确依赖；新金融价值仍取决于数据冲突、061与独立接合证据，不能把计划或代码完成当 alpha 通过。
