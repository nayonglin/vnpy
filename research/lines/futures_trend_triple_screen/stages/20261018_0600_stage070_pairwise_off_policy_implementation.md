# Stage070：A_OFF/B_OFF 共同政策及两个有限真实接合边界

- line_id：`futures_trend_triple_screen`；源码落盘与记录窗口：2026-10-18 05:56—06:00 CST（文件时间核对：测试05:56新增/05:58末改，policy05:57新增，此记录06:00新增）；分支 `codex/ai-training-data-expansion`；完成时只读到 HEAD `245d3c5e352cd150baf2aa28c4336afb5c291ee6`，本 agent 未 stage、commit、push、切分支或创建 worktree。
- 性质：Stage062 的 Task1/Task2 有界实施，非重要 alpha 突破；Task3/Task4 **未实施**。研究整体目标仍为完整 2020—2026 收益更高且回撤更低，不能只胜较弱 A_OFF 就宣告目标完成。
- 按分派只新增新 policy、仅含前两个具名测试的 integration 文件、此唯一 Stage070 和独立 Stage070 输出；未修改旧 021/022/028/035/036、LINE、registry、其他研究线、官方策略配置或其他 agent 文件。
- 实施合同：[Stage062](20261018_0546_stage062_pairwise_off_implementation_plan.md)，SHA256 `fc31120390ab4c04c95d52a7dfd629992aab0f6a4abf139d1976a0b2252343e1`。先读 AGENTS、registry、Stage059/062；依照 TDD 和 executing-plans 的有限实施流程，独立审查由 root 统一安排，本 agent 未再派 reviewer。

## 开始判断与调研结论

开始是否在过拟合：**否，本次新增行为是资格隔离，不按收益选择参数**；旧 pairwise19 的历史 PIT 问题并不因移除模型而转化为任何 alpha 证据。是否有价值：**是，先把真实 native/B 的共同决策依赖完整关闭，是下一步公平比较的必要工程证据。**

本次按 root 的禁止网络边界，未重复联网或 GitHub 调研；沿用 Stage059 已记录的官方 Qlib/TimeSeriesSplit 方法结论：工具不能自动证明标签成熟、选择无泄漏或 alpha。结合本次真实源码核对，判断是：native 已有无 runtime 的稳定候选插入顺序，rank0 原本不享受 margin 保护，035 原 fallback ordinal 也与 AI rank 分离；因此**保留冻结算法，不为了制造 RED 故意改坏旧实现**，只建立共同新政策及可复验边界。

原 B 已按 Stage063/064 真实 exit1：`qualified_delivery_old_value_conflict`，涉及 fu2209/2022-05-31 七值冲突，无完整 B 绩效。本阶段未重启 036、未读其部分 PnL，也未启动任何金融回测。

## 改动与参数

新增 `tools/stage065_pairwise_off_policy.py`，顶层只有 stdlib import；独立新进程验证导入后 numpy/pandas/sklearn/joblib 均未进入 `sys.modules`。运行时数值/native/B 延迟导入。

- `make_off_profile` 对真实 022 `capture_formal_profile` **完成正式 override 合并之后**的 spec 用 dataclass replace 投影，仅八项共同政策；保留原 profile/资本/风险/其他 metadata，账户名另存 `research_arm`。
- `expected_off_settings` / `check_settings_delta` 验完整 requested/actual，只允许八键；缺失 OFF 设置从真实 native MRO 声明默认补齐，并要求实际属性快照中存在、等于 OFF。只复用 022 原 shared-root 路径归一函数；风险值、月池路径、未知新增 path 和实际 protected rank 漂移都有负例拒绝。
- `disabled_pairwise_preflight` 明记 `disabled_by_shared_pairwise_free_policy`，不调用旧 model smoke；`check_effective_off_policy` 验 runtime=None、path-damage 继续禁用、strict minute 默认 True，并记录原月池开关/路径。
- `select_account_classes`：A_OFF 的 strategy/engine **is 原 native 类**；B_OFF 原样调用 035 strategy 与 028 engine factory，内部 `B_TS` 生产者身份不改。

八键固定为四个 False、三项 tilt strength=0、protected_selection_rank=0。真实正式 profile 本次只有 pairwise开关、tilt开关和 long strength 三项有实质数值变化；其余原来已为 OFF。Task1 对两臂分别验 173 个 requested/actual 键，非 OFF 差异为零。原 reference 缺的 catastrophic hard-filter 与 protected rank 均显式读出 native 默认并验证实际值。

本阶段没有新增可调 alpha 参数、修改或删除旧策略参数、候选排序/allocator、模型 bytes、月 AI 池 bytes、费用、真实 contract metadata 或资本。fixture 中 slots、budget、stop_loss_pct=.1、风险比率=.44 等只服务预声明合法算术反例，未投影进生产政策，不是参数搜索。

## TDD 与真实边界结果

两次 RED 都先于 policy 实现，冻结 native 栈正常导入，各自以明确 assertion failure `new shared OFF policy is absent at the real native/B boundary` 失败；不是 import/version error。证据：`outputs/stage070_pairwise_off_policy_implementation/test1_red.txt`、`test2_red.txt`。

