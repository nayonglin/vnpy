# Stage132 当前 C9 真实事件期权 metadata 原子分批采集终版

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-11 16:02 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：授权历史 metadata 数据采集与覆盖审计；不是策略候选
- 是否重要突破：是，完成 365 请求账本并证明当前 vendor 历史覆盖不足
- 是否触发A/B：否；`ready_for_option_strategy_ab=false`

## 外部调研与判断

- TqSdk 官方 API/回测文档确认 `TqBacktest` 的历史推进和 `query_options(..., expired=False)` 的时点过滤语义；本阶段冻结本机已验证的 `tqsdk=3.9.4`。
- 官方文档对 CZCE 三位年份格式的描述与 vendor GraphQL 历史关系目录存在差异；三位/四位和同期合约对照证明，旧合约报错来自 vendor catalog 缺口，不能用简单年份展开修复。
- 我的判断：请求账本完整不等于 metadata 覆盖完整。当前覆盖对年份、交易所和产品有严重选择偏差，不能支撑全周期保护策略结论。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage132_c9_event_option_metadata_batches.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage132_c9_event_option_metadata_batches.py`
- 新增预声明：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1430_stage132_c9_event_option_metadata_batches_predecl.md`
- 新增参数：固定 `365` events、batch size `10`、`37` batches、每事件独立 `TqBacktest(entry_date)`、`60s` 含 close 超时、固定 canary 10条、attempt 原子目录、producer tool/test/predecl SHA。
- 修改参数：无正式策略参数；canary 发现后新增严格终态 `underlying_not_in_option_catalog`，只接受 vendor GraphQL 错误 instrument 与 request underlying 精确一致。
- 删除参数：无策略参数；否决 CZCE 三位转四位简单修复和默认 `np.isclose` 容差。
- 删除结果：无回测结果删除；所有旧失败/旧 producer lineage attempts 均永久保留，但不再作为最终缓存。

## 数据参数与口径

