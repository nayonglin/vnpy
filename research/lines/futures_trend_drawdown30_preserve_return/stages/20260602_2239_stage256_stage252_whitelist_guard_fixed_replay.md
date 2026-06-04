# Stage256 Stage252 白名单闸门修复重放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 22:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：工程正确性重放；固定 Stage252 `dynamic_prevtop6_r050_pc15_maxpos3`，不扫 `TopN/risk/cap/maxpos/相关阈值`。
- 是否重要突破：是，确认年度白名单按下一真实成交窗口重验后语义可修复，但材料性仍不足。
- 是否触发A/B：否。本阶段不是新 alpha 候选，只是修复/验证 Stage252 既有候选的可执行语义。

## 外部调研与判断

- 参考资料：
  - AQR Trend Following / managed futures 分散化框架：https://www.aqr.com/insights/trend-following
  - Rob Carver / pysystemtrade 多品种相关性与 instrument diversification multiplier 工程框架：https://github.com/pst-group/pysystemtrade 和 https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md
- 我的判断：
  - 多品种分散与年度选品方向仍有第一性原理价值，但必须按真实成交窗口而不是信号日来判断当年白名单。
  - Stage255 的 `bu.SHFE` 问题本质是：`2021-12-31` 收盘信号允许，但下一真实成交窗口是 `2022-01-04`，此时 2022 白名单已经不允许；实盘应在成交前重验或取消。
  - 语义修复后，Stage252 top6 的增量仍只有几万级别，不足以作为部署增强。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage556_stage252_whitelist_guard_fixed_replay.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage556_stage252_whitelist_guard_fixed_replay.py`
- 删除脚本：无。
- 新增参数：
  - `ai_product_pool_use_next_trade_date_for_entry=False`，默认关闭；Stage556 固定开启。
- 修改参数：
  - AI product pool 的 `eval_date` 查找从 `searchsorted(..., side="left") - 1` 改为 `side="right" - 1`，使 `eval_date` 当天生效。
  - Stage556 中年度白名单按预计下一交易日成交窗口重验。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-17`。
- 账户规模：Stage526 主账户；Stage252 top6 为 Stage526 核心不替换 + `11.5万` 非核心 sleeve。
- 成本口径：正常成本，并复核 `1x/2x/3x` 成本压力。
- 样本过滤：仅固定 `dynamic_prevtop6_r050_pc15_maxpos3`。
- 策略/归因口径：
  - `flat_entry/reverse_entry/regular_add/donchian_add` 等新增产品风险路径必须按预计下一交易日白名单通过。
  - `rollover_reopen` 作为已有持仓换月自然延续，不强制年初平仓。
  - 严格材料性沿用 Stage255：收益相对 Stage526 至少 `100.5%`，回撤/Ulcer/63日/126日左尾有足够改善，3x 成本 DD40 通过，新增交易效率过线。

## 结果

- A Stage526：
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - Ulcer：`14.4691`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 胜率：非零日胜率 `53.6330%`
- C Stage256 fixed top6：
  - 期末权益：`23,423,510`
  - 总收益：`3708.7008%`
  - 相对 Stage526：`100.2373%`
  - 最大回撤：`-36.0729%`
  - Sharpe：`1.6433`
  - Ulcer：`14.3808`
  - 总滑点：`1,346,430`
  - 总交易次数：`1,109`
  - 胜率：非零日胜率 `53.7130%`
  - 卫星PnL：`54,005`
- 语义复核：
  - 非白名单产品级新开/加仓：`0`
  - `2021-12-31 bu.SHFE` 原本会在下一窗口成交；修复后 entry snapshot 显示 `candidate_status=skipped`、`skip_reason=ai_product_pool_blocked`、`ai_product_pool_entry_effective_date=2022-01-04`、`ai_product_pool_signal_date=2022-01-01`。
- 严格材料性：
  - `return_relative_vs_stage526_pct=100.2373`，未达 `100.5`。
  - `total_return_improvement_pp=8.7813`，未达 `18.5`。
  - `max_dd_improvement_pp=0.1941`，未达 `0.5`。
  - `ulcer_improvement_pp=0.0883`，未达 `0.25`。
  - `holding63_p05_improvement_pp=0.2735`，未达 `0.5`。
  - `holding126_p05_improvement_pp=0.2958`，未达 `0.5`。
  - `cost3_dd40_pass=-41.8307`，未达 `>=-40`。
  - `added_trade_count=204`，未通过。
  - `satellite_pnl_per_added_trade=264.7304`，未达 `500`。
  - `slippage_to_satellite_pnl_pct=7.8511`，通过但不足以抵消材料性失败。
- 视觉复盘：
  - 主权益曲线几乎完全重合，右上权益差最高约 `6万+`，到 2026 回落到约 `5.4万`。
  - 3/6个月 p05 条形图仅略微右移，改善幅度肉眼很小。
  - 1x/2x 成本回撤略优于 Stage526，但 3x 成本仍在 `-40%` 左侧，未形成厚安全垫。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_report_stage556_stage252_whitelist_guard_fixed_replay_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_decision_stage556_stage252_whitelist_guard_fixed_replay_v1.json`
- strict decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_strict_decision_stage556_stage252_whitelist_guard_fixed_replay_v1.json`
- strict materiality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_strict_materiality_stage556_stage252_whitelist_guard_fixed_replay_v1.csv`
- semantic violations：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_semantic_violations_stage556_stage252_whitelist_guard_fixed_replay_v1.csv`
- entry snapshots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_entry_snapshots_stage556_stage252_whitelist_guard_fixed_replay_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_chart_stage556_stage252_whitelist_guard_fixed_replay_v1.png`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_combined_daily_stage556_stage252_whitelist_guard_fixed_replay_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage556_stage252_whitelist_guard_fixed_replay_positions_stage556_stage252_whitelist_guard_fixed_replay_v1.csv`

## 结论

- 本阶段结论：`semantic_fixed_materiality_insufficient_keep_paper_only`。
- 是否进入下一步：不进入部署候选；年度 top6 只保留为 paper/经验。
- 下一步：
  - 不再救 Stage252/256 的 `TopN/risk/cap/family cap/相关阈值/maxpos`。
  - “选对品种”的继续价值应转向 forward 外生状态账本，或寻找更强、低自由度、能提前识别年度趋势土壤的事前特征。
  - 若后续继续扩池，必须先证明信号强度足够，而不是用微小 sleeve edge 叠执行复杂度。

## 过拟合反思

- 运行前判断：否。Stage256 是工程语义修复，不调选品参数。
- 运行后判断：否。修复成功后仍按严格材料性降级，没有为了保留候选而放宽阈值。
- 原因：本阶段只修真实执行偏差，且发现增量不足后停止路线；继续围绕这条薄 edge 调小数才会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage255 找到的是实盘语义缺陷，必须做一次工程正确性重放。
- 运行后判断：Stage252/256 子路线主动继续价值低，总目标仍有价值。
- 原因：语义问题已解决，但改善幅度仍不到部署材料性；总目标应转向更强外生状态或低保证金独立收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态为 Stage256。
- 是否更新 `research/registry.md`：是，摘要替换 Stage255。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段是年度选品路线的重要收束。
