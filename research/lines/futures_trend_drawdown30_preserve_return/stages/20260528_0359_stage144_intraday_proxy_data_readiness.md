# Stage144 分钟线执行代理数据覆盖审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-28 03:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行代理数据可用性审计；不新增策略、不修改交易规则、不调参数
- 是否重要突破：否；但属于重要执行前置约束
- 是否触发A/B：否；本阶段不是候选策略实验

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档示例显示 `api.get_kline_serial("SHFE.cu1812", 60)` 可获取1分钟K线，且合约格式为 `交易所.合约`。
  - TqSdk API 参考说明 `duration_seconds=60` 表示1分钟线，单序列默认返回 pandas DataFrame。
  - vn.py 官方仓库与本地接口均支持数据库层按 `Interval.MINUTE` 读取K线，本仓库日线已落库但分钟线 overview 为空。
- 我的判断：
  - 当前 Stage103/Stage079 最大的问题不是再找小参数，而是 `same_day_close` 与真实委托时段之间的执行代理风险。
  - TqSdk/QMT 技术路径可行，但本地没有分钟线数据，不能直接把 Stage103 推进到真实 paper/影子盘。
  - 应先按订单级目标窗口补 `14:55/20:55/21:00/08:55/09:00` 的分钟线或 QMT 行情采样，再重构真实可执行代理价。

## 本次变更

- 新增脚本：无，本阶段脚本已在 Stage144 初稿中创建
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage444_intraday_proxy_data_readiness.py`
- 删除脚本：无
- 新增参数：无策略参数；新增审计字段 `calendar_validation_required` 与 `suggested_tqsdk_symbol`
- 修改参数：将 TqSdk 建议合约格式从 vn.py `vt_symbol` 口径改为 `交易所.合约`，例如 `MA605.CZCE -> CZCE.MA605`
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage443 订单级 ledger，覆盖 2020-2026 全周期同日成交订单
- 账户规模：沿用 Stage079/Stage103 的 `615,000` 账户口径；本阶段不重算权益
- 成本口径：本阶段不新增成本；只检查分钟线数据覆盖
- 样本过滤：不筛日期、不筛品种；高优先级仅用于采样排序，不用于规则过滤
- 策略/归因口径：
  - 输入：Stage143/443 trade gap ledger，共 `757` 笔同日成交迁移订单
  - 目标窗口：`same_day_close_last_5m`、`day_session_auction_0855_0900`、`day_session_open_0900_0905`，夜盘品种额外检查 `night_auction_2055_2100` 与 `night_session_open_2100_2105`
  - 数据源检查：vn.py 本地数据库 `get_bar_overview()` 的 `Interval.MINUTE`

## 结果

- 期末权益：不适用，本阶段不做策略权益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：输入订单数 `757`
- 胜率：不适用
- 其他关键指标：
  - 决策标签：`minute_proxy_data_missing_build_sampling_plan`
  - 本地分钟线 overview 行数：`0`
  - 需要采样窗口：`3,561`
  - 已覆盖窗口：`0`
  - 覆盖率：`0.0000%`
  - 涉及合约数：`228`
  - 高优先级窗口数：`197`
  - 需要交易所日历复核的窗口数：`554`
  - tqsdk 可导入：`True`
  - xtquant 可导入：`True`
  - 本地数据库仅有日线 overview：`4,384` 行、`995,669` 根日线、`4,384` 个 symbol
  - 最高优先级补数合约：`MA605.CZCE`、`jm2509.DCE`、`fu2209.SHFE`、`fu2503.SHFE`、`rb2605.SHFE`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_report_stage444_intraday_proxy_data_readiness_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_coverage_summary_stage444_intraday_proxy_data_readiness_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_required_proxy_targets_stage444_intraday_proxy_data_readiness_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_readiness_stage444_intraday_proxy_data_readiness_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_symbol_download_plan_stage444_intraday_proxy_data_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_priority_targets_stage444_intraday_proxy_data_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage444_intraday_proxy_data_readiness_database_overview_stage444_intraday_proxy_data_readiness_v1.csv`

## 结论

- 本阶段结论：本地没有可用于 Stage103/Stage079 执行代理校准的分钟线数据，现有数据不足以证明 `same_day_close` 可执行。
- 是否进入下一步：是，但下一步不是继续优化信号，而是 Stage145 补分钟线/QMT采样并重构执行代理回测。
- 下一步：
  1. 先补高优先级 `197` 个窗口，验证最差缺口样本；如可行再补全 `3,561` 个窗口。
  2. 采集时必须按交易所真实交易日历校正 `554` 个自然日周末/节假日候选窗口，不能机械相信日线 `next_trade_date` 标签。
  3. 用真实 `14:55/20:55/21:00/08:55/09:00` 代理价重构 Stage079 与 Stage103 执行路径。
  4. 在 Stage145 完成前，Stage103 只保留为同日收盘研究主候选，不进入真实 paper/影子盘。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只审计数据覆盖并输出全订单采样清单，没有按坏日期、坏品种或坏交易过滤，也没有新增收益规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：Stage141-143 已证明执行时点会把回撤从 30% 内打到接近 50% 以上；如果不先校准分钟级执行价，继续在同日收盘口径上提升 3/6个月体验，结论可能不可部署。

## 合入建议

- 是否更新本线 `LINE.md`：是，增加 Stage144 数据缺口和 Stage145 优先级。
- 是否更新 `research/registry.md`：是，最新关键阶段从 Stage143 推进到 Stage144。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`，因为尚未产生最终候选或跨线长期记忆。
