# Stage018 人工资金核验与周一安装 Implementation Plan

> **For agentic workers:** 使用既有独立执行/信号/审查分工，实施任务逐项验收；root独占Git、物料与全局配置。

**Goal:** 把用户已选择的人工出入金核验落实到新不可变候选，完成本周真实日线的下周信号核对，准备2026-11-02 09:00后真实CTP核验与正式安装。
**Architecture:** 保留Stage014 C_R150固定alpha，新增operator_manual_v1现金来源及同actor原子消费；私有CLI只写人工记录和来源引用，不直接修改活跃运行状态。正式发布、资格、Stage948激活仍分别留证据。
**Tech Stack:** 原`.py311/bin/python`、vn.py、PipelineStateStore CAS、官方材料发布器、Stage948及Codex本对话一次性自动跟进。
**Spec:** `20261101_Stage018_manual_cash_design.md`、Stage017用户人工核验决定及本轮继续安装指令。

## Global Constraints

- 2026-11-02 09:00北京时间前不尝试CTP；本次不委托、不撤单、不转资、不SMTP，不启HTTP。
- 固定19品种、交易权益15万元、场外备用金15万元，alpha/MRO/风险参数及所有旧物料不改；与44品种研究完全隔离。
- 自动最终结算单解析、自动银行流水到账producer不再是前置；不把人工来源伪装成券商自动证据。
- 实际权益、Available、持仓、报价及source-qualified权限仍由真实来源提供；人工金额不能虚增账户资金。
- m0001永久保留；新代码测试、独审、干净source提交后冻结m0002候选，不把离线候选称为生产资格。

## Review Focus

- gross Deposit/Withdraw同日单调，跨日全部人工核对且有日历，不由Balance差倒推补资。
- 同一receipt/request/native admission不能跨review重复扣备用金；T+R严格等于15万元。
- CLI文件发布、cashrefs CAS与同actor消费三阶段失败均可恢复，坏引用不部分消费。
- 私有现金模式显式匹配不可变policy；人工核验不能关闭账户、持仓、报价或风险检查。
- 真实stable HEAD、CURRENT及五件套/loaded jobs才是安装事实；source或候选不能替代它们。

## Tasks

- [x] 本周信号：以2026-10-30真实日线独立重算19品种完成周，假定15万空仓；独审直接读取raw行情，确认0原始交叉/0候选，不是资金压零。见Stage018_signal_scope与Stage018_review_signal文件。
- [x] 全局policy先红后绿：`test_live_cash_verification_is_explicitly_operator_manual`先报缺字段，新增cash_verification_mode后5项配置测试通过；纳入新模块/CLI/测试的critical及controller闭包。
- [ ] 现金实现：funding/store/backend/manual组件与CLI、负例、同actor原子消费、人工操作说明；独立审查及修复。
- [ ] 新source测试/来源SHA封存，官方发布器冻结新m0002候选并核物料和LFS；保留旧m0001。
- [ ] 真实未来交易日历取得并独审来源；不猜未来工作日，不改旧approved snapshot。
- [x] 已设置本对话2026-11-02 09:00一次性跟进，automation id=9-19；正确正式env/framework先只读CTP，成功后续真实qualification/master/fresh clone/Stage948；失败留证据并说明具体原因。
- [ ] 周一后：实际CTP及新生产资格，正式激活/master/fresh clone和Stage948原子安装；这项不能提前声称完成。

开始判断：无过拟合，未调策略参数或寻找更优历史结果；有继续价值，解决真实人工职责与系统会计一致性。外部调研沿用vn.py正式API及Python/Apple官方文件原子性机制；定时跟进使用Codex官方工具，未另建cron或调度服务。
