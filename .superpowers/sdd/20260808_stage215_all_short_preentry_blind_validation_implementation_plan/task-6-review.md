# Stage216 最终独立审查

- 审查时间：2026-08-08 22:51 CST
- 审查者角色：未参与数据准备、图片标注、分歧裁决或统计实现的独立审查者
- 审查边界：只读复算 Stage214—216、Task4 完成态证据、统计代码与测试；未修改研究代码、数据、Stage216、策略、CTP 或订单入口
- 最终裁定：**Approve**
- 置信度：**99%**（结论方向）；**95%**（盲态执行过程，因为文件系统层面的未访问无法由静态产物完全证明）

## 开始反思

- 过拟合：**是，仍有先验风险**。假设来自 Stage213 的 17 笔空头赢家，视觉标签具有主观性；Stage214 的全体空头、唯一窗口、匿名双盲、冻结门槛和禁止事后救参能控制风险，但不能把假设生成阶段的选择偏差变成零。
- 继续价值：**是**。独立复算能判断这次预注册实验是否真正证伪原视觉线索，避免将赢家条件下的共性误接为预测规则。

## 外部调研与判断

- 复核了 SciPy 官方 `fisher_exact` 与 `scipy.stats.contingency.odds_ratio` 文档及其 GitHub 源码入口。官方口径明确：`fisher_exact` 的 2×2 statistic 是样本/非条件 OR；`odds_ratio(kind="conditional")` 给出条件极大似然 OR，其 `confidence_interval` 给出条件精确区间。
- 本地为 SciPy `1.17.1`。本审查不调用 Stage214 统计模块，直接从冻结 CSV 重建 2×2 表，以手算样本 OR、概率差和 kappa，并独立调用 SciPy 的 Fisher 与条件 OR/CI 交叉核验。
- 调研判断：Stage216 同时披露样本 OR、条件 OR 与条件精确 CI，统计名词和数值口径正确；不能把描述性正向差异等同于预测有效。

参考：

- <https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.fisher_exact.html>
- <https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.stats.contingency.odds_ratio.html>
- <https://github.com/scipy/scipy>

## 独立复算

### 1. 标签冻结、集合与裁决

- `blind_label_freeze.json` 中手册、Reviewer A、Reviewer B、裁决四个 SHA256 均与当前文件原始字节一致；图包哈希也与当前 64 张 PNG 的独立 bundle 复算一致：`96164ffdfd4f73e71ff89b52dfd138d3775d81a97434667bca00d26d661e70c4`。
- Reviewer A、Reviewer B、最终标签、mapping、reviewer manifest 均恰为 64 个相同且唯一的 `CASE-*`；A/B 一致 `55/64=0.859375`。
- 按四类标签边际分布手算 Cohen's kappa 为 `0.6953992596509783`，与落盘 `0.6953992596509784` 一致。
- A/B 分歧恰为 9 个；`adjudication_labels.csv` 的集合与分歧集合严格相等，无缺项、额外项或重复项。按“一致样本直取 A 标签、分歧样本取裁决标签”重建后，与 `adjudicated_labels.csv` 64/64 一致。
- 最终标签重算：`trend_same_direction=48`、`mixed_or_opposite=14`、`range_or_compression=2`、`insufficient=0`。
- 校准顺序证据一致：12 例校准 A/B 时间早于 v1 手册冻结，正式 A/B 标签时间晚于手册冻结，裁决又晚于正式 A/B；校准 `11/12=0.9167`、kappa `0.800`。

### 2. Mapping 联结与主统计

- `blind_mapping.csv` 与 `short_event_manifest.csv` 以 `open_trade_id` 一对一外联：64 行全部 `both`；其余 13 个事件/结果字段逐列不一致数均为 0。
- 结果状态严格为 61 resolved / 3 unresolved；三笔为 `BACKTESTING.166/.265/.589`，`aggregate_r`、`outcome_ge_2r`、`outcome_profitable` 均为 NA，未被误写为 False。
- 61 笔可分析样本独立重建主表：`[[14,32],[3,12]]`。
- 主统计复算：
  - 同向组 `P(>=2R)=14/46=0.3043478261`；非同向组 `3/15=0.2`；lift `0.1043478261`。
  - 样本 OR `14*12/(32*3)=1.75`。
  - 条件 OR `1.7350437824`；条件精确 95% CI `[0.3802211528,11.0646600778]`。
  - 双侧 Fisher `p=0.5235745695`。
  - R 中位数 `-0.1396420344` vs `-0.5`。
  - 盈利概率 `22/46=0.4782608696` vs `3/15=0.2`。
- 全部数值与 `primary_statistics.json`、Stage216 一致。

### 3. 稳健性与缺口边界

- 年份留一按 2020—2026 共 7 次重算，条件 OR 依次为 `1.302965/2.350779/1.778872/2.125993/1.953830/1.135153/1.910700`，全部大于 1，唯一最小值为剔除 2025 后的 `1.135153`。
- 在 61 笔可分析样本和全部 64 笔样本中，唯一最高频品种均为 `fu`（分别 8 笔/8 笔）；剔除后主表 `[[11,28],[3,11]]`，样本 OR `1.440476`、条件 OR `1.430998`，方向不反转。
- 对 3 个缺口独立穷举 `4^3=64` 个逐 case `signal × outcome` 分配，归并为 20 个统计等价的 2×2 表，正好覆盖 `gap_bounds.json` 的 20 个聚合分配：
  - 最有利：`[[17,32],[3,12]]`，lift `0.1469387755`、样本 OR `2.125`；即使最有利也未到 15pp 主门。
  - 最不利：`[[14,32],[6,12]]`，lift `-0.0289855072`、样本 OR `0.875`；方向反转。
