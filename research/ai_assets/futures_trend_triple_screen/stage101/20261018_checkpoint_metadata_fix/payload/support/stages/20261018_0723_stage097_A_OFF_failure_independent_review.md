# Stage097：真实A_OFF attempt1失败的独立有界审查

- line_id：`futures_trend_triple_screen`；记录2026-10-18 07:23 CST；独立reviewer `accepted_delta_review`。
- 真实owner：A_OFF、attempt1、run_id `982636a096884e7e9610b1ad49eb1ae1`。
- **结论：真实工具exit1，已返回引擎后在raw保存前失败；完整绩效N/A。现存材料不能证明完整等价恢复，不能补造raw/seal/summary。P0=0/P1=1/P2=1。**
- 本reviewer没有实施/重跑本次账户，也不授予098改源或新金融；源与原失败owner保持原件。

## 终态、owner与source

真实终态来自root已观察工具session13114、chunk8c75d9、exit1的不可变记录，SHA `8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085`。run_failure SHA `6a21416440f3f3441599435ebf55c1ae688006d865d5683a537fea5af2c3d082`，failure_capture SHA `443216dc4e7b3b2550f97aeafee33c9f4376a94aa1513ad3f8e19f5c71cfd96f` 均独立读字节核对。

context SHA `46126a8af641d76e47978bd10d5aba9b7a5f8072af24ef7f0f781b0f7f1db7f7`，preflight SHA `4612f307b30e6917d227d624cdbf35c9ff74238a73cd1d0bd7a8267a53d92bf5`。arm/attempt/run_id/output及内部source/data/preflight SHA一致；root readiness `8eee3c7753ac4c86e9dc9a9f754ba2785abfa92e31f54644c305d52cb3b5fe69` 与actual argv、preflight.document/source/data全等。HEAD和preflight/root terminal source_commit均`4e439c2e5d653d4171c4396afdc2aad037c547c7`。

五个关键源（runner/checkpoint/031collector/022capture/policy）当前字节与各owner不可变snapshot核对一致：runner仍d83、checkpoint仍7e5。context声明394 source bindings、preflight声明4647 data bindings；本次不全市场重hash，不能把有限五源核验冒称完整input guard已完成。根终态明确engine已返回；源码save调用位于run_profile_once返回之后，partial又含calculate_result收集的trades/usage，三者相互支持。

A目录只存attempt_started、空engine.log、context、preflight、failure capture、run_failure及sources；确无data_wait、checkpoint、seal、summary，capture wait/resolver均0。B_OFF根不存在。本次是第9个金融attempt，accepted ledgers仍3、训练0，计数继承root终态而非本reviewer重扫旧账。

只读ps在sandbox被PermissionError拒绝，未升级或猜测进程状态；终态真实性明确继承root真实工具观察，并用其pin与本地owner交叉绑定。空日志或文件锁不是终态证据。初版绑定harness因ps抛错exit1，改为如实记录观察不可用后metadata核验exit0；未因此再次unpickle或金融。

## P1-001：纯字符串元数据被按键名误拒

位置：`tools/stage065_account_checkpoint.py:196–200`。

精确被拒路径为`payload.preflight.ai_pool_audit.strategy`，type=`str`，value=`ai_top10_plus_fu_official_live_v1`。这是AI池来源身份，不能因为键名strategy就等同真实strategy对象。对已pin真实preflight单独调用冻结`_account_only`，真实重现`checkpoint_forbidden_engine_or_history`；无engine/strategy构造。此结论先独立读原件并复现，再与root反馈对照，不依赖作者自述。

guard递归所有Mapping、只要键属于engine/strategy/history等即拒绝；该生产preflight元数据进入raw payload，于raw原件写入前被拒。对象/隐藏DataFrame对象的原防线有价值，但不能把纯身份字符串无条件列为禁止对象。

原test3 checkpoint fixture preflight literal（test约302行）只有fixture_only/reference_calendar_scope/reference_calendar/source_bindings/data_bindings/account_classes/disabled_pairwise七键，不包含真实ai_pool_audit。它验证tiny真实fills、raw/seal/export生命周期与隐藏object拒绝，**未覆盖真实preflight元数据结构**；本轮不重跑该旧test。

