# L1 Top-of-Book 入场质量线

- line_id: `futures_trend_l1_topbook_entry_quality`
- 创建时间: `2026-07-13 01:02 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage001 固定12事件 canary 已完成并关闭；当前 TqSdk 账号统一缺少专业版 `tq_dl` 权限，未形成特征或策略候选
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 研究目标

- 验证 current-C9 每次计划入场的实际合约，在真实交易 session 开盘后60秒内是否能取得可复验的 L1 bid/ask price+size。
- 若数据全覆盖，再研究方向调整后的 queue imbalance/micro-price 是否能识别入场短时 adverse selection，减少开仓日止损与不必要 retry。
- 最终策略门仍要求多锚点收益保留正式 A 至少 `70%`，且最大回撤严格降低、2022水下缩短；Stage001 不读取任何收益或回撤。

## 第一性边界

- 外部研究只支持 top-of-book imbalance/micro-price 对短时价格方向有信息；它不天然解释多日趋势，也不能单独保证组合最大回撤改善。
- TqSdk tick 原始字段包含 `bid/ask_price1..5` 与 `bid/ask_volume1..5`，但本线 Stage001 只把 level1 当作合法字段。
- L1 snapshot 不能重建 order queue、cancel/add flow、排队成交或多档 market impact；不得把本线写成 Stage044 的 MBP10/MBO 替代。
- 若最终候选需要延迟到开盘后读取盘口，必须在真实引擎中按实际延迟价成交，不能继续使用原 daily open。

## 外部调研与判断

- Stoikov micro-price 研究表明 spread 与 best-level imbalance 对短时价格预测有信息，并提供公开 GitHub 实现。
- Cont/Kukanov/Stoikov 的 order-flow imbalance 研究与 queue-imbalance 文献支持 best bid/ask 对下一价格变化的短时解释。
- hftbacktest 的公开实现强调 L2/L3、snapshot、queue 与 latency；因此本线禁止用 L1 做 queue-position 或深度成交假设。
- TqSdk 官方 `get_tick_data_series` 提供精确时间段 tick，专业版限定；`get_tick_serial` 单序列最大10000条。本地 `tqsdk=3.9.4` 支持前者。
- 我的判断：这条路线与日线AI、OI、账户状态和仓位缩放不同，但作用尺度很短。它只值得先做覆盖 canary，不能在数据通过前讨论收益。

## Stage001 固定 canary

- 事件源：Stage131 冻结 `365` 个 current-C9 query events，SHA 必须匹配。
- 交易日源：Stage847 curve 中 `2,037` 个唯一 global trade dates，SHA 必须匹配。
- session 分类：沿用已审计 Stage501 的固定 `NIGHT_SESSION_PRODUCTS`；不根据查询结果猜夜盘。
- 分层：`exchange × has_night_session`。每层机械选择 entry_date 最早和最晚事件，去重后固定 `12` 条。
- 固定层：CZCE day/night、DCE day/night、GFEX day、SHFE night；当前 C9 没有 SHFE day、GFEX night 或 INE 事件，不制造空层。
- 夜盘窗口：entry date 前一个 global trade date `20:59:00 -> 21:05:00`。
- 日盘窗口：entry date `08:59:00 -> 09:05:00`。
- 接口：每条事件独立 `TqApi(TqSim, TqAuth)` 调用 `get_tick_data_series(actual tqsdk_underlying, start_dt, end_dt)`；不创建交易任务、不调用订单API。
- 原始 DataFrame 先原样落盘并 hash，再做 normalized/audit；凭据值不得落盘或出现在异常文本。

## Stage001 硬门

- canary 身份 `12/12`、分层 earliest/latest 全匹配；Stage131/curve SHA 与行数匹配。
- 每事件接口终态唯一，authentication/permission/empty/timeout/error 全部留在12分母。
- raw 必须包含 datetime、symbol、bid/ask_price1、bid/ask_volume1、last_price、volume、open_interest；symbol 只能是请求实际合约。
- integer ns 时间无 float64 精度往返；normalized 时间全部在请求窗口内，无重复 `(datetime,id,symbol)`。
- entry session 开盘后 `60` 秒内至少1条合法双边 L1：bid/ask price正且有限、ask>=bid、bid/ask size非负有限。
- 累计 volume 不回退；crossed spread、负 size、无穷值均为0。
- 12条全部通过才允许 `ALLOW_STAGE002_FULL_EVENT_ACQUISITION_PREDECL_ONLY`；否则 `CLOSE_LINE_L1_TICK_COVERAGE_INELIGIBLE`。
- 两种结果都保持 `ready_for_feature=false`、`ready_for_backtest=false`、`ready_for_live=false`。

## Stage001 结果

- 冻结 Stage131 `365` 事件/SHA 与 Stage847 `2,037` 个 global trade dates/SHA 均匹配；6层最早/最晚事件身份 `12/12` 匹配。
- 真实 run `20260713T011519+0800` 的12个唯一 attempt 全部返回 TqSdk 原生专业版权限提示，终态 `authentication_or_permission_failed=12/12`，extracted `0/12`，决策 `CLOSE_LINE_L1_TICK_COVERAGE_INELIGIBLE`。
- TqSdk `3.9.4` 本地源码在合约校验和 DataSeries 请求之前先检查 `_auth._has_feature("tq_dl")`；因此失败原因是当前账号权限，不是品种、年份、窗口、纳秒或统计逻辑。
- 专属 `unittest 7/7`、py_compile、12份 attempt/root manifest 与递归凭据扫描均通过；凭据命中0、总交易0、无回测、无订单/CTP/邮件/live修改。
- 独立 agent 终审 `P0/P1/P2/P3=0/0/3/1`，权限归因与机械闭线置信度均99%。三个P2和一个P3均不影响本次闭线，详见 `stages/20260713_0123_stage001_l1_tick_canary_closed.md`。

## 反过拟合边界

- 不换 canary，不只保留成功交易所/年份，不放宽60秒，不把夜盘失败改查日盘，也不反向。
- 不扫描 imbalance 阈值、聚合秒数、盘口档数、产品、方向、年份或亏损窗口。
- Stage001 不读取 event 后 markout、MAE、stop/retry、PnL、权益或回撤。
- 如果 canary 失败，不用分钟线、last price 或 option tick 代替实际 futures L1。

## 当前 TODO

1. 本线关闭，不进入 Stage002、全365事件采集、L1特征、markout、收益 proxy、真引擎或A/B。
2. 禁止换事件、换普通 tick serial、改窗口、放宽60秒、按成功交易所/年份取子集，或用分钟/last-price/option tick 代替实际 futures L1。
3. 只有未来获得合法 TqSdk 专业版权限，才允许原12事件、原窗口、原硬门不变地新增不可覆盖 attempt 复验。

## 外部资料

- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694
- https://github.com/sstoikov/microprice
- https://arxiv.org/abs/1011.6402
- https://arxiv.org/abs/1512.03492
- https://github.com/nkaz001/hftbacktest
- https://github.com/nkaz001/hftbacktest/blob/master/examples/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.ipynb
- https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html
