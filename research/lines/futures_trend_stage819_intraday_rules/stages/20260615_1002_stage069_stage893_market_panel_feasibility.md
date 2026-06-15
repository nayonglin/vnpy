# Stage069 - Stage893 全市场分钟面板本地可行性审计

- 时间：2026-06-15 10:02 CST
- 当前模式：day
- line_id：`futures_trend_stage819_intraday_rules`
- model_tag：`stage893_stage892_market_panel_feasibility_v1`
- 源候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 阶段性质：只读数据面板可行性审计；不新增交易规则、不接真实组合引擎、不改 Stage372 官方正式版、不改官方候选配置、不连接 CTP、不调用下单、不下载数据、不触发 A/B。
- 是否重要突破：否。它不是 alpha 突破，而是确认本地已有分钟文件不足以支撑全市场 first60 广度规则。

## 外部调研和判断

- 参考资料：
  - TqSdk `DataDownloader` 官方文档和示例：用于按合约、起止时间下载历史 K 线到 CSV，适合构建离线多合约面板。
  - TqSdk `get_kline_serial` 官方接口说明：更偏最近序列/订阅式 K 线获取，不应当被当作全周期离线面板构建器。
  - vn.py 官方 GitHub/文档：确认本地数据导入、回测和历史数据管理技术栈背景。
- 我的判断：市场广度是和单合约 `first60/OR15/OI/成交量` 不同的外生信息源，方向仍有第一性价值；但必须先有同一 entry_date 下足够多合约的分钟 K 线面板。没有面板就写规则，会把“样本缺失”伪装成“市场广度信号”，这是概念错误。

## 本次版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage893_stage892_market_panel_feasibility.py`
- 新增记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260615_1002_stage069_stage893_market_panel_feasibility.md`
- 固定审计定义：
  - 输入 Stage892 C9 features，提取 `401` 笔 closed lots 的 `299` 个唯一 `entry_date`。
  - 对每个 entry_date，统计同日每个 `vt_symbol` 是否至少有 `60` 根分钟 K。
  - 三类覆盖口径：Stage861 事件面板、Stage859 单日补洞 raw、本地 `downloaded_futures` 下所有已存在分钟 CSV 的合并 union。
  - 广度规则最少合约数固定为 `20`，不降低阈值、不按品种/年份/方向救参。
- 新增参数：无交易参数；只读审计常量 `EARLY_BARS=60`、`MIN_MARKET_SYMBOLS=20`、`CHUNK_SIZE=250000`。
- 修改参数：无。
- 删除参数：无。
- 官方正式版 Stage372：未修改。
- 官方候选配置：未修改。

## 数据与输出

- C9 closed lots：`401`
- 唯一 entry dates：`299`
- 扫描本地分钟 CSV：`1,671` 个
- 发现但不用于分钟面板的日线 CSV：`4,289` 个
- 官方候选 universe hint：`38` 行、`19` 个 product
- summary chart 尺寸：`2340x1800`
- 输出：
  - report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_report_stage893_stage892_market_panel_feasibility_v1.md`
  - source inventory：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_source_inventory_stage893_stage892_market_panel_feasibility_v1.csv`
  - entry coverage：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_entry_date_coverage_stage893_stage892_market_panel_feasibility_v1.csv`
  - date-symbol counts：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_date_symbol_counts_stage893_stage892_market_panel_feasibility_v1.csv`
  - candidate universe：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_candidate_universe_stage893_stage892_market_panel_feasibility_v1.csv`
  - summary chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_summary_chart_stage893_stage892_market_panel_feasibility_v1.png`
  - decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage893_stage892_market_panel_feasibility_decision_stage893_stage892_market_panel_feasibility_v1.json`

## 新增回测/代理结果

本阶段不新增真实回测，也不新增交易代理，只做数据覆盖审计：

- Stage861 事件面板覆盖：`min=0`、`p25=1`、`median=3`、`p75=6`、`max=10`，达到 `20` 合约的 entry_date 为 `0/299 = 0.0%`。
- 本地 downloaded minute union 覆盖：`min=0`、`p25=12`、`median=14`、`p75=17`、`max=23`，达到 `20` 合约的 entry_date 为 `12/299 = 4.0134%`。
- combined local 覆盖：同样只有 `12/299 = 4.0134%` 达到 `20` 合约要求。
- 最大的分钟源 `tqsdk_stage462_completed_preclose_full_dates_shard` 有 `436` 个分钟文件、覆盖 `238` 个 C9 entry_date，但单日最多也只是 `20` 个合约，而且不是全周期稳定覆盖。
- `tqsdk_daily_2010_2026_04` 有 `4,041` 个日线文件，但不能支持分钟级 first60 广度。

本阶段未跑真实回测，因此以下指标不适用：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率。

## 视觉检查

- 新增 summary chart 显示三条覆盖曲线：Stage861 事件面板、downloaded minute union、combined local symbols，并画出 `MIN_MARKET_SYMBOLS=20` 的红线。
- 图上只有极少数 2023-2025 日期触碰 `20`，2018-2019 以及大量 entry_date 明显不足。
- 这次不是 K 线形态复盘，而是 K 线数据面板可用性检查；结论是当前没有可供全市场广度规则使用的连续分钟面板。

## 决策

- decision：`stage893_local_market_panel_not_available_no_breadth_engine`
- 结论：本地已有 CSV 不能支撑全市场 first60 广度规则；不得用当前 union 数据写市场广度引擎，也不得把最少合约数降到 `10/14/17` 来制造信号。
- 操作：不接真实引擎、不触发 A/B、不改官方正式版、不改官方候选配置。

## 反过拟合反思

- 运行前：否。Stage893 只验证数据面板是否存在，不使用收益标签、不扫阈值、不写规则。
- 运行后：否。结论是拒绝在不足面板上继续做规则；如果为了让本地碎片触发信号而降低 `20` 合约要求、只取 2024-2025 或只取覆盖好的品种族群，那才是过拟合。

## 继续价值反思

- 运行前：有价值。市场广度作为外生参与度信息仍比继续挖 `first60/OR15/OI` 小变体更有本质差异。
- 运行后：当前本地数据条件下没有继续写规则的价值；市场广度路线只有在先构建全市场连续分钟面板后才有价值。若不补面板，本线应转账户级非交易层生存线，或阶段性暂停。

## 后续规划和 TODO

- 不使用当前 Stage861/full minute bars 或本地 downloaded minute union 继续做市场广度交易规则。
- 不扫描 `MIN_MARKET_SYMBOLS`、广度阈值、分钟窗口、品种族群、方向或年份。
- 如果继续市场广度方向，先建立独立的全市场连续分钟面板：明确 universe、主力/连续合约映射、交易日历、夜盘归属、数据权限和下载日志，然后再进入规则审计。
- 如果短期不补数据，下一步更务实的是回到账户级非交易层生存线，研究资金分层、出金锁盈、最大风险预算，而不是继续挖当前分钟 K 小变体。
- 本阶段不是正式候选、不是重要突破，不更新 `registry.md`、不追加根目录 `memory.md` / `back_log.md`。
