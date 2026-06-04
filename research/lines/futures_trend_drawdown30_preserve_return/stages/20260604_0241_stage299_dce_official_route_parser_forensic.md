# Stage299 DCE官方路线parser取证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 02:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据源取证；不做收益回测、不改策略、不生成交易白名单
- 是否重要突破：否；但把 Stage298 的 DCE 红灯从“AKShare报错”收敛为“官方端 HTTP 412 防护页/访问阻断”
- 是否触发A/B：否；`j/i` 仍不允许 paper、A/B 或白名单

## 外部调研与判断

- 参考资料：
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`，近期版本曾修复 `futures_warehouse_receipt_dce` 与 `futures_dce_position_rank`。
  - AKShare futures 文档/GitHub：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`，DCE 会员持仓接口仍被文档列为可用接口。
  - AKShare GitHub：`https://github.com/akfamily/akshare`，AKShare 是公共金融数据接口库，本阶段只把它当作外部数据解析层，不把第三方 wrapper 成功等同于官方源稳定。
- 我的判断：
  - Stage298 的 `BadZipFile/JSONDecodeError` 不是策略问题，也不是 `j/i` 品种本身问题，而是 DCE 官方 `dcereport` 路由在当前环境返回 `HTTP 412 + text/html` 防护页。
  - AKShare 本地版本 `1.18.55`，相关函数 4/4 均存在；失败发生在官方响应格式与 parser 预期不一致，不能通过继续做收益回测解决。
  - 因为官方 member/warehouse route 没有 point-in-time 可复验闭环，`black_ferrous(j/i)` 继续只能停留在 P1 source/TCA worklist。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage599_dce_official_route_parser_forensic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LOOKBACK_DAYS=7`
  - `HTTP_TIMEOUT=10`
  - `WORKER_TIMEOUT=16`
  - `EXPECTED_PRODUCTS=["j.DCE", "i.DCE"]`
  - 官方路线探测：`memberDealPosi/batchDownload`、`wbillWeeklyQuotes`、legacy `memberDealPosiQuotes.html`、legacy `wbillWeeklyQuotes.html`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-05-31 至 2026-06-04 最近交易/自然日探测窗口
- 账户规模：N/A
- 成本口径：N/A
- 样本过滤：只看 `j.DCE/i.DCE` 的 DCE 官方会员持仓与仓单路线
- 策略/归因口径：数据源 parser forensic；不回测收益、不筛交易、不调参

## 结果

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 其他关键指标：
  - AKShare 本地版本：`1.18.55`
  - 相关函数存在：`4/4`
  - AKShare wrapper 成功：`0/12`
  - DCE HTTP probe 成功：`0/22`
  - hard gates：`2/7`
  - official parser route ready：`0/4`
  - `futures_dce_position_rank`：`BadZipFile: File is not a zip file`
  - `futures_warehouse_receipt_dce`：`JSONDecodeError: Expecting value`
  - 直接 HTTP：`memberDealPosi/batchDownload` 与 `wbillWeeklyQuotes` 返回 `HTTP 412`、`text/html; charset=utf-8`，不是 zip/json
  - legacy `portal.dce.com.cn`：当前环境仍 DNS/解析不可用
  - decision：`dce_official_route_parser_blocked_no_paper`
  - promotion_allowed：`false`
  - paper_selector_allowed：`false`
  - trading_whitelist_allowed：`false`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_report_stage599_dce_official_route_parser_forensic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_decision_stage599_dce_official_route_parser_forensic_v1.json`
- orders：N/A
- daily：N/A
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_function_forensics_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_akshare_probe_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_http_probe_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_route_readiness_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_gates_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_next_actions_stage599_dce_official_route_parser_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage599_dce_official_route_parser_forensic_chart_stage599_dce_official_route_parser_forensic_v1.png`

## 结论

- 本阶段结论：
  - `j/i` 的 DCE member_detail 与 warehouse 官方路线仍不可用，根因是官方 `dcereport` 路由返回 `HTTP 412` 防护页，导致本地 AKShare parser 把 HTML 误当 zip/json 解析。
  - 这说明 Stage298 的 `j/i` 扩池方向不能因为 basis/inventory 第三方路线可抓而晋级；官方源红灯仍是硬阻塞。
  - 对用户提出的“减少单笔风险、扩大品种池、避免高相关、选对品种”，当前判断保持：方向对，但必须先补可复验数据源/TCA。没有官方源闭环时，选品只能靠历史收益或第三方单点快照，过拟合和实盘偏差都会很高。
- 是否进入下一步：进入下一步，但不是收益回测；是官方路线修复/替代源取证。
- 下一步：
  - P0：尝试 browser/cookie session 或官方页面下载路径，看能否绕过 `HTTP 412` 并稳定得到 zip/json。
  - P0：若 DCE 官方自动源仍阻塞，寻找可授权、可记录 `received_at/source_url/raw_hash` 的替代官方/准官方数据源；第三方源只能作为 monitor，不可直接当 alpha。
  - P1：`black_ferrous(j/i)` 继续累计 forward ledger，但在 member/warehouse 官方源和每品种 `3` 个 TCA 样本前，禁止 paper、A/B、白名单和收益回测。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有看收益标签，没有调品种名单、阈值、仓位或入场逻辑；只验证数据源是否能被真实时间戳账本复验。
  - 结果是红灯，不会被拿去救历史曲线，反而降低了错误晋级风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但路径更窄。
- 原因：
  - 低单笔风险扩池的核心不是“多加品种”，而是增加真正独立、可承载、可实时识别的风险槽。
  - `j/i` 相关性和容量初步有价值，但官方源/TCA未闭环前不具备交易资格；继续价值在于把源修通或明确放弃，而不是继续回测收益。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage299 源取证结论。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否；不是正式候选、重要突破或路线废弃。
