# Stage133 C9 2022 已覆盖真实事件期权行情可读性终版

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-11 17:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage132 覆盖硬失败后的有限 data-readiness；不是策略候选
- 是否重要突破：有限突破，证明固定已覆盖事件的真实 premium/盘口/OI 可读，但不改变 vendor 覆盖失败
- 是否触发 A/B：否；`ready_for_option_strategy_ab=false`

## 外部调研与判断

- TqSdk 官方接口定义与本机源码一致：1 分钟线提供 OHLC、volume、open_oi、close_oi；tick 提供 last、bid/ask、quote volume、累计 volume 与 open_interest。
- 当前 vendor 的字段接口在四个固定真实事件上可用，但 Stage132 全集仍只有 `123/365=33.698630%` metadata 覆盖，2022 只有 `11/48`，核心窗口原风险覆盖只有 `26.461965%`。
- 我的判断：字段/API 探针成功，不能抵消样本可用性与年份/品种的强选择偏差。当前 vendor 不具备全量采集或策略研究资格。

## 本次变更

- 新增预声明：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1611_stage133_c9_2022_extracted_event_market_data_readiness_predecl.md`
- 新增实施计划：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1613_stage133_c9_2022_extracted_event_market_data_readiness_implementation_plan.md`
- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage133_c9_2022_extracted_event_market_data_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness.py`
- 新增参数：固定四事件、每事件一张机械保护类别期权、1 分钟 `data_length=2000`、tick `data_length=5000`、每事件 `180s` 含 close、canary/remaining 分段。
- 修改参数：无策略参数；独立 review 后只修正数据精度、finite、证据链、padding、tick 累计量和报告语义。
- 删除参数：无策略参数；禁止收益、strike/DTE/保护比例扫描。

## 冻结样本与选券

- 样本是 `2022-03-09 -> 2022-06-29` 核心窗口中 Stage132 全部 `extracted && cacheable` 事件，共 `4 events / 6 lots`，不按收益挑选。
- 机械规则：方向决定 protection class，先最早 expiry，再按 `(abs(strike-entry), strike, symbol)` 取 rank 1。
- 固定映射：

| entry_date | underlying | direction | option | candidates |
| --- | --- | --- | --- | ---: |
| 2022-04-26 | CZCE.MA209 | short | CZCE.MA209C2700 | 30 |
| 2022-05-10 | SHFE.au2206 | long | SHFE.au2206P400 | 29 |
| 2022-05-13 | CZCE.MA209 | short | CZCE.MA209C2700 | 30 |
| 2022-06-13 | CZCE.MA209 | long | CZCE.MA209P2900 | 30 |

## TDD 与独立审查

- 初版 Stage133 focused tests `18/18`、Stage130-133 联合 `58/58` 后只运行固定 canary。
- 独立 agent `Noether` 首轮审查：`P0=0/P1=3/P2=3`，禁止 remaining。三个 P1 为 ns 先转 float、inf 可误批准、attempt 未闭合选券/上游输入证据；三个 P2 为 padding 误判、tick 未按时间排序/未拒绝累计量回退、缺 canary 执行范围证据。
- 每项均先做单变量 RED，再最小修复：整数 ns 不再转 float；minute/tick infinity 纳入 integrity；增加 selection candidates/audit 与完整 source/event/session binding；padding 排除新增列；tick 按时间排序并拒绝累计 volume 回退；request/status 增加 run_id/mode/selection/ordinal/total。
- 修复后 focused tests `25/25`、联合回归 `65/65`。同一 canary 原样重跑后，增量审查 `P0=0/P1=0/P2=1`，批准 remaining3。
- 全量首轮终审发现 root report 未保留 Stage132 `123/365` 覆盖硬失败，记 `P1=1`；新增报告语义 RED 后修复，所有四事件再次按最终 producer lineage 原样重跑。
- 最终独立终审：`P0=0/P1=0/P2=2`，数字置信度 `99.8%`、语义置信度 `99%`，批准严格限定的 Stage133 data-readiness 结果。

## 最终数据结果

| entry_date | option | minute underlying/option | tick rows | tick volume first -> last | change | 五类字段 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2022-04-26 | C2700 | 345 / 345 | 5000 | 48 -> 88 | 40 | 全部 observed |
| 2022-05-10 | P400 | 555 / 555 | 5000 | 671 -> 860 | 189 | 全部 observed |
| 2022-05-13 | C2700 | 345 / 345 | 4802 | 0 -> 259 | 259 | 全部 observed |
| 2022-06-13 | P2900 | 225 / 225 | 5000 | 945 -> 2872 | 1927 | 全部 observed |

- `4/4` 当前事件均观察到 positive premium、finite OI、tick last、合法双边 bid/ask 和正成交。
- 四事件 OHLC 关系错误、重复时间、负 volume/OI/quote volume、infinity、crossed spread 和 tick 累计 volume 回退均为 `0`。
- 当前 cache：canary `attempt_0003`，其余三条 `attempt_0002`；此前 `5` 个旧 lineage attempt 全部保留且 `cacheable=false`。
- 每个当前 attempt manifest `11` 项，四份 bytes/SHA/detached checksum、raw -> normalized 重算、selection candidates/audit、producer/upstream lineage 全闭合；root manifest `6` 项闭合。
- canary request 明确 `1/1`；remaining 三条共享同一 run_id，ordinal `1/2/3`，network fetch count `3`。
- 凭证逐字命中 `0`；AST 订单、账户、持仓、CTP、邮件/live 调用命中 `0`；策略交易次数 `0`。

## P2 与适用边界

- TqSdk serial 的 raw `datetime` 是 `float64`；当前 parser 对 typed raw 不再产生二次损失，但无法恢复 DataFrame 形成前不可观测的 vendor 原始 ns。CSV 字面量最大量化差为 `72ns`，不影响本阶段分钟/session/字段可读性，不能用于要求纳秒级撮合时序的研究。
- 联合回归 `65/65` 由主流程实际运行并记录，但 root outputs 没有独立 test receipt；独立 agent 没有重跑完整测试，因此保留为 P2 证据边界。

## 回测结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：`0`
- 胜率：不适用
- 原因：本阶段没有策略订单、保护损益、资金曲线或 A/B 回测。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage133_c9_2022_extracted_event_market_data_readiness/rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness_report_stage133_c9_2022_extracted_event_market_data_readiness_v1.md`
- event status：同目录 `*_event_status_*.csv`
- attempt inventory：同目录 `*_attempt_inventory_*.csv`
- decision/lineage/root manifest：同目录对应 json/csv/txt。
- event attempts：同目录 `event_attempts/<event_id>/attempt_*/`。

