# Stage013 执行账本

2026-10-30T19:19:44.345721+08:00；base HEAD=01aa45b690435c4a7bd15fd7f4511c9d6eb1e8e6。

任务1：金融builder只新增10core/test；任务2：独立reviewer只新增独审工具/证据；任务3：reporter只新增report/plot及2tests；任务4：root冻结/调度/中文总stage/manifest/本地提交。

Ruling：用户已明确改为10万并此前要求改完直接回测，金额/基线/起点/会计规则明确，不重新索取设计确认。沿现有工作树和已审架构新增Stage013，以原Stage009 C_R150为对照，不修改旧Stage012及其哈希。

Ruling：按AGENTS研究目录隔离，账本与计划位于本线stages而非默认docs/.superpowers。三个独立文件边界的agent并行，独审不写金融/报告；沿用已熟悉源代码的agent以避免重复发现，由全源码/参数/数据与结果独立检查控制遗漏风险。

初步原账本检查得19非绑定、4绑定；需独立准入后才决定精确复用。paired字段method100、r100_，variations C_R100/C_R150。

过拟合：是，有反复同历史并看5万结果后选择10万的风险。继续价值：是，固定金额资本需求验证；不扫其他金额，不晋级。

首次潜在受限旧事件：
[
  {
    "date": "2020-02-07",
    "transfer_amount": 44190.0,
    "cumulative_transfer": 139875.00000000006,
    "start": "2017-01-01"
  },
  {
    "date": "2020-02-07",
    "transfer_amount": 44190.0,
    "cumulative_transfer": 114215.00000000006,
    "start": "2017-06-01"
  },
  {
    "date": "2019-03-08",
    "transfer_amount": 7640.0,
    "cumulative_transfer": 105900.00000000003,
    "start": "2018-01-01"
  },
  {
    "date": "2019-03-29",
    "transfer_amount": 15360.0,
    "cumulative_transfer": 102620.00000000003,
    "start": "2018-06-01"
  }
]

2026-10-30T19:26:08.490171+08:00：金融20目标测试GREEN，report8+plots10，Stage013全部38目标测试GREEN；独审8反例GREEN。金融5模块AST与原版仅备用常量/研究namespace/审计witness差异。独立准入118084检查、4675源/7.02GB重新SHA读，19proof/4fresh接受。金融HEAD=0c9f18628303519247666ee09ba7e018cd1e8689，freeze SHA=c398ed516b8b7f68ead10fb764de127a5cb8350e9e91ed9fb0f0953a255c3a7c；2017Jan canary已dispatch，session6996。金融中冻结源及HEAD不变。

2026-10-30T19:30:36.476429+08:00：V1首个子进程在shared helper import前置阶段失败，未金融；确认第二处shared pointer亦被误命名，均恢复旧Stage012上游绑定。V1所有证据保留，V2新freeze/BASE/attempt002/auditor/receipt隔离；详见pre_engine_import_recovery。

2026-10-30T19:35:07.742030+08:00：V2最小入口/资产绑定修复独审通过，25core＋20report/plots目标测试GREEN，原金融try/Engine/overrides不变。源码HEAD=e2606ffb2b30a101450aabcef4a39a11d72a4854；freeze_v2 SHA=333c77c0602e566c68bdde426eab901edad82a942fd14f3e611e80ce7d6d01d4，71源码/实际imports/共享冻结资产路径及SHA，39静态导入明确解析。V1的1dispatch/0engine证据保留；V2 canary attempt002已dispatch，独审stream_v2跟随。

2026-10-30T19:40:02.773583+08:00：V2 canary2017Jan attempt002完成并独审通过，gate SHA=cee250eae236362c546553564d7be3bed64b2685d462f5fa0d640eeb6d854768。前751交易日/131成交与旧原C相同；2020-02-07首次补资限制T4315，累计100000；E2483255/真实PnL2233255/E-DD−54.3395%/Sharpe.924795，仅单窗，未作全组结论。resume剩3已启动session66089，2并发，独审全23 follow。

2026-10-30T19:51:14.841912+08:00：V2金融4fresh＋19proof/23old全部完成，23候选独审通过；numeric8379checks与46/23/70998/6cohorts一致，五图/HTML/23中文窗最终静态与像素审核通过。成熟22净利3升18同1降，DD0浅19同3深；耗尽R1004/R1503，保证金超100%窗15/14，均无E非正日。2015两线同E4219305/PnL4025345/T43960，新R56040。45目标测试通过。保留1pre-engine0financial失败和同字节stat审计恢复，未金融重跑。过拟合风险仍有；固定资本需求验证有价值，不扫描其他金额/不晋级。接下来只封最终manifest与本地研究提交。
