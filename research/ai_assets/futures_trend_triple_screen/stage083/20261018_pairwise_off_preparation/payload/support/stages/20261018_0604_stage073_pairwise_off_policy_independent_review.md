# Stage073：共同 pairwise-OFF 政策 Task1/2 独立有限审查

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:04 CST。
- 工作区：`/Users/mac/Desktop/fian`；分支 `codex/ai-training-data-expansion`；只读 HEAD `245d3c5e352cd150baf2aa28c4336afb5c291ee6`。
- 性质：Stage062 Task1/2 的独立工程审查，非重要 alpha 突破。按分派只写本 Stage073 和 `outputs/stage073_pairwise_off_policy_independent_review/`；未改作者文件、LINE、registry、旧 suite 或其他研究线，未 stage/commit/push，未再派审者。
- 前置阅读：AGENTS、registry、Stage059、Stage062（相关全局与 Task1/2）、Stage070、新 policy/test 及必要冻结 native/022/028/035 接口。现 registry 未列本线显式行；本次线身份由既有本线目录与 Stage062/分派固定，不以审查为由创建新研究线或修改索引。

## 调研与开始判断

依本次明确禁止网络的边界，未重复联网/GitHub；沿用 Stage059 已核对的官方 Qlib/TimeSeriesSplit 方法结论：工具不能自动证明标签成熟、无选择泄漏或 alpha。本次通过真实冻结接口核对共同政策的实现，不据收益选择新规则。

开始是否在过拟合：**否**，没有训练、参数搜索、收益读取或金融回放，审查的是已固定的八键政策与原预算机制。是否值得继续：**是**，旧固定 pairwise 的历史 PIT 已有 Stage058 两项 P1，先证明新两臂共同消除此决策依赖，有明确资格工程价值；月 AI 池仍保留，不能称整套系统无模型。

## 审查结论

**P0=0、P1=0、P2=0；接受 Task1/2 的有限工程边界。** 此结论不等于新金融放行、全历史收益成立或生产资格。

1. `make_off_profile` 使用真实 022 `capture_formal_profile` 已完成正式 overrides 合并的 profile，再以 dataclass replace 合入八键 OFF；原 profile/spec 输入未变，资本与非政策字段保留。两臂真实构造器及 native MRO 均验证 OFF，未被正式 True 覆盖。
2. `check_settings_delta` 对完整 requested/actual 分别比较预期设置，原缺 OFF 键取已 pin native 的声明默认，actual 仍必须有对应有效属性。两臂各验 **173 键**。`account_capital/c3_capital` 由真实 engine.capital 补回 actual 后完整比较，没有因不是 strategy 属性而忽略资本；风险、月池路径、未知新增字段和缺字段均不能放行。路径只复用原 022 的 shared 空输入根归一函数，没有新增任意 path 豁免。
3. A_OFF 返回的 strategy/engine 与原 native 类分别 `is` 相等；B_OFF 原样调用 035 strategy 与 028 engine factories，内部 producer 仍为 `B_TS`。有效 runtime 均 None、四开关 False、三 tilt 强度0、AI rank 保护0，path-damage 仍禁用、strict minute 仍 True，月 AI 池原开关与路径保留。
4. 对整个限定测试外加失败 spy，覆盖 joblib.load、pairwise runtime 构造/score、Pipeline predict/predict_proba/fit、022 旧 model smoke。作者测试自带 spy 与外层 spy 均0；禁用 preflight 如实写 `disabled_by_shared_pairwise_free_policy`，没有伪造 passed model smoke。
5. 真实 metadata 构造将倒序 fixture CSV 恢复为 `AP.CZCE,au.SHFE,rb.SHFE`。原 planner 在旧 score 残值 -100/0/100 下仍按插入顺序，rank0、tilt applied0/multiplier1；slot2/budget1000 前两项入选，第三项 concurrent_limit；slot3/budget450 原量3得到3/1/0，第三项被普通 margin 拒绝，未享 rank 保护。
6. B 真实 on_bars、035 finalizer 和产品 reservation 路径得到原 admitted 10/10/10 → 最终10/10/5，gross 前缀0/1000/2000；原 finalizer 仅处理 admitted 项、保留跳过项及次序、只缩量不补位。人工执行 ordinal1/2/3 与 plan/sizing/decision 的 AI rank0 分开。每产品真实 reserve 恰一次，余额0→1000→2000→2500，plan.volume=selected_volume，无订单或成交。

## fresh 实测与证据

只执行新 integration 文件内的两个具名测试；没有运行旧 suite、数据扫描、load_data 或完整 run_backtesting。实际以 `.py311/bin/python` stdin harness 运行，先配置冻结数值栈，再安装外层失败 spy，导入原测试并只把其 `EVIDENCE` 指向本 Stage073 输出。harness 原文和实际命令保存在 `independent_test_harness.py` / `independent_test_receipt.json`，作者 Stage070 输出未被覆盖。

- 新 integration 两测试：**exit0，Ran 2 tests，0 failure/0 error**；日志 `independent_tests.txt`，独立输出 `test1.json/test2.json`。
- 必要小反例命令：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage073_pairwise_off_policy_independent_review/small_counterexamples.py`；**exit0**，两臂共88次预期拒绝，覆盖 requested/actual 分别漂移账户资本、C3资本、风险、月池路径、未知字段、缺八键/资本/风险字段，以及有效 OFF/runtime/path-damage/strict-minute 漂移。不是参数或收益扫描；证据 `small_counterexamples.json`。
- policy 独立 stdlib 导入后 numpy/pandas/sklearn/joblib 均未进入 sys.modules；数值栈实际为 numpy2.4.4/pandas2.3.3/sklearn1.8.0/joblib1.5.3，未安装或升级依赖。
- policy SHA256：`edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f`。
- test SHA256：`51731fdd31bd9fe2d7ba7f04ed34fc99f3c19fddb70dd7abae839d35c5771539`。
- Stage070 manifest 所列10个新源/计划/冻结依赖重新核 SHA 均相等，含原 qmt `6d6aa534715200c40a5743697114f73080111d609b29980d924dcb1d362792e9`；见 `source_binding_check.json`。总收据 `review_receipt.json`。

## 覆盖边界与后续

Task3 的真实 fill 身份、checkpoint/seal、纯 export，Task4 runner/dispatch/完整 preflight 均未实施，本次明确未审，也不以这些未来任务扣当前缺失。当前 preflight 禁用函数正确不代表未来 runner 已无旧 smoke；未来须在真实入口重新验收。fixture 的微型资金/预算仅为固定合法算术反例，不是金融参数。

原 B 仍为 Stage063 的真实 exit1（`qualified_delivery_old_value_conflict`），完整绩效 N/A；不重启、不读取部分 PnL、不因关闭 pairwise 抹去失败。新金融仍须数据冲突闭环、061 实际 commit 前缀冻结/独立签收、Task3/4 有限接合和 root 单次放行。有限 fixture 未证明全区间收益、严格 OOS、成本或生产资格，不能只胜 A_OFF 就宣告原目标完成。

本次新增/修改/删除策略代码、可调参数和回测结果：均0；仅新增审查证据及本文。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均 **N/A**。金融回放、模型 load/predict/fit、网络、CTP及订单均0；`production_qualified=False`。

结束是否在过拟合：**否**，88项是固定不变量的拒绝性边界检查，没有依据收益修改策略；既有历史研究选择偏差仍存在。是否值得继续：**是**，Task1/2 已足以支持 Task3/4 的有界工程准备；现有证据不足以启动金融或训练。合入者可读取本 Stage073 后统一整理状态，本审者不改 LINE/registry/memory/back_log。
