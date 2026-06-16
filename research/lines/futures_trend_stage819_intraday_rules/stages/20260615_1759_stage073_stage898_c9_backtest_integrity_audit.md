# Stage073 Stage898 C9 回测可信度独立审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 17:59`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读可信度审计 + 滚动回测分钟源修正重跑；不改 C9 策略逻辑、不连接 CTP、不调用下单。
- 是否重要突破：是，发现并修复 Stage896/897 滚动脚本使用旧分钟源的问题，同时确认 C9 本体仍有 8 笔开仓 entry-day 分钟缺口。
- 是否触发A/B：否。审计失败，不进入正式候选或 A/B。

## 外部调研与判断

- 参考资料：Backtrader order execution 文档强调 OHLC 触发与真实成交之间存在撮合假设；QuantStart 的回测偏差文章把 look-ahead、优化/数据挖掘列为核心风险；Bailey/Lopez de Prado 的 Deflated Sharpe Ratio 论文指出多重试验会抬高历史表现预期。
- 我的判断：C9 不能表述为“无偏差的实盘级分钟回测”。它是日线组合引擎上叠加入场日分钟 stop/retry 的路径增强，可信度高于纯日线止损假设，但仍低于完整分钟/tick 撮合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/audit_qmt_roll_stage898_c9_backtest_integrity.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage896_c9_vs_official_halfyear_rolling3y.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage897_c9_janjun_rolling1y.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无策略参数修改；仅将 Stage896/897 的 C9 分钟源从旧 `s825._load_minute_bars` 改为 Stage861 full minute bars。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - Stage863 全周期：`2018-01-02 -> 2026-05-29`
  - Stage896 3 年滚动：`2020-01-01 -> 2026-05-29`，每半年起点
  - Stage897 1 年滚动：`2018-01-01 -> 2026-05-29`，每年 1 月/6 月起点
- 账户规模：C9 `300,000`；官方对照 Stage372 `200,000`
- 成本口径：沿用仓库 vn.py 组合回测费率、滑点、保证金口径；未新增成本假设。
- 样本过滤：滚动窗口按完整窗口和 partial 分开统计。
- 策略/归因口径：C9 = Stage847 `C4 + 0.5R stop + 原入场价 reclaim 后重试一次`；审计不改策略。

## 结果

- Stage898 审计：
  - 指标复算检查：`225`
  - 指标复算失败：`0`
  - P0 fail：`1`
  - P1 watch：`3`
  - Stage861 full minute bars：`1,479,592`
  - Stage861 symbols：`216`
  - Stage819 基准 entry-day missing：`0`
  - C9 开仓 entry-day missing：`8/384`
  - 旧 Stage825 分钟源重复 rows：`662,690`
  - 旧 Stage825 分钟源重复 keys：`331,345`
  - 旧 Stage825 分钟源 OHLC 冲突 keys：`330,875`
  - C9 stop/retry 合成成交：expected `197`，actual `197`，diff `0`
- Stage896 full-minute 修正重跑，完整 3 年窗口：
  - C9 positive：`7/7`
  - C9 median return：`479.2947%`
  - C9 worst DD：`-56.6137%`
  - C9 median Sharpe：`1.7436`
  - C9 peak broker10：`106.6510%`
  - 官方 positive：`7/7`
  - 官方 median return：`259.6375%`
  - 官方 worst DD：`-39.1172%`
  - 官方 peak broker10：`78.5348%`
- Stage897 full-minute 修正重跑，完整 1 年窗口：
  - positive：`13/15`
  - negative windows：`2018_01_to_2018_12_31 = -4.9218%`，`2018_06_to_2019_05_31 = -3.6223%`
  - median return：`60.8912%`
  - worst 1Y return：`-4.9218%`
  - worst DD：`-35.4203%`
  - median Sharpe：`1.5313`
  - peak broker10：`95.8771%`
- Stage863 C9 原全周期结果仍可复算：
  - 期末权益：`50,637,144.6`
  - 总收益：`16,779.0482%`
  - 最大回撤：`-42.6313%`
  - Sharpe：`1.6312`
  - 总滑点：`3,607,030`
  - 总交易次数：`786`
  - 胜率：`53.5299%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_report_stage898_c9_backtest_integrity_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_summary_stage898_c9_backtest_integrity_audit_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_findings_stage898_c9_backtest_integrity_audit_v1.csv`
- coverage gaps：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_coverage_gaps_stage898_c9_backtest_integrity_audit_v1.csv`
- metric recompute：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage898_c9_backtest_integrity_audit_metric_recompute_stage898_c9_backtest_integrity_audit_v1.csv`
- Stage896 修正后 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_report_stage896_c9_vs_official_halfyear_rolling3y_v1.md`
- Stage897 修正后 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_report_stage897_c9_janjun_rolling1y_v1.md`

## 结论

- 本阶段结论：独立 agent 的关键质疑成立。旧 Stage896/897 滚动结论不可作为最终验证；已修正为 Stage861 full-minute 口径并重跑。修正后 C9 仍有右尾收益，但 3 年窗口最差回撤达到 `-56.6137%`，且 1 年窗口不是年年正收益。
- 数据可信结论：当前不能说 C9 回测“没有任何偏差”。核心指标内部复算通过，但 C9 本体仍有 `8` 笔开仓 entry-day 缺分钟，触发代码在无 bars 时会跳过日内规则。
- 是否进入下一步：是，但下一步不是优化参数，而是补齐这 8 个 exact contract/date 分钟数据，并重跑 Stage863/896/897/898。
- 下一步：补齐 `MA905.CZCE 2019-03-04`、`au1912.SHFE 2019-08-06`、`CF009.CZCE 2020-05-12`、`CF009.CZCE 2020-07-10`、`rb2101.SHFE 2020-09-04`、`FG201.CZCE 2021-09-13`、`fu2205.SHFE 2022-02-25`、`SA209.CZCE 2022-07-07` 的分钟K；重建 Stage861 full bars 后重跑。

## 过拟合反思

- 运行前判断：否，本阶段目标是审计可信度，不调参、不寻找更好收益。
- 运行后判断：审计本身不是过拟合；但 C9 研究过程仍有事后筛选/多次试验风险，滚动验证只能部分缓解。
- 原因：本阶段发现的是数据链路问题和口径问题，不是收益优化；同时不能把已知历史上筛出来的 C9 当成天然 out-of-sample。

## 继续价值反思

- 运行前判断：有价值，因为用户关心的核心不是能不能接受回撤，而是数据是否可信。
- 运行后判断：仍有价值，而且必须继续到补数重跑。
- 原因：当前已定位到明确数据缺口和旧源污染，补齐后可以让 C9 的收益/回撤讨论建立在更干净的输入上。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage898 可信度结论。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这不是正式候选或跨线合入，但最终若补数后推翻/确认 C9，应再写重要摘要。
