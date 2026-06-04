# Stage325 公开源 Raw-Text 抓取探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读公开源联网抓取探针；不追加 master ledger、不新增收益回测、不改策略规则、不生成 paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否，但把 Stage324 的 source catalog 推进到部分公开源 raw-text/hash 可自动抓取。
- 是否触发A/B：否。没有形成可接入正式版本的新策略或新风险预算。

## 外部调研与判断

- 参考资料：
  - ESMIS Crop Progress release page：https://esmis.nal.usda.gov/publication/crop-progress/2026-06-01
  - NASS Crop Progress methodology：https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Crop_Progress_and_Condition/index.php
  - SHFE Daily Data：https://www.shfe.cn/eng/reports/StatisticalData/DailyData/
  - ESMIS WASDE corrected release page：https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates/2026-05-12-0
  - CZCE reference data：https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm
- 我的判断：
  - `ag/CY/SR` 的公开源至少能形成自动抓取 + `received_at` + raw hash 的 forward monitor 证据。
  - ESMIS 页面可以自动发现并抓取 `prog2226.txt`、`wasde0526v2.txt`，这比只记录网页目录更接近实盘可执行数据链。
  - CZCE 静态参考页在当前脚本下仍返回 `412 Precondition Failed`；旧 USDA WASDE latest text 返回 `403 Forbidden`，不能假设这些 URL 稳定可抓。
  - 成功抓取公开源仍不是 alpha；必须继续保持 `history_selector=0`、`event_signal_ready=0`。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage625_public_source_raw_text_probe.py`
- 修改正式策略脚本：无。
- 删除脚本：无。
- 新增参数/闸门：
  - `TIMEOUT_SECONDS = 15`
  - `MIN_RESPONSE_BYTES = 500`
  - `MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20`
  - `source_contract_complete`
  - `event_auto_monitor_validated`
  - `linked_text_fetch_status`
  - `linked_text_sha256`
  - `usable_for_history_selector = 0`
  - `event_signal_ready = 0`
- 修改参数：
  - WASDE 主源从旧 `www.usda.gov/oce/commodity/wasde` 路径改为 ESMIS 修正版页面 `2026-05-12-0`；原因是旧路径/旧 latest text 在本地联网探针中返回 `403`，ESMIS 是当前官方归档入口。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 数据区间：不适用；本阶段只做 source fetch probe。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只覆盖 Stage324 中公开源可抓取对象：`ag.SHFE`、`CY.CZCE`、`SR.CZCE`。
  - 只保存阶段级 raw fetch ledger，不追加 master forward ledger。
  - 对页面中发现的 `.txt` 链接做二次抓取，但仍只记录 hash、bytes、状态、短 excerpt，不保存全文。
- 策略/归因口径：
  - `ag.SHFE`：SHFE Daily Data HTML。
  - `CY.CZCE`：ESMIS Crop Progress、NASS 方法页、ERS Cotton and Wool Outlook、CZCE reference。
  - `SR.CZCE`：ESMIS WASDE 修正版、旧 USDA latest text、CZCE reference。

## 结果

- 决策：`public_source_raw_text_fetch_validated_selector_locked`
- rows：`8`
- covered products：`3`
- source contract complete rows：`5`
- event auto monitor validated rows：`4`
- history selector rows：`0`
- event signal ready rows：`0`
- selector unlocked now：`0`
- paper/whitelist allowed：`0`
- hard gates：`7/9`
- 成功抓取：
  - `ag.SHFE` / SHFE Daily Data：HTTP `200`，`307794` bytes，关键词命中 `4`。
  - `CY.CZCE` / ESMIS Crop Progress：HTTP `200`，并发现/抓取 `prog2226.txt`，linked text `72948` bytes。
  - `CY.CZCE` / NASS Crop Progress guide：HTTP `200`，linked text `137136` bytes。
  - `CY.CZCE` / ERS Cotton and Wool Outlook：HTTP `200`，`41169` bytes。
  - `SR.CZCE` / ESMIS WASDE corrected release：HTTP `200`，并发现/抓取 `wasde0526v2.txt`，linked text `121466` bytes。
- 失败抓取：
  - `CY.CZCE` / CZCE reference：HTTP `412`。
  - `SR.CZCE` / USDA WASDE latest text：HTTP `403`。
  - `SR.CZCE` / CZCE reference：HTTP `412`。
- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增收益曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增收益曲线。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易。
  - Stage526 参考：`1,342,190`
- 总交易次数：无新增交易。
  - Stage526 参考：`905`
- 胜率：无新增交易。
  - Stage526 非零日胜率参考：`53.6330%`

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_chart_stage625_public_source_raw_text_probe_v1.png`
- 左上 heatmap：`ag.SHFE` 在 `public_html_daily_data` 为 `OK`；`CY.CZCE` 在 `public_html_event_methodology` 和 `public_html_event_release_page` 为 `OK`；`SR.CZCE` 在 ESMIS release page 为 `OK`。`official_static_reference` 和 `public_text_event_file` 仍空/红，说明 CZCE 静态页和旧 WASDE latest text 没打通。
- 右上 source class：完整 raw-text 行集中在 `public_html_event_release_page=3`、`public_html_event_methodology=1`、`public_html_daily_data=1`；没有 official static reference 完整行。
- 左下 readiness：`source_contract_complete/raw_hash/keyword_hit` 均为 `62%`，`event_auto_monitor` 为 `50%`；但 `history_selector/event_signal_ready/paper_whitelist` 均为 `0%`，边界清楚。
- 右下 hard gates：公开源覆盖、raw fetch、event auto monitor、hash、selector/paper 锁定均为绿；`pit_dates_reach_20` 和 `dce_authorized_source_closed` 仍红。