- 冻结输入：Stage131 query events `365` 行，SHA256 `7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- 时间区间：events 覆盖 `2018-01-15 -> 2026-04-30` 入场日；每事件只查询同一入场日历史上下文。
- 终态：`extracted/empty_chain/underlying_not_in_option_catalog` 为 cacheable；auth/timeout/query/integrity/missing 均 fail-close。
- request-ledger completion：cacheable events / `365`。
- metadata coverage：extracted events / `365`；empty/catalog 不从分母删除。
- extracted cache 校验：untouched 全列保留；normalized 从 untouched 重算，numeric 固定 `rtol=0/atol=0`；symbol/underlying/class/expiry/strike/expired/multiplier/tick 全守恒。

## TDD 与 canary 审查

- 最终 Stage132 focused tests `19/19`；Stage130+131+132 合计 `40/40`。
- canary 初轮 `3 extracted + 5 empty + 2 query_failed` 后硬门停止；两条 query_failed 经 vendor 对照改为独立 catalog-missing 终态，旧 attempts 保留。
- 独立 agent `Locke` 首轮发现 `P1=2/P2=3`：normalized 未逐值绑定、catalog instrument 未绑定、close 不在60s、缺固定分母 ratio、缺 producer SHA；全部按 TDD 修复。
- 第二轮剩余 `P1=1`：默认 `np.isclose` 会接受 `3000 -> 3000.01`；用单变量反例 RED 后改为零容差。
- 最终固定10条由最终 tool/test/predecl SHA 强制重跑，独立增量终审 `P0=0/P1=0/P2=0`，批准 remaining355，仅限 metadata。

## 全量结果

- 365 个最终事件全部 cacheable，历史 attempts `387` 个；request-ledger completion `100%`。
- 最终终态：`123 extracted / 149 empty_chain / 93 catalog-missing / 0 failure-or-missing`。
- metadata coverage：`123/365 = 33.698630%`；normalized metadata `8,168` 行。
- 年度覆盖：2018 `0/25`、2019 `0/43`、2020 `14/68`、2021 `20/57`、2022 `11/48`、2023 `13/36`、2024 `26/41`、2025 `27/35`、2026 `12/12`。
- 交易所覆盖：CZCE `55/145`、DCE `4/39`、GFEX `10/11`、SHFE `54/170`。
- 产品关键缺口：`hc 0/27`、`jm 0/25`、`fu 1/37`、`sp 1/16`。
- 2020+：event `123/297=41.4141%`、lot `134/333=40.2402%`、原风险金额覆盖 `56.6805%`。
- 2022全年：event `11/48=22.9167%`、lot `13/54=24.0741%`、原风险金额覆盖 `24.0061%`。
- 2022-03-09 -> 2022-06-29 核心窗口：event `4/16=25%`、lot `6/18=33.3333%`、原风险 `831,960/3,143,984.2=26.461965%`；`fu/jm/FG/SM/hc` extracted 均为0，仅 MA/au 有链。

## 完整性与隔离

- 387/387 attempt manifest bytes/hash/checksum 错误 `0`；365 最终 request identity/producer SHA/integrity 错误 `0`。
- untouched -> normalized 精确重算 mismatch `0`；catalog instrument mismatch `0`；非 extracted 夹带 metadata `0`。
- root manifest SHA256：`50e578bd7b5b4a83bbe8649ba6d8e26b0de990b452b53eae0abc7e6bffa66473`。
- 凭证逐字命中 `0`；订单 API `0`、CTP 未连接、正式实盘/邮件/launchd 未改；后台进程残留 `0`。
- 输出目录约 `13 MiB`。

## 回测结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：`0`
- 胜率：不适用
- 原因：本阶段没有策略订单、premium、bar 或收益回测。

## 独立全量终审

- 独立 agent `Locke` 全量终审：数据/代码完整性 `P0=0/P1=0/P2=0`，数字置信度 `99.99%`、语义置信度 `99.5%`。
- 准入裁决：不批准当前 vendor 的全量 premium/liquidity 采集；不批准策略 A/B。
- 只批准一个严格隔离的小型 data-readiness probe，资格池只能来自 123 extracted events，目标仅验证 premium/bid-ask/volume/OI/时间覆盖是否可读，任何策略结论均视为严重选择偏差。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage132_c9_event_option_metadata_batches/rebuilt_c9_v2_stage132_c9_event_option_metadata_batches_report_stage132_c9_event_option_metadata_batches_v1.md`
- terminal ledger：同目录 `*_event_terminal_status_*.csv`
- attempt inventory：同目录 `*_attempt_inventory_*.csv`
- coverage：同目录 `*_coverage_by_year/product/exchange_*.csv`
- event attempts：同目录 `event_attempts/<event_id>/attempt_*/`
- decision/lineage/manifest：同目录对应 json/csv/txt。

## 结论

- 本阶段数据结论：`stage132_metadata_batches_complete_ready_for_coverage_review`，仅指请求账本完整。
- 策略数据结论：`stage132_current_vendor_metadata_coverage_hard_fail_no_full_premium_or_ab`。
- 是否进入下一步：只允许一个小型实际事件 data-readiness probe；不允许全量 premium、不允许保护策略回测。
- 下一步：若继续期权线，只能固定少量 extracted 事件验证真实 premium/流动性可读性；若目标仍是2022整体回撤，应优先更换能覆盖 `fu/jm/FG/SM/hc` 的授权 vendor，而不是在123条子集上制造策略结论。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：数据采集本身否；基于 extracted 子集做策略结论则是高选择偏差风险。
- 原因：365全集和终态规则在返回前冻结，无收益字段和结果删样；但 vendor 可用性与年份/品种强相关。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：当前 vendor 全量策略路线无继续价值；小型 data-readiness probe 有有限价值。
- 原因：它能确认真实事件 premium 数据接口是否可读，但无法用当前覆盖证明2022整体回撤改善或70%收益保留。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，属于重要负向数据准入结论。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`，不追加 `memory.md`。
