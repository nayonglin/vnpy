# Stage043 Stage867 高热 stop-first 不重试真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 04:09 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：研究线内冻结 A/C 真实组合引擎验证；只比较 Stage830 C4、Stage847 C9、Stage867 C11；不改 Stage372 官方正式版，不改 Stage819 官方候选配置，不连接 CTP，不调用下单。
- 是否重要突破：否
- 是否触发A/B：否，`formal_ab_triggered=false`，本阶段未达到“可能接入正式版/候选合入”的门槛。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：https://github.com/vnpy/vnpy
  - Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - backtesting.py contingent order docs：https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html
- 我的判断：
  - Stage866 的 `HH_NR1_retry_failed_only_no_retry` 只读代理有启发，但如果直接按“知道重试后来会二次失败才不重试”写入引擎，会使用未来信息。
  - Stage867 因此只验证实时可执行近似：entry projected broker10 `>=90%` 且入场日先触发 `0.5R` adverse stop 时，立即平仓，且当天不再按 reclaim 重试。
  - 这不是 AI、不是机器学习，也不使用未来收益标签；它只用下单当时可知的投影 broker10 和入场日分钟K逐根推进后的实时触发。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage867_stage866_high_heat_no_retry_engine.py`
- 修改脚本：
  - 同一新增脚本内修正两处可视化/匹配问题：
    - `entry_risk_diagnostics` 与真实开仓 trade 的时间不在同一天，不能 exact datetime 匹配；改为同合约、同方向、同手数、`0 <= trade_ts - decision_ts <= 4 days` 的最近决策匹配。
    - atlas 画图显式传入本次加载的 `minute_bars`，并把带 `+08:00` 的事件日期转为无时区日期后与 `bar_date` 比对。
- 删除脚本：无
- 新增参数：
  - `enable_stage867_high_heat_stop_first_no_retry`
  - `stage867_high_heat_projected_broker10_pct=90.0`
- 修改参数：无；C9 的 `stop_retry_r=0.5`、`max_retries=1` 沿用 Stage847。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage847/C9 全周期 `START` 到 `END`。
- 账户规模：沿用 Stage819/Stage830/Stage847 的组合回测口径。
- 成本口径：沿用既有组合回测成本和滑点口径。
- 样本过滤：无额外年份、品种、方向过滤；不扫描阈值、R、时间窗、品种、方向。
- 策略/归因口径：
  - A：`stage830_stage819_c2_broker10_100_cap`，即 C4。
  - B：`stage847_stage819_c4_05r_stop_retry_once`，即 C9。
  - C：`stage867_stage819_c9_high_heat_stop_first_no_retry`，即 C11。
  - C11 规则：在 C9 的 stop-first/retry 基础上，如果开仓对应 entry risk 的投影 broker10 `>=90%`，则首次 `0.5R` stop 后不做同日 reclaim retry。
  - broker10 计算继续使用 broker margin multiplier `1.65`。

## 结果

| arm | 期末权益 | 相对C4 | 相对C9 | 总收益 | 最大回撤 | 相对C9回撤 | Sharpe | 相对C9 Sharpe | 总滑点 | 总交易次数 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | 46,015,805.0 | 0.0 | -4,621,339.6 | 15,238.6017% | -47.1915% | -4.5602pp | 1.5996 | -0.0316 | 3,023,410 | 678 | 53.0630% | 111.4255% |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | 50,637,144.6 | +4,621,339.6 | 0.0 | 16,779.0482% | -42.6313% | 0.0000pp | 1.6312 | 0.0000 | 3,607,030 | 786 | 53.5299% | 114.3987% |
| C11 `stage867_stage819_c9_high_heat_stop_first_no_retry` | 47,772,889.7 | +1,757,084.7 | -2,864,254.9 | 15,824.2966% | -43.1208% | -0.4895pp | 1.6029 | -0.0282 | 3,295,210 | 778 | 53.7980% | 111.5707% |

- 期末权益：C11 `47,772,889.7`，低于 C9 `2,864,254.9`。
- 总收益：C11 `15,824.2966%`，低于 C9 `16,779.0482%`。
- 最大回撤：C11 `-43.1208%`，比 C9 差 `-0.4895pp`，但仍好于 C4。
- Sharpe：C11 `1.6029`，低于 C9 `1.6312`。
- 总滑点：C11 `3,295,210`，少于 C9，但收益损失更大。
- 总交易次数：C11 `778`，比 C9 少 `8`。
- 胜率：C11 `53.7980%`，略高，但不足以弥补右尾损失。
- 风险路径：C11 max broker10 `111.5707%`，确实把 C9 的 `114.3987%` 拉回到接近 C4 的 `111.4255%`，但这不是免费的，权益和 Sharpe 明显变差。

### 事件结果

| profile | final_state | events | volume | high_heat_events | reclaim_observed | retry_failed_observed | median projected broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C11 | `flat_high_heat_no_retry` | 9 | 321 | 9 | 5 | 2 | 99.4231% |
| C11 | `flat_no_reentry` | 66 | 13,565 | 0 | 0 | 0 | 41.0111% |
| C11 | `flat_retry_failed` | 24 | 4,424 | 0 | 24 | 24 | 38.7948% |
| C11 | `open_after_reentry` | 23 | 4,830 | 0 | 23 | 0 | 37.6779% |

- C11 命中 high-heat no-retry 事件 `9` 笔，其中事后观察到 reclaim 的有 `5` 笔，真正 reclaim 后又二次失败的只有 `2` 笔。
- 这解释了为什么 Stage866 代理看起来有价值、但 Stage867 真实引擎失败：真实盘不能提前知道哪一笔 reclaim 会二次失败，粗暴“高热先止损就不重试”会误伤 `3` 笔 reclaim 后未二次失败的路径，还会改变右尾复利。

### K线视觉复核

- `jm2205.DCE long 2022-01-06` 和 `lh2205.DCE short 2022-02-17` 是接近 Stage866 理想形状的事件：先 0.5R stop，reclaim 后又 retry fail；但只有 `2/9`。
- `jm2101.DCE long 2020-11-26`、`OI009.CZCE long 2020-05-18` 等事件显示：先 stop 后仍能 reclaim，且没有二次失败；禁重试会把这类可恢复结构错杀。
- `sp2005.SHFE`、`FG009.CZCE` 这类 stop 后不 reclaim 的事件本身不需要 no-retry 规则，C9 原本就不会重试；把它们纳入 high-heat 规则不产生有效增益。
- 人眼复核结论与数据一致：高热不是“错”的充分条件；错的是极窄的二次失败路径，但这个路径在实时上不能用事后标签直接识别。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_report_stage867_stage866_high_heat_no_retry_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_summary_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_comparison_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_curve_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_trades_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_entry_risk_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_entry_candidates_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_trade_events_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_intraday_events_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_stop_retry_events_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_closed_lots_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_event_summary_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_path_chart_stage867_stage866_high_heat_no_retry_engine_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_atlas_manifest_stage867_stage866_high_heat_no_retry_engine_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_atlas_page001_stage867_stage866_high_heat_no_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_atlas_page002_stage867_stage866_high_heat_no_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_atlas_page003_stage867_stage866_high_heat_no_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_atlas_page004_stage867_stage866_high_heat_no_retry_engine_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage867_stage866_high_heat_no_retry_engine_decision_stage867_stage866_high_heat_no_retry_engine_v1.json`

