# Stage234 开仓日证据链实现与离线验收

- line_id：`futures_trend_stage819_intraday_rules`。
- 开始时间：2026-09-08 17:23；本验收记录建立于 18:10（北京时间）。
- 工作区：`.worktrees/live-broker-account-sizing`；分支：`codex/live-broker-account-sizing`；基础提交：`f70c2833055a2a7f59c67942c35b7f2c45dcb9ee`。
- 目标：补齐真实账户定量后，未来 owned 夜盘新仓的 OpenDate 原始证据、重启恢复及正常跨日全平，不优化 alpha。
- 是否重要突破：否，属于执行安全及正常退出兼容性修复。开始反思：不过拟合，未使用回测收益选择实现；继续有价值，新增风险之前必须具备可验证退出链。
- 执行计划：同目录 Stage233。本记录不是生产资格、当前券商持仓或已部署回执。

## 调研与判断

- [vnpy_ctp 原始结构定义](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)将 TradeDate、TradingDay、OpenDate 分别定义；不能用任一字段替代另一字段。实现读取原始 Detail.OpenDate，并验证日期范围而不是 OR 匹配。
- [vnpy_ctp 网关](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)与本地原始回调/查询路径共同作为接线依据。纯 checksum 通过不等于完整归属证明，必须关联原生委托、实际预留、逐笔成交和完整查询。
- 判断：不新增策略参数、不认领历史 unbound 仓位、不改变止损或 retry；缺证据应先阻止新增风险，不能先开仓后才发现无法正常退出。

## 实现范围

- 新纯模块重验完整账户查询、8 秒有界窗口、实际回调/事件/native 水位、物理委托及 reservation 归属、逐笔 Trade/Detail/Position 覆盖，输出独立 durable sidecar，不修改 canonical fill。
- Stage931 接入开仓前冻结基线、pre-native 原始身份、成交后串行查询、缺 seal 恢复、零成交终态证明及迟到回包冲突记录。仅影响新开风险准入，保护 close 保持自身既有门。
- consumer 从实际 ledger 校验原始引用与完整 native/fill/history 集合，在局部副本中补齐 query 来源日期；未验证的来源标签不能授权归属。
- critical 清单增加纯模块与两套测试；required suites 从 52 增至 54。旧资格回执不满足新集合。

## 已暴露问题与回归边界

1. 初版过滤请求可冒充完整查询、缺少必要水位/时间、显式账户/lease 冲突、日期矛盾、重复 Position 虚增数量以及终态状态量矛盾，均经独立语义负例复现并补测。
2. 正常 O→P→O 后还存在账户/最大委托量查询，native reqid 不能被错误要求紧邻 O→P→O。保持 query bundle 内连续，native 使用实际插入前 query 水位，并验证执行水位不变。
3. 迟到 Detail 在 builder 与 append 之间进入、append 期间超过 deadline、终态零成交永久 pending，已纳入适配器故障注入验收；不能用仅 helper 正向测试替代实际接线验证。
4. 真正 reserve 记录的 payload 经济字段必须按既有 fingerprint 规则复算；当前 reservation 由原始 checksum 和完整 warm identity 精确绑定。旧 lease 只有既有 durable 无副作用终态证明才可排除，不能借封存扩大再次开仓权限。
5. 仅核验引用存在仍不够：新增未被 seal 覆盖的同单成交、危险旧 lease 记录必须拒绝。普通后到 audit/reconciled 不应无故破坏合法历史证明。
6. 18:09 独立评审还发现 reserve@1947 → 安全终态 → 新 lease reserve@1948 的合法变价重试会被 consumer 旧全局 payload 比较误拒绝；当前正在增加真实 API 回归并修复。此时不能宣称完整退出 P1 已关闭。

## 已完成的主任务验证

- 清单 TDD：补新文件要求后先见 2 项失败；加入 critical/required 后，清单专项 `3 passed, 24 subtests passed`。
- 第一轮 trusted 白名单定向回归：`295 passed, 5 failed, 49 subtests passed`，21.40 秒；测试前后所测源文件哈希一致。5 失败来自 consumer 旧手工 fixture 与新增真实 reserved 证明不兼容，没有放宽生产门或错误正则。
- 修复 fixture 并完成第一轮集合闭包修复后，同四套 trusted 定向回归：`360 passed, 49 subtests passed`，20.65 秒，源哈希一致。此回执不覆盖随后变价重试修复，也不是完整 54 套或正式资格。
- 原始 stdout、JUnit、环境白名单回执与前后 SHA 保存在 `~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-stage233-20260908T1748/`，分别为 `scoped*` 和 `scoped-v2*`；失败未覆盖或删除。

## 参数、生产与后续

