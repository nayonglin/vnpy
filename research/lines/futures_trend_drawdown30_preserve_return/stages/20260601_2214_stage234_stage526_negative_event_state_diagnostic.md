# Stage234 Stage526负贡献事件状态诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 22:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage233 后续只读诊断；聚焦 `MA/AP/SA` 负贡献事件共同状态，不改策略。
- 是否重要突破：否。发现可研究线索，但仍是事后诊断，不能直接合入。
- 是否触发A/B：否。本阶段没有新增可接入候选，只生成下一步候选假设。

## 外部调研与判断

- 参考资料：
  - 假突破/whipsaw 常见过滤方向包括 ADX 趋势强度、ATR/Keltner/Donchian 突破质量、RSI/动量确认、多周期一致性。
  - `mlm-trend-following` 等开源趋势框架强调波动过滤和前月合约执行，说明过滤机制要保持工程可执行：https://github.com/amstrdm/mlm-trend-following
  - PyTrendFollow 这类工程样例强调自动换月、回测和实盘接口链路，不支持只靠回测后验标签合入：https://github.com/chrism2671/PyTrendFollow
  - ADX/趋势强度、ATR 突破过滤是常见技术分析工具，但若对单窗口/单品种拟合，容易把趋势策略的少数大收益截掉。
- 我的判断：
  - 这轮不能直接做 “MA/AP/SA 黑名单”，因为 Stage229/233 已经证明产品贡献不是稳定黑名单逻辑。
  - 更有价值的是找跨品种状态。当前最强线索不是 RSI，也不是中长均线 spread，而是“快失败 + 大手数/低相关”这类路径形态。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage534_stage526_negative_event_state_diagnostic.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；新增诊断特征：
  - `rsi_direction_strength`
  - `trend_spread_pct`
  - `price_extension_mid_pct`
  - `price_extension_long_pct`
  - `stop_distance_pct`
  - `fast_fail`
  - `large_delta`
  - `low_corr_or_no_active`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage233 事件账本，覆盖 `2020-01-01` 至 `2026-04-30`。
- 账户规模：沿用 Stage526/Stage233 50万 C3 下单口径与组合账户口径。
- 成本口径：正常成本事件归因；本阶段不重算 2x/3x。
- 样本过滤：
  - 使用 Stage233 的 `165` 个有手数差异事件与 `6` 个无差/整数事件，总事件 `171`。
  - focus 产品：`MA.CZCE/AP.CZCE/SA.CZCE`。
- 策略/归因口径：
  - 只读比较事件特征，不做产品黑名单，不改入场/退出。
  - `fast_fail` 当前定义为事后标签：`edge<0 且 segment_days<=6`，只能作为诊断，不可直接实盘。

## 结果

### 总览

| 指标 | 数值 |
| --- | ---: |
| 决策标签 | `low_corr_fast_fail_possible_followup_probe` |
| 事件数 | 171 |
| focus产品事件数 | 35 |
| focus负贡献事件数 | 24 |
| focus产品总edge | -164,860 |
| focus负贡献edge | -260,700 |
| 全部负贡献edge | -610,515 |
| focus负贡献占全部负edge | 42.7017% |

### 规则探针

| 探针 | 事件数 | edge | 负edge | 正edge | 负事件 | 正事件 | 覆盖负edge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large_delta_fast_fail | 20 | -339,685 | -339,685 | 0 | 20 | 0 | 55.6391% |
| all_fast_fail_low_corr | 40 | -297,440 | -297,440 | 0 | 40 | 0 | 48.7195% |
| focus_fast_fail | 19 | -249,970 | -249,970 | 0 | 19 | 0 | 40.9441% |
| focus_products_only | 35 | -164,860 | -260,700 | 95,840 | 24 | 10 | 42.7017% |
| focus_fast_fail_low_corr | 7 | -122,700 | -122,700 | 0 | 7 | 0 | 20.0978% |

解释：

- 直接按产品过滤会误伤 `95,840` 正 edge，因此产品黑名单仍不成立。
- `large_delta_fast_fail` 和 `all_fast_fail_low_corr` 的诊断表现更干净，但它们依赖 `fast_fail` 事后标签，不能直接实盘。
- 真正值得下一轮验证的是：能否用入场时可见状态提前代理“快失败风险”，例如突破质量、近端波动扩张、开仓前短期趋势延续质量、ATR/K线实体质量等。

