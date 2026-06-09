# Stage009 - 保留官方sleeve的edge60正常风险绕过验证

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 多周期回测；验证“保留官方 recovery sleeve，只对高质量官方恢复 setup 取消一手限制”。
- 是否重要突破：否，关键无效结论。
- 是否触发A/B：否。候选无实际路径差异，不进入正式 A/B。

## 外部调研与判断

- 参考资料：
  - Meta-labeling 概念：`https://en.wikipedia.org/wiki/Meta-Labeling`
  - regime filter 概念参考：`https://www.darwintiq.com/articles/what-is-a-regime-filter`
  - 趋势跟随回测参考仓库：`https://github.com/trustdan/trend-following-backtesting-strategies`
- 我的判断：外部资料只支持“机会质量过滤必须是事前可定义、分段可复验”的纪律。Stage727 是低自由度结构验证，合理；但如果它没有触发交易差异，就不能把检查项通过误读为策略有效。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage727_official_sleeve_edge60_bypass.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无。
- 新增默认关闭参数：
  - `recovery_sleeve_normal_risk_bypass_require_directional_edge60=False`
  - `recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct=-1.0`
- 新增诊断字段：
  - `recovery_sleeve_normal_risk_bypass_enabled`
  - `recovery_sleeve_normal_risk_bypassed`
- 修改参数：
  - Stage727 C 运行期启用 `recovery_sleeve_normal_risk_bypass_require_directional_edge60=True`
  - Stage727 C 运行期设置 `recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct=0.05`
  - `directional_edge_period=60`
  - long close position `>=0.80`
  - short close position `<=0.20`
- 删除参数：无。
- 正式配置修改：无，新增策略参数均默认关闭。

## 回测参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 对照 A：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- 候选 C：`stage526_200k_force95_to80_official_sleeve_edge60_bypass_stage727`
- 成本口径：正常成本，并输出 2x/3x 成本压力。
- 多周期：全周期、`since_2021~since_2026`、`phase_2020_2021`、`phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`。
- 逻辑：保留官方 `recovery_sleeve`；只在官方 `long_case1a/short_case1a` clean-book recovery setup 同时满足 `directional_edge60` 与账户回撤 `<=5%` 时，不压成一手，保留正常风险 sizing。

## 结果

### 全周期

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 强制减仓 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 recovery sleeve | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% | 6 / 299手 |
| C Stage727 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% | 6 / 299手 |

### 关键分段

| 窗口 | A 总收益 | C 总收益 | A 最大回撤 | C 最大回撤 | 交易差值 | 滑点差值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full_2020_20260430 | 4264.1425% | 4264.1425% | -38.6713% | -38.6713% | 0 | 0 |
| since_2022 | 133.8550% | 133.8550% | -28.0550% | -28.0550% | 0 | 0 |
| phase_2022_2023 | 0.2975% | 0.2975% | -28.0550% | -28.0550% | 0 | 0 |
| phase_2026_latest | 1.1450% | 1.1450% | -16.3027% | -16.3027% | 0 | 0 |

- `decision=official_sleeve_edge60_bypass_no_effect_not_promoted`
- `no_effect=True`
- 全部窗口 `delta_end_equity=0`
- 全部窗口 `delta_max_dd_pct=0`
- 全部窗口 `delta_sharpe=0`
- 全部窗口 `delta_total_slippage=0`
- 全部窗口 `delta_total_trade_count=0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_report_stage727_official_sleeve_edge60_bypass_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_summary_stage727_official_sleeve_edge60_bypass_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_comparison_stage727_official_sleeve_edge60_bypass_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_cost_stress_stage727_official_sleeve_edge60_bypass_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_curves_stage727_official_sleeve_edge60_bypass_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_chart_stage727_official_sleeve_edge60_bypass_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage727_official_sleeve_edge60_bypass_decision_stage727_official_sleeve_edge60_bypass_v1.json`

## 结论

- 本阶段结论：`official_sleeve_edge60_bypass_no_effect_not_promoted`。
- 这个候选不是“通过”，而是“无效果”：在全周期和所有独立窗口里，权益、回撤、Sharpe、滑点、交易次数完全一致。
- 因此，当前历史样本中没有出现“官方恢复仓 setup 同时满足 edge60 + DD<=5%，且正常风险 sizing 会改变实际路径”的有效机会。
- 高质量机会豁免这条线目前没有找到可靠可接正式版的特征；正式版继续保持 Stage372/20万 `1,1,1,0.1 + recovery_sleeve`。

## 过拟合反思

- 运行前判断：否。它是 Stage726 后的低自由度结构验证，保留官方 sleeve，不按品种、年份、红框或阈值救参。
- 运行后判断：推广它不是过拟合，而是无意义；继续围绕这个条件放宽阈值则会进入过拟合。
- 原因：没有交易路径差异，就没有可证伪的收益/风险证据。为了制造差异去扫 `DD%`、`edge60` 周期或 close-position 阈值，本质是在历史样本里找触发点。

## 继续价值反思

- 运行前判断：有价值。它能澄清 Stage725 是否只是因为关闭官方 sleeve 才失败。
- 运行后判断：本形状没有继续价值；总问题仍有价值，但不能继续在当前历史字段上做条件堆叠。
- 原因：Stage721/722 已否决现有历史字段，Stage724/725 已否决 `directional_edge60` 及账户健康门控，Stage727 又显示保留官方 sleeve 后该正常风险绕过没有触发。

## 后续规划

- 不合入正式版，不开正式 A/B。
- 不扫 `edge60` 周期、`0.8/0.2` close-position 阈值、`DD 5/10/15%` 或品种/年份补丁。
- 若继续寻找高质量机会，只能做两个方向：
  - 预声明 forward watch，先积累真实 OOS 样本。
  - 引入新的外生特征或账户级 selector，目标直接对齐账户收益、回撤、成本、保证金和右尾保留。