- 策略/资金比例/止损/retry 参数：无新增、修改、删除。8 秒是证据窗口上限，沿用已有 final query 默认值，不放宽交易 deadline。
- 无回测；期末权益、收益、最大回撤、Sharpe、滑点、交易次数和胜率均不适用。
- 本阶段未连接真实 CTP、未调用真实委托或撤单，未改 master、生产 checkout、CURRENT、manifest、launchd 或生产凭证。
- 后续：完成剩余兼容性修复和交叉评审 → 冻结源码做完整离线回归 → 保存候选源码 → 正式物料及 clean-commit 资格。最终真实交易启用由用户操作，不通过临时入口绕过资格门。
- 当前状态：实施/验收中，尚未取得生产资格。

## 18:22 第一轮完整离线矩阵与最后竞态复审

- 18:15:05 至 18:21:49，使用现有 `build_trusted_runner_environment` 白名单逐套执行 `_trusted_pytest_argv`，包括固定 `/usr/sbin/taskpolicy -a` 压力套件，没有外部 LANGUAGE/PYTHONPATH/emergency override。
- 54/54 套返回零，合计 `1633 passed, 828 subtests passed`；全部 critical 文件运行前后 SHA 一致。stdout、JUnit、逐套命令、调度策略、环境和 SHA 回执位于 `~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-stage234-20260908T1816/`。
- 变价重试 P1 已由原独立 reviewer 确认关闭：先验证完整 seal/history，再绑定当前 reservation；无 seal 路径仍严格拒绝不同 payload。
- 虽然矩阵全绿，独立 fault injection 仍发现两项 P1：开仓前 flat O→P→O 的迟到回包未使 baseline 失效；zero durable reuse 校验后收到 poison/新成交仍可清 pending。这说明全绿不代表完整安全资格；矩阵源冻结完成后才允许作者继续修复，两种源码状态不混用。
- 适配器已验证模拟 instrumentation→worker/同日重启→ledger JSON 重载→次日空 Order/Trade 查询→SHFE 实际 2 手（shadow=4）昨仓退出证明。测试仍手工设置 native context，不是完整授权 fresh_bundle→send_order E2E，此限制明确保留。
- 本阶段只读复核生产 checkout 与远端 master 均仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`；生产 tracked clean。没有升级生产或启动真实交易。
- 后续只修上述两处竞态并独立复验，不扩展 alpha 或放宽准入；资格仍未获得。

## 18:40 最终离线回执与源码收尾

- 两处竞态以 13 个先红后绿故障用例修复；作者定向回归 `302 passed, 422 subtests passed`。原独立 reviewer 又完成 7 项重放，确认 baseline 原证明失效/新 fresh 恢复、native 后 durable poison、zero 复用遇迟到包/新增成交/持久化冲突拒绝、正常跨日复用通过。本轮已发现的 P1 均已专项复验关闭，不能据此宣称没有任何系统风险。
- 最终适配器 SHA256 为 `077f92312db800f3f00a1bbc6c40a64247c11c010cf2daa22b7d2120611bdf68`，独立重放前后相同；没有在 native 临界区新增查询或 ledger 重读。
- 18:32:12 至 18:39:42，最终源码再次以相同白名单、逐套精确 runner 命令执行 54 套：`1647 passed, 828 subtests passed`，54 套全部返回零，全部 critical 文件前后 SHA 一致。`git diff --check` 通过。
- 最终原始 stdout、JUnit、命令、调度策略、环境和 SHA 回执：`~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-stage234-final-20260908T1832/receipt.json` 及同目录逐套产物。第二轮重跑是为绑定两处源码修复，不是因压力失败反复试到通过；参数和压力阈值始终不变。
- 收尾按已获授权只保存开发分支源码提交，不推送、不合入 master、不安装或激活新生产版本。提交后的具体 SHA 由 Git 与私有源码保存回执记录，避免在提交内部伪造自引用 SHA。
- 18:40 再次只读确认生产 HEAD 仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，tracked clean；本任务真实 CTP 连接、委托、撤单均未发生。

### 保留的发布阻断

1. 尚未覆盖完整授权 `fresh_bundle→send_order` E2E；已验证的是实际模拟 instrumentation/worker/recovery 和后续正常全平 gate，不混淆这两个层级。
2. 本次是开发态源码 SHA 一致性回归，不是从 clean commit 生成并签署的正式 qualification bundle；正式物料/生产 manifest、runtime/env、两次正式只读账户采集和生产日数据绑定尚未完成，不能借用旧版本资格。
3. 历史 unbound 或缺失证据仓位不自动认领；相关历史会在新开前拒绝。若要迁移，必须另行完成历史及当前真实账户的一致性资格，不能清账或绕过该门。
4. 最终真实资金交易启用由用户操作，本任务没有执行自动启动或创建绕过正式入口的替代脚本。

- 最终状态：`offline_candidate_verified_production_not_qualified`。
- 结束反思：不过拟合，没有 alpha、资金比例、止损或 retry 调参，没有回测收益筛选。继续有价值，但后续价值在完整授权链及正式资格，不是把测试全绿当成可直接实盘的授权。
