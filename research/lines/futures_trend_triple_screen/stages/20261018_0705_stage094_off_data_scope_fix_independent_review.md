# Stage094：087两项P1修复的定向独立复核

- line_id：`futures_trend_triple_screen`；2026-10-18 07:05 CST。
- 独立reviewer：`accepted_delta_review`，非087/093实现者。
- **结论：仅关闭090的P1-001、P1-002；本次剩余P0/P1/P2=0/0/0，固定093两源有限接合接受。** 090原P1=2失败receipt/原始反例永保，本结论不覆盖或改写原失败身份。

## 固定身份与限界

scope新SHA `5919f098af14ea9819cee3445e2555f9a740ebc2c808af1afdafa508235d01fb` / 52670 bytes；provider `33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46` / 16901；test `17863dd4ec07ee43128c9ef606cb131fc07fd9fae79df2c917680062dd29dd6a` / 35924。最终093实施receipt SHA `b535d1b06817ff2db55389bdac012c027264937e6f4b44325b2ce70ae85b8c4b`，stage SHA `e6a8dac58ad82d4e07c2c1f3baa32f53c5e746db89f55f1412c2842dedea6710` 已核。

按root授权先固定三SHA启动，后补文档仅核身份，不因文档补齐重复测试。只读两源直接diff、新两项回归及084 readiness/中性checkpoint序列化的必要接口段；不重审061/071、旧市场历史或090其余资格算法。16对象旧快照、两源精确diff、五冻结源、13旧记录及作者36 artifact SHA均核对；原三个方法AST未变。090 receipt SHA仍`91ea83235b9cbc6f2c13240fbc31d3a97a64e145b2de17aa39227fd723a774da`、p1_findings=2，不覆写。

## 两项关闭依据

P1-001：非fixture verify新增context schema/内部preflight SHA与实际pin字节相等，source/data bindings内部SHA与实际preflight一致；preflight arm/attempt/fixture身份一致。owner readiness path/SHA/document等于实际preflight.execution_readiness，内容符合原084已有arm/root授权/source-data/1800-7200要求；实际ps argv的唯一readiness路径/SHA同一。没有发明替代readiness协议。

owner.run_started_at须与有时区context.started_at原字符串完全相等；remaining每次核owner并从已pin context bytes读真实起点。定向回归中原context已3小时前，正例余量继续约-3600秒，不被重置；错readiness、独立改时钟、argv path/SHA、preflight arm/attempt、document及内部preflight SHA共9负例拒绝。对照084的实际`{document,path,sha256}`返回/prepare全等门及checkpoint JSON hash格式确认字段匹配。

P1-002：公开run_once在SDK前核同owner/current及≥840，SDK后、创建attempt和Popen前再次核同current/余量；不足无attempt、无子进程。840仅启动reserve，worker启动后不重复要求840；原570soft/600hard、真实父子wait/finally和once attempt未变。

新增定向回归覆盖0/839拒绝、正常900/900启动一个fake child，启动后第三个0余量不再读取，已有attempt拒绝。reviewer补的必要边界进一步证明：恰840/840允许1个fake child；SDK期间900降至839拒绝且无attempt；SDK后current变化拒绝且无attempt。没有真实worker、SDK或网络。

## 实际验证与继承

本reviewer仅一次执行新增两个具名方法：

- `ScopeBoundaryRegressionTests.test_owner_readiness_and_context_clock_are_bound`
- `ScopeBoundaryRegressionTests.test_public_provider_launch_reserve_cannot_be_bypassed`

**exit0，Ran2，0 failure/error，0.030s**。只在内存将OUT改为094；原test、assertions、作者093/087证据不动。作者的RED一次exit1/2FAIL/0.010s及GREEN一次exit0/2pass/0.028s只作为其历史核验，不算本reviewer执行。

额外三个边界为单个stdlib临时/fake脚本，exit0；没有重新执行原090脚本，没有重跑原三测/旧suite。命令、exit、stdout、SHA及小反例原脚本/观察保存在094目录，详见evidence.json。初次文件清单末尾未匹配尚未落盘的093 stage导致只读shell exit1，后root补文档核SHA；不是测试或源码失败，也未因此重跑回归。

090其余有限验证按该版已审逻辑继承：同digest隔离、current guard、旧cache按新R资格/191无commit继承、整R与anchor/full分权、七值重叠原子门、daily四连接、独立reader/driver终态与publish责任；本次未冒称093版再次三测或重新市场资格。直接diff未改这些算法/接口，所以不扩大回归。

## 接受边界与结果

094 receipt的source_bindings恰新scope/provider两个绝对路径→SHA/bytes，test/dependency另列；independent_review=true、p0_findings=p1_findings=0，可作为084有限代码接受的小合同。它不是真实来源资格、实际owner/PID、SDK交付、prepare/preflight、金融readiness或授权；这些仍由root用真实证据另行决定。未生成任何真实owner或readiness。

089非阻塞P2失败capture可能遗漏已收集fill身份的限制仍保留；成功raw/seal门未改，不完整失败绩效不得合格。原A0受限、原B失败N/A、PIT与不能仅胜弱A就达标的限制不变。

真实prepare/provider/网络/金融/模型load-fit-predict/订单0，整库/全市场预检0，不读新途中PnL；无作者源、LINE/registry/Git修改或新reviewer。新增/修改/删除策略参数与完整金融结果0；权益、收益、DD、Sharpe、滑点、次数、胜率均N/A，production_qualified=false。

调研判断：按root无网络边界，只核本地已冻结合同、反例、真实接口和两项diff，没有新外部/GitHub研究。开始及结束过拟合判断：**否**，没有收益筛选或调参；继续价值：**是**，两个阻塞已关闭，可以交root整理后续真实证据，但工程接受不代表金融已就绪。

