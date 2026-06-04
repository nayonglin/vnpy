# Stage347 ec.INE 第二独立槽 source probe

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 11:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池路线的第二非 DCE 独立驱动侦察；只做本地风险槽重筛与 INE/SSE 官方源 active probe，不做收益回测、不改交易规则、不连接 CTP、不生成 selector/paper/A/B/交易白名单。
- 是否重要突破：否。属于 source monitor 新线索，不是策略突破。
- 是否触发A/B：否。selector/paper/whitelist 仍为 `0/0/0`。

## 外部调研与判断

- 参考资料：
  - INE SCFIS 欧线品种页：`https://www.ine.cn/products/futures/index_f/ec_f/`
  - INE English EC 页面：`https://www.ine.cn/eng/market/futures/index/ec/index.html`
  - 上海航运交易所 SCFIS 当前查询：`https://www.sse.net.cn/index/singleIndex?indexType=scfis`
  - 上海航运交易所 SCFIS 指数简介：`https://www.sse.net.cn/indexIntro?indexName=scfis`
  - GitHub 搜索未找到可靠专用 SCFIS Python 项目，后续应使用官方页面 raw hash + 自定义 parser。
- 我的判断：
  - `ec.INE` 的经济驱动是集装箱航运运价，和现有商品趋势池的金属、农产品、化工、油品不同，方向上更像“第二独立风险槽”而不是同族扩容。
  - 但它不是严格低相关：`max_abs_corr_to_p0=0.1634`，只在 watch 区间，未过 `0.15` 严格线；本地 futures proxy 也因历史短/数据滞后被 Stage633 标成 `reject_data_or_liquidity`。
  - 官方源可执行性主要来自上海航交所 SCFIS 页面。INE 两个页面本次 HTTP 200 且有 raw hash，但 `keyword_hit_count=0`，主动抓取到的内容更像动态壳或弱语义 payload，不能单独算 parser-ready。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage647_ec_ine_second_slot_source_probe.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `STRICT_CORR_THRESHOLD = 0.15`
  - `WATCH_CORR_THRESHOLD = 0.20`
  - `REQUIRED_COLLECTION_PIT_DATES = 20`
  - `REQUIRED_EPISODES = 3`
  - source targets：INE EC product page、INE EC English market page、SSE SCFIS current query、SSE SCFIS methodology intro。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：非收益回测；本地风险槽证据来自 Stage633，官方源 active probe 时间为 `2026-06-04 11:13 CST`。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：只审计 `ec.INE` 作为第二非 DCE 独立经济驱动候选，同时列出 `CJ/au/ag/lc/SR/pb/sn` peer board。
- 策略/归因口径：只读相关性、流动性、趋势代理、官方源抓取、raw hash、SCFIS 欧线当前值解析和 selector 闸门；不看未来收益，不做交易回放。

## 结果

- 期末权益：不适用，非回测。
- 总收益：不适用，非回测。
- 最大回撤：不适用，非回测。
- Sharpe：不适用，非回测。
- 总滑点：不适用，非回测。
- 总交易次数：不适用，非回测。
- 胜率：不适用，非回测。
- 其他关键指标：
  - decision：`ec_ine_scfis_official_source_validated_watch_only_selector_locked`
  - source probe rows：`4`
  - source ok rows：`4`
  - raw hash rows：`4`
  - SCFIS current parse rows：`1`
  - latest SCFIS Europe：`2026-06-01`，`2038.09`，环比 `+9.40%`
  - max abs corr to P0：`0.1634`
  - rolling abs corr p75 to P0：`0.2175`
  - tail abs corr to P0 composite：缺失/NaN
  - recent median volume：`22007.5`
  - days behind latest tradable：`67`
  - collection PIT dates：`1`
  - selector/paper/whitelist：`0/0/0`
  - hard gates：`10/15`

## 图表视觉复盘

- 左上：`ec.INE` 位于 `0.15` 严格线之上、`0.20` watch 线之下，说明它不是严格低相关，只是观察级低相关。`CJ.CZCE` 和 `au.SHFE` 相关性更低，但 CJ 仍缺 PIT/episode，贵金属已有 prior alpha failed 约束。
- 右上：SSE SCFIS current query 为绿色，HTTP `200`、hash `1`、keyword `4`、parsed；SSE methodology intro 为蓝色，HTTP `200`、hash `1`、keyword `2`。INE 两个页面虽然 HTTP `200`，但 keyword `0`，说明 INE 主动抓取语义不够强，后续 parser 应以 SSE 为主。
- 左下：official source rows `4`、raw hashes `4`、SCFIS parse rows `1`，但 collection PIT dates 只有 `1`，selector rows `0`，离 `20` 日红线很远。
- 右下：红灯集中在 local price data fresh、strict corr、tail corr、20 PIT、3 episodes；绿色集中在独立经济驱动、流动性、watch corr、SSE 官方源、raw hash 和 fail-closed。结论清楚：可以 source monitor，不可交易晋级。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_report_stage647_ec_ine_second_slot_source_probe_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_decision_stage647_ec_ine_second_slot_source_probe_v1.json`
- fetch ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_fetch_ledger_stage647_ec_ine_second_slot_source_probe_v1.csv`
- product evidence：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_product_evidence_stage647_ec_ine_second_slot_source_probe_v1.csv`
- peer board：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_peer_board_stage647_ec_ine_second_slot_source_probe_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_gates_stage647_ec_ine_second_slot_source_probe_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_chart_stage647_ec_ine_second_slot_source_probe_v1.png`
- orders/daily/quality：不适用，非交易回测。

## 结论

- 本阶段结论：`ec.INE` 是 CJ 之后值得纳入 forward source monitor 的第二个非 DCE 独立经济驱动候选。它的优势是官方标的指数 SCFIS 可抓、可 hash、可解析当前欧线值，且经济驱动和传统商品高度不同。
- 它不是交易候选：本地 futures proxy 滞后 `67` 天、tail corr 缺失、严格相关性不过线、collection PIT dates 只有 `1`、episode 和 TCA 均为 `0`。
- 是否进入下一步：进入 source/PIT monitor 下一步；不进入 selector/paper/A/B/交易白名单。
- 下一步：
  - 写 `ec.INE` / SCFIS master PIT append gate，仅按新 `received_pit_date` 累计。
  - 修复或补齐本地 `ec.INE` 最新 futures proxy，重新审计 data freshness、tail corr 和 rolling corr。
  - 累计至少 `20` 个 SCFIS collection PIT dates 后，再做固定 `20/63/126` outcome schedule。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有做收益回放、没有根据历史收益选品、没有调参数，只用独立经济驱动、相关性、流动性和官方源可执行性做准入；抓到 SCFIS 当前值后仍锁定 selector/paper/whitelist。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但仅限 source monitor。
- 原因：扩池路线需要第二个非 DCE 低相关/独立经济驱动，`ec.INE` 在经济含义和官方源上比继续挖高相关金属更有结构价值；但它的历史短、数据新鲜度和相关性证据不足，短期只能做前向数据累计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage347 当前状态。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破、路线废弃或跨线合并。
