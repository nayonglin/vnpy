# Stage295 P0官方endpoint discovery审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 02:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方外生数据 endpoint 定位与自动化访问边界审计；不做收益回测，不修改策略，不生成交易候选。
- 是否重要突破：否。它是执行边界证据，不是 alpha 或候选版本突破。
- 是否触发A/B：否。没有形成可接正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AKShare 本地源码 `.py311/lib/python3.11/site-packages/akshare/futures/futures_warehouse_receipt.py`：定位 DCE `wbillWeeklyQuotes` 与 SHFE legacy `dailystock.dat` 路径。
  - AKShare 本地源码 `.py311/lib/python3.11/site-packages/akshare/futures/receipt.py`：定位 SHFE 新版 `stockdata/dailystock_{date}/ZH/all.html` 路径。
  - AKShare 本地源码 `.py311/lib/python3.11/site-packages/akshare/futures/futures_settle.py`、`futures_daily_bar.py`：定位 INE `js{date}.dat` 与 `kx{date}.dat` 交易/结算上下文路径。
  - INE 官方页面探测：`https://www.ine.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock` 与 `?query_params=weeklystock`。
- 我的判断：
  - 官方入口已经不是“找不到”，而是“自动化使用还没打通”。`v.DCE` 卡在 DCE `412`，`ao.SHFE` 卡在新版 stockdata WAF 和 legacy 当前日期 `404`，`lu.INE` 可访问 `kx/js` 但它们不是库存/仓单/周库存路线。
  - Stage294 的第三方库存和基差可以继续做 forward monitor 辅助，但不能升级成官方 alpha 证据，也不能用于历史 selector 回填。
  - 若后续继续基本面/舆情方向，下一步必须解决 cookie/WAF/412、官方授权接口或合规 vendor snapshot；否则只能做观察账本，不能做可交易选品。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage595_p0_official_endpoint_discovery.py`
- 修改脚本：无策略脚本修改；本阶段脚本内修正过 JSON 解析，改为从完整 `raw_text` 解析，避免截断文本导致假阴性。
- 删除脚本：无。
- 新增参数：
  - `PROBE_DATE=20260603`
  - `LEGACY_SHFE_DATE=20200702`
  - `HTTP_TIMEOUT_SECONDS=12`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用。本阶段只做 `2026-06-03` 当前日期 endpoint 探测，并用 `2020-07-02` 验证 SHFE legacy DAT 历史可解析性。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：只探测 Stage292/294 明确的 P0 缺口产品 `v.DCE`、`ao.SHFE`、`lu.INE`。
- 策略/归因口径：官方 endpoint discovery；`usable_for_history_selector=0`，禁止将发现结果直接当历史 alpha。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p0_official_endpoints_located_access_or_parser_blocked`
  - endpoint rows：`11`
  - hard gates：`2/7`
  - products with official page or endpoint：`3/3`
  - products with current parsed product data：`1/3`
  - products with official auto monitor ready：`0/3`
  - WAF/412 rows：`6`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`

## 产品级判断

- `v.DCE`：官方仓单 JSON API `http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes` 已定位，但自动 POST 返回 `412`；官方页面连接也不稳定。结论是入口明确、访问阻塞。
- `ao.SHFE`：legacy `20260603dailystock.dat` 当前日期 `404`，legacy `20200702dailystock.dat` 可解析但没有氧化铝且不是 forward；新版 stockdata HTML 和官方 UI 均返回 WAF。结论是路径明确、当前监控不可用。
- `lu.INE`：官方 `dailystock/weeklystock` UI 参数已定位；`kx20260603.dat` 与 `js20260603.dat` 可解析并匹配 `lu`，但只是交易/结算上下文，不是库存/仓单/事件路线。结论是有上下文数据，缺 exact monitor route。

## 图表视觉复盘

- 左上 readiness heatmap 显示三个产品的 `located` 全绿，但 `monitor` 全红；这说明问题不是研究方向没源，而是自动化监控没有闭环。
- 右上 route counts 显示 `lu.INE` endpoint 数最多且 access ok 为 `2`，但左上只有 `matched=1`、`monitor=0`，视觉上提醒不能把“能访问日行情/结算”误读成“库存/仓单 alpha 可用”。
- 左下 probe status 中 `ao.SHFE` 和 `lu.INE` 的紫色 WAF 明显集中，`v.DCE` 则同时有 error 和 `412`；这支持下一步分成 cookie/WAF flow 与 vendor snapshot 两条路线。
- 右下 hard gates 只有 `located` 和 `history zero` 为绿，其余全空/红，确认 Stage295 不能晋级为 paper selector 或交易白名单。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_report_stage595_p0_official_endpoint_discovery_v1.md`
- endpoint discovery：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_endpoint_discovery_stage595_p0_official_endpoint_discovery_v1.csv`
- product readiness：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_product_readiness_stage595_p0_official_endpoint_discovery_v1.csv`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_gates_stage595_p0_official_endpoint_discovery_v1.csv`
- next actions：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_next_actions_stage595_p0_official_endpoint_discovery_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_decision_stage595_p0_official_endpoint_discovery_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage595_p0_official_endpoint_discovery_chart_stage595_p0_official_endpoint_discovery_v1.png`

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage595_p0_official_endpoint_discovery.py`：通过。
- `python -m json.tool ...decision_stage595_p0_official_endpoint_discovery_v1.json`：通过。
- 输出文件存在：通过。
- 图表视觉检查：通过，四个面板可读且与决策一致。

## 结论

- 本阶段结论：P0 缺口产品的官方入口已经定位，但当前自动化访问或解析仍未满足实盘 selector 要求。`official_auto_monitor_ready=0/3`，所以不能晋级 paper selector、交易白名单或历史回测 alpha。
- 是否进入下一步：是，但只能进入源接入/账本工程，不进入收益回测。
- 下一步：
  - `v.DCE`：解决 DCE `412` 或改用合规 vendor snapshot。
  - `ao.SHFE`：解决 SHFE stockdata WAF 或 browser-cookie flow。
  - `lu.INE`：打通 INE `dailystock/weeklystock` 的 exact 数据路线，不能用 `kx/js` 替代库存/仓单。
  - 全部数据源必须写 `received_at/source_url/published_at/raw_hash`，并累计至少 `20` 个 received_at 日期后再做预测力审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做官方 endpoint 定位与访问状态审计，没有选择收益窗口、没有调策略参数、没有生成产品白名单，也明确禁止 `usable_for_history_selector`。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但应收缩到工程打通和 forward collection。
- 原因：Stage295 把“官方源缺口”从模糊问题变成了三个可执行 blocker：DCE `412`、SHFE WAF、INE exact route 未解析。只要这些没有解决，基本面/舆情方向不能用来承诺实盘无偏差；解决后才值得做 selector 预测力审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与下一步。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
