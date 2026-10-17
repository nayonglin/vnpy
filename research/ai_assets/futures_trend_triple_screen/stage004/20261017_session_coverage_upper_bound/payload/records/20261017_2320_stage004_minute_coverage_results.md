# Stage004 分层分钟覆盖审计结果

- line_id：`futures_trend_triple_screen`
- 当前模式：离线、只读、零账户的数据需求审计；`production_qualified=false`。
- 记录时间：2026-10-17 23:20 CST，读取时钟后记录。单次审计于 23:16:31 开始，用时 15.83 秒。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。
- 阶段性质：Stage001 C0 第二次因缺分钟终止后的批量覆盖诊断，不是新策略版本，也不是 C0 第三次金融尝试。
- 是否重要突破：否；是避免逐缺口金融重跑所需的基础数据证据。
- 是否触发A/B：本阶段不新增 A/B 金融实验；后续候选仍受既有 A/B 协议约束。

## 外部调研与判断

- 参考资料：沿用本线已冻结的三重滤网调研和 Stage001 设计；本阶段不新增 alpha 假设。具体依据为 Stage004 协议、原 `qmt_roll_intraday_execution.session_minutes`、Stage502 的真实 bar 与 carry bar 分发语义，以及原引擎 metadata、mapping、数据库。
- 我的判断：当前主力加紧邻前主不能保证覆盖跨多次换月的旧持仓或延迟订单；只统计真实日线也不能认证引擎中全部 carry 状态。因此分别列示四个有重叠的需求集合，并保留上界的条件与局限，而不按收益或失败日期反向挑选需求。

## 本次变更

- 新增脚本：`tools/stage004_minute_coverage.py`、`tools/test_stage004_minute_coverage.py`。
- 修改脚本：无；Stage001 runner、Stage002 builder、正式策略和原分钟缓存保持冻结。
- 删除脚本：无。
- 新增参数：独立 CLI `--audit`；输出目录存在时拒绝覆盖，不添加策略参数。
- 修改参数：无。
- 删除参数：无。
- 已运行源码 SHA256：`a30bc542b0b8c2dabea666f7a55a995a90c4b763e80d508369dc55c7767a75e3`。
- 冻结协议：`stages/20261017_2312_stage004_minute_coverage_protocol.md`；运行时 SHA256 `55a1285e07c9a75b89667e1c580912ca80d6b599124f0da534a4f436e4091565`。

## 回测/归因参数

