# Stage058 Stage882 C9 `+0.5R` 顺势加仓真实引擎审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 07:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结真实组合引擎审计；不改 Stage372 正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否，真实引擎把 Stage881 强代理线索反证为“收益高但不可执行风险失控”。
- 是否触发A/B：否；本阶段是 Stage819 候选研究线内的 C9/C16 隔离验证，不是正式 Stage372 A/B/C。

## 外部调研与判断

- 参考资料：
  - `https://github.com/vnpy/vnpy`
  - Turtle/trend-following pyramiding 规则资料
  - `https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf`
  - CME open interest / futures risk management 教育资料
- 我的判断：
  - 顺势加仓的一阶逻辑成立：只给已经盈利的仓位加仓，并给新增风险设置独立止损。
  - 但趋势加仓不是免费 alpha，它本质上把路径凸性和保证金压力同时放大；必须用真实组合资金、成交、复利和 broker10 路径检验。
  - Stage881 的代理增量 `+34,513,422.1` 足够大，值得做一次真实引擎；但本阶段必须冻结规则，不允许为了修风险再扫 `0.25R/0.75R`、加仓比例、止损位置、品种、方向或年份。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage882_stage881_progress_pyramid_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_stage882_progress_pyramid_once`，默认关闭，仅 C16 profile 打开。
  - `stage882_pyramid_progress_r = 0.5`
  - `stage882_pyramid_add_volume_multiplier = 1.0`
  - 新增仓止损：原始入场价。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-05-29`
- 账户规模：Stage819 候选 `30w` 口径。
- 成本口径：沿用现有真实组合引擎成本；C16 新增合成开仓/平仓会进入交易次数、滑点、权益和保证金路径。
- 样本过滤：
  - 读取 Stage861 full minute bars：`1,479,592` 根，`216` 个合约。
  - 对照使用 Stage863 既有 C4/C9 同口径输出。
- 策略/归因口径：
  - B：C9，即 Stage847 C4 + `0.5R` stop/retry once。
  - C：C16，即 C9 保持不变；若入场日先触达 `+0.5R` progress 而不是先触达 `-0.5R` adverse，则按 `+0.5R` 合成同手数加仓一次。
  - 新增仓止损为原始入场价；入场日回打即合成平仓；否则作为普通仓位进入后续日线退出路径。
  - 不扫描 progress R、加仓比例、止损位置、品种、方向、年份或分钟窗口。

## 结果

- 期末权益：`134,885,396.7`
- 总收益：`44,861.7989%`
- 最大回撤：`-61.6881%`
- Sharpe：`1.5740`
- 总滑点：`8,279,150`
- 总交易次数：`1,045`
- 胜率：`51.6784%`
- 其他关键指标：
  - C9 期末权益：`50,637,144.6`
  - C16 相对 C9 期末权益增量：`+84,248,252.1`
  - C16 相对 C9 最大回撤恶化：`-19.0568pp`
  - C16 相对 C9 Sharpe 下降：`-0.0572`
  - C16 max broker10：`203.4450%`，C9 为 `114.3987%`
  - C16 p95 broker10：`80.1650%`，C9 为 `61.5244%`
  - pyramid events：`171`
  - pyramid open events：`97`
  - pyramid stopped events：`74`
  - pyramid add volume：`52,053`
  - synthetic open trades：`171`
  - synthetic closed lots：`183`
  - synthetic lot realized PnL：`56,117,235.0`

### 对照表

| arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | `46,015,805.0` | `15,238.6017%` | `-47.1915%` | `1.5996` | `3,023,410` | `678` | `53.0630%` | `111.4255%` |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | `50,637,144.6` | `16,779.0482%` | `-42.6313%` | `1.6312` | `3,607,030` | `786` | `53.5299%` | `114.3987%` |
| C16 `stage882_stage819_c9_progress_pyramid_once` | `134,885,396.7` | `44,861.7989%` | `-61.6881%` | `1.5740` | `8,279,150` | `1,045` | `51.6784%` | `203.4450%` |

