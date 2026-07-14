# Stage002 FU-SC ATM 代理期权执行数据资格预声明

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 当前模式：`day`
- 预声明时间：`2026-07-12 23:39 CST`
- 阶段性质：metadata语义修复、固定选券、entry-day可成交性与整数粒度；不是收益回测
- 是否重要突破：待定
- 是否触发 A/B：否
- 当前授权边界：仅预声明；真实 premium/bar/tick 下载须先通过独立 review

## 冻结问题

对 Stage001 已通过 basis 与历史链的全部32个 FU 事件，使用严格 T-1 的单一 ATM adverse-side SC 期权，是否具备足够的事件日行情、双边报价、成交/OI 与整数 money-delta 粒度，值得进入后续固定保护层设计？

## 强制前置修复

- Stage001 chain reviewer P2：cache validator 只验证 hash/identity/行数，未重算 metadata 语义。
- Stage002 必须逐事件重新读取 `untouched_metadata.csv`，调用冻结 Stage132 `normalize_option_metadata/audit_extracted_metadata/compare_normalized_metadata`。
- `32/32` 必须 raw->normalized 零差异、underlying/class/strike/expiry/expired/multiplier/tick 全通过；否则 `CLOSE_LINE_METADATA_SEMANTICS_INVALID`，不得联网取价格。

## 固定选券合同

- 事件全集：Stage001 query plan 全部 `32`，核心仍为 `2022-03-09 -> 2022-06-29` 的 `6` 条。
- FU `long -> PUT`，FU `short -> CALL`；Stage001 三窗 beta 全为正，不反转方向。
- SC reference：entry date 对应 T-1 OI 所选 SC 实际合约的 `prior_close`，即 selection date 已知 close；禁止 entry-day SC price。
- metadata 必须是同一 `requested_underlying`、未过期、expiry严格晚于entry date、正确 CALL/PUT。
- 选择 `abs(strike - sc_t1_close)` 最小的 ATM；并列固定按 strike 升序、option_symbol 升序。
- 不选择 DTE：所选 SC underlying 的 metadata 只有一个 expiry；禁止跨 underlying/月择期。

## Entry-day 数据合同

- 每事件历史上下文：`entry_date-1 20:00 -> entry_date 16:00`，覆盖夜盘与日盘。
- 固定调用：SC underlying 60秒K、所选 option 60秒K、所选 option tick；不请求 FU 价格、不请求持有期或退出日数据。
- entry-day readiness 只证明同交易日有可成交市场，不把 earliest ask 直接当策略成交价，也不计算 option PnL。
- 必须保存 untouched serial、session-normalized数据、审计、请求、source hash 与原子 manifest。

## 固定流动性门

- underlying minute 与 option minute session rows 均 `>0`，OHLC finite/positive、重复和负volume/OI为0。
- option 至少一个 finite/positive/non-crossed 双边 tick，bid/ask volume 非负。
- earliest valid two-sided quote 的 `(ask-bid)/mid <= 10%`。
- option 至少有一个正 minute volume，或 tick cumulative volume 在session内正增长。
- option minute/tick OI 至少一个 finite positive observation。

## 固定整数粒度门

- FU money exposure：`FU total_volume * 10 * FU weighted entry_price`。
- SC ATM money-delta proxy：`1000 * SC T-1 close * 0.5`；`0.5` 只作为 ATM 粗粒度，不称真实delta。
- event full126 beta 沿用 Stage001，不重估。
- `ideal_option_lots = FU money exposure * beta / SC ATM money-delta proxy`。
- 要求 `ideal_option_lots >= 2.0`，这样 nearest-integer 最大理论取整误差不超过25%；不允许 min1 强行过度对冲。
- Stage002 不根据 premium 预算决定手数，也不实际下单。

## 顺序与硬门

1. metadata semantic revalidation `32/32`。
2. 固定 ATM adverse-side selection `32/32`，无T-1/underlying/class/expiry冲突。
3. 独立 agent review Stage002 预声明、preflight与测试；任何 P1 修复后原口径重跑。
4. 只有1-3通过，才允许核心6条真实 entry-day data canary。
5. 核心 execution/liquidity/granularity pass `6/6`，才允许剩余26条。
6. 全体完整请求 `32/32`，execution/liquidity/granularity pass rate `>=90%`。

## 机械决策

- metadata失败：`CLOSE_LINE_METADATA_SEMANTICS_INVALID`。
- selection失败：`CLOSE_LINE_SELECTION_INELIGIBLE`。
- 核心或全体执行门失败：`CLOSE_LINE_EXECUTION_DATA_INELIGIBLE`。
- 全部通过：`ALLOW_STAGE003_FIXED_HEDGE_SPEC_PREDECL_ONLY`。
- 任意结果下 `ready_for_option_strategy_ab=false`、`ready_for_live=false`；Stage003也必须另预声明。

## 禁止事项

- 不改 ATM 为 OTM/ITM，不扫 strike、DTE、delta、spread阈值、等待分钟或预算。
- 不按2022盈利/亏损、方向、月份或单事件删样。
- 不用 last/settle/close 替代 ask 声称成交。
- 不获取持有期/退出价格，不计算保护收益、回撤或收益保留。
- 不修改正式C9、AI池、止损重试、实盘或shadow。

## 回测结果占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A。

## 过拟合反思

- 运行前判断：否，但阈值若结果后修改会成为过拟合。
- 原因：事件全集、选券、0.5 delta proxy、2手和10%spread均在首次价格读取前冻结。

## 继续价值反思

- 运行前判断：有，仅限一次真实执行数据门。
- 原因：链存在不足以证明可以买到；价差、活跃度和整数粒度可能直接否决整个路线。

## 外部依据

- https://www.ine.cn/products/option/
- https://www.ine.cn/upload/20210617/1623896844158.pdf
- https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
- https://doi.org/10.1002/fut.1801

