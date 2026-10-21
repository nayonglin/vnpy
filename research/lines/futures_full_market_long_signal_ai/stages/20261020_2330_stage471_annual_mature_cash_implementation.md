# Stage471：固定年度成熟更新的四本连续现金适配

- line_id：`futures_full_market_long_signal_ai`；改动时间：2026-10-20 23:19—23:30 CST；非重要突破版本。
- 本次只实现现金适配和最少必要的小型行为验证，尚未运行真实现金。Stage469 冻结协议 SHA：`f62281e099200e065785b61cc89a47a2111fe7d3dbf2ec60102b167b0708d4f6`。
- 不建 worktree、分支，不 commit/push；未改正式 C9、CTP、邮件、launchd、原四前瞻账户、旧 stage/LINE/registry 或其他研究线。

## 修改内容与固定参数

新增 `tools/stage471_annual_mature_cash.py`，将 470 的年度完整选择流交给原 157 `make_voluntary_signals`/原 131 `run_cash_account`。外部候选固定为 `C_RESEARCH_COMMON52_FIXED_ANNUAL_MATURE_UPDATE`，内部 `VOLUNTARY_RESELECT` 仅为已有 helper schema 别名，不继承 Con4 身份或训练审核门。

现金仅接受 470 `cash_handoff.json` 的新派生输入和绑定：完整 399252 母体的七 identity、161014 main choices、候选 main 所选动作的 16 现金字段、held diagnostic、calendar、boundaries，以及完成 fit/selection manifest。handoff 与 manifest 的 artifacts 必须逐项一致，派生表必须属于同一 470 输出目录。原 129 actions、COMMON 和原 mothers 不在本现金进程打开；没有从旧大表补读的 fallback。

新增参数只有上游已冻结的年度 Jan1 成熟经验更新；现金层没有新增策略参数。修改的是适配 schema、单次运行的检查点及报告恢复；删除参数 0。固定值如下：

| 项目 | 固定值/约束 |
| --- | --- |
| 初始权益 | 1,000,000 |
| 单 family 风险 | 0.0025 |
| 总风险 | 0.02 |
| 缓冲后保证金上限 | 0.25 |
| margin buffer | 1.10 |
| 初始止损 | 0.25N |
| 单日参与率 | 0.01，沿原 gross 与入场半额容量 |
| 成本 | base、stress，原费用/滑点/整数 lot |
| 窗口 | 2020 连续、2023 冷启，均至 2026-10-16 |
| 最多新现金 | 4，最多新 fit 0，原控制重放 0，SQL 0 |
| 置信区间 | 原 252 日块/2000 次 indices，绝不重生 |

所有年度选择先拼成一条信号流，再各运行 2020 连续/2023 冷启×base/stress 的完整窗口。`cutoff` 与 `deployment_fold_cutoff` 必须保持原 2020/2023 部署分段，`training_cutoff` 另列同年 Jan1；年界不清仓、不 reset 现金、不累计独立年度收益，不将 2023 控制状态注入 2020 候选自身路径。canonical reference 使用完整母体投影，原 SL0+20low、anchor、共同 K、联合预算、D 开盘减量、费用/滑点、容量/stale/生命周期完全沿原核。

控制严格来自 469 所绑定的 **157 自身四本**：其 4 summaries 与 36 ledger 的绑定全部验证，绝不取 157 `baseline_references` 指向的旧 131B。原 native cache 只 restore 一次服务四账，经济投影与 calendar/common-K 保持原身份；实际结束只核 DB stat，没有原库 SQL。

零新现金分支只在完整 assembled signals 的全部字段、分数、行顺序以及原 canonical/calendar/K/economic/native 身份一致时触发。选中 ID 相同但 score 或生命周期等任一现金相关字段改变，仍正常运行最多四本候选。若确实完全一致，逐项引用原控制账，并用零配对增量进入原严格门，因此不能把身份复用写成改善。

原 157 经济门保持：四窗自身收益>0、财富始终正、相对控制收益不低且 DD 不更深；2020 stress 收益、DD 均须严格改善且原配对日 log 增长差 CI95 下端>0。没有 epsilon、Sharpe/年度替代门或收益/DD 放宽；held known/unknown 独立披露，不将无界未知补零或签 across-family 资格。

