# Stage002 连败阈值 3/4/6 多起点鲁棒性验证

- line_id：`futures_trend_loss_streak_threshold_sweep`
- 当前模式：`day`
- 记录时间：`2026-06-08 17:40 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版连败降风险阈值反证验证；不改正式配置。
- 是否重要突破：否；属于重要反证与稳健性审查。
- 是否触发A/B：已按 A/B 前置要求读取 `skills/version-ab-experiment/SKILL.md`；因未通过鲁棒性门槛，未进入正式 A/B。

## 外部调研与判断

- 参考资料：
  - Walk-forward analysis / parameter robustness：`https://quanthop.com/learn/validation-robustness/walk-forward-analysis`
  - Backtest overfitting and robustness：`https://tradingstrategy.ai/docs/learn/backtesting.html`
  - GitHub trend-following position sizing参考：`https://github.com/trustdan/trend-following-backtesting-strategies`
- 我的判断：连败阈值属于仓位管理参数，不能用单条全周期权益曲线定案；必须看多起点、阶段窗口、弱路径窗口和成本压力。GitHub 资料没有可直接复制的期货组合代码，参考价值主要是“固定规则、仓位限制、分段验证”的研究纪律。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage718_loss_streak_threshold_robustness.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `THRESHOLDS=(3,4,6)`
  - `FLOOR_MULTIPLIER=0.1`
  - 25 个季度独立启动窗口：`2020Q1~2026Q1`
  - 阶段窗口：`2020-2021`、`2022-2023`、`2024-2025`、`2026-01-01~2026-04-30`
  - 弱窗口：`2021-05-01~2021-07-31`、`2022-03-09~2022-12-07`
  - 红框诊断窗口：`2025-04-16~2025-07-25`，仅诊断，不用于调参。
- 修改参数：仅运行期替换 `streak_risk_multipliers`，即连续亏损达到阈值后把新开仓风险倍率降为 `0.1`；其余官方 Stage372/20万参数不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：各窗口独立计算，最长为 `2020-01-01~2026-04-30`。
- 账户规模：`200,000`。
- 成本口径：官方回测成本；另输出成本 `1x/2x/3x` 压力表。
- 样本过滤：不按品种、方向、单个年份或截图窗口筛选；红框窗口只作诊断。
- 策略/归因口径：基于 `official_live_stage372_20w_recovery_sleeve` / `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`，只比较连败阈值 `3/4/6`。

## 结果

- 主全周期口径阈值 3：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 保证金峰值 `79.6015%`
  - 强制减仓 `6` 次，平仓手数 `299`
- 主全周期口径阈值 4：
  - 期末权益 `3,976,010`
  - 总收益 `1888.0050%`
  - 最大回撤 `-41.6430%`
  - Sharpe `1.3586`
  - 总滑点 `301,560`
  - 总交易次数 `642`
  - 胜率 `52.2007%`
- 主全周期口径阈值 6：
  - 期末权益 `3,758,300`
  - 总收益 `1779.1500%`
  - 最大回撤 `-44.8384%`
  - Sharpe `1.2723`
  - 总滑点 `303,520`
  - 总交易次数 `673`
  - 胜率 `51.7241%`
- 多窗口鲁棒性：
  - 阈值 3：32 个窗口收益冠军 `15` 次，季度起点收益冠军 `12/25`；回撤冠军 `21` 次，季度起点回撤冠军 `17/25`。
  - 阈值 4：32 个窗口收益冠军 `7` 次，季度起点收益冠军 `5/25`；季度相对阈值 3 的平均收益保持率 `141.0025%`，中位数 `96.3425%`。
  - 阈值 6：32 个窗口收益冠军 `10` 次，季度起点收益冠军 `8/25`；季度相对阈值 3 的平均收益保持率 `162.3984%`，中位数 `96.0517%`。
  - 阈值 3 的季度回撤 `40%` 闸门通过 `24/25`；唯一未通过是 `2020Q3`，最大回撤 `-40.7818%`。
  - 阈值 3 的成本翻倍季度回撤 `40%` 闸门通过 `22/25`。
- 阶段窗口：
  - `2020-2021`：阈值 3 最强，`441.4650% / -24.2699% / Sharpe 2.1114`。
  - `2022-2023`：阈值 4 最强，`34.5025% / -27.3652% / Sharpe 0.6991`；阈值 3 只有 `0.2975%`。
  - `2024-2025`：阈值 6 最强，`136.3500% / -25.4740% / Sharpe 1.3078`；阈值 3 为 `33.2675%`。
  - 弱窗口 `2021` 和 `2022`：阈值 3/4 更防守，阈值 6 更差。
  - 红框诊断 `2025-04-16~2025-07-25`：阈值 4/6 为 `94.7750%`，阈值 3 只有 `3.3200%`；该窗口解释了“局部增长消失”，但不能作为反向调参依据。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_report_stage718_loss_streak_threshold_robustness_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_summary_stage718_loss_streak_threshold_robustness_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_curves_stage718_loss_streak_threshold_robustness_v1.csv`
- robustness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_robustness_stage718_loss_streak_threshold_robustness_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_comparison_vs_threshold3_stage718_loss_streak_threshold_robustness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_decision_stage718_loss_streak_threshold_robustness_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage718_loss_streak_threshold_robustness_chart_stage718_loss_streak_threshold_robustness_v1.png`

## 结论

- 本阶段结论：`threshold3_not_fully_proven`。阈值 3 不是被证明为普适收益最优，但它作为防守闸门有明显价值：全周期强、早期长窗口强、弱窗口更稳、季度回撤冠军最多。
- 是否进入下一步：是，但下一步不应该继续扫阈值小数。
- 下一步：验证“连败阈值 3 + 高质量机会豁免”的机制，即连败后默认降到 `0.1`，但当机会质量足够高时允许正常开仓；质量信号必须预先定义，不能用红框窗口反推。

## 过拟合反思

- 运行前判断：存在过拟合风险。全周期阈值 3 最强可能只是路径依赖，所以必须做多起点和弱窗口反证。
- 运行后判断：阈值 3 的收益普适性未完全证明，不能说“3 就是最优参数”；但阈值 3 的防守价值不是单一窗口偶然。
- 原因：阈值 3 在季度收益冠军只有 `12/25`，未过预设 `13/25` 门槛；但季度回撤冠军 `17/25`，弱窗口也不差，说明它更像风险闸门而非收益增强器。

## 继续价值反思

- 运行前判断：有价值继续，因为连败机制直接影响正式版能否抓住恢复段，同时关乎账户生存。
- 运行后判断：仍有价值继续，但方向应从“调阈值”转为“质量条件豁免”。单纯把阈值从 3 后移会牺牲弱路径保护，继续扫描参数容易过拟合。
- 原因：2022-2025 多个晚启动窗口显示阈值 4/6 收益更强，红框诊断也支持“恢复段被阈值 3 压住”；但弱窗口和早期长窗口又支持阈值 3 防守，因此需要区分劣质恢复和高质量恢复。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，本次不是正式合入。
- 是否追加根目录 `memory.md/back_log.md`：否，本次仅作为本研究线 Stage002 记录。