## 结论

- 本阶段结论：`stage867_high_heat_no_retry_not_promoted`。
- 是否进入下一步：高热 stop-first no-retry 这一分支不进入下一步，不进入正式候选，不触发正式 A/B。
- 下一步：
  - 不继续扫 `90%`、`0.5R`、reclaim 时间窗、重试次数、品种、方向、年份。
  - 不把 Stage866 的 `retry_failed_only_no_retry` 代理包装成实盘规则，因为那是未来信息。
  - 若继续本研究线，必须换一个第一性、实时可观测的状态变量；例如在二次尝试前要求另一个独立的价格结构确认，并接受更差成交价，而不是在原入场价机械重试/机械不重试之间调阈值。

## 过拟合反思

- 运行前判断：否。原因是只测试一个从 Stage866 得出的冻结、实时可执行近似，不做阈值扫描。
- 运行后判断：本次实现本身不是过拟合；但如果继续救 `90%` 阈值、`0.5R`、时间窗、品种/方向过滤，就会进入过拟合。
- 原因：结果失败不是因为参数没扫细，而是因为实时可观测变量不够区分“会二次失败的 reclaim”和“可恢复的 reclaim”。继续用小参数补这一点，本质是在拟合 9 个事件。

## 继续价值反思

- 运行前判断：有继续价值。Stage866 的 4 笔 narrow proxy 值得一次真实引擎反证。
- 运行后判断：高热 no-retry 分支没有继续价值；更大的“分钟级实时止损和有限重试”研究线仍有价值。
- 原因：C11 确实降低 max broker10，但以 `-2,864,254.9` 期末权益、`-0.4895pp` 回撤恶化和 `-0.0282` Sharpe 损失为代价。它不是穿越周期的规则，更像事后代理向实时规则落地时暴露出的信息不足。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage043 否决结论，并停止高热 no-retry 阈值分支。
- 是否更新 `research/registry.md`：否，本线未变更归属。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、不是路线合并、不是正式候选、也没有触发正式 A/B。