### 特征对比

- focus负贡献事件的持仓段中位数 `4` 天，正贡献事件中位数 `10` 天。这是最强结构差异。
- focus负贡献事件的方向 RSI 强度中位数 `19.7970`，正贡献为 `20.4628`，差异很小，不足以单独构成规则。
- focus负贡献的 `trend_spread_pct` 中位数 `1.1491`，正贡献为 `0.7633`，不是“均线 spread 越弱越亏”的简单形态。
- focus负贡献的相关性中位数 `0.2302`，正贡献为 `0.0000`；低相关本身不能解释亏损，必须和快失败/大手数结合看。

### 分组观察

- 最差状态组：
  - `fast_fail=1|low_corr=1|weak_rsi=0|low_spread=0`：20事件，edge `-164,420`，全部为负。
  - `fast_fail=1|low_corr=0|weak_rsi=0|low_spread=0`：7事件，edge `-117,390`，全部为负。
  - `fast_fail=1|low_corr=1|weak_rsi=0|low_spread=1`：12事件，edge `-104,170`，全部为负。
- 产品层：
  - `MA.CZCE` edge `-108,770`，中位持有 `5` 天。
  - `AP.CZCE` edge `-38,390`，中位持有 `5` 天。
  - `SA.CZCE` edge `-17,700`，中位持有 `4` 天。

## 图表视觉复盘

- 图表：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_chart_stage534_stage526_negative_event_state_diagnostic_v1.png`
- 视觉判断：
  - 左上 RSI 散点没有形成清晰分界，红色 focus 负贡献点与其他点混在一起；用 RSI 强度做硬过滤大概率不稳。
  - 右上箱线图很清楚：focus负贡献和其他负贡献的持有段集中在 `3-6` 天，正贡献明显更长，说明“快失败”是核心形态。
  - 左下规则探针中，`large_delta_fast_fail` 和 `all_fast_fail_low_corr` 都是纯负 edge，但这是后验诊断，不能直接用。
  - 右下产品图仍显示 `MA/AP/SA` 拖累，但同时 `jm/OI/hc/ru/lh` 是明显正贡献，说明不能转为产品删减。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_report_stage534_stage526_negative_event_state_diagnostic_v1.md`
- event_features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_event_features_stage534_stage526_negative_event_state_diagnostic_v1.csv`
- feature_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_feature_summary_stage534_stage526_negative_event_state_diagnostic_v1.csv`
- group_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_group_summary_stage534_stage526_negative_event_state_diagnostic_v1.csv`
- rule_probe：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_rule_probe_stage534_stage526_negative_event_state_diagnostic_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_decision_stage534_stage526_negative_event_state_diagnostic_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage534_stage526_negative_event_state_diagnostic_chart_stage534_stage526_negative_event_state_diagnostic_v1.png`

## 结论

- 本阶段结论：不产生可合入版本；发现“快失败 + 大手数/低相关”是下一步值得验证的低自由度方向。
- 是否进入下一步：是，但必须把 `fast_fail` 从事后标签转成入场时可见代理。
- 下一步：
  - 设计一个固定、可实盘的“弱突破/快失败风险代理”候选，优先用已有字段或当日之前的 K 线：突破实体质量、ATR扩张、近5/10日趋势延续、入场价相对中线/长线位置。
  - 先做只读预测力检验：入场时可见代理是否能覆盖 `large_delta_fast_fail/all_fast_fail_low_corr`，且不明显覆盖大正 edge。
  - 通过后才进入真实引擎 A/C，不允许用 `segment_days<=6` 这种未来信息。

## 过拟合反思

- 运行前判断：否。只读诊断，不改规则。
- 运行后判断：否，但风险很高。
- 原因：`fast_fail` 是事后标签，任何直接使用它的规则都是未来函数；本阶段只允许把它当作要预测的现象，而不是策略条件。

## 继续价值反思

- 运行前判断：是。Stage233 指向 `MA/AP/SA` 负贡献共同状态。
- 运行后判断：是。
- 原因：已经从产品拖累收敛到更本质的“快失败/假突破”现象；下一步若能用入场前可见状态预测它，才可能改善短持有体验和成本压力。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage234 诊断结论。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`，因为没有形成默认策略政策变更。
