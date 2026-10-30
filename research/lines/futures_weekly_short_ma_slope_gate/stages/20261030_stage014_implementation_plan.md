# Stage014 Five Starts Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or executing-plans. 用户已授权直接回测；执行在当前隔离研究线，计划/账本位置按AGENTS覆盖默认docs目录。

**Goal:** 原C_R150每年5起点，2015起全部独立至2026-10-30，完整59窗与报告。
**Architecture:** 独立数据agent追加30；builder仅新金融入口/合同/适配器/调度及测试；独审不写金融；root冻结/执行/交付，数据完成后agent转纯报告。
**Tech:** .py311/bin/python、vn.py、pandas、Matplotlib、离线HTML。
**Spec:** stages/20261030_stage014_five_starts_design.md。

## Constraints / Review Focus

- 用户已确认months1/3/6/9/11，59start至30，54成熟5观察；金融前固定。
- 仅C_R150，原risk/shortbottom20/E150R150W300不变；原Stage009金融方法AST保持。
- 本轮59全部fresh；旧23仅截至29prefix controls，不冒充新终点结果。
- 预热/生命周期/主力/physical数据先独审，30完整周与11/2forming严格分离。
- 全main实际依赖origin与FROZEN共享资产冻结；禁机械重命名上游stage012helper/pointer。
- 每次输出不可覆盖；最多2金融并发，disk gate，完成即checkpoint；后处理不重算金融。
- E含入金、真实PnL分列、非正E不裁剪、未入金不进风险，成熟/观察/月cohort全部保留。
- 只写Stage014，旧线/源/生产不写，NO_PROMOTION。

### Task1 数据
Files: stage014_data_prepare/verify及专属tests、data_stage014_20261030/output、stage014_data_*receipt。
- [ ] 先读旧stage001 additive，列覆盖与预算，Tq只读、订单API阻断，排除11/2。
- [ ] 复制旧快照后补30，<=29 CSV和SQL prefix严格相等；19main/可能physical持仓完整，不填未知0。
- [ ] 保存source/data manifest、全缺失/结构限制、真实cutoff/nextday，提交独审准入。

### Task2 金融核心
Files: run_stage014.py、stage014_contract.py、stage014_reserve.py（仅新验证imports）、stage014_coordinator.py以及对应新tests。
Interfaces: required_financial_sources、validate_freeze、validate_run、checkpoint_key/read/write；STARTS/CUTOFF由最终固定设计一致生成；C-only输出stage014_C_<date>_attempt001。
- [ ] 写59/54/5边界、原R150/风险、5个月月份/未来排除、main导入origin/共享pointer、独立冷启动与失败checkpoint反例，RED。
- [ ] 从已审Stage009经济逻辑显式定向适配新scope；不能复用旧validate_start23或全局patch旧模块。
- [ ] 完整main imports/静态资产相对原入口白名单；新数据路径和trade_start/end是仅允许设置delta，原经济方法AST保持。
- [ ] GREEN/源SHA锁定＋独审，准备freeze（无金融）。

### Task3 审核
Files: stage014_independent_* tools/stages，stage014_independent_receipts/<start>_C.json。
- [ ] 独立源/全main依赖/数据前缀/59warmup与生命周期准入；解析真实有效参数。
- [ ] canary2015Jan到30，至29逐日/成交/入金/成本/MTM与旧原C对齐，新30核价；签checkpoint gate。
- [ ] follow全部59raw/钱包/FIFO/MTM/费用/统计，闭合PnL+未平MTM桥，完整窗口/source绑定。
- [ ] 总表/59曲线/月cohort/成熟观察/5图/HTML/中文stage，保留审计失败尝试。

### Task4 纯报告（数据完成后）
Files: stage014_report.py、stage014_plots.py及tests；artifacts/stage014_five_starts_R150/。
- [ ] 输入只来自59已审窗口，完整scope/date/资金桥/异常值验证；单arm不做虚构比较。
- [ ] 五图全部曲线、59中文窗、selfcontained HTML，pending→独审numeric→reviewed状态-only绑定。

### Task5 root
- [ ] 记录用户已确认日期、核对设计/计划，记录过拟合与价值判断。
- [ ] source/data独审后commit金融+设计，freeze新cutoff/SHA/59scope/资源限制。
- [ ] canary gate→resume58，持续审查进度，失败保留；完整之前不报全组绩效。
- [ ] 中文总stage/事实审/manifest/本地研究commit，仅Stage014；最终数据和旧版本hash核验。

Self-review：全部用户范围与实际终点覆盖；date已由用户明确确认；金融经济逻辑保持，主风险为新增月份被旧固定23校验拒绝、main共享依赖误命名、完成周终点变更造成历史泄漏、数据缺价静默填0及入金误作盈利，均有任务对应。
