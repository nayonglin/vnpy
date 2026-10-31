# Stage016 周线19品种正式迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将用户已确认的Stage014原C迁移为可验证真实资金与真实成交的正式候选，完成受控master与本机生产安装。
**Architecture:** 保留原factory/MRO与全部固定配置；资金确认、策略决策、执行治理三个边界隔离。正式profile显式路由，旧C9不能混入，所有发布与安装依资格failclosed。
**Tech Stack:** 现有.py311 Python/vn.py、标准库Decimal/JSON/锁、unittest、现有Stage179/948发布治理与邮件transport。
**Spec:** stages/20261031_stage016_weekly19_migration_contract.md及20261031_1555_stage016_runtime_design.md。

## Global Constraints

- 原冻结树/44品种/历史release不写；用户明确的现有生产替换仅通过受控合格安装。
- 不改alpha，不自动银行转账或真实委托；所有mock/fixture不等于真实资金资格。
- shared .py311无pytest；用unittest，不设runtime guard紧急绕过。
- 代码/单位/时间/交易日/资金/释放顺序按Spec；source-bound SHA/actual fill id为唯一身份。

## Review Focus

- Friday→Monday名义日现金流、未到账或无连续证据必须阻断open，close/reduce仍可。
- warmup/重启/partial fill不造层、不重复增加E/风险/AM，不让0权益回退base_capital。
- C9 intraday tick stop、retry/AI及旧epoch/release意图拒绝，周保护只fresh周close。
- actual E/Available/position与模拟target有差异时优先真实账户；报价/会话/映射/epoch缺失failclosed。
- release/current/source/qualification/remote/stable/7jobs任何漂移不能声称正式，旧8commits保留。

### Task 1: 来源准备及实际语义审查
- [x] 原Stage014 397+71 pins完好、当前正式m0008/远端e41只读核对、生产候选d558 ahead8及无有效runtime资格/7jobs。
- [x] 新managed worktree/branch、.py311 link、原6 profile tests绿色；native runtime设计与完整MRO/周保护/夜盘/恢复审查。
- [ ] 将本机生产8commits仅合入source并验证15:10/资产治理关键测试；提交来源合并，生产保持不动。

### Task 2: 真实场外资金状态机（独立agent）
**Files:** qmt_roll_weekly19_funding.py、funding_store.py、tests/test_weekly19_external_funding.py。
**Interfaces:** Spec资金API及原始证据envelope；无网络/资金副作用。
- [ ] RED: E/Deposit不同、native-admission时点、partial/duplicate/foreign/stale/unknown flow、Friday/Monday完整与缺失链、R耗尽/E<=0、CAS/WAL崩溃等测试。
- [ ] GREEN: 最小实现，不原地变输入；存储0600原子事务。
- [ ] 独立审查后固定schema、测试证据/源码SHA，真实capture adapter另做资格。

### Task 3: 原策略runtime薄适配（独立agent）
**Files:** qmt_roll_weekly19_runtime.py、weekly19_frozen/、tests/test_weekly19_runtime.py、test_weekly19_strategy_equivalence.py；原settings/19池资产进入显式inventory。
**Interfaces:** Spec四runtime方法；producer无真实send，只actual fill应用持仓。
- [ ] 原样提取factory源码并生成原→副本AST/hash映射；full actual settings去绝对私有路径改显式资产依赖。
- [ ] RED/GREEN: 周时点/stop/换月/daily risk/native signals equivalence、warmup、原生signal+real fill identity、restart/AM/层恢复、no fake E或无层重建；覆盖真实资料回放但不虚报金融结果。
- [ ] 冻结可移植closure与实际风险flag，独立审查可用于新资格，任何unsupported state阻断。

### Task 4: 新profile与全部执行消费者
**Files:** execution_profile.py、weekly19 live pipeline/dispatcher、Stage905/927/931/930/945/947/948、manifest/qualification/receipt/health及对应tests。
- [ ] 以新weekly19 key/strict source允许表注册；旧C9仅显式历史兼容。
- [ ] 所有新open强制资金ready与fresh broker/cash/quote/真实Available cap；rollover旧仓真实close才reopen。
- [ ] 新weekly branch不运行C9 monitor/detector/retry/AI；未知profile/旧intent/source drift拒绝。
- [ ] RED/GREEN隔离/费用/保证金/重启/新cold-start/7labels/单个consumer漏接回归，完整策略与资金闭环审查。

### Task 5: 周五邮件和实际read-only现金/成交provider
**Files:** weekly19 account/cashflow capture adapter、weekly19 report/mail/outbox及postclose路由，现有email transport。
- [ ] 真实原始account需Deposit/Withdraw/TradingDay/generation/source SHA及闭日/零起点/银行流水可验证证据，不使用现有仅Balance/Available snapshot伪造现金流。
- [ ] 周五15:10沿data-ready链，输出信号、E/浮盈/场外R、建议T及条件手数，未到账阻开；holiday、未知E发blocked说明。
- [ ] mail/outbox按week/release/receipt幂等，失败/不确定发送不静默重复；dry-run真实预览不发测试邮件。
- [ ] 跨session真实订单/成交查询与保护层持久化对账，缺真实资格数据则停在明确gate，不能用fixture充数。

### Task 6: 新不可变release与正式晋升
- [ ] source clean/AST+source+资产清单、qualification suite选定及独立final review。
- [ ] prepare→精确commit→verify→fresh clone（LFS实体/executable）→release-bound新资格，订单API均0。
- [ ] activate→controlled promote-master→独立readback/freshclone身份。
- [ ] Stage948原子替换本机目标（保留原ahead8历史），7jobs精确绑定、零冲突、无CTP/订单副作用；六身份最终审计。
- [ ] 中文stage/manifest/根里程碑与LINE/registry仅在实际完成后更新；部分完成及外部阻断如实区分。
