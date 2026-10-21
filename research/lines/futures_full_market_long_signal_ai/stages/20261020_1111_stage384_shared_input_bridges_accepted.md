# Stage384 双模型既有账户已接入，实际新行情恢复仍待验收

- line_id：`futures_full_market_long_signal_ai`；整理：2026-10-20 11:11 CST；非重要收益突破、非正式C9晋级。
- 本轮是实质工程进展：补齐370旧模型context读取和357持久化终态的最小恢复接口，并真实读取了两个模型的既有空态。**没有新训练、历史预测、资金回测或行情连接，盈利目标仍未达成。**

## 判断与范围修正

381实查时钟11:02仍早于完整日线窗口，但发现既有370/378状态、357/339固定定义已足够完成这两项必要依赖。383独立读前确认可实施。因此修正“所有收盘前接线都等待实物”的过宽禁令，没有改旧证据、模型或科学比较，也没有把剩余目标缩为兼容性。

调研依据是[Freqtrade维护者关于前视偏差及验证覆盖范围的说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)，实际工程判断来自原357/339/321/376字段。维护者资料不提供本策略alpha；本次不执行其重复历史回测命令。我的判断：让两个模型在同一真实输入上使用各自真实账户，是获得未来收益/回撤证据的必要步骤，可以现在完成，不能借此声称收益更好。

## 新增接口与验证

新增382工具及一个组合fixture；旧359/370/375/376/378、所有原核和账户均不改。科学参数新增/修改/删除0，旧回测结果修改/删除0。

- baseline桥从原370 manifest/envelope/source_bundle读取2023模型、原T0/T_init、原两本状态和既有journal；重建identity须与原身份完全一致。缺journal文件就拒绝，不新建/补签；不调用new_state或append。
- 恢复器读取357保存的final warmup_state/inventory，使用同core的from_dict/to_series和原SnapshotMarket；**不追加u20、不重读raw874**。原321 input_snapshot对象提供真实provenance、source_receipt、D_context与clock；完整economics按331+344原冲突规则合并，保留98产品/95族及全inventory。
- 完整重建observations/raw26必须与已存357证据相同，不作模型评分。未保存的adapter诊断字段明确省略，不猜为空；两个版本以后使用同一恢复对象的明确身份，不冒称原内存对象逐字节重建。development_only仍True，实际接受留待361/362/363。

唯一新组合fixture为合成落盘输入，作者RED→GREEN、最终1test/0.325秒；383独跑同一组1test/0.328秒，P0/P1/P2=0。覆盖公开读取入口、原文件不变、终态N不doubleappend、完整经济域/双时钟/缺失、旧与无状态epoch、损坏或不匹配拒绝。旧suite/真实历史价格或训练实体读0；不重审373训练数值。

冻结工具15907B/SHA `fcd567e8b7ab5c4c320306c3fc30d9adbe137c0c8183fa81c175a404792f27ae`；fixture16108B/SHA `9eb68ded5aa518396b6568ee6488da07fe10f4b02399f5bf38ebe835e0b60a6d`。[源绑定](../outputs/stage382_shared_input_restore/prepare1/source_bundle.json)包含原依赖和381 scope；[383阶段](20261020_1104_stage383_readonly_bridge_feasibility_review.md)记独立结论。

## 一次真实双context读取

root唯一真实读取exit0、0.284492秒，context_loads=2。调用期间profiler禁止new_state、append、infer/process_snapshot、seal/advance、cash runner及actual restore；没有重新初始化账户。

| 版本 | 真实模型冻结（北京时间） | 原账户初始化（北京时间） | 场景/初资 |
| --- | --- | --- | --- |
| 原2023参考 | 20日04:21:56.703789 | 20日04:34:30.535301 | base/stress各100万 |
| latest成熟版本 | 20日04:48:38.399842 | 20日05:03:07.185431 | base/stress各100万 |

四个accountID保持原样且互不相同；旧policyhash `0db5d710…23f13`，新`06d86200…06eff`。两个模型的base/stress均awaiting_u/next_u5290、仓位/pending为空、inactive。12个原state/envelope/policy/index/object文件的前后binding全部相同。加载时间没有被拿来重置T_init或模型冻结时点。

[真实读取收据](../outputs/stage384_shared_input_wiring_decision/actual_context_binding.json)，71387B/SHA `bec2ba4c2345f70e15ef933e545685582dd7d63adbef5ffa6473c5fa4fab5f6a`。[独立最终小核](../outputs/stage383_shared_input_bridge_review/actual_dual_context_binding_review_receipt.json)，2780B/SHA `99da536bc82f66fb690e76822d9523af1d1b4acea1ef63dbe902677c66f219cd`；审阅只看小收据/profile/绑定字段，不重跑loader、fixture或市场实体，剩余P0/P1/P2均0。

本轮new_state/append/推断/实际input restore/financial_D/fit/cash/API/SQL/Git全0。累计454完整fit/246cash及1旧金融partial不变。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全N/A；初资不是收益结果。

## 接收条件与实际未完成项

最小文件/runtime检查：凭证文件存在、未读内容；tqsdk=3.10.2与原授权一致；原一次输出目录未占用，入口/授权binding未变。没有连接或启动后台任务，该检查不能证明接收一定成功。

`actual361_restore_qualified=False`、`actual_forward_E2E_ready=False`仍保留。实际361原计划仅20日15:15后且21:00前单次874×3、最多1API/不重试。收到真实终态后362独审、363裁决，再一次actual restore核原观测，接受描述必须绑定真实terminal/review/decision与同一composed/双域；不能仅把development_only改False或复用原未出资seal。

随后376才可对同一输入、各自原context生成新的完整资金proposal，两个模型分别满足freeze及自身T_init早于source完成、完整proposal真实seal早于prescore eligible-or-unresolved全执行域Dopen，含自身持仓/pending依赖。unknown/late保留gap与事实，不重置或跳u。当前仍只u20/D21，没有永久日更/自动唤醒或生产就绪声明。

[root裁决](../outputs/stage384_shared_input_wiring_decision/decision.json)，SHA `6a8a8514511897acc0d3a666f19e593b38f04c3a7c2ec1e12a5f74eb0f2ace65`；[唯一下一范围](../outputs/stage384_shared_input_wiring_decision/next_scope.json)，SHA `daf1f608b274b752636677ebf579185cd30aa6918caa7895d8ed472a3fa38c11`。新工具/fixture副本与现有依赖引用已本地保存，不复制大行情/训练实体，不声称独立运行时或正式发布。

开始及结束新增按收益调参过拟合：否；历史择题风险和新增训练版本自由度仍在。继续价值：是，必要读取/恢复依赖已完成，下一步应真正消费新日线来取得经济证据，而不是继续补同类工程。高收益/低回撤、高质量泛化、极窄损与增加投注仍未证明，goal保持active；恢复后的阻塞审计0，不沿用旧380三轮。只更新本线LINE/registry，不追加根总账，不改正式版/生产/CTP/订单/邮件/调度/Git。