- 因此缺口边界不稳健，但它不能把已经失败的主效应门改写为有效信号。

### 4. 决策优先级与 11 门

- `evaluate_decision()` 的优先级与 Stage214 结论分级一致：可靠性失败 -> `visual_definition_not_reproducible`；可靠性通过但任一主效应门失败 -> `reject_signal`；仅在主效应全过时，缺口方向翻转才降为 `insufficient_data`；之后才判断阶段稳定性或晋级。
- 本案 11 门独立复算为 6 过/5 败：可靠性 2 门、R 中位数、盈利概率、年份留一、最高频品种剔除通过；15pp lift、样本 OR>2、Fisher p、CI 下界、最不利缺口失败。
- 因主效应六门已有四门失败，最终必须是 `reject_signal`，不能误判为 `insufficient_data` 或 `qualified_for_numeric_translation`。

### 5. Task4 完成态与 bundle

- Task4 独立复核已在 `task-4-review.md:48-83` 批准 Fix2，且当前数据可再次复算：74 个授权 exact-contract/date 文件、22,530 行；74/74 均有唯一 14:59，14:59 flat+zero 为 0；305/305 目标质量日通过；30/30 旧截断日 dominance 通过，低优先级混入合计 0。
- 当前 label freeze 绑定 Fix2 bundle `96164ffd...e70c4`。`blind_chart_bundle.json` 将 `50a86...` 和历史无效 `dc3dd1...` 标为 superseded；partial/mixed archive 审计明确 `reviewer_eligible=false`。未发现旧 bundle 进入正式标签或统计链。

### 6. 泄漏、偏差与范围

- 主图只绑定 `[D-5,D-1]`，reviewer manifest 仅含 case、文件名、可用日数和 bar 数；当前 64 图 PNG metadata 通过 allowlist 审计。未发现身份、结果、D0 或 Stage213 标签进入 reviewer 产物。
- 盲态是“sealed surface + fork none + 审阅者不得访问映射”的程序性隔离，不是操作系统级访问控制；静态文件能证明 reviewer 输入不含结果、冻结顺序和哈希一致，但不能密码学证明 agent 从未读取共享工作区的其他文件。当前没有泄漏证据，而且最终结果为拒绝，残余风险不会制造假阳性晋级。
- 从控制器基线 `4ad44ae0a..HEAD` 的已提交 Stage214 变更只包含 Stage214 工具、测试、Task4 报告和本线 Task4 数据证据，没有 Stage217—220、CTP、订单或正式策略文件。
- 当前 index 为空；工作区同时存在用户的 Stage217—220/正式执行文件改动。最终合入不得使用宽泛 `git add -A`，只应强制添加 Stage216、Task5/6 小型 CSV/JSON/Markdown 证据和本审查报告，继续排除 PNG、Stage217—220、CTP、订单与无关 live 文件。

## Findings

### Critical

None.

### Important

None.

### Minor

1. **Stage216 的过拟合反思把“风险受控”写成了“无过拟合风险”。** Stage214 `:276-279` 明确记录运行前“是，存在较高过拟合风险”、运行后“仍存在风险”；Stage216 `:96-98` 改成运行前后均“否”。冻结与双盲控制了研究自由度，但不能消除假设源自 17 笔赢家和主观视觉标签的选择风险。建议最终合入者把 Stage216 两句改为“是，但已受预注册控制；运行后仍有有限风险”，不改变 `reject_signal`、任何统计值或后续停止条件。

2. **SDD 进度账仍停在 Task5 in progress。** `.superpowers/.../progress.md:16` 尚未记录正式 64 图标注、裁决、揭盲和本终审。它不影响研究结论，但最终整理时应同步 Task5/6 完成态，避免后续读者误判流程未闭环。

3. **Task5/6 小型证据和 Stage216 当前尚未进入 Git 跟踪。** 这符合“终审后再最终提交”的执行顺序，因此不阻塞本次研究裁定；但它们受 outputs ignore 规则覆盖，最终合入必须按 Stage215 `:310-318` 显式 force-add，不能只提交 Stage216 文本而丢失冻结标签与机器统计证据。

## 验证证据

- 相关回归：`88 passed in 22.76s`。
- 范围：Stage208 atlas、Stage214 prepare、Stage214 stats 三份测试。
- `py_compile`：两个 Stage214 工具脚本通过。
- `git diff --check`：通过。
- Stage216 文件单独 whitespace check：通过。
- 复算未运行 `prepare()` 或 `reveal()`，未覆盖研究数据；所有核心数字均由只读加载后独立计算。

## Verdict

**Approve.** 未发现会改变 `reject_signal` 的 bug、结果泄漏、选择性剔除、统计错误或提交污染；Critical=0，Important=0，Minor=3。Minor 1/2 建议在最终记录整理时修正，Minor 3 必须在最终提交动作中落实，但均不要求重跑图片、标签或统计。

## 结束反思

- 过拟合：**是，但当前拒绝结论没有依赖事后救参，风险已被良好控制。** 假设来自赢家样本的固有选择风险仍在；全体空头、冻结双盲、唯一主检验以及在正向描述性差异下仍执行拒绝，显著降低了把偶然形态误当信号的风险。
- 继续价值：**继续优化当前 64 笔上的同一形态没有价值。** 主效应量、样本 OR、Fisher、CI 与缺口稳健性同时失败，继续改窗口、阈值、标签或品种会转为过拟合。只有保留冻结手册、前瞻积累未参与设计的新样本后做真正样本外复验，才有有限继续价值。
