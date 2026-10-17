# B_TS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task; root owns integration/commit and economic launch.

**Goal:** 实现独立三重滤网首次信号、u已知T一致估量和最终只减量预算，完成一个可独立复核的B账户对照。

**Architecture:** 035 pricing和B策略分别隔离；复用027状态/028执行持仓，036从031可靠入口适配。原正式源及C实验不改，root在部件审查后单次启动金融。

**Tech Stack:** .py311/bin/python；已接受冻结numeric site和vn.py vendor；标准库/原pandas，无新依赖。

**Spec:** research/lines/futures_trend_triple_screen/stages/20261018_0333_stage035_b_ts_execution_contract.md

## Global Constraints

- 当前codex分支、不建worktree；只改本线独立文件，原028/031/033/正式源/脏registry保持。
- 2020-01-01—2026-10-14、150000、原AI历史字节/19特征、0.5R ON/一次retry/原成本；B unknown禁开。
- 不新增数值阈值，不救旧C；原A0/周/FI复用，金融前部件测试不得构建大数据/跑preflight/账户。
- B最终q只缩原admitted，gross原量前缀、不重排补位；T预测与真实Dgap分开。

## Review Focus

- 真MRO过830而S仍804：Task1真实类/手算测试。
- 旧native残留或held被替换：Task2无native/unknown/held同context测试。
- tilt及同批预算回收：Task1四个预算算术/不补位断言，Task2实际单reserve组合。
- 原snapshot close混同T及实际fill同步：Task2/4检查冻结预测不丢。
- owner/schema仍C或export-only偷偷回放：Task3 B身份/小checkpoint恢复测试。

### Task1：T估价与最终预算（独立实现者）

Files create: tools/stage035_b_ts_pricing.py、tools/test_stage035_b_ts_pricing.py、outputs/stage035_pricing_impl_receipt.json。
Interfaces: build_trigger_priced_base(native_base)->class（保留830/804真实MRO）；B注册self.ts_trigger_by_key[(day,contract,direction)]=T；finalize_b_plan_batch(strategy,plans)->list[dict]只修改原admitted B计划q/status/sizing审计。
- [ ] 写少量新失败测试并运行观察RED：真实long/short S与T算术、缺T拒绝/非B原路径、tilt10→12限10、三项gross前缀和不补位。
- [ ] 实现原方法SHA绑定静态复制，仅三处估价替换；外层保存830 E；按spec精确字段最终min，非法预算fail-closed。
- [ ] 仅跑新测试GREEN与compile，出sourceSHA/接口/结果receipt；不自行commit/金融。

### Task2：独立B首次信号（另一实现者，可与Task1并行）

Files create: tools/stage035_b_ts_strategy.py、tools/test_stage035_b_ts_strategy.py、outputs/stage035_strategy_impl_receipt.json。
Interfaces: build_b_strategy(native_base,weekly_lookup,fi_lookup,next_days)->class，内部用Task1 build_trigger_priced_base，复用028持仓/activation，独立B machine/planner。shared price map如Task1。
- [ ] 写失败测试并观察RED：原native空但B合法、unknown/通用filter拒绝、held保留与恰一次观察、最终量单reserve。
- [ ] B同一flat context前置注入新signal/generic OI；精确short权限；原planner完整返回后只调一次Task1 finalize并冻结q/T/S/rank，旧C观察不运行。
- [ ] 预算/预测字段写decision与冻结plan、snapshot明确signal close/T，真实fill审计arm B_TS；原公共holding/samebar路径不重写。
- [ ] 仅新增测试GREEN/compile；接口若必须改先消息root/Task1，不改对方文件，不自行commit/金融。

### Task3：B独立runner/provider（root，Task1/2接口定后）

Files create: tools/stage036_run_b_ts_checkpoint.py、tools/test_stage036_b_ts_checkpoint.py、tools/stage037_b_ts_request_provider.py及对应真实入口协议。
- [ ] 从冻结031适配arm=B_TS/attempt1、独立OUTPUT/所有owner/schema/writer/adapter/provenance、绑定新035源码；不改031，不重建FI/A0。
- [ ] 新小fixture先RED再GREEN：B owner/schema与C拒混、真实synthetic身份、sealed-only恢复不建engine；不重跑完整031旧suite。
- [ ] provider只改032四行scope，保存diff/compile，无实际请求不连接。

### Task4：独立接合审查与冻结（root+独立reviewer）

- [ ] 审Task1/2 spec和code后，跑一组真实native847+028engine B hook组合：B无native可开/unknown禁开、T预算和single reserve、真实止损/信号身份。
- [ ] 新runner/provider owner/源码/原A配置、raw-before-guard/恢复合同有限审查；剩余阻塞修一次聚焦delta，不重复旧全量。
- [ ] root精确冻结source/协议/receipt资产并commit；保护其他线/用户dirty。无alpha结果。

### Task5：唯一完整B与经济复核（root+新独立financial reviewer）

- [ ] 一次--run内联预检，记录真实tool handle；只对实际分钟缺口同engine等待并独立签收，不因观察超时重启。
- [ ] terminal后先保存完整checkpoint/exports；必要仅export-only恢复。独立审计现金/持仓/成本/母链/最终预算/T-vs-F/七门，不回放A0。
- [ ] 中文结果/失败与参数写本线并保存复现资产，目标active直至真正双目标与固定稳健性通过；B失败停止固定形状不救参，promising才后续组合与多周期。

## Root preflight self-review

Task1->2共享接口已固定（factory、trigger map、finalize），不同文件无写冲突；Task2->3为build_b_strategy签名与B audit字段；Task1/2->4用真实MRO/算术/单观察reserve组合；Task3->5为精确B owner与原data gate/checkpoint。全部按spec，不要求旧C重跑或B按A相同手数；固定sizing模式0。Task4/5不得只凭fixtures或summary宣告完整目标达成。
