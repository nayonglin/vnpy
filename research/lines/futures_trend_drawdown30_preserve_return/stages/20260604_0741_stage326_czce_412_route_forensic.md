# Stage326 CZCE 412 路由取证审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:41 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：CZCE 公开静态页/参考页路由取证；不追加 master ledger、不新增收益回测、不改策略规则、不生成 selector/paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否。它是执行性证据的反证闭环：当前脚本访问方式下 CZCE 路由不可作为自动化实盘源。
- 是否触发A/B：否。没有形成可接入正式版本的新策略、新品种或新风险预算。

## 外部调研与判断

- 参考资料：
  - CZCE 官网：https://www.czce.com.cn/
  - CZCE English reference 示例：https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm
  - CZCE 持仓排名入口：https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm
  - CZCE 仓单日报入口：https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm
  - MDN HTTP 412 解释：https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/412
- 我的判断：
  - 外部搜索没有找到 CZCE 对 `412 Precondition Failed` 的官方解释或稳定脚本访问协议，不能假设只是缺一个简单 header。
  - 公开源实盘可执行性必须按 `received_at/source_url/raw_hash/status/product_vt_symbol/route` 做 point-in-time 合同；路由取证只证明能否自动抓取，不构成 alpha。
  - 本阶段请求矩阵显示：普通 browser-like header、referer、cookie warmup、download accept 都没有打通 CZCE English reference、中文持仓排名或仓单路由。
  - 因此 `CY.CZCE/SR.CZCE` 的公开事件源下一步应优先使用 Stage625 已验证的 USDA/ESMIS/ERS 路线；CZCE 官方静态文件暂时降级为浏览器/人工取证或授权替代源分支。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage626_czce_412_route_forensic.py`
- 修改正式策略脚本：无。
- 删除脚本：无。
- 新增参数/闸门：
  - `TIMEOUT_SECONDS = 15`
  - `MIN_RESPONSE_BYTES = 500`
  - `MIN_KEYWORD_HITS = 1`
  - `HEADER_VARIANTS = minimal/chrome_en/chrome_zh/chrome_download`
  - `PROBE_STRATEGIES = direct/referer/warmup/download_accept`
  - `route_ready`
  - `usable_for_forward_monitor`
  - `usable_for_history_selector = 0`
  - `event_signal_ready = 0`
  - `paper_or_whitelist_allowed = 0`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 数据区间：不适用；本阶段只做当前联网路由取证。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - English reference：`2024-04-18`、`2023-12-29` 两个静态参考页。
  - 中文持仓排名：`2024-01-02`、`2024-04-18` 两个静态持仓页。
  - 中文仓单：`2024-04-18` 的 HTTPS/HTTP xlsx 路径。
  - 每个 target 测试 `7` 种请求策略，共 `42` 行。
- 策略/归因口径：
  - 只判断机器可读 route readiness。
  - 即便 route ready 也只能进入 forward monitor，不允许进入历史 selector、event signal、paper 或交易白名单。

## 结果

- 决策：`czce_412_route_forensic_completed_selector_locked`
- probe rows：`42`
- targets：`6`
- strategies：`7`
- route-ready rows：`0`
- HTTP 412 rows：`28`
- HTTP 403 rows：`0`
- HTTP 404 rows：`14`
- forward monitor rows：`0`
- history selector rows：`0`
- event signal ready rows：`0`
- selector unlocked now：`0`
- paper/whitelist allowed：`0`
- hard gates：`4/8`
- 分路由结果：
  - English reference 两个 target：全部策略 HTTP `412`，route-ready `0/14`。
  - 中文持仓排名两个 target：全部策略 HTTP `412`，route-ready `0/14`。
  - 中文仓单 HTTPS/HTTP 两个 target：全部策略 HTTP `404`，response bytes `709`，route-ready `0/14`。
- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增收益曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增收益曲线。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易。
- 总交易次数：无新增交易。
- 胜率：无新增交易。

## 图表视觉复盘

- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_chart_stage626_czce_412_route_forensic_v1.png`
- 视觉结论：
  - 左上热力图没有任何绿色 `READY` 单元。English reference 和中文持仓页全是 `412`；仓单两行全是 `FAIL`，结合 ledger 是 `404`。
  - 右上状态柱显示 `412=28`、`404=14`，说明问题不是个别请求失败，而是官方静态/参考/仓单路由整体未被当前脚本方式打通。
  - 左下每个请求策略 route-ready 都是 `0`，cookie warmup、referer listing、Chrome header、download accept 都没有边际改善。
  - 右下硬闸门只有“复现 412”和“selector/paper 保持 0”是绿；`czce_route_ready_any`、`english_reference_ready`、`cn_position_or_warehouse_ready`、`warmup_cookie_helped` 全红。
  - 图表没有标签遮挡或坐标误读，但 bottom-left 全 0 时坐标轴略空，这是数据本身的警示，不影响结论。

## 输出文件

- script：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage626_czce_412_route_forensic.py`
- probe ledger：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_probe_ledger_stage626_czce_412_route_forensic_v1.csv`
- target summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_target_summary_stage626_czce_412_route_forensic_v1.csv`
- strategy summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_strategy_summary_stage626_czce_412_route_forensic_v1.csv`
- gates：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_gates_stage626_czce_412_route_forensic_v1.csv`
- decision：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_decision_stage626_czce_412_route_forensic_v1.json`
- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_report_stage626_czce_412_route_forensic_v1.md`
- chart：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage626_czce_412_route_forensic_chart_stage626_czce_412_route_forensic_v1.png`

## 结论

- 本阶段结论：
  - CZCE English reference、中文持仓排名和仓单静态路径在当前脚本访问矩阵下全部不可作为自动化实盘数据源。
  - `CY.CZCE/SR.CZCE` 的 forward monitor 不应依赖这组 CZCE 静态文件；Stage625 已打通的 USDA/ESMIS/ERS 路线可以继续累计 PIT source rows。
  - 本阶段没有新增 alpha、没有 selector 资格、没有 paper/交易白名单资格。
- 是否进入下一步：
  - 是，但不是继续调 header 小数。下一步应把 CZCE 分支降级为浏览器/CDP 或授权替代源取证，同时继续用已成功抓取的 USDA/ESMIS/ERS 源累计 PIT 观测。
- 下一步：
  - 用真实浏览器/CDP 检查 CZCE 页面点击下载时的实际 network request、cookie、query 参数和最终文件名；若仍不可自动化，则标注为 `manual/browser-only source`。
  - 对 `CY/SR` 继续用 ESMIS Crop Progress/WASDE、ERS Cotton 形成定期 raw hash monitor。
  - 扩池/选品侧继续按独立风险槽推进，禁止在 source/TCA/live context 未闭合前生成 selector、paper 或白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段不改策略规则、不扫收益参数、不根据历史盈亏选择品种，只验证公开源 route 是否能被机器按 point-in-time 方式抓取。
  - 结果是执行性反证，不是为了适配某个历史窗口的 alpha 解释。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但 CZCE 这条脚本抓取子路由应降级。
- 原因：
  - 对基本面/事件源来说，“不能自动抓”本身就是重要结论，可以防止未来把不可实盘的数据接入 selector。
  - 继续价值在于把可抓的 USDA/ESMIS/ERS/SHFE 路线形成 PIT 监控，同时把 CZCE 改为浏览器/授权替代源，不再在 header 矩阵里空转。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage326 结论。
- 是否更新 `research/registry.md`：是，把最新关键阶段推进到 Stage326。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是局部 source route 阻塞，不是正式候选、重大突破、路线废弃或跨线合并。
