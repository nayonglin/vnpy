# Stage047 Stage871 Stage870 broker10 路径归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 05:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因和分钟K视觉复盘；读取 Stage870 C4/C9/C13 输出，分解 C13 broker10 恶化的分子/分母来源；不改策略、不改 Stage372 官方正式版、不改 Stage819 官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否，Stage871 不产生新策略版本，也不满足正式候选或 A/B 前置条件。

## 外部调研与判断

- 参考资料：
  - Turtle Trading 原始规则：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 趋势跟随里的组合风险不是单笔入场质量问题，必须拆开组合 heat 的分子和分母：分子是持仓保证金/名义暴露，分母是权益路径。
  - Stage870 的矛盾是“回撤更浅但 broker10 更差”。如果 broker10 更差主要来自权益分母被削低，继续写缩手、过滤或 progress R 小变体会误判因果。
  - 本阶段只做分解和视觉复盘，不生成新规则，不复制任何资料中的固定阈值。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage871_stage870_broker10_path_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage870 输出覆盖的 Stage819 候选全周期。
- 账户规模：沿用 Stage870 C4/C9/C13 组合回测口径。
- 成本口径：沿用 Stage870 既有成本、滑点和 broker10 估算口径。
- 样本过滤：
  - 不按年份、品种、方向筛选。
  - C13 broker10 峰值取 top10；C4/C9/C13 peak dates 取 top10 union。
  - atlas 优先选 C13 相对 C9 broker10 product-direction 正增量且有完整分钟K的 active lots。
- 策略/归因口径：
  - C4：`stage830_stage819_c2_broker10_100_cap`
  - C9：`stage847_stage819_c4_05r_stop_retry_once`
  - C13：`stage870_stage819_c9_progress_confirm_recovery`
  - 分解公式：`C13 broker10 - C9 broker10 = denominator_effect + exposure_effect`。其中 denominator_effect 把 C9 的 broker10 margin 放到 C13 equity 分母上，exposure_effect 再比较 C13 实际持仓保证金分子。

## 结果

### Stage870 源版本结果

| arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | 46,015,805.0 | 15,238.6017% | -47.1915% | 1.5996 | 3,023,410 | 678 | 53.0630% | 111.4255% |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | 50,637,144.6 | 16,779.0482% | -42.6313% | 1.6312 | 3,607,030 | 786 | 53.5299% | 114.3987% |
| C13 `stage870_stage819_c9_progress_confirm_recovery` | 46,668,137.3 | 15,456.0458% | -38.7460% | 1.5783 | 3,344,700 | 753 | 53.4070% | 120.7738% |

### Stage871 分解结果

- C13 top10 broker10 峰值机制：
  - `equity_denominator_compression`：`8/10`
  - `exposure_numerator_expansion`：`1/10`
  - `mixed_or_lower_than_c9`：`1/10`
- C13 top1 峰值 `2020-11-23`：
  - C13 broker10 `120.7738%`，C9 `114.3987%`，差 `+6.3750pp`。
  - C13 equity / C9 equity `0.7842`。
  - C13 broker10 margin 比 C9 少 `178,842.84`，说明当日持仓分子不是更大。
  - denominator effect `+31.4725pp`，exposure effect `-25.0975pp`，净差才是 `+6.3750pp`。
- C13 top2 峰值 `2020-12-01`：
  - C13 broker10 `117.8559%`，C9 `94.3907%`，差 `+23.4652pp`。
  - C13 equity / C9 equity `0.7627`。
  - C13 broker10 margin 比 C9 少 `46,491.72`。
  - denominator effect `+29.3623pp`，exposure effect `-5.8971pp`。
- 唯一明显 exposure expansion 峰值是 `2020-09-09`：
  - C13 broker10 `94.6245%`，C9 `42.4363%`，差 `+52.1883pp`。
  - exposure effect `+38.7034pp`，denominator effect `+13.4848pp`。
  - product-direction 主要来自 `MA.CZCE long` 的 C13-only active exposure（`+69.3983pp`），但这是单个早期路径，不足以写通用规则。

### 累计收益缺口归因

- 到 `2022-04-07` / `2022-07-07` 一带，C13 相对 C9 的权益分母劣势主要来自前序右尾被削掉：
  - `OI long`：C13 - C9 累计 realized PnL `-2,051,060`
  - `sp long`：C13 - C9 累计 realized PnL `-1,839,544`
  - `FG.CZCE long`：C13 - C9 累计 realized PnL `-290,400`
  - `SM.CZCE long`：C13 - C9 累计 realized PnL `-233,580`
