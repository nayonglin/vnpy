# Stage064：B_TS attempt1 真实失败的独立有限复审

- line_id：`futures_trend_triple_screen`；复审时间：2026-10-18 05:48 CST，精确到分钟；审者：独立子 agent `delivery_guard_readonly`。非重要策略突破，不修改 LINE/registry、当前源码、数据或已签收据。
- 结论：原 B 第1次金融尝试已经真实 **exit1**，是 `2022-05-31` 实际 Stage021 `ensure` 的 `qualified_delivery_old_value_conflict`，不是超时。没有完整账户checkpoint/seal/summary，完整绩效全部 **N/A**。不能把部分审计、190次数据追加或独立delivery收据当作完整金融结果，也不能从不存在的checkpoint做export-only恢复。

## 真实终态与失败链

1. root实际观察的Stage063终态：`outputs/stage063_b_ts_actual_failure/actual_tool_terminal.json`，SHA `8f556fb6b76c27f28db7ff7799643bda5c7e934c844a29546545efe10d21981b`。独立核其内容及绑定：金融session70433真实exit1，数据session43111真实exit1；本审查不假称重新等待了已结束session。
2. `run_failure.json` SHA `f39f9d60b3e975263b0ee9411b70b766a9a8c4a3f12d068b9c35650888928536`，状态`failed_closed_no_accepted_performance`；唯一捕获bar失败为`2022-05-31 00:00:00+08:00 / ValueError('qualified_delivery_old_value_conflict')`。失败始末为03:47:59—05:44:11，实际墙时6972.581391秒、观察到数据等待6678.624222542945秒；没有WholeRunBudget超时错误。
3. `batch038` journal为`blocked`、provider_connections=2。最后本机交付指针发出后，B因上述bar错误退出；driver随后`ps -p 21822`身份检查失败。这是数据driver的停止原因，不是把B退出归因成新的provider超时。该journal SHA `73ef1b15348583ef9e8947f2d70202f18bc4a5f2e6039d82c6fd9ef5cceac480`与真实终态绑定一致。
4. 原036源码及`runner_used.py`均为`34563257e25e49b19c9631e06cd9107fc26cfd954713739e01a1bf67d574ff43`；原021仍为`150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b`。本审查没有更改进程、模型、价格、源文件或错误记录。`engine.log`为0字节，不能从它补造堆栈；具体失败由结构化run_failure与gate审计证明。

## 191个指针与190个实际追加必须分开

- `data_wait/audit.json`共191条，全部状态为`qualified_delivery_pointer_accepted`；与run_failure内resolver及最终`qualified_wait_audit.json`完全一致。
- gate审计为`data_requested=191 / data_qualified_appended=190 / data_gate_failed=1`，request_sequence恰为1—191且请求摘要唯一。
- 对190个实际追加逐条比对request、receipt路径/SHA、data路径/SHA，与191个resolver记录对应一致，无重复、无反向缺项；这190条的`old_keys_changed`全部为0。这里校验的是绑定和事件，不重复190份资格源的完整数据审查。
- 唯一“pointer accepted但没有runtime appended”的请求是191号：`6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730`，`fu2209.SHFE / 2022-05-31 / full_session`，R=345、E=226、M=344、候选新物理键119。最后gate事件正是该请求的`data_gate_failed`。
- 原021在全部旧键七值`np.array_equal`通过前不提交mapping或dynamic资格集合；当前唯一symbol在overlap处抛错，因此本delivery的119个候选新键及整包新权利均未提交。已经由其他证据获得的先前权利不因此被这份失败交付覆盖或撤销。

## 最后一份收据的实际声明与继承限制

- 最后收据：`outputs/stage052_generic_daily_source_resolver/request_6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730/delivery_receipt.json`，SHA `274190b95b9c1ff18cdee2743730ddec0a89b6ad4f035e108f69f269701327bf`；data SHA `7e41b88df89143f1205f83e53280c9b84f23ff15ce06309aac698e7b70ddec22`。响应指针、parse_result、key/local checks与以上绑定一致。
- 它的`old_physical_values_independently_compared=False`和`old_value_comparison_delegated_to_actual_stage021=True`均明确；没有错误宣称已独立重载engine旧值并全部相等。`full_session_qualified=True`/parser通过只表示交付本身按完整分钟和daily合同被接受，不等于与原engine物理旧键兼容，更不等于已经执行追加。
- 新写`outputs/stage064_b_ts_failure_independent_review/excluded_delivery.json`，明确该请求`runtime_gate_accepted=False / data_qualified_appended=False / inheritance_eligible=False`。原收据和数据文件保持immutable；失败整包不能进入继承层，也不能仅凭`parse_result.status=accepted`扩大权利。
- 后续若重建继承数据，必须将独立资格/指针证据与对应原runtime `data_qualified_appended` 的精确receipt/data绑定结合；此次190条通过事件可保留证据，最后一包单列拒绝。此限制不等于判定其所有raw值都是错误的。
- 具体冲突列、数量和engine旧值来源由root另行只读定位，本审查不重复大源读取，也不猜测是价格、OI、浮点序列化或策略alpha导致。

## 有限关键旧资产字节检查

- A0 accepted的四项小资产`daily.csv / summary.json / metrics.json / run_provenance.json`逐个重算SHA，全部与036内冻结`A0_SHA`一致；未打印或分析其金融内容。
- 最后收据绑定的Stage002/Stage011两份source_manifest，以及fu2209日线和Stage491/459/462三份本机分钟CSV逐个重算SHA，全部匹配已有绑定。这些来源总量有界，检查仅为字节一致性，没有再次解释冲突字段或重签市场源资格。
- 没有重hash完整full-minute baseline、数据库或全市场文件，不能据本审查声称所有市场数据的终态字节均已验。完整有限路径/SHA保留在evidence；A0关键资产不变也不等于本次B回放完成。

## 分级、计数及后续边界

- P0=0；P1=1：交付与当前engine物理旧值不兼容，导致原B没有完整金融结果；本复核不把未知具体冲突原因归责为实现bug或模型问题。P2=1：pointer/data独立接受与runtime追加是不同资格，继承入口不得混用。
- Stage057/058的固定pairwise历史PIT两项P1仍独立保留，但不是本次异常或终态原因。即使未来补好数据兼容，也不能因此自动补回模型PIT资格。
- 按root既有总账，8次attempt/3次完整验账不变；本B attempt1记为失败，不新增完整绩效，本审查新增金融尝试0。
- 新增/修改/删除策略参数、金融结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A，未报告任何部分PnL。
- 复核脚本`outputs/stage064_b_ts_failure_independent_review/review_failure.py`实际exit0、约0.025秒。独立收据SHA `916edbc472fb49dcb9e1fbcde396b0b555a82b1468622b1db526a98c1bee9963`；evidence SHA `5c74bbc5c5fd219c954f94bd72ed931d0daa2d42367680bbe3c4380116586196`。
- 开始与结束新增过拟合：否，本次不看部分收益、不调参、不选源救结果。继续价值：是，定位并保留真实拒绝证据有价值；不得为了完成曲线绕过旧值守门、覆盖旧源或无授权重跑。
- 网络/模型训练/预测/金融回放/订单均0；外部资料/GitHub按root明确禁止网络的失败证据审查范围未检索；`production_qualified=false`。