root可另授权的最小修复边界：只对明确路径/类型/值的已验证元数据作窄例外，保留真实engine/history、DataFrame attrs/object cell等拒绝；在真正prepare阶段用实际preflight/spec/parameters先做同account-only元数据门，避免金融后才发现接口不兼容。本reviewer未改冻结源或自行加修复波次。

## partial实际保留与完整恢复判断

本reviewer在冻结numpy/pandas栈，以已pin原033的`OwnedAccountUnpickler`（SHA `940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf`）**仅一次**解读SHA固定430064-byte failure capture。只执行该原class的AST投影，allowlist不允许导入策略/native模块；无engine、strategy、市场loader或模型模块装载，没有计算收益或完整财务曲线。

| 保存对象 | 覆盖诊断 |
| --- | --- |
| capture.trades / usage | 各817条，各817唯一trade_id，ID集合相同；保留成交及执行来源信息 |
| capture.equity | 1697日期，2019-10-15至2026-10-14；覆盖1641参考日，另56预热日 |
| minute_requests / anchor_requests | 500 / 534条，仅核字段/数量，不宣称严格分钟门通过 |
| failures / weekly_gate | 0 / 0条 |
| actual / effective_off_policy | 各1组真实捕获 |
| wait_audit / resolver_audit | 各0 |
| ordered | A要求的None |
| context/preflight | outer context仍在，preflight可另取已pin JSON |

**完整等价恢复不可行，缺项如下：**

1. returned `combined`完全缺失，包括原native每日PNL/成本/保证金合并表。
2. `frames`整体缺失：trades、positions、entry_risk、entry_candidates、trade_events、intraday_events、c2_events、stop_retry_events、rollover_shape_same_volume、rollover_delay、long_signal_atr_shock、long_signal_range_atr、pending_orders共13张原返回表均没有保存。
3. 独立collector的actual_trade_identities原列表缺失；capture.trades少signal_datetime/signal_order_id/intraday_episode_id，usage虽有这些字段，却不是独立native identity原件，不能用join声称原件已保存。
4. 实际返回spec、parameters、engine_elapsed_seconds缺失；preflight的预期身份不能替作运行时实际返回观察。
5. raw/validation/seal/export及之后actual settings/parameters、combined calendar/1641、strict minute、全inputs unchanged门尚未完成，没有独立财务算术审查资格。

1697条内部estimated_equity/settled_balance不是原returned combined；即使筛成1641日，也不能补回日成本/持仓估值/保证金或母单所需事件链。817 trades与usage可以保留作取证，不能补造positions/候选/risk/retry/rollover/pending等表。当前目录没有另一份完整经济账本可直接复用；不能称恢复通过，也不能从该partial发布完整收益、胜率或seal。

这次原guard误拒导致本可在RAM中的完整返回表未落盘；原异常分支按partial设计只投影capture/audits，不含combined/frames。本审查把它作为恢复硬限界如实列出，不以拼造缺表或再跑账户来绕过。

## P2-001：phase诊断误标

runner phase初值`engine_not_returned`，只在save_raw_checkpoint成功后改为post_engine_validation。本次save失败，所以partial仍记初值；这不证明引擎未返回。真实根终态、调用顺序及capture证明已完成calculate_result并返回。属于非阻塞定位限制，成功门未放宽；不因此自行扩大098或触发新回测。

## 交付与判断

完整命令/exit/SHA在097 evidence.json，表覆盖在coverage_diagnostic.json，owner/终态在owner_terminal_binding.json；原诊断脚本与tool输出单独保存。现存证据的cause/owner/字段缺失结论置信度高，经济完整性和等价恢复均N/A。没有签seal、summary或财务接受receipt。

新增金融/旧账户/旧tests/完整曲线/市场hash/网络/模型load-fit-predict/订单0，不改source、失败owner、LINE/registry或Git，不另派agent。当前仅交root选择后续最小修复，不授权重启A或启动B。新增/修改/删除策略参数和完整绩效0；权益、收益、DD、Sharpe、滑点、次数、胜率均N/A，production_qualified=false。

调研与判断：遵root明确无网络边界，仅查冻结本地真实失败、metadata和接口，不新做网上/GitHub或alpha研究。开始及结束过拟合判断：**否**，没有按收益选参数或诊断曲线；继续价值：**是**，根因已可定向修复且恢复不可行已证实，可避免对缺失账本作虚假接受。原A0受限、原B失败N/A、PIT限制及目标未达结论继承。