## 输出文件

- raw fetch ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_raw_fetch_ledger_stage625_public_source_raw_text_probe_v1.csv`
- product summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_product_summary_stage625_public_source_raw_text_probe_v1.csv`
- source summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_source_summary_stage625_public_source_raw_text_probe_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_gates_stage625_public_source_raw_text_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_decision_stage625_public_source_raw_text_probe_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_report_stage625_public_source_raw_text_probe_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_chart_stage625_public_source_raw_text_probe_v1.png`

## 结论

- 本阶段结论：
  - `ag/CY/SR` 公开源的自动 raw-text/hash 证据已经部分打通，尤其 ESMIS 的 `prog2226.txt` 和 `wasde0526v2.txt` 能从 release page 自动发现并抓取。
  - 这比 Stage324 的 source catalog 更进一步，但仍只是可执行数据链证据，不是选品因子有效。
  - CZCE 静态页 `412` 和旧 WASDE latest text `403` 是真实阻塞，后续需要单独修 headers/browser/session 或换官方可用端点。
  - `j/i` 的 DCE 授权源和 live TCA 没有被本阶段解决。
- 是否进入下一步：进入，但仍是数据工程/forward monitor；不进入收益回测 selector、paper、A/B 或交易白名单。
- 下一步：
  1. 将 Stage625 变成每日可重复的 public source monitor，持续累计 `20` 个 PIT received_at 日期。
  2. 修 CZCE `412`：优先尝试官方页面入口、referer/session、浏览器抓取或其他 CZCE 静态文件索引。
  3. 对 `prog2226.txt`、`wasde0526v2.txt` 只做结构化字段抽取草案，不做收益回测，直到 PIT 深度满足。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有使用历史收益，没有调交易参数，没有新增产品白名单。
  - 所有抓取行继续强制 `usable_for_history_selector=0`、`event_signal_ready=0`。
  - 失败的 CZCE/旧 WASDE 路由被保留为失败证据，没有为了好看结果删掉。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只能继续做可执行数据链。
- 原因：
  - 已证明部分公开源能在脚本里自动获得 raw text/hash，这是实盘可执行外生数据的必要前置。
  - 但样本日期仍只有 `1/20`，没有预测力验证，不能进入选品收益回放。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage625_public_source_raw_text_probe.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage625_public_source_raw_text_probe.py`：初始沙箱内 DNS 失败；按规则使用联网权限重跑后通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage625_public_source_raw_text_probe_decision_stage625_public_source_raw_text_probe_v1.json`：通过。
- 图表已视觉检查：fetch evidence 增强，但 selector locked 边界清晰。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage325。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破、路线废弃或跨线合并。