- 这说明 Stage870 的 progress-confirm 规则不是“降低风险后保住收益”，而是前面砍掉右尾后，使后面同等或更小保证金暴露落在更低权益分母上。

### K线视觉复核

- summary chart 已复核：C13 top10 broker10 峰值里，多数绿色 denominator effect 明显为正，橙色 exposure effect 多数为负；这与表格一致。
- atlas page001 已复核：
  - `SM101.CZCE long 2020-09-09` 与 `lh2205.DCE short 2022-02-17` 都是 C13 中单笔 broker10 贡献较高的 active lots；K线显示它们不是单纯入场当日错误，而是持仓日内价格有反复，风险来自仓位/分母组合状态。
  - `ru2101.SHFE long 2020-12-01` 显示日内价格推进后仍持仓，C13 broker10 高更多来自账户分母低。
- atlas page002/page003 已复核：所有入选样本均有分钟K，未再混入缺分钟K空白样本。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_report_stage871_stage870_broker10_path_forensics_v1.md`
- peak_dates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_peak_dates_stage871_stage870_broker10_path_forensics_v1.csv`
- active_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_active_lots_stage871_stage870_broker10_path_forensics_v1.csv`
- product_direction：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_product_direction_attribution_stage871_stage870_broker10_path_forensics_v1.csv`
- pair_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_pair_delta_stage871_stage870_broker10_path_forensics_v1.csv`
- decomposition：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_denominator_decomposition_stage871_stage870_broker10_path_forensics_v1.csv`
- cumulative_pnl_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_cumulative_pnl_delta_stage871_stage870_broker10_path_forensics_v1.csv`
- entry_context：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_entry_context_stage871_stage870_broker10_path_forensics_v1.csv`
- summary_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_summary_chart_stage871_stage870_broker10_path_forensics_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_atlas_manifest_stage871_stage870_broker10_path_forensics_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_atlas_page001_stage871_stage870_broker10_path_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_atlas_page002_stage871_stage870_broker10_path_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_atlas_page003_stage871_stage870_broker10_path_forensics_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage871_stage870_broker10_path_forensics_decision_stage871_stage870_broker10_path_forensics_v1.json`

## 结论

- 本阶段结论：`stage871_broker10_worse_mainly_equity_denominator_no_engine`。
- 是否进入下一步：Stage871 不进入真实引擎，不进入正式候选，不触发 A/B。
- 下一步：
  - 停止把 Stage870 的 broker10 恶化解释为“需要更强仓位缩手”或“需要继续调 progress-confirm”。
  - 不扫 progress R、仓位热度阈值、broker10 分档、单品种/方向或年份。
  - 如果继续本线，应回到 C9，而不是 C13，研究 C9 的右尾为什么能覆盖风险；下一步更有价值的是 C9 的“赢家保护/右尾保留 + 独立生存线”只读审计，而不是继续削重入。

## 过拟合反思

- 运行前判断：否。Stage871 是只读因果分解，不生成规则、不扫参数。
- 运行后判断：否。但如果把 `2020-09-09 MA.CZCE long` 或 `2022-07-07 SA/rb` 这些峰值样本写成黑名单、阈值或单品种规则，就是过拟合。
- 原因：top10 中 `8/10` 主要是权益分母压缩，不是当下持仓分子扩大；单个 exposure expansion 样本没有跨周期普遍性，不能作为规则源。

## 继续价值反思

- 运行前判断：有价值。Stage870 留下的核心未解问题就是“回撤更浅但 broker10 更高”，必须先分解原因，才能决定是否继续组合风险治理。
- 运行后判断：Stage871 这条“由 C13 反推仓位规则”的方向没有继续价值；研究线整体仍有价值。
- 原因：C13 的 broker10 恶化多数来自前面少赚导致权益分母低，不是可通过简单当下缩手修复的暴露问题。继续有效方向应回到 C9 的右尾保留机制，寻找不误伤大趋势的外层生存线或赢家保护审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage047 结论，并明确 Stage870/C13 不再作为后续引擎基础。
- 是否更新 `research/registry.md`：否，本线归属未变更。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、不是正式候选、也没有触发正式 A/B。
