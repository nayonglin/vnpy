# Stage374 Stage372 30万启动资金多周期审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-05 14:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金口径 A/C 研究回测
- 是否重要突破：否，结论为 30万资金口径硬失败
- 是否触发A/B：是，A=当前官方 Stage372 20万，C=Stage372 逻辑 + 30万启动资金

## 外部调研与判断

- 参考资料：公开期货回测/风险管理资料均强调期货组合回测必须同时评估账户规模、保证金、杠杆、止损风险、回撤和成本压力，而不能只看可开手数或收益曲线。
- 我的判断：30万资金测试不是 alpha 改动，属于部署资金层 A/C；低过拟合，因为只改启动资金，不改入场、AI池、恢复仓阈值或强制减仓阈值。但资金规模会改变整数手、复利速度和保证金路径，不能由 20万线性外推。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage663_stage372_30w_multiperiod.py`
- 修改脚本：无官方实盘配置修改
- 删除脚本：无
- 新增参数：`CAPITAL_30W=300000.0`、`VARIANT_30W=stage526_300k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- 修改参数：`account_capital/c3_capital` 从 `200000` 改为 `300000`
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 历史窗口：`2020-01-01` 至 `2026-04-30`
  - 最新 AI 池 YTD：`2026-01-01` 至 `2026-06-04`
- 账户规模：`300,000`
- 成本口径：正常成本、2x 成本、3x 成本
- 样本过滤：沿用 Stage372 官方逻辑与 Stage182 最新月度 AI 池
- 策略/归因口径：只改启动资金，不改 alpha、AI池、信号、恢复仓规则、强制减仓规则

## 结果

- 期末权益：`13,529,150`
- 总收益：`4409.7167%`
- 最大回撤：`-40.1418%`
- Sharpe：`1.6086`
- 总滑点：`768,240`
- 总交易次数：`667`
- 胜率：`53.3276%`
- 其他关键指标：
  - broker10 保证金峰值：`81.8965%`
  - 超 `90/100%` 保证金天数：`0/0`
  - 强制减仓：`7` 次 / `698` 手
  - 2x 成本：`12,760,910 / 4153.6367% / -42.8258% / Sharpe 1.5343`
  - 3x 成本：`11,992,670 / 3897.5567% / -45.6857% / Sharpe 1.4609`
  - 最新 AI 池 YTD：`337,675 / 12.5583% / -15.7341% / Sharpe 1.0985`
  - 63/126/252 日任意启动 p05：`-15.6529% / -7.8994% / 7.8786%`

## 多周期结果

| 窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | broker10峰值 | 交易 | 滑点 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| full_2020_20260430 | 13,529,150 | 4409.7167% | -40.1418% | 1.6086 | 81.8965% | 667 | 768,240 | 失败，DD40破线 |
| since_2021 | 6,036,820 | 1912.2733% | -37.3730% | 1.5550 | 73.5478% | 482 | 340,960 | 通过 |
| since_2022 | 700,930 | 133.6433% | -22.8139% | 0.8520 | 60.9179% | 267 | 37,540 | 通过 |
| since_2023 | 947,065 | 215.6883% | -22.0360% | 1.2168 | 62.3366% | 238 | 50,880 | 通过 |
| since_2024 | 711,785 | 137.2617% | -26.2704% | 1.2093 | 63.4147% | 162 | 28,860 | 通过 |
| since_2025 | 544,285 | 81.4283% | -20.2716% | 1.4031 | 59.7950% | 82 | 11,200 | 通过 |
| since_2026_hist | 304,305 | 1.4350% | -15.7341% | 0.3082 | 56.3162% | 21 | 1,940 | 通过 |
| phase_2020_2021 | 1,674,945 | 458.3150% | -23.6193% | 2.1361 | 67.7043% | 288 | 70,040 | 通过 |
| phase_2022_2023 | 355,885 | 18.6283% | -21.5317% | 0.5185 | 53.0755% | 103 | 8,180 | 通过 |
| phase_2024_2025 | 774,780 | 158.2600% | -26.2704% | 1.4260 | 63.4147% | 136 | 26,940 | 通过 |
| weak_2021_drawdown | 249,550 | -16.8167% | -20.0288% | -1.8557 | 61.7743% | 18 | 930 | 压力窗口亏损 |
| ytd_2026_latest_ai | 337,675 | 12.5583% | -15.7341% | 1.0985 | 56.3162% | 28 | 2,350 | 通过 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_report_stage663_stage372_30w_multiperiod_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_chart_stage663_stage372_30w_multiperiod_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_summary_stage663_stage372_30w_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_cost_stress_stage663_stage372_30w_multiperiod_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_annual_stage663_stage372_30w_multiperiod_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_monthly_stage663_stage372_30w_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_curves_stage663_stage372_30w_multiperiod_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage663_stage372_30w_multiperiod_rolling_stage663_stage372_30w_multiperiod_v1.csv`

## 结论

- 本阶段结论：30万启动资金收益更高，但全周期正常成本最大回撤 `-40.1418%` 已破 `40%` 红线，2x成本回撤 `-42.8258%` 明显失败；不建议把当前官方实盘资金口径从 20万切到 30万。
- 是否进入下一步：不进入正式切换。
- 下一步：如果确实要用 30万，应先做 30万专属的轻微降风险方案，例如只降低风险倍率或降低最大并发，而不是直接用 Stage372 20万逻辑放大。

## 过拟合反思

- 运行前判断：否，单变量资金口径测试，不调策略阈值。
- 运行后判断：否，但若继续为修复 `-40.1418%` 去微调恢复仓冷却、保证金线或特定年份规则，会转为过拟合。
- 原因：失败来自资金放大后的路径风险和交易/滑点增加，不是一个小数阈值可以可靠解决的问题。

## 继续价值反思

- 运行前判断：有价值，30万能检验资金放大后的真实路径风险。
- 运行后判断：有价值，但不应继续直接切 30万正式版。
- 原因：结果说明 30万不是简单更优资金口径；它提升收益，但破坏回撤边界。下一步价值在设计“30万专属低一点风险”的结构化方案，而不是继续原逻辑放大。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。
