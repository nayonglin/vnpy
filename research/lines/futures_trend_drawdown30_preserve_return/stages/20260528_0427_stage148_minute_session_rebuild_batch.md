# Stage148 分钟会话执行重建扩展批次

- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 时间：2026-05-28 04:27 CST
- 阶段性质：执行口径重建，不是新策略，不是参数优化。
- 是否重要突破：是。Stage147 的前5合约错位证据扩展到全部高优先级合约后仍成立，说明日线成交代理错位不是偶发样本问题。
- 是否触发 A/B：否。本阶段不判断 A/C 策略优劣，只校准执行价格口径。

## 本阶段判断

我没有继续按 3个月/6个月体验去调 Stage079 或 Stage103，因为在执行价格口径未重建前，继续优化同日收盘曲线会把研究带向过拟合。当前更值得晋级的不是某个新 alpha 版本，而是“分钟会话执行 ledger 重建”这条工程审计路径。

## 外部调研与判断

- TqSdk 官方文档支持使用 `TqBacktest + get_kline_serial(..., duration_seconds=60)` 在历史回放中取得分钟K，因此可以绕开本地 vn.py 没有分钟线的问题。
- `DataDownloader(dur_sec=60)` 属于专业历史下载路径；Stage145 已确认本地账号没有该权限，所以本阶段不再依赖它。
- xtquant 官方文档显示历史行情下载依赖 MiniQMT 环境；本地导入 xtdata 曾失败，因此本阶段不使用 QMT 分钟数据作为主路径。
- 调研结论：TqBacktest 是当前最现实的数据补洞路线，但只能先用于执行代理重建，不能直接证明策略收益。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage448_minute_session_rebuild_batch.py`
- 修改正式策略：无。
- 修改 Stage079/C3/Stage103 交易规则：无。
- 新增参数：
  - `STAGE448_TARGET_SCOPE=high`
  - `STAGE448_MAX_SYMBOLS=35`
  - `STAGE448_SYMBOL_OFFSET=0`
  - `STAGE448_MAX_SECONDS_PER_SYMBOL=150`
  - `STAGE448_FORCE_REFRESH=0`
  - `14:55` 同日最后5分钟、`21:00` 夜盘开盘5分钟、`09:00` 日盘开盘5分钟作为可观测执行代理窗口。
- 修改参数：窗口收益、策略规则、资金参数均未修改。
- 删除参数：无。

## 回测参数与结果

本阶段不是策略回测，不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。Stage079 仍保留为当前 baseline，Stage103 仍只保留为同日收盘口径研究候选，真实 paper/影子盘晋级暂停。

为了满足总账字段一致性，本阶段字段记录如下：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：`45` 笔高优先级账本交易被接回分钟代理明细；不是策略总交易次数。
- 胜率：不适用。

## 新增执行审计结果

- 目标范围：Stage443 高优先级执行代理窗口。
- 选中合约数：`35`
- 成功/缓存合约数：`35`
- 失败/超时/空合约数：`0`
- 抽取分钟K数量：`50,781`
- 目标窗口：`197`
- 覆盖窗口：`111`
- 覆盖率：`56.3452%`
- 已接回账本交易数：`45`
- 有效日线 same close 交易数：`44`
- 无效 same close 数量：`1`
- 有效日线 next_open 交易数：`42`
- 无效 next_open 数量：`0`
- `14:55` 代理价相对日线 same close 大错位：`38/44 = 86.3636%`
- 真实开盘代理价相对日线 next_open 大错位：`36/42 = 85.7143%`
- 最大价差：
  - 原始 `14:55 vs same close`：`73,212.0000`
  - 剔除无效日线价后的 `14:55 vs same close`：`4,008.0000`
  - `real open vs daily next_open`：`6,000.0000`
  - 剔除无效日线价后仍为：`6,000.0000`
- 已接回样本真实开盘相对同日收盘现金差估计：`107,877,429.00`

## 关键解释

- 原始最大 `73,212` 来自 `lc2505.GFEX` 的日线 same close 为 `0`，这是无效日线价格，不能作为真实错位强度解释。
- 即使剔除无效日线价，错位仍非常大：有效价格最大 `14:55 vs same close` 价差为 `4,008`，真实开盘代理相对 daily next_open 最大价差为 `6,000`。
- 35个高优先级合约全部成功或缓存命中，且错位率仍在 `85%+`，说明问题不是 TqBacktest 前5合约偶然抽样，也不是单合约异常。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage448_minute_session_rebuild_batch_report_stage448_minute_session_rebuild_batch_v1.md`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage448_minute_session_rebuild_batch_decision_stage448_minute_session_rebuild_batch_v1.json`
- 明细 ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage448_minute_session_rebuild_batch_ledger_proxy_detail_stage448_minute_session_rebuild_batch_v1.csv`
- 分钟K汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage448_minute_session_rebuild_batch_minute_bars_stage448_minute_session_rebuild_batch_v1.csv`

## 决策

- 决策标签：`session_proxy_mismatch_confirmed_extend_full_rebuild`
- 结论：Stage079 仍是当前正常成本 baseline，但不能只用日线同日收盘口径继续宣称 Stage103 或后续候选可真实 paper/影子盘晋级。
- 晋级判断：值得晋级的是“全量分钟会话执行 ledger 重建”，不是新策略参数。
- 下一步：用同一脚本或新 Stage 扩展到全量 Stage443 订单，目标是覆盖约 `228` 个合约、`757` 笔订单、`3,561` 个代理窗口；完成后重算 Stage079、Stage103 和所有后续候选的 3个月/6个月体验。

## 过拟合与继续价值反思

- 运行前过拟合反思：否。只校准执行价格，不修改策略规则、不筛坏日期、不筛坏品种。
- 运行后过拟合反思：否。错位结果只用于否决错误成交代理，不用于构造过滤条件或收益补丁。
- 运行前继续价值反思：是。Stage147 已暴露同日收盘和 T+1 日线 open 都可能不是真实执行口径。
- 运行后继续价值反思：是，而且优先级上升。高优先级35合约全部可抽取且错位系统性存在，继续全量重建比继续调 3个月/6个月曲线更有价值。