```sh
.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage065_pairwise_off_integration.py -k test_disabled_profiles_native_and_b_no_model -v
.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage065_pairwise_off_integration.py -k test_real_planner_fallback_slot_margin_and_b_final_budget -v
```

最小实现后，首次 GREEN 尝试发现两项 fixture 错误，保留 `initial_green_fixture_failures.txt`，未将其冒称有效 RED：一是 formal 设置的 account_capital/c3_capital 是 engine 元数据，按真实 022 行为核验 engine.capital；二是 Stage804 真实 stop 会取 `max(low,close*(1-stop_loss_pct))`，fixture 改用明确 `.1` 使原设定 S89 成立，未替换真实 stop 方法。

最后一次新文件有限验证（未扫旧 suite）：

```sh
.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage065_pairwise_off_integration.py -v
```

退出码0，`Ran 2 tests ... OK`；最终日志为 `outputs/stage070_pairwise_off_policy_implementation/green.txt`。冻结数值栈：numpy2.4.4、pandas2.3.3、sklearn1.8.0、joblib1.5.3；没有为测试导入当前不兼容 sklearn。

**Task1**：真实 A native 与 B factory 构造成功，完整 OFF profile/设置一致，原输入未修改，月池保留且路径相等，strict minute=True。joblib.load、pairwise runtime构造/score、Pipeline predict/predict_proba/fit、022 old model smoke 均装失败 spy，全部调用数0，模型实体未加载、未预测、未拟合。证据为 `test1.json`（含类/MRO、实际有效属性、完整 fixture requested/actual、默认值、严格差异与 spy 计数）。这只证明 policy/constructor 接合，尚无 Task4 runner 完整入口资格。

**Task2**：保留真实 native planner/score早退/tilt/margin 算法，只隔离与本反例无关的候选历史构造和给定预算资源。真实 constructor 的 metadata 排序把故意倒序 CSV 恢复为 `AP.CZCE,au.SHFE,rb.SHFE`；即使旧 score 残值为 `-100,0,100`，也不重排、赋 AI rank、tilt 或保护 rank0。

| 反例 | 真实结果 |
| --- | --- |
| 基础量3、margin100、reserved0、slot2、budget1000 | 前两项 opened；第三项仍保留候选量3但 `skipped/concurrent_limit`，没有被当作入选 |
| 同一输入、slot3、budget450、reduce=True | 量3/1/0；第三项 `skipped/incremental_margin_budget_gate`；所有protected_by_rank=0，tilt applied0/multiplier1 |
| 真实3产品 B on_bars/035 finalizer，T100/S89/rho110/m100、R1100/L2500 | 原admitted量10/10/10，最终10/10/5；gross前缀0/1000/2000；plan.volume与selected_volume一致，无补位 |
| 真实产品循环 reservation | AP 0→1000、au 1000→2000、rb 2000→2500，每产品恰一次；pending_active_products为三项，orders/fills均0 |
| B执行序号与AI rank | intents ordinal1/2/3；原plan、sizing、decision的selection_pairwise_rank仍0；内部signal_machine_arm=B_TS |

B 真实 on_bars 场景只把 native alpha生成替换为字面“无原信号”，用 synthetic AM seed，保留真实 weekly/FI setup、T估量、原 u S、planner、finalizer、snapshot 和 reservation；没有直接手造 reservation 计数。spy 包装真实 reserve 方法并记录真实前后余额。没有 load_data、run_backtesting、minute全集或成交模拟。证据为 `test2.json`。

## 源码身份与输出

- `stage065_pairwise_off_policy.py` SHA256：`edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f`。
- `test_stage065_pairwise_off_integration.py` SHA256：`51731fdd31bd9fe2d7ba7f04ed34fc99f3c19fddb70dd7abae839d35c5771539`。
- `implementation_manifest.json` 绑定上述新源及实际旧native/022/028/035 SHA，冻结qmt仍为 `6d6aa534715200c40a5743697114f73080111d609b29980d924dcb1d362792e9`。
- 所有本次证据均位于 `outputs/stage070_pairwise_off_policy_implementation/`，未借旧金融目录、未创建 checkpoint 或 runner。

## 结果、边界与结束反思

新增/修改/删除回测结果：0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：全部 N/A（未运行金融）。模型load/predict/fit=0，网络/行情下载=0，CTP/订单=0，production_qualified=False。

结束是否新增过拟合：**否**，本次只有资格隔离和预声明有限反例，未看新收益选规则；这不抹去既有研究选择偏差。是否值得继续：**是，Task1/2 证据支持继续中性 checkpoint/export 与独立 runner 的有界工程准备；现在还不能运行新金融或宣告 alpha/生产完成。**

TODO：root单一独立review本次两个边界；之后另按冻结合同完成 Task3（真实fill身份、中性checkpoint/纯export）与Task4（新runner、输入/资格/终态封存）；数据方面仍须fu2209七值冲突闭环、061实际commit前缀的冻结与独立签收，缺口继续走021同等门。新金融仍需完整有限接合接受、数据资格和 root 单次放行。原 A0/原 B 终态不可隐去，不能只胜弱基准；整套全历史严格OOS或生产资格均未获得。
