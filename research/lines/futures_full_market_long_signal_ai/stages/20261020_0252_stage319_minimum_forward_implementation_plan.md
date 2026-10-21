# 最小因果前瞻链路 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已经确定的318设计补齐原纯52政策的无标签因果生成、真实时钟记录及连续paper状态，不把它当新alpha实验。

**Architecture:** 三个薄模块复用原129/130/156/157/070/131的计算；原代码不修改。320负责特征/推断/选择，321负责时钟分型与不可静默覆盖的本地记录，322负责原prepare预算与连续D推进，323独立审阅。root在模块稳定后做最小连接，只有输入路径/代码/初始状态齐全后才另冻真正T0。

**Tech Stack:** 现有.py311 Python3.11.5/numpy2.2.3；标准库JSON/hash/datetime/文件锁，现有原核。无安装/模型训练。

**Spec:** research/lines/futures_full_market_long_signal_ai/stages/20261020_0246_stage318_minimum_prospective_observation_contract.md；317 smallrefs；outputs/stage315_joint_integer_budget_decision/forward_preparation_acceptance.json。

## Global Constraints

- line_id futures_full_market_long_signal_ai；原分支codex/ai-training-data-expansion，无新worktree、Git推送或生产动作。
- 0新fit、0历史cash回测、0旧控制重放、0SQL、0实际大表/行情；本轮合计最多3组新tiny，禁止旧suite/新增策略臂/调参。
- 原main/2023-01-01 portable+scaler；26原值加26missing flags，不滚动重居中。原NARROW风险与成本不变，不使用已关闭312整数算子。
- 同一u只用u及以前的原件版本；先原资格/正score/D<K再argmax；K pending且真实D<K_target充分证明沿原规则。
- 当前T0=None，真正forward观察未开始。冻结前晚取日期仍历史，迟于D首开不得补发，98既有母域与新catalog unsupported都保留。
- 最多三组新tiny验证接口/时间/算术，不据此声明receiver/PIT/盈利/生产ready。

## Review Focus

1. 同月份21bar own11的SMA TR与Wilder seed续接不是同一归一化；320因果组核间隙重暖/续接及未来追加不影响旧u。
2. 原缺失位置标准化0并追加missing flag，不能把经济unknown伪造0；320同组核固定scaler与列序。
3. K pending证明分支、夜盘交易日和D首开不能机械自然日加一；321时钟组核晚取/迟到/缺时钟，320核D/K原选前资格。
4. 新输入修订和重复调用不能覆写既往first_seen/decision；321同组核append幂等、版本追加及损坏检测。
5. 分段执行/恢复不能重置资金或重复D，base/stress不能串态；322状态组核连续两session与一次推进一致及pending/缺价。

## Task 1：320 因果特征与评分

文件：tools/stage320_causal_forward_core.py、tools/test_stage320_causal_forward_core.py。负责人offset_interface279。
接口：WilderState.append(u_index,bar)、to_dict/from_dict；build_u_observations(series_by_epoch,u_index,dates,economics,products,*,D_context)输出mothers/candidates/raw_rows/references/statuses；infer_scores(raw_rows,model,scaler)输出原26+52及score；select_u(observations,scores,dates,*,D_context)沿原156输出choices/完整audit/boundaries。D_context含confirmed/D_index/D_date，不能由未来价格存在推定。

- [ ] 先写唯一causal测试组，独立预期覆盖固定scaler/缺失、未来追加不变、Wilder续接及原K/选择边界。
- [ ] 用.py311运行该组并记录预期RED。
- [ ] 仅实现这些薄接口；可从原源码抽纯函数，不导入或调用label action_stream/fit。
- [ ] 运行同组GREEN并记录源binding；不运行旧suite或实际价格。

## Task 2：321 时钟与追加记录

文件：tools/stage321_forward_journal.py、tools/test_stage321_forward_journal.py。负责人root。
接口：evaluate_clock(*,frozen_at,source_completed_at,received_at,decision_sealed_at,D_open_at)->状态dict；所有已提供时间须带时区，未知保持unknown。ForwardJournal(path,policy_identity).append(kind,payload,*,key)->receipt；entries()->完整可核索引。policy身份不匹配拒复用目录，首收记录由当前UTC写入；同key同内容幂等，不同内容要求新版本key，链中对象损坏或断尾不静默修复。

- [ ] 写唯一clock/journal组核T0前后、迟到、未知/时区及幂等/修订/损坏。
- [ ] 运行并记录预期RED。
- [ ] 标准库最小实现：canonical JSON对象、内容hash、追加序号/prev链及文件锁；拒NaN，不冒充外部可信时间戳服务。
- [ ] 运行同组GREEN；本模块不创建T0/定时任务，不触行情。

## Task 3：322 连续paper状态

文件：tools/stage322_continuous_paper_state.py、tools/test_stage322_continuous_paper_state.py。负责人k_payoff_numeric_review。
接口：函数式new_state、seal_u、advance_D、export_state/restore_state；状态dict用于journal。seal_u使用prepared(potential_by_u,references_by_u)与自己的u状态，封存原预算；advance_D只消费已封u和实际到达D，拒重复或串态。具体关键字由作者发root同步321，无新金融选择自由度。

- [ ] 写唯一state组，纯synthetic真核验证两相邻session、保存/恢复、两个场景、pending/取消/缺价与D只减量。
- [ ] 运行预期RED。
- [ ] 复用原131 prepare code与D function/private globals，原模块不改；JSON-safe保存原ledger和容量状态，不借未来重算旧决定。保留ever_insolvent。
- [ ] 同组GREEN并交323，不回放旧历史账本。

## Task 4：323独立审阅与最小连接

负责人k_payoff_source_design只在source稳定后一次审三模块及tiny证据；root整合调用字段。每次只修实质逻辑/数据问题，不能展开新指标/资格循环。若模块不能保证原政策或时钟，则明确未ready，不调参数换策略。

- [ ] 核无label/fit、前缀因果性、预算与状态同一政策、receipt时间真实性边界；绑定最终源与测试。
- [ ] root记录真实完成/未完成项；模型身份、代码、输入接收与初始状态未齐全前不签T0，不把当前实现测试当forward收益。

## 调研、自检与继续价值

已读registry和317318。复核scikit-learn官方common pitfalls与Freqtrade维护者GitHub lookahead文档：新数据沿旧预处理，未来数据不能改变过去输出。外部原则支持接口/因果核验，不提供中国期货alpha证明，不安装其框架。

上一goal turn分类为progress：311–315实际失败现场及精确witness审查完成，316研究路线审查、317资产盘点、318观察设计改变下一动作；不是verified wait，旧session65606已exit1，不再poll/重启。完整累计453fit/246cash及本次1未完成attempt维持。

开始过拟合判断：本轮新增寻优否；原模型历史择题风险仍是。继续有价值，因其建立可核的新证据产生路径，不是在旧区间加列寻赢家。本计划不声明高质量long、小止损安全、加注或目标完成。

计划自检已核：三个模块职责/接口/约束一致；五项易错均映射到三组tiny；用户授权持续研究与实施方式延续，不重复询问批准，不commit/push或改正式策略。

322接口已锁定：new_state(*,scenario,account_id,start_u,base_kernel,initial=1000000)；seal_u(state,*,u_index,prepared,market,dates,economics,base_kernel)；advance_D(state,*,D_index,references,market,dates,economics,base_kernel)；export_state/restore_state。均返回新dict不改旧state，真实datetime门由321负责。