### 路径诊断

- C16 最大回撤峰谷：`2020-09-01 -> 2020-10-15`，权益 `2,185,111.9 -> 837,158.3`，回撤 `-61.6881%`。
- C9 最大回撤峰谷：`2022-03-09 -> 2022-06-29`，权益 `21,071,895.4 -> 12,088,682.6`，回撤 `-42.6313%`。
- 视觉路径图显示：C16 权益右尾显著抬高，但 2020 年先发生深水下与 broker10 `203.4450%` 峰值，已经越过实盘生存边界。
- K线 atlas 显示：
  - 未止损样本中，绿色加仓线通常出现在价格先给出 `+0.5R` 后，后续趋势延展解释了右尾增厚。
  - 止损样本中，价格触达 `+0.5R` 后同日回打原始入场价，新增仓按红线止损，但账户层总体杠杆仍被显著放大。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_report_stage882_stage881_progress_pyramid_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_summary_stage882_stage881_progress_pyramid_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_comparison_stage882_stage881_progress_pyramid_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_curve_stage882_stage881_progress_pyramid_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_trades_stage882_stage881_progress_pyramid_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_entry_risk_stage882_stage881_progress_pyramid_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_entry_candidates_stage882_stage881_progress_pyramid_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_trade_events_stage882_stage881_progress_pyramid_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_intraday_events_stage882_stage881_progress_pyramid_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_stop_retry_events_stage882_stage881_progress_pyramid_engine_v1.csv`
- pyramid_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_pyramid_events_stage882_stage881_progress_pyramid_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_closed_lots_stage882_stage881_progress_pyramid_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_event_summary_stage882_stage881_progress_pyramid_engine_v1.csv`
- path_diagnostics：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_path_diagnostics_stage882_stage881_progress_pyramid_engine_v1.csv`
- path_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_path_chart_stage882_stage881_progress_pyramid_engine_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_manifest_stage882_stage881_progress_pyramid_engine_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_atlas_page001_stage882_stage881_progress_pyramid_engine_v1.png` 至 `page004`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage882_stage881_progress_pyramid_engine_decision_stage882_stage881_progress_pyramid_engine_v1.json`

## 结论

- 本阶段结论：`stage882_progress_pyramid_true_engine_not_promoted`
- 是否进入下一步：不进入滚动起点、不进入成本压力、不进入正式候选或 A/B。
- 下一步：
  - 停止同手数 `+0.5R` pyramiding 分支。
  - 不继续扫 `0.25R/0.75R/1R`、加仓比例、止损位置、品种、方向或年份。
  - 如果继续研究右尾增厚，只能先回到一阶问题：账户层风险预算如何在右尾参与和 broker10 生存之间分配；不能直接救这个 C16。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本轮不是过拟合，但继续救参会过拟合。
- 原因：
  - 本轮完全冻结 Stage881 预声明规则：`+0.5R`、同手数、原始入场价止损。
  - 没有按年份、品种、方向或阈值筛选。
  - 真实引擎失败的原因不是收益不够，而是回撤、Sharpe 和 broker10 路径不满足实盘生存纪律；继续用小数参数修 `-61.6881%` 回撤会把问题变成历史路径拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：具体 C16 不值得继续；右尾增厚这个大方向仍有抽象价值，但不能沿本形状推进。
- 原因：
  - C16 证明 Stage881 代理不是空信号，确实能大幅放大右尾收益。
  - 但同手数加仓把 broker10 峰值推到 `203.4450%`、最大回撤推到 `-61.6881%`，已经不具备实盘候选意义。
  - 继续价值只在账户级风险预算/资金分层/生存线框架，而不是该分钟加仓规则本身。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage058 结论并关闭本 pyramiding 分支。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段明确不晋级、不触发正式 A/B；保留在本研究线即可。
