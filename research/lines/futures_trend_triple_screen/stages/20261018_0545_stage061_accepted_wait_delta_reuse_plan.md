# Stage061：A_OFF/B_OFF继承本轮已接受分钟数据的实现合同与计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. 本阶段仅计划，不实现或执行。

**Goal:** 原B真实终态后，一次性冻结其实际已接受数据为有明确full/anchor权限的追加层，供下一轮完整2020-01-01—2026-10-14公平A_OFF/B_OFF复用，避免只读旧022 stack再次取同一份数据。

**Architecture:** 保留原022 stack、016修正、036已有两个精确anchor来源与全部旧source字节；新层只收集终态同一run已完成021 gate commit的独立delivery。新runner按固定SHA读取新层，外层append仅接受旧七值完全相同的重叠行；权限以独立索引组合，禁止因新source标签而把anchor变full。

**Tech Stack:** .py311/bin/python；原冻结pandas/numpy runtime；原021 request/receipt parser、022 source SHA门；无训练、预测、网络或金融回放。

**Spec:** root在本次会话给出的Stage061只读任务；相应实码接口见下。记录时间：2026-10-18T05:45:21.513291+08:00。line_id=futures_trend_triple_screen；非alpha突破。

## 本轮只读事实及必要判断

- 022 `read_data_stack`只接受原schema及append_order=['002','011','015','020']，不会自动发现036/data_wait动态追加。036现有loader另继承cu2609/OI009两个精确anchor；它们也不应因复用新层而丢失。
- 022 FileWaitResolver在收到022 pointer并验证独立receipt后先写`qualified_delivery_pointer_accepted`；随后021才做所有symbol旧七值精确比较、原子更新与`data_qualified_appended`。因此**仅有response、driver journal成功或resolver accepted不能证明实际commit**。
- 021成功event保存request_sha、receipt/data path/SHA、appended_keys和old_keys_changed=0；失败另有data_gate_failed。036失败会在`run_failure.json`内保留`qualified_wait_gate_audit`与`resolver_audit`，成功导出`qualified_wait_audit.json`的gate/resolver数组，并在run_provenance提供本次来源指纹。
- 有限抽看已终态batch002/003：均是4连接后正常暂停driver；MA005/2020-01-23和CF005/2020-03-06的独立receipt仅获anchor1，并有request/response/data SHA。它们用于确认接口形状，不把journal当最后全量清单，本阶段未扫描全部request或构建数据。
- 重要权限陷阱：022 inherited_qualification_predicates把非stage859物理行视为full；若把新anchor行直接混入overlay_frame后沿用该函数，会误升权。新adapter必须显式屏蔽新追加键的隐含full，再根据本层签署的full/anchor集合授予权利。

- Root随后已观察原B/session70433真实exit1，run_failure已落盘；失败点为2022-05-31 `qualified_delivery_old_value_conflict`，不是timeout。最后一个delivery即使resolver已记录accepted、独立provider已完成，也因021 append失败而必须从061层排除；不能把其七值冲突当作可覆盖旧层的修复。本阶段只纳入这项终态事实，不重复root/064的逐价失败审计。Root将以063绑定真实终态及失败文件SHA；如无raw/seal/summary则所有绩效N/A，数据复用仍仅取此前真正commit成功且来源未变的项。

## 全局约束

1. 原B保持同一PID21822/session70433与原1800/7200秒预算，现已由root观察真实失败终态；禁止本计划中断、重启、延长或读取其中间PnL。只有root观察到真实工具terminal后才能freeze。失败金融不等于此前独立已接受数据无效，但不得借失败末包补资格。
2. 旧source、模型、配置、策略、已消费脚本和协议字节全保留；旧022/016层不重聚合日线、不重新审价格，不用新数据覆盖旧qualified或correction。下一轮pairwise OFF选择由另一个金融合同处理，本计划不定义或修改alpha。
3. 新层只能来自原独立receipt签署的精确时间键和权限。anchor不会因与225/345/555完整物理序列邻接而自动升full；不合并相邻日期来补全未签full资格；其他raw、仅prepare、provider完成未签、receipt签了但引擎未commit的末包全部排除。
4. 冻结数据覆盖只是已接受集合，不宣称新A_OFF/B_OFF所有未来路径已经齐数。两个新臂必须运行完整2020—2026；遇新增真实缺口仍走同等021门，不能截为局部成绩或用日线open兜底。

## 终态输入和accepted选择接口

拟新增单一模块 `tools/stage061_accepted_wait_delta.py`，同时提供freeze和只读loader；测试 `tools/test_stage061_accepted_wait_delta.py`。不修改022/021/036等旧source。示意CLI：

`--freeze --run-facts ABS --run-facts-sha256 SHA --terminal-evidence ABS --terminal-sha256 SHA --base-stack ABS --base-stack-sha256 SHA --output ABS`

- `run-facts`只允许036该run的真实`run_failure.json`，或完成的`run_provenance.json`。失败直接读取它内嵌gate/resolver；成功另显式传`--accepted-audit ABS --accepted-audit-sha256 SHA`指向同owner导出的qualified_wait_audit.json，root最终terminal证据绑定其SHA。成功路径同时核run_context/run_id、export_success/checkpoint seal身份，沿已有checkpoint审查合同确认audit来自同一封存账户；不把stage050/driver活跃journal作为替代。
- terminal证据由root真实工具观测产生，包含原PID/session、run_id、runner SHA、true terminal/exit_code及run-facts等文件SHA。失败允许非0 exit，但必须确为原B终态；不能把driver paused/exit0误认为B终态。若金融进程死了却没有owner失败或完成证据，freeze保持blocked，不猜测live audit尾部。
- 对同一request，仅在resolver `qualified_delivery_pointer_accepted`与021 `data_qualified_appended` **双记录精确匹配**、old_keys_changed=0、没有该request的data_gate_failed时入选。匹配request、receipt、data、response path/SHA以及同run的source记录；按原gate接受顺序输出，去重不得用“最后文件优先”。
- 每个入选项调用原021 `_read_delivery(request, QualifiedDelivery(...))`，重验canonical request/file fingerprint、receipt schema、independent/P0/P1/qualified flags、准确accepted键、内容SHA及整条已消费source闭包。这里复用已签资格，不重新算分钟日线七值聚合。source指纹和终态source记录矛盾时整体fail closed，保留具体路径/差异，不静默改选另一版本。
- 未入选请求仅记exclusion理由，例如pending、provider_failed、pointer_only_no_gate_commit、source_changed；不读其raw补入，不给性能结论。

