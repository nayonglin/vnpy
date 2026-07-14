# Stage002 FU-SC 代理期权执行数据预检闭线

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-13 00:09 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：执行数据资格预检、统计缺陷修复、研究线闭线
- 是否重要突破：否；这是必要的否证与风险隔离，不是策略收益突破
- 是否触发A/B：否；未产生策略候选，禁止进入 A/B、正式或 live

## 外部调研与判断

- 参考资料：沿用 Stage001 已冻结的 INE 原油期权上市公告、TqSdk 历史回测接口文档、cross-hedging/basis-risk 文献与 CME basis 教材。
- 我的判断：Stage001 的 `FU -> SC` T-1 basis 与历史链可读性只证明“可能存在代理工具”，不能绕过执行日选券资格。若入场日只能选到当日到期的 SC 期权，它不能作为预声明中的多日凸性保护；事后换下一 SC 月份会改变冻结的 underlying 与 ATM 选择合同，属于结果后救参。

## 本次变更

- 新增脚本：`tools/stage002_execution_preflight.py`，逐事件重算 Stage001 raw metadata 的 normalization/audit/identity，构造 T-1 SC 参考价、adverse-side ATM 选券和整数粒度门，全程无网络。
- 新增测试：`tests/test_stage002_execution_preflight.py`，覆盖 expiry 严格晚于 entry、方向映射、ATM 排序、手数公式、真实32事件闭线与无网络条件。
- 修改脚本：独立首轮 review 发现 `granularity_pass` 未要求 `selection_pass`，导致3个无有效期权事件被误计为粒度通过；修复为未选券事件粒度必为0，并重跑全部输出。
- 删除脚本：无。
- 新增参数：`ATM_DELTA_PROXY=0.5`、`MIN_IDEAL_OPTION_LOTS=2.0`、`MIN_ALL_PASS_RATE=0.90`、核心事件数 `6`；选券固定为 T-1 SC prior close 最近 ATM，long FU 选 PUT、short FU 选 CALL，expiry 必须严格晚于 entry date。
- 修改参数：无正式参数；review 修复只改统计语义，不改任何资格阈值、事件、方向、合约月、strike 或 expiry。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage131 中 SC 期权上市后全部 `32` 个 FU 入场事件；核心窗口 `2022-03-09 -> 2022-06-29` 共 `6` 个事件。
- 账户规模：沿用当前 C9/15w 事件风险字段，仅用于理论 money-delta 手数；未建立期权账户或资金曲线。
- 成本口径：不适用；未读取期权 premium、minute、tick、成交量、OI 或买卖价差。
- 样本过滤：不删事件；metadata 语义必须 `32/32`，ATM adverse-side selection 必须 `32/32`，核心粒度 `6/6`，全体粒度通过率 `>=90%`。
- 策略/归因口径：SC 参考价为 entry date 前一交易日所选 SC 实际合约 close；理论手数 `FU手数 × FU乘数 × FU加权入场价 × full126_beta / (SC乘数1000 × SC T-1 close × 0.5)`。

## 结果

- 期末权益：不适用；未回测。
- 总收益：不适用；未回测。
- 最大回撤：不适用；未回测。
- Sharpe：不适用；未回测。
- 总滑点：不适用；未回测。
- 总交易次数：`0`。
- 胜率：不适用；未回测。
- metadata 语义复验：`32/32`。
- ATM adverse-side selection：`29/32`，未达到冻结硬门 `32/32`。
- 修复后整数粒度：`29/32=90.625%`；核心 `6/6`；理论手数最小/中位/最大 `19.986408/45.816039/88.287732`。粒度率虽过90%，但不能覆盖 selection 硬失败。
- 三个固定失败事件：`2023-08-15 FU2310 long -> SC2309 PUT`、`2025-02-12 FU2503 long -> SC2503 PUT`、`2025-06-12 FU2509 long -> SC2507 PUT`。对应链存在 CALL/PUT metadata，但目标合约 expiry 均等于 entry date，当日到期，严格 `expiry > entry_date` 后候选数为0。
- 网络调用：`false`；entry-day minute/tick 下载 `0`；订单、账户、持仓、CTP、邮件和 live 调用均 `0`。
- 机械决策：`CLOSE_LINE_SELECTION_INELIGIBLE`；`ready_for_entry_day_data_canary=false`、`ready_for_option_strategy_ab=false`、`ready_for_live=false`。
- 首轮独立 review：`P0=0/P1=1/P2=2/P3=1`，唯一 P1 为无选券事件被误计粒度通过；不改变闭线结论，但影响审计证据，已修复。
- 修复后独立终审：`P0=0/P1=0/P2=0/P3=0`，闭线结论置信度 `99%`。
- 测试：Stage002 聚焦 `4/4` 通过；reviewer 未自行重跑测试，但逐项核对源码、测试、decision JSON、CSV 与 producer hash 一致。

## 输出文件

- report：`outputs/stage002_execution_preflight/stage002_preflight_report.md`
- summary：`outputs/stage002_execution_preflight/stage002_preflight_decision.json`
- orders：不适用；未生成订单。
- daily：不适用；未运行日级策略回测。
- quality：`stage002_preflight_gate_matrix.csv`、`stage002_metadata_semantic_revalidation.csv`、`stage002_event_context.csv`、`stage002_atm_candidate_ranking.csv`、`stage002_atm_selection_and_granularity.csv`、`stage002_preflight_manifest.csv`

## 结论

- 本阶段结论：`FU -> SC` 固定代理期权路线在预声明的全事件选券资格门失败，研究线关闭。失败来自真实合约到期结构，不是回测收益、缓存损坏、未来函数或统计 bug。
- 是否进入下一步：否；不得下载 entry-day minute/tick，不得计算保护收益，不得跑 A/B、多周期或 live。
- 下一步：回到当前 C9/15w 的结构性研究目标；下一条实验必须是与已关闭路线不同的新假设，并先注册、外部调研和预声明。禁止把失败事件删掉、把 `expiry > entry` 放宽为 `>=`、改选下一 SC 月或扫描 strike/DTE 来救本线。

## 过拟合反思

- 运行前判断：否；事件全集、方向、T-1 参考价、ATM、expiry 和硬门均在执行结果前冻结。
- 运行后判断：否；发现失败后没有改合约月、到期日、事件或阈值，只修复会误导审计但不改变结论的统计 bug。
- 原因：闭线由 `29/32 < 32/32` 的机械资格失败决定；若继续围绕三个失败事件换月或放宽到期日，才会形成明显的结果后过拟合。

## 继续价值反思

- 运行前判断：有；Stage001 已通过 basis 与 metadata，需要执行资格门阻止不可交易的概念进入回测。
- 运行后判断：本线无继续价值；整体研究目标仍有价值。
- 原因：固定 `FU -> SC` 映射无法满足全事件选券门，继续采集 premium 只会制造选择偏差；下一步应寻找结构不同、能直接改变亏损尾部且不压缩趋势右尾的机制。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage002 关闭。
- 是否更新 `research/registry.md`：是，登记闭线状态与禁止救参边界。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 的重要闭线摘要；不追加 `memory.md`。
