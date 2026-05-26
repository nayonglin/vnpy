# Stage023 C3叠加低相关卫星组合前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 21:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：组合层低相关收益源验证
- 是否重要突破：否；出现 C3 目标研究候选，但未达到正式合入标准
- 是否触发A/B：是；若后续通过真实组合资金和保证金约束，可能成为独立组合候选

## 外部调研与判断

- 参考资料：
  - 趋势跟踪组合常见做法是用低相关收益源改善回撤，而不是只在同一策略内部继续降杠杆。
  - Stage307 已经在 `C_pressure040` 底座上识别出 `range_reversion_v8_two_stage_stop` 是最有希望的低相关卫星。
- 我的判断：
  - 在 Stage322 证明条件热度门禁失败后，继续沿组合层低相关收益源探索，比继续调风险门禁小数更符合不过拟合原则。
  - 本阶段只复用 Stage307 的已知最佳卫星，不重新海选，避免把卫星选择做成新的过拟合入口。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage323_c3_low_corr_satellite_frontier.py`
- 修改脚本：
  - 无
- 删除脚本：
  - 无
- 新增参数：
  - `BASE_VARIANT=C3_supply_headwind`
  - `REFERENCE_VARIANT=C_pressure040`
  - `SATELLITE_NAME=range_reversion_v8_two_stage_stop`
  - `BASE_WEIGHTS=(0.80,0.825,0.85,0.875,0.90,0.925,0.95,0.975)`
- 修改参数：
  - 无
- 删除参数：
  - 无

## 回测/归因参数

- 数据区间：
  - 全样本：`2020-01-01` 到 `2026-04-30`
  - 多周期：`since_2022`、`since_2023`、`since_2024`、`phase_2024_2025`、`ytd_2026`
- 账户规模：组合层净值验证，不直接模拟真实保证金占用
- 成本口径：使用各策略已有日权益曲线，成本已体现在底层曲线
- 样本过滤：只使用 Stage307 已识别最佳低相关卫星，不做新卫星海选
- 策略/归因口径：
  - 主趋势底座：`C3_supply_headwind`
  - 对照：`C_pressure040`
  - 卫星：`qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_daily`

## 结果

最佳 C3 目标研究候选：`c30.800_sat0.200`

| 窗口 | C3收益 | C_pressure040收益 | 组合收益 | 相对C3收益保留 | 相对C_pressure040收益保留 | C3最大回撤 | 组合最大回撤 | 组合Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full_2020_2026 | `6092.809%` | `4992.125%` | `4875.400%` | `80.0189%` | `97.6618%` | `-31.0767%` | `-29.6208%` | `1.6223` |
| since_2022 | `695.931%` | `721.923%` | `557.969%` | `80.1759%` | `77.2892%` | `-34.9148%` | `-29.3725%` | `1.3131` |
| since_2023 | `695.527%` | `721.956%` | `557.303%` | `80.1267%` | `77.1935%` | `-24.9751%` | `-24.2707%` | `1.5883` |
| since_2024 | `204.458%` | `379.215%` | `164.643%` | `80.5268%` | `43.4169%` | `-29.5488%` | `-27.8420%` | `1.2105` |
| phase_2024_2025 | `244.409%` | `400.201%` | `196.591%` | `80.4350%` | `49.1229%` | `-27.6113%` | `-24.9763%` | `1.5430` |
| ytd_2026 | `-14.782%` | `-14.782%` | `-11.8124%` | 不适用 | 不适用 | `-28.4063%` | `-23.4642%` | `-0.9180` |

其他关键指标：

- C3目标通过窗口数：`5/5` 个正收益窗口
- 严格通过窗口数：`0/5`
- 研究通过窗口数：`1/5`
- 卫星与 C3 日收益相关中位数：`0.0118`
- 全样本最大回撤改善：从 `-31.0767%` 到 `-29.6208%`
- 全样本收益相对 C3 保留：`80.0189%`
- 全样本收益相对 C_pressure040 保留：`97.6618%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage323_c3_low_corr_satellite_frontier_report_stage323_c3_low_corr_satellite_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage323_c3_low_corr_satellite_frontier_summary_stage323_c3_low_corr_satellite_frontier_v1.csv`
- windows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage323_c3_low_corr_satellite_frontier_windows_stage323_c3_low_corr_satellite_frontier_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage323_c3_low_corr_satellite_frontier_decision_stage323_c3_low_corr_satellite_frontier_v1.json`

## 结论

- 本阶段结论：`research_candidate_only`
- 是否进入下一步：可以进入下一步，但不能直接合入正式第78-1。
- 下一步：
  - 先做真实组合资金约束和保证金占用验证，确认 `80% C3 + 20%卫星` 是否能在同一账户中执行。
  - 再做“相对 C_pressure040 近端收益损失”的归因：问题来自 C3 供需过滤、卫星低收益，还是组合权重过高。
  - 不做 `0.19/0.21` 这类小数权重搜索。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本轮不是过拟合，但不能直接升级为正式候选。
- 原因：
  - 卫星来自前序 Stage307 已识别候选，本阶段没有重新海选。
  - 权重为粗粒度资金分配，不是围绕结果微调小数。
  - 但 `20%卫星` 刚好是边界通过点，必须经过真实资金/保证金约束和更严格的近端收益归因。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 这是目前第一条在 C3 底座上让所有正收益窗口回撤都进入30以内，同时保留C3至少80%收益的路径。
  - 但近端相对 `C_pressure040` 收益损失明显，说明它只是研究候选，不是最终答案。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为新的研究候选摘要
