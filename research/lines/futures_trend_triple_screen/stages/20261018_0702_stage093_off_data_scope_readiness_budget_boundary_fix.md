# Stage093：087 readiness/真实时钟与公开parent启动余量两项P1修复

- line_id：`futures_trend_triple_screen`；时间 2026-10-18 07:02 CST；实现者 `/root/ordered_execution_review`。只处理090完整阻塞清单P1-001/002，一波必要修复，无新alpha/预算/框架。
- 本轮先读090实际反例脚本/原始tool观察，不把原三test通过误当真实owner链完整；再核084 `_readiness` 返回的`{document,path,sha256}`、preflight.execution_readiness及真实checkpoint内部hash/started_at。
- 原087记录、CLI、三源和证据保持历史身份；原源先复制到093/original_stage087，再改当前087两源/test。未改090、084、061、071、022、中性checkpoint、LINE/registry；未stage/commit/push或另派reviewer。

## 原始问题与根因

090源实测：严格nonfixture分支中，context.started_at已3小时前，owner把run_started_at改当前并绑定另一个B_OFF dummy readiness，旧load_owner/verify仍接受；真实context7200余量约−3600，旧remaining报告约1800。根因是只分别校验owner引用的JSON哈希，没有把readiness关联到**真实preflight及实际ps argv**，预算也直接用owner自报时钟。

第二个独立反例：直接公开provider `--role run` 的run_once绕过driver预算门；把remaining_engine_seconds替为0，旧parent仍启动一个受控假worker，预算检查调用0、fake launches1。这里没有真实provider/network，但足以证明入口会绕过原launch reserve。

原090反例脚本SHA`db6b14021ae187f8b10705bac81e714ef7d268df65e054ddfa2220a748fa9bcd`；原观察SHA`17274058f529202f2fc1f20425352e9927204795e40116d1a537a1d686fc4bae`；evidence SHA`4e2566d0aba25997c8fc7a9cb51849f8484a78bef9f9c3af0da305be1c3843a4`。均按root提供SHA读并复制为093/original090_*，没有重跑090原命令或覆盖其输出。

## 唯一修复波次

P1-001：仅加强Owner.verify及remaining_engine_seconds的nonfixture边界。context仍按原schema、arm/attempt/run_id/output/writer身份核验；新增context内部preflight_sha256与实际已pin preflight字节一致、source/data bindings内部SHA和实际preflight一致、preflight arm/attempt/fixture身份一致。owner execution_readiness的path/SHA必须等于真实preflight.execution_readiness，document必须等于该SHA实际解析的文档，arm/root授权/既有source-data绑定/原1800-7200限额保持一致。再对齐真实ps argv中唯一`--execution-readiness`及其SHA参数；不是另造替代readiness合同。

owner.run_started_at必须与context.started_at**原字符串一致且有时区**，禁止重设。remaining从再次验证后的真实context字节读取started_at，fixture分支保持原测试隔离，不把fixture当金融。checkpoint.writer继续为stage065_account_checkpoint.py，金融runner仍取context/preflight source bindings。

P1-002：公开provider run_once自身先重验owner/current，在SDK离线检查前核金融剩余≥840，再在实际attempt/worker启动前复核current及同余量；不足则无attempt、无Popen。840仅launch reserve，worker正常完成不再要求余下840；原570soft/600hard、单attempt/无retry不变。没有给公开入口增加免费连接或新预算。

除这两处真实边界及两个具名回归外，没有改新scope协议、缓存资格、provider/API/collector、策略或独立reader逻辑。旧087原三test方法的bytes仍完整保留，按移除新regression class重建SHA精确等于旧test `629f81cb4ce3880e96f52756f8fd33c62e7f104b18803356d33b92d89fbe8e2f`。

## 定向RED→GREEN及证据

真实命令（仅两个新增方法）：

```sh
PYTHONDONTWRITEBYTECODE=1 .py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage093_off_data_scope_boundary_fix/run_two_regressions.py
```

适配器只在内存中把测试OUT从087改到093，原`__file__`与实际实现身份不变；不会覆盖原087证据。测试仅`ScopeBoundaryRegressionTests.test_owner_readiness_and_context_clock_are_bound`及`test_public_provider_launch_reserve_cannot_be_bypassed`。

- RED一次：2 tests/0.010秒/exit1，两个assertRaises均因原问题未抛异常而FAIL；public budget calls0/fake launches1。非import/环境错误。RED两观察另存red_regression_*，不被GREEN覆盖。
- 修复后GREEN一次：2 tests/0.028秒/exit0。正确旧context时钟继续约−3600秒；错readiness、单独改时钟、实际argv path/SHA、preflight arm/attempt、document冲突及内部preflight SHA拒绝。全部是同一P1身份链的字段反例，不另扩安全矩阵。
- parent余量0/839时各budget calls1/fake launches0、无attempt；900余量允许一个受控假child，SDK前后共检查2次，child结束不再核840；已有attempt拒绝。所有worker/SDK/ps观察为明确受控替身，无真实owner/网络/金融。
- 三文件compile exit0；未重跑087原三测、旧suite、整库/全市场预检。共两个方法各RED/GREEN一次，4次方法执行，0金融。
- 084/061/071/022/checkpoint五源SHA前后未变；13份原087记录/证据原文件未变；完整16对象原始快照和SHA在original_snapshot_manifest.json。新旧源码精确diff保存各文件.patch。

## 冻结身份与交接

| 文件 | 原087 SHA | 新093 SHA | 新bytes |
| --- | --- | --- | --- |
| stage087_off_data_scope.py | `7c65bb01147a687529e27901d82b74ff4284a4dc1c84be2c7fe22e8f3aa5d737` | `5919f098af14ea9819cee3445e2555f9a740ebc2c808af1afdafa508235d01fb` | 52670 |
| stage087_off_data_provider.py | `d8ecebf5b27ebb4179f81f7b960165a14ddbe9ce8655837bbf58ff1ecbf4706f` | `33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46` | 16901 |
| test_stage087_off_data_scope.py | `629f81cb4ce3880e96f52756f8fd33c62e7f104b18803356d33b92d89fbe8e2f` | `17863dd4ec07ee43128c9ef606cb131fc07fd9fae79df2c917680062dd29dd6a` | 35924 |

CLI/五个数据边界API均不新增、不改签名；新增精确要求是owner时钟原样复制实际context.started_at，readiness只能取实际preflight/argv同一path/SHA/document。root在未来真实runner/PID存在后才能绑定，不会因本轮测试生成金融owner。

两源与test已先发root，可并行交同一独立reviewer094定向复核；本记录/实施收据`independent_review=false`，不自签关闭090或data_scope_review。root后续独立receipt仍需source_bindings恰两源绝对path→SHA+bytes，test/dependency另字段；旧087/090身份不覆盖。自检未见这两项剩余失败，是否接受由094/root决定。

金融/真实provider/网络/训练/预测/订单/全市场审计均0，production_qualified=false。新增/修改/删除策略参数与完整回测结果0；权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。

开始/结束过拟合判断：否，这是有真实反例的身份和预算接线修复，不按PnL选参数；继续价值：是，原完整对照数据通路必须拒错授权及超时启动。未使用新外部资料或联网，判断来自090原反例及084真实源字段，不证明alpha、数据齐备或金融readiness。
