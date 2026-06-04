# Stage300 DCE 412浏览器session取证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 02:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据源可执行性取证；不做收益回测、不改策略、不生成交易白名单
- 是否重要突破：否；但进一步反证“普通浏览器 cookie session 可直接修复 DCE 412”
- 是否触发A/B：否；`j/i` 仍不允许 paper、A/B 或白名单

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档/GitHub：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`，DCE 会员持仓与仓单接口仍被列为公共接口。
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`，近期版本曾多次修复 DCE 仓单、会员持仓等接口，说明交易所页面和接口存在持续漂移。
  - 大商所对外门户上线通知：`https://finance.sina.com.cn/money/future/wemedia/2024-10-18/doc-incsxqvm2046236.shtml`，DCE 已上线“对外门户/业务通办”等新入口，老公开页面/API 的访问控制变化不能忽视。
- 我的判断：
  - Stage299 已证明普通 HTTP 返回 `412`；Stage300 进一步证明真实 Chrome headless 能产生 DCE cookie，但仍不能把 member/warehouse endpoint 变成可用 JSON/ZIP。
  - 这不是策略问题，也不是 `j/i` 相关性问题，而是数据源执行链不满足实盘可复验要求。
  - 继续“绕过 412”不应成为 alpha 研究主线；下一步应找可授权、可稳定、可记录 `received_at/source_url/raw_hash` 的官方/准官方源，或者把 `j/i` 新族继续停在 worklist。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage600_dce_412_browser_session_probe.py`
- 修改脚本：
  - 同脚本内新增浏览器 cookie 回放测试：`browser_cookie_replay`
- 删除脚本：无
- 新增参数：
  - `PROBE_DATE=20260603`
  - `BROWSER_TIMEOUT_SECONDS=150`
  - `NPM_INSTALL_TIMEOUT_SECONDS=120`
  - `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`
  - DCE 路线：home、warehouse page、member page、ext portal、`wbillWeeklyQuotes`、`memberDealPosi/batchDownload`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-06-03 单日官方源取证，执行时间 2026-06-04 02:57 CST
- 账户规模：N/A
- 成本口径：N/A
- 样本过滤：仅 DCE `j/i` P1 新族相关的 member_detail 与 warehouse 官方路由
- 策略/归因口径：source executability forensic；不回测收益、不筛交易、不调参

## 结果

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 其他关键指标：
  - decision：`dce_browser_session_not_ready_official_source_blocked`
  - hard gates：`3/7`
  - direct requests：`2/2` 复现 `HTTP 412`
  - requests.Session warmup：DCE home/member/warehouse 页面仍为 `HTTP 412`
  - Playwright/Chrome：可启动，`channel=chrome`
  - browser cookies：`2`
  - browser endpoint fetch：warehouse/member 均为 `HTTP 400 text/html`、`content_length=6`，不是 JSON/ZIP
  - browser cookie replay：warehouse/member 均为 `HTTP 400 text/html`、`content_length=6`，不是 JSON/ZIP
  - browser screenshot：空白页，未加载出 DCE 实际内容
  - promotion_allowed：`false`
  - paper_selector_allowed：`false`
  - trading_whitelist_allowed：`false`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_report_stage600_dce_412_browser_session_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_decision_stage600_dce_412_browser_session_probe_v1.json`
- orders：N/A
- daily：N/A
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_http_probe_stage600_dce_412_browser_session_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_browser_probe_stage600_dce_412_browser_session_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_browser_cookies_stage600_dce_412_browser_session_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_gates_stage600_dce_412_browser_session_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_next_actions_stage600_dce_412_browser_session_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_chart_stage600_dce_412_browser_session_probe_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage600_dce_412_browser_session_probe_browser_page_stage600_dce_412_browser_session_probe_v1.png`

## 图表视觉复盘

- 主图左上：requests/session/cookie replay 全部为橙色 `wrong format`，说明不是“先访问首页拿 cookie”就能修复。
- 主图右上：browser context fetch 两条 endpoint 都停在 `HTTP 400`，不是可用数据。
- 主图左下：只有 `playwright_browser_available`、`browser_cookies_observed`、`no_strategy_backtest` 等技术项为绿；真正的数据可用闸门仍红。
- 主图右下：有 `2` 个浏览器 cookie，但 challenge markers 有 `7` 个，说明 session artifact 存在但没有通过官方防护。
- 浏览器截图为空白，结合 page title 为空，说明无登录/无授权 browser session 未进入实际 DCE 内容页。

## 结论

- 本阶段结论：
  - 浏览器/cookie session 不能直接把 DCE `member_detail/warehouse` 官方路由转成可交易数据源。
  - `j/i` 新族继续只能保留在 P1 source/TCA worklist；不能 paper、不能 A/B、不能白名单，也不能做收益回测。
  - 对“减少单笔风险、扩大品种池、避免高相关、选对品种”的判断保持：方向对，但 `j/i` 当前的短板不是相关性或容量，而是官方源和 TCA 闭环。
- 是否进入下一步：进入下一步，但不再把普通 browser-cookie 绕防护作为主路径。
- 下一步：
  - P0：寻找可授权 DCE 数据通道、交易所可下载替代源、或稳定准官方源，必须保留 `received_at/source_url/raw_hash`。
  - P0：继续补 DCE 事件 monitor 与每品种 `3` 个真实/独立分钟 TCA 样本；官方 member/warehouse 未闭环前不做 `j/i` alpha。
  - P1：第三方 basis/inventory 继续只做 forward monitor，不作为历史 selector 或交易信号。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只验证数据源执行链，没有看收益、没有改策略、没有调参数或品种名单。
  - 红灯结论阻止了错误晋级，降低了把数据源问题包装成 alpha 的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但继续方向必须收窄。
- 原因：
  - 扩池的本质是增加可实时识别、可成交、低相关的独立风险槽；DCE 官方源不能自动化时，`j/i` 不能承担这个角色。
  - 继续价值在于找授权/替代源或转向其它新产品族，而不是继续对 `j/i` 做收益回测。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage300 浏览器/session 反证。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否；不是正式候选、重要突破或路线废弃。
