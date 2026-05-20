# Stage002 首日失败归因

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：day
- 记录时间：2026-05-15 14:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage001 原始边际失败后的归因分析
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TradingMetrics Marubozu：`https://docs.tradingmetrics.com/en/technical-analysis/trading-patterns/candlestick-patterns/special-patterns/marubozu`
  - RobustTrader Marubozu：`https://therobusttrader.com/marubozu-candlestick-pattern/`
  - GitHub Candlestick Patterns：`https://github.com/xomarquez27/Candlestick_Patterns`
- 我的判断：
  - 外部资料仍然支持“无影线/Marubozu 代表单边力量”，但也反复强调必须结合市场结构、后续确认、成交量或支撑阻力。
  - 本阶段不把这些资料直接转成过滤器，因为 Stage001 样本只有 86 笔开仓，先归因失败结构比直接加趋势/量能过滤更稳。
  - 当前亏损更像开盘追多后的首日反身性问题，而不是移动止损持仓逻辑的主要问题。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_no_lower_shadow_swing_failure_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG = no_lower_shadow_swing_failure_attribution_v1`
  - 对开仓事件按跳空幅度、初始风险距离、入场日振幅、20日涨跌、信号日量比、品种、板块、年份做归因。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage001，2020-01-01 到 2026-04-30。
- 账户规模：500,000。
- 成本口径：继承 Stage001 回测成交与滑点结果。
- 样本过滤：只分析 Stage001 已生成的 86 笔实际开仓事件；候选跳过原因单独统计。
- 策略/归因口径：
  - 将退出原因为 `long_initial_stop` 的事件定义为首日/初始止损失败组。
  - 其余 `long_trailing_stop`、`long_first_day_half_exit`、`rollover_forced_exit` 归为其他组。
  - 对比 `entry_day_open_to_low_r`、`entry_gap_vs_signal2_close_pct`、`entry_risk_distance_pct`、`entry_day_range_pct`、`pre20_return_pct`、`signal2_volume_ratio_20d` 等特征。

## 结果

- 期末权益：`463,825`（Stage001 原始回测）
- 总收益：`-7.2350%`（Stage001 原始回测）
- 最大回撤：`-13.5818%`（Stage001 原始回测）
- Sharpe：`-0.4146`（Stage001 原始回测）
- 总滑点：`21,130`（Stage001 原始回测）
- 总交易次数：`207`（Stage001 原始回测）
- 胜率：`23.2558%`（Stage001 原始回测）
- 其他关键指标：
  - 开仓事件：`86`
  - 首日/初始止损事件：`33`，占比 `38.37%`
  - 首日/初始止损净亏：`-80,505`
  - 非首日止损事件合计净盈亏：`44,330`
  - 首日止损组平均 `entry_day_open_to_low_r`：`3.1925`
  - 其他组平均 `entry_day_open_to_low_r`：`0.4585`
  - 首日止损组平均 `entry_gap_vs_signal2_close_pct`：`-0.1037%`
  - 其他组平均 `entry_gap_vs_signal2_close_pct`：`0.0694%`
  - 年度最差：2022 年 `-15,870`，首日止损率 `58.33%`
  - 年度唯一明显为正：2025 年 `17,285`，但首日止损率仍有 `50.00%`
  - 板块亏损集中：`chemicals_building` `-18,645`、`black_ferrous` `-10,975`、`precious_nonferrous` `-6,665`
  - 候选跳过：`risk_budget_below_one_contract` 17、`rollover_between_signal_and_entry` 6、`entry_open_not_above_stop` 3

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_report_no_lower_shadow_swing_failure_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_summary_no_lower_shadow_swing_failure_attribution_v1.json`
- events：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_events_no_lower_shadow_swing_failure_attribution_v1.csv`
- feature_contrast：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_feature_contrast_no_lower_shadow_swing_failure_attribution_v1.csv`
- bucket_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_bucket_summary_no_lower_shadow_swing_failure_attribution_v1.csv`
- product_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_product_summary_no_lower_shadow_swing_failure_attribution_v1.csv`
- sector_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_sector_summary_no_lower_shadow_swing_failure_attribution_v1.csv`
- year_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_year_summary_no_lower_shadow_swing_failure_attribution_v1.csv`
- skip_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_failure_attribution_skip_summary_no_lower_shadow_swing_failure_attribution_v1.csv`

## 结论

- 本阶段结论：
  - Stage001 的核心亏损来自第三天开盘后向下回撤直接打初始止损，而不是后续移动止损拖累。
  - 原始形态里确实存在一部分可盈利波段，因为非初始止损事件合计为正；但原始开盘入口对首日反向波动过敏，风险收益被 33 笔初始止损吞掉。
  - `pre20_return_pct` 为正的事件更容易亏，说明连续无下影线上涨发生在短期已有涨幅后，可能带有追高/买盘衰竭特征。
  - 成交量不是简单越高越好：`signal2_volume_ratio_20d` 的 `1.2~2x` 桶为正，但 `0.8~1.2x`、`2~3x`、`>3x` 均为负，不能直接上量能过滤。
- 是否进入下一步：谨慎进入下一步，只做执行反事实，不做大网格参数搜索。
- 下一步：
  - 做“第三天不开盘追入，改为回踩信号2低点/中位/收盘附近才入场”的反事实，不作为实盘规则，只看是否能解释首日止损。
  - 做“入场日首日止损是否放到信号1低点或两日低点”的风险结构反事实，同时观察手数下降后的收益质量。
  - 若反事实仍无法显著降低初始止损亏损，则停止该线，保留经验为“无下影线原始开盘追多无边际”。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段没有优化参数，也没有选择性修改策略规则，只拆解 Stage001 固定规则的失败来源。
  - 最大过拟合风险来自下一步若直接按最赚钱分桶删样本；因此下一步只能做第一性原理反事实，不能把 86 笔小样本当成筛选器训练集。

## 继续价值反思

- 运行前判断：仍有价值。
- 运行后判断：有价值但降级为执行机制验证。
- 原因：
  - 原始版本整体为负，不能升级，也不能接第78。
  - 非初始止损事件合计为正，说明这条线不是完全随机噪声；但真正有价值的问题已经从“形态是否有边际”变成“开盘追多是不是错误执行”。
  - 如果执行反事实不能解释初始止损，应该停止，而不是继续添加趋势、成交量、RSI 等过滤器硬救。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage002 归因结论。
- 是否更新 `research/registry.md`：是，更新最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是失败归因，不是重要突破、正式候选或跨线合并。
