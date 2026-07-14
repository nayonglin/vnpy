# 趋势策略期权凸性保护 Tushare 覆盖研究线

- line_id: `futures_trend_option_convexity_tushare_coverage`
- 创建时间: `2026-07-12 22:33 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage001 已完成并以 `CLOSE_LINE_MARKET_STRUCTURE_INELIGIBLE` 关闭；禁止同标的期权收益回测
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 研究目标

- 先验证授权 Tushare 数据能否覆盖当前 C9 冻结的全部真实入场事件，尤其是 2022 回撤窗口与 `fu/jm/FG/SM/hc`。
- 只有覆盖与数据语义通过，后续才允许研究机械、固定预算的反向期权保护层。
- 最终策略目标仍是每个验证起点保留正式 A 至少 `70%` 收益，同时严格降低最大回撤，并缩短 `2022-01`、`2022-07` 起点最长水下期。

## 结构性假设

- 趋势策略的右尾收益与反复止损之间存在不对称；小额固定权利金的反向期权可能保留期货趋势敞口，同时截断跳空和连续不利路径。
- 该机制不是减少期货手数、账户暂停、现金稀释或品种 veto，而是额外购买凸性。
- 当前假设仅有理论资格，没有数据资格。Stage132 已证明原 vendor 只有 `123/365=33.698630%` metadata 覆盖，2022 只有 `11/48`，因此必须先更换数据源并重做全集覆盖门。

## 冻结上游

- 事件全集：Stage131 `365` 个唯一 `contract + entry_date` 事件、`405` 个 closed lots、`19` 个产品。
- 事件区间：`2018-01-15 -> 2026-04-30`；主目标区间仍按 `2020+` 单列，不删除更早事件。
- 冻结 query-events SHA256：`7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- 方向合同：期货 `long -> PUT`、期货 `short -> CALL`。
- 所有 event、空返回、未上市、权限失败和映射失败均保留在分母中。

## Stage001 边界

- 只调用 Tushare 官方 `opt_basic` 与 `opt_daily`，保存原始响应、查询参数、schema、行数、重复键和 SHA256。
- 只判断 underlying 映射、事件日是否存在反向期权、是否存在事件日行情；不选择 strike、到期月、DTE、预算或成交价。
- `opt_daily` 只有日 OHLC/settle/volume/OI，不足以证明盘口可成交；Stage001 即使全绿，也只能允许下一阶段的数据获取预声明，不能允许策略 A/B。
- 任何权限不足、截断、空数据或 schema 漂移必须 fail-close，不能用旧 vendor、插值或合成价格补齐。

## Stage001 硬门

- 冻结输入 hash 一致，`365/365` 事件唯一终态与查询账本完成。
- 2020+ adverse-side metadata event coverage `>=90%`。
- 2020+ entry-date daily quote event coverage `>=90%`。
- `2020-2021`、`2022-2023`、`2024-freeze` 各阶段 quote coverage `>=85%`。
- 2022 全年以及 `2022-03-09 -> 2022-06-29` 核心窗口 quote coverage 均 `>=90%`。
- `fu/jm/FG/SM/hc` 各产品 quote coverage `>=85%`；无上市期权也按结构性不可覆盖计入失败。
- API 返回不得触发单次上限截断；`ts_code + trade_date` 重复键为零，日期、call/put、上市/退市、成交量/OI schema 通过。

## 反过拟合边界

- 不按亏损、年份、产品、方向、账户状态或未来期权收益删事件。
- 不因覆盖不足而降低硬门、换分母、只看已覆盖子集或声称“可用事件效果”。
- 不在 Stage001 扫 strike、DTE、delta、保护比例、再平衡频率或平仓规则。
- 不把日收盘/结算价当作已证明可成交价格；没有 bid/ask 或分钟数据时明确降级。

## Stage001 最终结论

- Tushare SDK 可用且环境变量存在，但服务端返回 `您的token不对，请确认。`；没有下载任何 Tushare 数据，也没有泄露 token。
- 更本质的结构门已失败：`2022-03-09 -> 2022-06-29` 的 `16` 个冻结事件中，当时有同标的期权的只有 `MA 3 + au 1`，理论最大 event 覆盖 `4/16=25%`。
- 理论最大原风险覆盖为 `831,960/3,143,984.2=26.461965%`；`fu/jm/FG/SM/hc` 各自 event 覆盖均为 `0%`。
- `SM/FG/fu/jm` 期权分别晚至 `2023/2024/2025/2026` 才上市；`hc` 到 `2026-04-30` 仍处于期权合约征求意见阶段。换 vendor 不能补出 2022 年不存在的交易工具。
- 输入 SHA 与 Stage131 冻结值一致；本线标准库回归 `2/2` 通过。独立 agent 复算数字一致，最终 review `P0=0/P1=1/P2=4/P3=3`、闭线置信度 `99.9%`。
- P1 是本记录和 registry 未及时闭线，现已修复。P2/P3 不改变偏宽松覆盖上界仍远低于硬门的结论，完整保留在 Stage001 结果日志。
- 该结果只证明同标的期权路线在目标历史窗口不可实施，不证明期权保护本身有效或无效。

## 当前 TODO

- 本线无后续策略实验 TODO；不重试无效 token，不换分母，不下载 covered subset，不跑 option PnL、真引擎或 A/B。
- 保留预声明、结构上界工具、测试、逐事件账本、产品汇总、decision 和独立 review 供查重。
- 若继续凸性研究，必须另开结构不同研究线，先验证跨品种代理的 T-1 基差风险；不能把本线四个可用事件外推到全集。

## 外部资料

- https://tushare.pro/document/2?doc_id=158
- https://tushare.pro/document/2?doc_id=159
- https://tushare.pro/document/1?doc_id=108
- https://www.nber.org/papers/w20439
- https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
