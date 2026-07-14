# Stage001 Tushare 期权事件覆盖审计预声明

- line_id：`futures_trend_option_convexity_tushare_coverage`
- 当前模式：`day`
- 预声明时间：`2026-07-12 22:33 CST`
- 阶段性质：数据权限、完整性与覆盖审计；不是策略回测
- 是否重要突破：待定
- 是否触发 A/B：否；本阶段无收益字段和交易动作

## 冻结问题

Tushare `opt_basic + opt_daily` 能否在不删样、不插值、不使用未来信息的前提下，为 Stage131 全部真实入场事件提供与期货方向相反的期权 metadata 和事件日真实日行情，尤其覆盖 2022 核心回撤窗口及 `fu/jm/FG/SM/hc`？

## 冻结输入

- query events：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage131_c9_event_targeted_option_acquisition_manifest/rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_query_events_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv`
- 预期 SHA256：`7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- 预期行数/唯一事件：`365/365`；预期产品 `19`；事件日期 `2018-01-15 -> 2026-04-30`。
- Stage132/133 只作为旧 vendor 反证，不作为 Tushare 缺失值回填源。

## 查询合同

- metadata：Tushare `opt_basic`，字段至少包含 `ts_code,symbol,exchange,name,opt_code,call_put,exercise_price,s_month,maturity_date,list_date,delist_date,multiplier`。
- daily：Tushare `opt_daily`，字段至少包含 `ts_code,trade_date,pre_settle,pre_close,open,high,low,close,settle,vol,amount,oi`。
- 交易所覆盖：从 Stage131 事件实际交易所反推；每个 API 请求保存 endpoint、非敏感参数、时间、返回 schema、原始行数、去重行数、响应 hash 和终态。
- token 只从环境读取，禁止写入日志、命令输出、manifest 或 stage 文件。
- 必须证明未触发单次行数上限；若无法分页，则改为 event/underlying/date 分批查询，不接受截断全集。

## 映射合同

- Stage131 `tqsdk_underlying` 是冻结期货实际合约；不得只按产品名把任意期权链视为同一标的。
- 使用 `opt_basic.opt_code`、合约月份、交易所与 metadata 日期共同建立映射；字符串规则只能生成候选，最终必须由 metadata 字段闭合。
- 事件日有效条件：`list_date <= entry_date <= delist_date/maturity_date`，且方向满足 `long -> P/PUT`、`short -> C/CALL`。
- daily 可用条件：同一 `ts_code` 在 `entry_date` 有唯一行情行，OHLC/settle 至少存在一个可审计 premium 字段；`vol/oi` 缺失单列，不伪造为零。
- 未上市、当日休市、无反向合约、无日线、权限失败、schema 错误、映射歧义、API 空返回均是不同终态，但全部留在覆盖分母。

## 冻结统计口径

- event 是唯一 `event_id`，同一事件可有多个候选期权，但覆盖率分子最多记 `1`。
- metadata event coverage：事件日存在至少一个映射闭合且方向相反的有效期权。
- quote event coverage：上述有效期权中至少一个在事件日存在唯一 `opt_daily` 行。
- 2020+、自然年、三阶段、交易所、产品、方向、2022 全年与核心窗口全部从同一 365 行账本聚合。
- 旧 vendor、未来日期补发、上一交易日行情和下一交易日行情不得计入 entry-date quote coverage。

## 冻结硬门

1. 输入 hash、行数、唯一键和日期边界全部一致；每个事件唯一终态，request ledger `365/365`。
2. 2020+ metadata event coverage `>=90%`。
3. 2020+ entry-date quote event coverage `>=90%`。
4. `2020-2021`、`2022-2023`、`2024-freeze` quote coverage 各 `>=85%`。
5. 2022 全年及 `2022-03-09 -> 2022-06-29` 核心窗口 quote coverage 各 `>=90%`。
6. `fu/jm/FG/SM/hc` 每个产品 quote coverage `>=85%`。
7. `ts_code + trade_date` 重复键为零；未解释的 API 截断、schema 漂移、日期越界、call/put 冲突和 mapping ambiguity 均为零。

## 机械决策

- 任一硬门失败：`CLOSE_LINE_DATA_INELIGIBLE`，禁止 option PnL、真引擎或 A/B。
- 全部硬门通过：`ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`；仍然 `ready_for_option_strategy_ab=false`，因为日线不证明开仓时点 bid/ask、滑点与分钟可成交性。
- 不允许依据失败分布修改阈值、删除产品/年份、改用最近交易日或只回测 covered subset。

## 计划产物

- `request_ledger.csv`：所有 API 请求与唯一终态。
- `raw_manifest.csv`：原始缓存文件、行数、schema 和 SHA256。
- `option_basic_normalized.csv`、`option_daily_normalized.csv`：标准化去重数据。
- `event_coverage_ledger.csv`：365 事件逐行映射、方向、有效期权数、日线数和终态。
- `coverage_summaries.csv`：全体/时期/年份/交易所/产品/方向统计。
- `gate_matrix.csv`、`decision.json`、`lineage.json`、`report.md`。

## 参数与结果占位

- 新增参数：上述冻结覆盖门。
- 修改参数：无。
- 删除参数：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A（本阶段不回测）。

## 过拟合反思

- 运行前判断：否。
- 原因：365 事件全集、分母、关键窗口和覆盖门均在首次 API 返回前冻结；不读取任何策略盈亏。

## 继续价值反思

- 运行前判断：有，但只允许一次完整覆盖审计。
- 原因：它直接检验当前唯一未被数据缺口否决的结构性路线；失败后继续换阈值或删样没有价值。