## 检查点与报告恢复

每个 kernel 完成本后先保存 gzip pickle 原始 book 及 SHA checkpoint；四本全部保存后才生成财务报表。因此报告故障不会触发已完成 kernel 重放。`--reports-only` 仅允许读取原 manifest 已绑定的完整四本 checkpoint、上下文、控制及报告所需经济输入；不调用 prepare/native cache/cash。运行失败终态按 attempt 保留，不能自动重新开始失败的 kernel。

输出 manifest 提供账户 ledger、summary、comparison、annual、paired annual、bootstrap、decision、signals、source receipt、checkpoint 的直接绑定，供一次合并独立审查使用。未自行启动第二审查 agent，也未运行旧 suite 或旧现金 CLI。

## 小型验证与计数

新增唯一 fixture：`outputs/stage471_annual_mature_cash/synthetic_fixture.py`。最新 `.py311/bin/python` 实测 6 项通过，exit 0：

1. 2021 的 training cutoff 不覆盖原 2020 deployment cutoff；错误拆年度被拒。
2. 假账户 kernel 仅 4 次完整窗口调用，跨 2020/2021 年界保留持仓和已变现金。
3. 假报表故障发生前四本已全部保存；报告恢复后 kernel 调用数仍 4，恢复进程新 cash 0。
4. 相同选择 ID 但 score/生命周期改变，禁止零现金复用。
5. 收益/DD/CI 全相等不能通过严格改善门。
6. 派生输入仅读已绑定 bytes，不直接从原始路径开表。

另只读导入原执行 helper，并核原 157 绑定的 16 份执行源码与 100 万/.0025/.02/.25/1.1 常数；真实 kernel 调用 0、native cache load 0、原 actions/COMMON/mothers 读取 0、SQL 0、fit 0、现金 0。

初始 RED 因新适配文件尚不存在而失败，属于预期；随后报告恢复新增 hash 检查曾暴露 macOS `/var` 与 `/private/var` 临时目录别名差异，统一 `resolve()` 后 6 项重验全绿。两者均发生于合成 fixture，未造成真实回测启动、源数据读取或账本重跑。

最新源/fixture 字节绑定、完整 fixture 输出、导入验证与零实际计数写入 `outputs/stage471_annual_mature_cash/implementation_verification.json`。本子任务新增 fit 0、新现金 0；469 冻结前累计 466 fit/254 完成 cash 及 1 旧 partial。并行 470 如有新增实际 fit，由 root 在合并阶段统一更新，本文不将并行预算冒充结果。

## 回测结果与后续

新增/修改/删除回测结果均为 0。真实期末权益 N/A、总收益 N/A、最大回撤 N/A、Sharpe N/A、手续费 N/A、总滑点 N/A、总交易次数 N/A、胜率 N/A；假账户数值只用于行为验证，不能当作财务结果。

待 470 完整 handoff 签发后，root 按精确 source bundle 启动唯一真实四账；若完整现金身份同控制则 0 新账。一次实际结果后由同一个独立 agent 合并核模型、选择、现金数据/逻辑、置信度与 bug，不重 fit 或重放 cash。结果失败即停止此固定年度包，不扫描月/季/衰减/窗口/阈值救参。

## 调研判断与开始/结束反思

本次复核 [sklearn TimeSeriesSplit 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) 与 [微软 Qlib task generator 源码](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py)。判断：它们支持时间顺序和扩窗任务的设计原则，但现金跨年连续性仍须由本账户内核和显式部署列保证；不能从这些资料推断年度更新有 alpha，固定 gap 也不能取代原变长退出标签的 `label_known_date<cutoff`。

开始新增结果调参过拟合：否。原因是只实现 469 收益前冻结的年度单点，没有读候选真实财务成绩，也未搜索风险、止损或更新频率；同史长期择题风险仍是。

结束新增结果调参过拟合：否。修正仅为检查点路径适配和输入闭包，6 个行为检查未用于选择赚钱参数；它们不提供独立收益证据。

开始/结束继续价值：是，有条件。完成一次最多四账可以证伪年度吸收成熟经验是否改善原现金路径，且保护旧控制和计算预算；工程验证本身不是目标达成，仍不能授权晋级、加注或生产，完整 goal active。