## 产物和权限schema

独立输出目录 `outputs/stage061_accepted_wait_delta/<原run_id>/`，已有目录拒绝覆盖：

- `source_run_snapshot.json`：schema=`stage061_source_terminal_snapshot_v1`；root终态、run-facts、accepted-audit、run_context、原base stack和已有两个精确anchor输入的path/SHA，仅记录身份与接受事件，不搬运账户PnL。
- `accepted_deliveries.json`：schema=`stage061_accepted_wait_deliveries_v1`；每个原request/response/receipt/data和source闭包、原gate索引、要求kind与accepted时间键；有明确excluded末包列表。
- `overlay.csv`：仅原receipt数据的并集，列`vt_symbol,bar_datetime,open,high,low,close,volume,open_oi,close_oi`，按key排序。相同key跨receipt出现时七值必须逐值相同；否则原子拒绝整层。此文件可保留与旧物理数据同值的行，loader只append不存在的键，并跳过同值重叠；因此不为提取append_only再重载/扫描旧行情整库。
- `rights.csv`：每个确切key有`qualified_full`、`qualified_anchor`及proof request集合；full只来自原full_session签署，anchor来自原anchor/full签署。若同key分别有full和anchor证明可保留full，但必须有真实full receipt，不得靠物理覆盖率推断。
- `manifest.json`：schema=`stage061_accepted_wait_delta_manifest_v1`；base stack及旧继承anchor身份、原run终态、各产物SHA、完整source_fingerprints、accepted/full/anchor计数、`old_key_value_policy=equal_only_no_replace`、`qualification_scope=accepted_exact_keys_only`、`status=frozen_pending_independent_review`。
- 独立审查后另发schema=`stage061_independent_wait_delta_review_v1`，固定manifest SHA，确认零P0/P1与权限/旧值不变。下一runner必须同时pin manifest和该review，builder自称freeze不自动获资格。

## 下一完整replay最小接入

1. 原022 stack、原016 correction和036已有精确anchor按原顺序加载及原SHA验证不变；新层包在它们的**最外层**，原correction先完成。新runner不得把061伪装塞成022的第五个append stage而绕开其固定schema。
2. 新层loader可仿036 `temporary_reused_anchor`：对选中symbol逐key比较旧七值，重叠相同保留原行及原minute_source；不存在才追加。全部symbol验证通过后才发布新cache，失败不部分更新。记录本层实际`newly_appended_keys`，原cache上下文退出完整恢复。
3. 原inherited predicates及已有reused-anchor修正保持；新增组合明确为：`full(k) = (old_full(k) and k not in newly_appended_keys) or frozen_full(k)`；`anchor(k) = old_anchor(k) or full(k) or frozen_anchor(k)`。这里old_full可能由enriched physical cache构造，屏蔽所有本层新增键可阻止其source标签隐式升权；旧物理键原有full权利不因新anchor而降低。
4. 下一runner新增显式`--accepted-wait-delta-manifest/--accepted-wait-delta-sha256/--accepted-wait-delta-review-sha256`输入，并把新层所有来源交原InputRecorder。A_OFF和B_OFF pin完全相同旧stack+061层，金融身份、完整起止、费用与独立账户审核另冻结。
5. 原B若失败，只有双记录commit且SHA不变的前缀数据可用；若完成则同样门，不因成功金融放宽数据资格。没有复用数据的具体新路径仍可正常等待必要数据；新dataset不是“全路径已覆盖”证书。

## 仅三个必要反例与实施顺序

- [ ] 先写RED测试：只有anchor1的receipt即使邻近物理分钟已齐、source tag非859，也不能授予OPEN/full；有真正full receipt才授予其准确网格，不蔓延到其他日/合约。
- [ ] 写RED测试：任一旧key的OHLCV/OI七值有1项不同就原子拒绝、cache不部分改变；同值重叠保留旧source和016修正结果，唯独新key可append。
- [ ] 写RED测试：pointer accepted但没有021 commit、provider成功未签、末包失败/未accepted、source或SHA漂移、仍活跃journal，均不能进入冻结层；真正终态下匹配成功事件可进，即使原金融最终失败。
- [ ] 最小实现freeze/loader，三个有限合同测试GREEN；不扫旧suite、不重新聚合旧各层，不做金融证明数据adapter。
- [ ] 独立agent只审新层选择、SHA、key去重、权限和原子append；通过后root再将同一层接入新的完整A_OFF/B_OFF runner。当前不实现、不运行、不作root日志或资产登记。

## 反思与本阶段结果

- 开始和结束：新增过拟合为否，数据选择按真实独立接受/commit与SHA，和收益无关；继续价值为是，可避免原有合格数据被下一回放遗忘，又保留权限边界。现有固定模型历史PIT问题沿057披露，下一OFF比较不能倒改原B。
- 新增/修改/删除策略参数、金融结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。无金融/网络/训练/预测、无B中间PnL读取、无源码实现或旧层重审。production_qualified=false。