## 结论

- 本阶段结论：`stage133_data_readiness_observed_all_four_no_strategy_inference`。
- 允许表述：固定 4 条 vendor-extracted 真实事件的 premium、OI、tick、双边盘口和成交字段可读。
- 禁止表述：不能说 365 事件可用，不能说保护策略有效，不能说收益或回撤改善。
- Stage132 硬失败保持不变：`123/365`；2022 `11/48`；核心风险覆盖 `26.461965%`；`fu/jm/FG/SM/hc` 在核心窗口 extracted 为0。
- 准入：`ready_for_full_premium_acquisition=false`、`ready_for_option_strategy_ab=false`、`ready_for_live=false`。
- 下一步：关闭当前 vendor 的全量策略路线；若继续期权保护，只能先获得覆盖 2018-2022 和关键产品的授权历史数据源并重新做全量 coverage gate。

## 过拟合反思

- 运行前判断：data-readiness 本身否。
- 运行后判断：仍否；没有收益字段、没有参数扫描、没有换事件或合约救结果。
- 风险：若在这 4 条 vendor-extracted 子集上计算保护收益、调 strike/DTE/比例，会立即形成严重选择偏差和过拟合。

## 继续价值反思

- 运行前判断：有限但有。
- 运行后判断：字段/API 探针目标已完成；当前 vendor 全量采集和策略研究无继续价值。
- 仍有价值的方向：寻找覆盖完整的授权 vendor，或转向与当前缺失数据无关、结构不同的新 PIT/账户治理路线。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`，不追加 `memory.md`。
