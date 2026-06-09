# Stage384 Stage372 50万 risk0.05 四品种放宽持仓限制反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 02:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 多周期审计，纠正 Stage383 的测试对象。
- 是否重要突破：否。
- 是否触发A/B：是，属于资金/品种池/并发持仓治理候选。

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟踪长期研究：`https://www.aqr.com/Insights/Research/Alternative-Thinking/A-Century-of-Evidence-on-Trend-Following-Investing`
  - Man Group 趋势跟踪市场组合研究：`https://www.man.com/insights/trend-following-optimal-market-mix`
  - pysystemtrade 系统化期货组合工程：`https://github.com/pst-group/pysystemtrade`
- 我的判断：趋势策略可以从更多市场和更宽组合中受益，但前提是波动率、相关性、保证金和总风险预算同步治理；低风险倍率下放宽并发有结构性测试价值，但不能预设“更多持仓一定更好”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`BASE_VARIANT=stage372_500k_risk005_plus_ni_ag_sc_p_maxpos4`，`CANDIDATE_VARIANT=stage372_500k_risk005_plus_ni_ag_sc_p_maxpos23`，`EXTRA_PRODUCTS=(ni.SHFE, ag.SHFE, sc.INE, p.DCE)`。
- 修改参数：在 Stage382 四品种 `50万 + risk_multiplier=0.05` 口径上，仅将 `max_concurrent_positions` 从 `4` 放宽到产品池规模 `23`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：历史窗口至 `2026-04-30`；最新 AI 池 YTD 至 `2026-06-05`。
- 账户规模：`500,000`
- 成本口径：正常成本、2x滑点成本、3x滑点成本。
- 样本过滤：固定 Stage372 逻辑，固定追加 `ni.SHFE/ag.SHFE/sc.INE/p.DCE` 到产品宇宙和每月 AI eligibility，不重新训练，不重排 AI。
- 策略/归因口径：
  - A：`stage372_500k_risk005_plus_ni_ag_sc_p_maxpos4`
  - C：`stage372_500k_risk005_plus_ni_ag_sc_p_maxpos23`

## 结果

### 全周期

| 指标 | A maxpos4 | C maxpos23 | C-A |
| --- | ---: | ---: | ---: |
| 期末权益 | `1,016,240` | `1,004,850` | `-11,390` |
| 总收益 | `103.2480%` | `100.9700%` | `-2.2780pp` |
| 最大回撤 | `-18.7329%` | `-18.9539%` | `-0.2211pp` |
| Sharpe | `0.8443` | `0.8146` | `-0.0297` |
| 总滑点 | `32,660` | `34,200` | `+1,540` |
| 总交易次数 | `337` | `341` | `+4` |
| 胜率 | `50.5348%` | `50.5348%` | `0.0000pp` |
| broker10保证金峰值 | `58.2065%` | `60.4103%` | `+2.2038pp` |
| 2x成本最大回撤 | `-19.3194%` | `-19.5756%` | `-0.2562pp` |
| 3x成本最大回撤 | `-19.9178%` | `-20.2117%` | `-0.2939pp` |

### 多周期

- `since_2021`：C 收益少 `0.4500pp`，回撤相同，Sharpe 少 `0.0035`。
- `since_2022`：C 收益少 `1.1760pp`，回撤相同，Sharpe 少 `0.0093`。
- `since_2023`：C 收益少 `1.8480pp`，回撤劣化 `0.0855pp`，Sharpe 少 `0.0149`。
- `since_2024/since_2025/since_2026_hist/YTD2026`：A/C 基本完全相同。
- `phase_2020_2021`：C 收益少 `1.8720pp`，回撤劣化 `0.2694pp`，Sharpe 少 `0.0817`。
- `phase_2022_2023`：C 收益少 `0.3520pp`，回撤相同。
- `weak_2021_drawdown`：A/C 相同。

### 资金占用

| 指标 | A maxpos4 | C maxpos23 |
| --- | ---: | ---: |
| active_days | `674` | `674` |
| active_rate | `43.9948%` | `43.9948%` |
| 平均占用（全日） | `3.9858%` | `4.0845%` |
| 平均占用（有仓日） | `9.0598%` | `9.2840%` |
| p95 | `25.3484%` | `25.7964%` |
| 峰值 | `58.2065%` | `60.4103%` |
| `>30%` 天数 | `21` | `30` |
| `>50%` 天数 | `4` | `5` |
| `>70%/>90%/>100%` 天数 | `0/0/0` | `0/0/0` |

### 滚动窗口

- 63日 p05：A `-8.4752%`，C `-8.5630%`。
- 126日 p05：A `-11.5569%`，C `-11.7016%`。
- 252日 p05：A `-12.5739%`，C `-12.7318%`。
- C 的滚动左尾全部略差。

### 新增品种贡献

- A：`ag +38,520`，`ni +81,040`，`p -16,940`，`sc -34,000`，合计 `+68,620`。
- C：`ag +38,520`，`ni +81,040`，`p -18,200`，`sc -34,000`，合计 `+67,360`。
- 放宽持仓限制后新增品种贡献少 `1,260`，主要来自 `p` 更差；交易使用量从 `p 112` 增到 `114`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_report_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_summary_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_comparison_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_margin_usage_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_chart_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_decision_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1.json`

## 结论

- 本阶段结论：`stage372_500k_risk005_plus_four_no_maxpos_rejected`。基于 Stage382 四品种 `50万 + risk_multiplier=0.05` 口径，放宽持仓限制没有提高收益，反而轻微降低收益、Sharpe 和滚动左尾，并抬高保证金峰值。
- 是否进入下一步：不进入“直接关持仓限制”方向。
- 下一步：若继续研究并发，只能做状态化并发放宽，例如低相关、低保证金、趋势质量强、AI 质量强同时满足时临时增加槽位；不建议扫 `5/6/7/.../23`。

## 过拟合反思

- 运行前判断：不是过拟合。用户要求纠正实验对象，测试的是结构性并发约束是否在低风险、扩池版本中成为瓶颈。
- 运行后判断：继续扫整数上限会过拟合。
- 原因：C 只比 A 多 `4` 笔交易，收益没有改善，资金占用更高；说明问题不是简单的 `maxpos4` 卡住趋势机会。

## 继续价值反思

- 运行前判断：有价值。因为四品种低风险组合可能被并发槽位限制，值得做一次反证。
- 运行后判断：直接放宽没有继续价值；状态化并发仍有研究价值但优先级低于 Stage379 `ni+ag` 观察和通用 selector。
- 原因：直接放宽没有带来增益，且 Stage382 已显示 `sc/p` 本身拖累四品种组合。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为未来禁止直接关闭四品种低风险并发限制的经验。
