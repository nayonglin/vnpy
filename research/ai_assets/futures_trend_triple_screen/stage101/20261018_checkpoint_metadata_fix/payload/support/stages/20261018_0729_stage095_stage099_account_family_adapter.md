# Stage095后续：Stage099账户族最小路径与来源绑定适配

- line_id：`futures_trend_triple_screen`。
- 时间：2026-10-18 07:29:28 +0800。
- 依据：root Stage099合同`20261018_0723_stage099_checkpoint_repair_run_family_contract.md`及真实098最终pins。不是alpha突破，不产生金融成绩。

## 改动与判断

这不是调参过拟合：没有策略、风险预算、成本、日期、手数或模型变化。继续有价值：合法元数据误拒导致原A失败且没有完整可恢复账本，未来真实新请求必须使用清楚披露历史的新运行族，不能把旧partial当accepted。

原095源SHA `796aaef7994018196deb4799132a0cd288c027516f21ce672646c880d05990dd`、原准备收据、原唯一阶段、两原模板及静态证据共7文件逐字节保存到`outputs/stage095_off_financial_audit/stage099_family_adapter/original_stage095_snapshot/`，原件未覆盖。快照manifest SHA：`f09a993c49cad968046d35a1007dcf789ac003cbbe38a6e869f1202a051fc757`。原065账户族及096/097失败证据未修改，未读取账户或失败partial。

本次只改：

1. 固定`ACCOUNTS`改为`outputs/stage099_pairwise_off_account`。每臂attempt1只是新族内序号。
2. 实际checkpoint pin改为`ff2790a36d8b66d8de7e854c6daf3bd6efd7f275d474f4374883ead66e21fe99`，实际runner pin改为`1717f2ef30d098f4e503906c032f9b6ddac7aa9b968ae072b60b32b86b0725fb`。未猜测未来hash。
3. completion与真实preflight/readiness严格共同披露`repaired_checkpoint_family=stage099_checkpoint_metadata_fix_v1`、`global_financial_attempts_before_family=9`、`global_arm_attempt=2(A_OFF)/1(B_OFF)`及`prior_A_OFF_checkpoint_failure`精确096工具终态路径/SHA。金融审计receipt和四行comparison传递该身份，保留原A第1次`failed_no_complete_performance_NA`。原A1不是成功或可恢复绩效，下一A不是全局首次。
4. 094继续作为历史外部有限审查继承；当前scope review不硬编码未来100 SHA，而取已外部SHA闭合的实际`preflight.execution_readiness.document.data_scope_review`，必须与`preflight.data_scope_binding.review`精确相等。同一份review bytes先验SHA后解析，要求独立审查、P0/P1=0、`source_bindings`恰为实际preflight中087 scope/provider两源SHA+bytes；继续重验两源当前文件并保留原checkpoint全部source快照/owner/seal验证。100可同文件作integration/data_scope review，不产生095与收据hash循环。

现金/库存/净值/成本一次、A原001母单算法、B038原q/T/S/gross、真实pairwise rank0与独立ordinal、1641日、原七门、1.10/1.65诊断算术均不改。`adapter_fragments`、`runtime`、`settings_review`、`raw_exports`、`a_mothers`全文与旧源一致，其他diff仅上述身份和绑定，见`source_diff.patch`。没有新增alpha参数，没有新增/修改/删除回测结果；权益、收益、DD、Sharpe、滑点、交易数、胜率均N/A。

## 有限验证与交付

真实单次子进程执行：

```sh
.py311/bin/python -m py_compile research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py --schema-check
```

两命令真实exit均0；仅stdlib路径/元数据/静态adapter compile。未重跑旧suite，未读账户/PnL、engine、行情、DB、数据或模型，金融/provider/网络/训练均0。`verification.json`保存精确argv/stdout/stderr/returncode；source diff SHA `8764d5c6897ffbb5342560c3776938eb461b5cb2c988343aec00978b6f43192e`。

最终源：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py`，SHA `be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f`，`40131` bytes。原095准备记录保持历史内容，新族真实输入仅用本后续目录两份`*_completion_input_TEMPLATE_NOT_TERMINAL.json`，仍不是终态或执行授权。

未来CLI保持：

```sh
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage095_independent_off_account_review.py --audit --arm A_OFF --completion-evidence /ABS/root_actual_terminal.json --completion-evidence-sha256 ROOT_SHA
```

只有root未来明确给出本族实际exit0工具终态、完整raw/seal/summary及精确SHA才可执行；B_OFF同入口。当前没有金融accepted结论。071/087资格仍只继承外部078/081/历史094及未来实际readiness绑定的当前独立收据，095不自审这些来源。root100仅需定向看本次路径/pin/lineage/current-review差异，不重审旧会计算术。

本次调研结论限本仓库真实接口与root修复合同；没有新增外部alpha主张或网络调研。新金融仍需root后续独立接受、新族真实preflight/readiness及另行启动指令；此次只是代码和临时元数据fixture授权。目标未达成，`production_qualified=false`。