- 数据区间：2020-01-01—2026-10-14，共同源交易日 1,641 天，正式 19 品种。
- 账户规模：N/A；未创建或运行账户。
- 成本口径：N/A；未计算成交、费用、滑点或收益。
- 样本过滤：原引擎 metadata 806 个合约，与原正式品种 mapping 合约身份一致；其中 500 个合约在本次范围有至少一种 session 需求。
- 策略/归因口径：只比较预期完整 session 时间键与已验 base、Stage002 overlay 的可用时间键。保留既有价格资格证据，本次不重新认证价格或生成交易。
- 四个集合：当日主力；当前主力加紧邻前主；metadata 合约的真实日线日期；研究期曾为主力的合约从首次主力日起保留至截止日的条件性旧主上界。
- 上界假设：初始空仓、暖机在 2020-01-01 前不交易，开仓与换月合约来自固定 mapping 且在 metadata 中。任意注入持仓、研究前遗留持仓、非 mapping 入场及所有任意 metadata carry 状态不在保证范围内。上界不是精确潜在信号集。
- 实际命令：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage004_minute_coverage.py --audit`。只执行一次，退出码 0。

## 结果

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。
- 金融尝试 0、下载 0、模型训练 0、原始数据修改 0；全部输入指纹运行前后不变。
- base 1,411,116 行，overlay 1,078,530 行，合计 2,489,646 个唯一可用分钟键，重复键 0。
- 四集合并集输出 452,069 个合约日 session，缓存 28,451 个品种日网格；采用有序索引及二分计数，不展开约 1.34 亿行虚拟分钟。

| 需求集合 | session 数 | 完整 session | 完整率 | 有真实日线 session | 无真实日线 carry 风险 session | 有真实日线但不完整 session |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 当日主力 `main_only` | 28,451 | 6,360 | 22.35% | 28,451 | 0 | 22,091 |
| 当前主＋紧邻前主 `main_plus_previous` | 55,516 | 6,369 | 11.47% | 39,193 | 16,323 | 32,824 |
| metadata 真实日线 `metadata_real` | 110,902 | 6,813 | 6.14% | 110,902 | 0 | 104,089 |
| 条件性旧主上界 `ever_main_upper` | 380,550 | 6,369 | 1.67% | 39,383 | 341,167 | 33,014 |

四集合互有重叠，不能相加为总需求、总缺口或下载量。完整率指本次已验分钟缓存对该集合的完整 session 覆盖率，不表示日线准确率，也不表示每个上界 session 都会发生交易。

- 旧主上界的 341,167 个无真实日线 session 仅为 carry 风险诊断；大量为已到期旧合约，不应变成待下载清单。即使真实日线存在但分钟不完整，也需先匹配无收益信息的实际候选或准备事件，才能判定应补需求。
- 两个已知终止点：`rb2010.SHFE` 2020-05-18 已有 345/345 分钟、anchor 存在；2020-08-12 为 0/345 分钟、anchor 缺失。二者都是真实日线上的当日主力。后者证实是实际数据缺口，不能将 C0 的终止归因为周线过滤 alpha 失败。
- 本机候选源路径 7,912 条，列出族、文件大小及旧 manifest 中的声明 SHA（如有）。本阶段读取候选 payload 0、实测候选 SHA 0、自动接入 0。路径存在或旧 SHA 声明均不等于该 session 已验覆盖；rb2010 的 30 条候选路径也同理。
- 6 个有意义测试通过：单分钟缺口、向量化与枚举一致、重复键拒绝、跨多次换月旧主保留、无真实 bar 不归为真实数据缺口、周五夜盘归周一。
- 独立审查通过有限语义与小样本枚举检查：8 个 session 哨点及 1 个稀疏网格探针，核对真实 bar/carry 分类、计数和选定产物指纹。未重复全批审计、旧账户或周特征计算，也未宣称独立重算全部 452,069 行或重验价格。

## 输出文件

以下均位于 `outputs/stage004_minute_coverage/`，完整 session gzip 保留本机，后续归档可仅纳入小汇总及指纹。

- report：本阶段记录。
- summary：`summary.json`、`requirement_set_summary.csv`。
- orders：N/A。
- daily：`session_coverage.csv.gz`；这是数据覆盖表，不是账户日权益。
- quality：`input_manifest.json`、`attempt_started.json`、`known_failure_session_coverage.csv`。
- 分组汇总：`contract_year_summary.csv`、`product_year_summary.csv`、`year_summary.csv`、`contract_summary.csv`。
- 小清单：`gap_examples.csv`（1,872 条确定性分组示例）与 `local_source_candidates.csv`。
- 独立审查：`outputs/stage004_independent_review/sample_checks.json`，状态 `limited_semantic_and_small_enumeration_checks_pass`。
- 本次 summary SHA256：`d4edaf2926d9cd227afaba623201d2df3bd01c2b50eda33b3025d76702ba24f9`；逐输出 SHA 见其 `artifact_sha256`。

## 结论

- 本阶段结论：现有已验分钟以旧路径实际消耗的 session 为主，无法直接保证过滤后新路径的完整分钟需求。缺口范围已一次性按固定集合表达；最宽集合包含大量无真实 bar 的 carry 诊断，不能直接用于采购或下载。
- 是否进入下一步：是，进入无账户、无收益信息的精确候选/准备事件需求生成；当前不启动金融尝试，不下载整个上界。
- 下一步：先从固定策略语义生成不因账户变化漏信号的可解释事件需求，再对这些 session 检查本机候选完整性与日线一致性。准备齐全后才讨论 C0 后续回放；保留两次 C0 失败及实际 runner 字节证据，不采用“补一个缺口就再跑一次”的流程。

## 过拟合反思

- 运行前判断：否，本次覆盖审计不以收益选样本，不调策略规则或参数。
- 运行后判断：否，未读取新的收益结果、未改变模型或周线规则，只输出固定集合的覆盖与条件。原策略历史选择偏差仍保留，本阶段不提供新 alpha 有效性证据。
- 原因：数据门与策略效果分离；真实缺口、条件性 carry 诊断和未验候选源明确区分，不以最宽上界制造数据需求。

## 继续价值反思

- 运行前判断：是，能避免逐缺口反复进行金融回放。
- 运行后判断：是，但价值在于下一步缩小真实执行需求，而非补齐全部保守上界。
- 原因：当前已确认覆盖不足的结构性范围及本机来源候选，继续重复账户只会再次触发数据门；精确事件需求可先解决这一前置条件。

## 合入建议

- 是否更新本线 `LINE.md`：由 root 汇总本记录后统一更新，本任务未改。
- 是否更新 `research/registry.md`：由 root 决定，本任务未改。
- 是否追加根目录 `memory.md/back_log.md`：否，属本线常规数据阶段，未晋级正式候选。
- 工具、测试和小汇总可作为研究证据归档；不合入正式策略运行通道，不宣称生产资格通过。
