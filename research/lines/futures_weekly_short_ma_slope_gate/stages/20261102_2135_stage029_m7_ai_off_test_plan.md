# Stage029 weekly19无AI收据兼容测试 Implementation Plan

> For agentic workers: use superpowers:executing-plans; root本轮直接实施，独立agent复核。

**Goal:** 修复4处旧C9测试对AI路径必须存在的假设；完整保留C9核验，使已授权weekly19实际生产资格可被正确检验。
**Architecture:** 只修改tests/test_official_live_config_import.py、tests/test_stage929_official_ai_pool_policy.py、tests/test_stage947_production_support_launcher.py。当前实际活动物料为weekly19时，检查weekly19 profile、AI关闭、config与Stage945都为None；C9活动物料保留原strict path/not-backtest-output断言。新增隔离进程从既有不可变C9 fixture实际导入Stage945，保留旧分支及物料hash覆盖。
**Tech Stack:** Python3.11、unittest/pytest、原formal publisher和Stage179/948。
**Spec:** Stage024_existing_account_cutover_runbook.md；用户已定weekly19关闭AI，Stage029_m6_QM_failure.json真实RED。

## Global Constraints

- 仅3个测试文件变化；298 critical闭包中其余295、所有产品代码、参数、资金/风险和19品种均逐SHA不变。
- 保留m6 sourceR6资格通过、M6真实生产资格失败，以及全部Git/LFS原传输失败；不能激活M6或合并旧测试/native冒新通过。
- 场外R150000/T0、operator_manual_v1、现仓新管理周期和真实权益仍原规则；与44研究隔离。

## Review Focus

- weekly19必须明确关闭AI且路径None，不能通过None就跳过。
- C9继续strict resolve、不可变物料/文件hash、不能指向backtest_outputs。
- 旧C9采用现有真实冻结fixture隔离导入，不能用直接mock两条相等路径冒覆盖。
- 未知活动物料显式失败。
- 新m7必须单独source/material/实际Q_R7、远端M7与canonical Q_M7；不能改生产源码/断言计数强行放行。

## Task 1 三文件兼容修复

- [ ] 保留原canonical M6全96/2408/1F原件并独审；在ROOT实际active weekly19上重现三个目标suite的原4处RED。
- [ ] 改命名case：按实际活动物料身份分支，weekly19强断言profile/关闭及双None，C9原断言原样保留，未知显式fail。
- [ ] 新增isolated frozen-C9 producer-import case，核真实Stage945路径、SHA及非mutable来源。
- [ ] 跑整份test_official_live_config_import.py；两模式均过，独立review差异及297其余critical/所有产品不变。
- [ ] 记录中文stage/源码锁并commit；原publisher创建新不可变m7，candidate actual完整96资格作为新全CI，实际case数据XML不硬套2408；随后原晋升/生产新资格和安装链。

无金融复跑/回测结果变更。过拟合：否，修测试覆盖已声明模式；继续价值：有，避免把正确AI关闭误判产品错误，也不降低C9旧约束。
