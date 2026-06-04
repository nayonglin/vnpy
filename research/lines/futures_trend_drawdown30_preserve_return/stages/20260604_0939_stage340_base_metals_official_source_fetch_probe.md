# Stage340 base_metals 官方源 active fetch 探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 09:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`base_metals` 官方源 source contract/fetch probe；阶段级输出，不追加 master
- 是否重要突破：否；source 证据有进展，但当前 payload 日更和 WAF 仍未闭合
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - LME stock movement report：`https://www.lme.com/market-data/reports-and-data/warehouse-and-stocks-reports/stocks-summary/stock-movement-report`
  - LME historical warehouse stock movements PDF：`https://www.lme.com/-/media/files/data/accessing-market-data/historical-data/lme-warehouse--stock-movements.pdf`
  - LME market data services agreement：`https://datalicensing.lme.com/LinkClick.aspx?fileticket=UFrs0Huks4Y%3D&portalid=0`
  - SHFE Daily Data：`https://www.shfe.cn/eng/reports/StatisticalData/DailyData/`
  - SHFE dailystock UI：`https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock`
  - GitHub 搜索：`LME warehouse stocks Python fetch`、`SHFE daily data Python warehouse stocks futures`
- 我的判断：
  - LME 官方材料清楚说明库存报告的发布时间、计量单位、on/cancelled warrant 和 warehouse location/grade 语义；但完整日度数据更接近 licensed distributor/OLP/登录授权路径，不适合直接当成免费自动化 selector 源。
  - SHFE Daily Data 更贴近国内期货合约和仓单，但脚本直接访问中文仓单 UI/current stockdata 会遇到 WAF 或端点变化。
  - GitHub/开源路线没有发现能替代官方授权、稳定日更并可实盘留痕的成熟方案；因此第三方或开源 wrapper 最多做辅助 monitor，不能直接升级成 selector。
  - 本阶段只验证 source 可达性、raw hash、PIT 纪律和字段结构，不允许接入历史 selector。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage640_base_metals_official_source_fetch_probe.py`
- 修改脚本：同一脚本内修正 `route_id` 字段遗漏和图表语义；最终图表将 `WAF-like` 作为红色阻塞显示
- 删除脚本：无
- 新增参数：
  - `PROBE_DATE=20260603`
  - `LEGACY_SHFE_DATE=20200702`
  - `MIN_RESPONSE_BYTES=500`
  - `REQUIRED_PIT_DATES_FOR_SELECTOR=20`
  - 探针目标：`7` 条 LME/SHFE 官方路线
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增策略回测；只抓取 `2026-06-04 09:39 CST` 当时可见官方源
- 账户规模：不适用
- 成本口径：不适用
- 策略/归因口径：
  - 不重放策略、不改交易规则、不扫参数
  - 不追加 master PIT ledger
  - 不生成 selector/paper/交易白名单
  - 不连接 CTP、不调用订单 API

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`base_metals_official_payload_probe_partial_selector_locked`
  - fetch rows：`7`
  - source authorities：`2`
  - active page fetch validated rows：`3`
  - payload data validated rows：`1`
  - raw hash rows：`7`
  - WAF-like rows：`2`
  - PIT dates now：`1`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`8/9`

## 路线结果

| route | 结果 | 解释 |
| --- | --- | --- |
| `lme_stock_movement_page` | HTTP `403`，有 hash，无 page/payload validated | LME 当前页面需要 JS/cookie 或访问控制，不能自动日更 |
| `lme_historical_stock_movements_pdf` | HTTP `200`，page validated | 方法论和发布时间语义可留痕，但不是交易 payload |
| `shfe_daily_data_english_page` | HTTP `200`，page validated | 可抓取 SHFE Daily Data 英文页，包含 Daily Warrant/Ranking/Warehouse 关键词 |
| `shfe_dailystock_ui` | HTTP `200` 但 WAF-like | 中文仓单 UI 不能直接脚本自动化 |
| `shfe_current_dailystock_dat` | HTTP `404` | 当前 DAT 路径不成立或端点变化 |
| `shfe_current_stockdata_html` | HTTP `200` 但 WAF-like | 当前 stockdata HTML 路线被 WAF 阻断 |
| `shfe_legacy_dailystock_dat_known_ok` | HTTP `200`，payload validated | 历史 DAT 能解析 `铜/铝` 等仓单字段，证明字段结构存在，但不是当前日更 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_report_stage640_base_metals_official_source_fetch_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_decision_stage640_base_metals_official_source_fetch_probe_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_fetch_ledger_stage640_base_metals_official_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_route_status_stage640_base_metals_official_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_source_readiness_stage640_base_metals_official_source_fetch_probe_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_gates_stage640_base_metals_official_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage640_base_metals_official_source_fetch_probe_chart_stage640_base_metals_official_source_fetch_probe_v1.png`

