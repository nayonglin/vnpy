# Stage015 Stage839 未覆盖失败交易分钟K法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 20:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据分析 + K线视觉法证；不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。有一个 H3 lot-level 线索，但还不是可推广策略。
- 是否触发A/B：否。没有新版本达到接入正式版、与 Stage372/第78基准结合或正式 A/B 的标准。

## 外部调研与判断

- 参考资料：
  - CME Position and Risk Management：期货交易风险管理应围绕仓位、止损、风险承受度和交易计划。
  - CME/交易所保证金资料：保证金与风险会随品种、波动和持仓变化，不应把名义仓位等同于固定风险。
  - GitHub/开源日内回测参考：常见模块是 stop loss、take profit、opening range、breakeven/trailing stop，未找到可直接复制到本线的成熟规则。
- 我的判断：Stage834 已反证 OR15 确认会误伤右尾，本阶段不继续 OR 形状；应拆 C2 未覆盖失败，看 `target_first` 后回吐、`neither` 无进展且收盘逆向、以及 0.5R fail-fast 是否有低自由度、实时可执行线索。不能按产品、年份或单笔图形补丁化。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage839_stage825_uncovered_failure_kline_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `PER_PAGE=4`
  - `MAX_ATLAS_PAGES=8`
  - H1：`target_first_breakeven_guard`
  - H2：`neither_adverse_entryday_close_exit`
  - H3：`120m_half_r_failfast_exit`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：复用 Stage825 `2018-01-01 -> 2026-05-29` 的 Stage819 baseline closed lots 与入场日分钟特征。
- 账户规模：Stage819 候选 30w 口径。
- 成本口径：本阶段只做 lot-level gross 诊断；H1/H2/H3 的 delta 不含完整换手成本、资金联动、组合路径和再开仓影响。
- 样本过滤：
  - 全部 baseline closed lots：`341`。
  - 亏损 lot：`179`。
  - C2 可覆盖的 `entry_day_first_1p0r_outcome=stop_first` 亏损：`43`。
  - C2 未覆盖亏损：`136`。
  - C2 未覆盖且有入场日分钟证据的亏损：`70`。
  - C2 未覆盖但缺入场日分钟数据的亏损：`66`。
- 策略/归因口径：
  - `c2_shape_stop_first`：C2 已覆盖形状，作为对照。
  - `uncovered_neither_no_1r_entryday`：入场日既未先到 +1R 也未先到 -1R。
  - `uncovered_target_first_then_later_loss_risk`：入场日先到 +1R，但最终仍转亏或未守住右尾。
  - `uncovered_missing_minutes`：没有入场日分钟K，不能作为分钟规则证据。

## 结果

- 期末权益：不适用，本阶段未重跑组合权益曲线。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 全部 `341` 笔 baseline closed lots 总 PnL `28,171,880`。
  - 全部亏损 `179` 笔，亏损合计 `-32,489,020`。
  - C2 `stop_first` 可覆盖亏损 `43` 笔，亏损 `-14,784,145`。
  - C2 未覆盖亏损 `136` 笔，亏损 `-17,704,875`。
  - C2 未覆盖且分钟可测亏损 `70` 笔，亏损 `-11,725,485`。
  - C2 未覆盖但缺分钟亏损 `66` 笔，亏损 `-5,979,390`。
  - `uncovered_neither_no_1r_entryday`：`87` 笔，亏损笔 `45`，总 PnL `3,260,580`，亏损 PnL `-8,701,215`，赢家 PnL `11,961,795`，说明这个桶不能简单全砍。
  - `uncovered_target_first_then_later_loss_risk`：`91` 笔，亏损笔 `25`，总 PnL `36,237,740`，亏损 PnL `-3,024,270`，赢家 PnL `39,262,010`，说明 +1R 后保护止损极易误伤右尾。
  - H1 `target_first_breakeven_guard`：影响 `22` 笔，gross delta `-1,000,420`；虽然救亏损 `+1,368,780`，但误伤赢家 `-2,369,200`，直接否决。
  - H2 `neither_adverse_entryday_close_exit`：影响 `44` 笔，gross delta `+737,350`；救亏损 `+4,476,845`，误伤赢家 `-3,694,495`，线索偏弱，不直接进入引擎。
  - H3 `120m_half_r_failfast_exit`：影响 `57` 笔，gross delta `+3,461,542.4`；救亏损 `+8,526,721.6`，误伤赢家 `-5,032,679.2`，且真正未覆盖亏损只影响 `13` 笔。它是当前最强诊断线索，但不是 clean rule。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_report_stage839_stage825_uncovered_failure_kline_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_summary_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_candidate_diagnostics_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- bucket_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_bucket_stats_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- subshape_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_subshape_stats_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- top_uncovered_losses：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_top_uncovered_losses_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- bucket_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_bucket_chart_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_atlas_manifest_stage839_stage825_uncovered_failure_kline_forensics_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page001_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page002_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page003_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page004_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page005_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page006_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page007_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_uncovered_atlas_page008_stage839_stage825_uncovered_failure_kline_forensics_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage839_stage825_uncovered_failure_kline_forensics_decision_stage839_stage825_uncovered_failure_kline_forensics_v1.json`

## 结论

- 本阶段结论：`stage839_uncovered_failure_no_single_clean_rule_yet`。C2 没覆盖的亏损不来自单一形状：一半左右缺分钟证据，`neither` 桶中赢家也很强，`target_first` 桶更是主要右尾来源。
- 是否进入下一步：H1 否决；H2 暂不进引擎；H3 可作为唯一一次冻结真实引擎候选，但必须预声明“不扫 15/30/60/120，不扫 0.4/0.6R，不加产品/年份过滤”，且先承认它误伤赢家很重。
- 下一步：若继续做真实引擎，建议 Stage016 只测一个 C7：`C4 + 120m 0.5R fail-fast no-retry`，目的不是直接推广，而是验证 lot-level gross 线索在组合资金联动后是否仍有价值；如果失败，停止 fail-fast 时间窗路线，回到视觉分类或数据补齐。

## 过拟合反思

- 运行前判断：低到中。规则形状来自既有 Stage825 预声明特征和常见日内风控形状，但这次是在已知失败集合上做法证。
- 运行后判断：Stage839 本身不是过拟合；如果直接把 H3 当候选推广或继续扫窗口/倍数，就是过拟合。
- 原因：H3 的收益来自已知样本里的 lot-level gross delta，且 winner hurt 很大；真实价值必须通过冻结引擎验证，而不是继续调参。

## 继续价值反思

- 运行前判断：有价值。Stage014 后必须回到分钟K主线，明确 C2 未覆盖左尾到底在哪里。
- 运行后判断：仍有价值，但只剩窄门：H3 可做一次冻结真实引擎验证；H1/H2 暂不值得推进。
- 原因：未覆盖失败有 `70` 笔、`-11,725,485` 的分钟可测亏损，说明分钟层仍有研究对象；但 `missing_minutes` 和强右尾误伤说明不能简单做过滤器。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