## 图表视觉复盘

- 左上图：
  - 所有 `7` 条路线均有 raw hash，说明外部网络重跑后页面/错误页/JSON 均能留痕。
  - `lme_historical_stock_movements_pdf`、`shfe_daily_data_english_page`、`shfe_legacy_dailystock_dat_known_ok` 通过 page 层。
  - 只有 `shfe_legacy_dailystock_dat_known_ok` 通过 payload 层，且它是历史日期参考，不是当前日更。
  - `shfe_dailystock_ui` 和 `shfe_current_stockdata_html` 的 no-WAF 为 `0`，说明直接脚本访问会被 WAF 阻断。
- 右上图：
  - SHFE 有 `2` 个 page ok、`1` 个 payload ok，同时有 `2` 个 WAF-like。
  - LME 只有 `1` 个 page ok，payload ok 为 `0`；LME 当前 stock movement 页面 HTTP `403`，但方法论 PDF 可抓。
- 左下图：
  - 两类官方源 PIT 日期都只有 `1`，远低于 `20` 日 selector 门槛。
  - history selector 和 paper/whitelist 均为 `0`，锁定纪律正确。
- 右下图：
  - 唯一红色硬失败是 `waf_like_rows_zero=FAIL 2`。
  - 绿色闸门中 `pit_dates_below_selector_threshold`、`selector_rows_zero`、`paper_whitelist_zero` 是 fail-closed discipline，不代表晋级。

## 结论

- 本阶段结论：
  - `base_metals` 是值得保留的 source-first 方向，但当前只能算“部分 source probe 成功”，不能作为新风险槽或 selector。
  - SHFE 历史仓单 DAT 能解析出铜/铝等 payload，证明字段结构可用；但当前日更端点不是 `20260603dailystock.dat`，而 current stockdata HTML 和中文 UI 被 WAF 阻断。
  - LME 官方源语义强，但当前 stock movement 页面脚本访问为 HTTP `403`，完整日度 payload 很可能需要登录/授权/数据分发商。
  - 因此 `base_metals` 不能晋级 paper、A/B 或交易白名单。
- 是否进入下一步：继续，但下一步必须是 route forensic，不是收益回测。
- 下一步：
  - 优先做 SHFE 当前仓单 WAF/端点取证：尝试浏览器/CDP session、cookie replay 或查找官方可下载端点。
  - LME 分支只保留为方法论/source contract；若要用完整日度库存，必须确认 OLP/licensed data distributor 的成本和自动化合同。
  - 未解决当前 payload 日更和 `20` 个 PIT 日期前，继续禁止 selector。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有看收益、没有调参数、没有改变交易规则，也没有把任何 source 接入 selector。
  - 输出保留了 WAF/403/404 失败证据，没有为了晋级而把 page hash 误写成可用 payload。
  - SHFE 历史 payload 只用于证明字段结构，不用于回填历史 alpha。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但必须继续 source 工程，不应直接回测。
- 原因：
  - `base_metals` 年度机会和相关性处在可研究区，官方源也能部分抓取。
  - 真正缺口是当前日更 payload、WAF/登录授权和 PIT 样本深度。
  - 如果 SHFE 当前仓单端点可闭合，`base_metals` 才有资格进入 master PIT append gate 和 outcome/TCA 审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage340 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
