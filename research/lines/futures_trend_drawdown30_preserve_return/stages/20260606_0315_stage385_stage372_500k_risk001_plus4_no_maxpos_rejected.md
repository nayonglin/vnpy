# Stage385 Stage372 50万 risk0.01 四品种放宽持仓限制反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 03:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 多周期审计；在 Stage384 基础上把 `risk_multiplier` 从 `0.05` 改为 `0.01`。
- 是否重要突破：否；但 `risk0.01 maxpos4` 相对 `risk0.05` 出现反直觉高收益，需要后续归因，不可直接推广。
- 是否触发A/B：是。

## 外部调研与判断

- 参考资料：
  - pysystemtrade 仓位优化与有限资金/最小合约问题：`https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization`
  - Concretum trend following position sizing：`https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/`
  - AQR 趋势跟踪长期研究：`https://www.aqr.com/Insights/Research/Alternative-Thinking/A-Century-of-Evidence-on-Trend-Following-Investing`
- 我的判断：期货仓位 sizing 不是连续变量，低风险倍率会和最小 1 手、保证金门槛、恢复仓 sleeve 发生离散交互；因此 `risk_multiplier=0.01` 不能简单解释为“风险降到 0.05 的五分之一”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos.py`
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos.py`，将阶段名、报告标题、风险标签、决策名参数化，供 Stage673 wrapper 复用。
- 删除脚本：无。
- 新增参数：`RISK_MULTIPLIER=0.01`，`BASE_VARIANT=stage372_500k_risk001_plus_ni_ag_sc_p_maxpos4`，`CANDIDATE_VARIANT=stage372_500k_risk001_plus_ni_ag_sc_p_maxpos23`。
- 修改参数：相对 Stage384 仅把 `risk_multiplier` 从 `0.05` 改为 `0.01`；仍固定 `50万 + ni/ag/sc/p`，A 用 `max_concurrent_positions=4`，C 用产品池规模 `23`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：历史窗口至 `2026-04-30`；最新 AI 池 YTD 至 `2026-06-05`。
- 账户规模：`500,000`
- 成本口径：正常成本、2x滑点成本、3x滑点成本。
- 样本过滤：固定追加 `ni.SHFE/ag.SHFE/sc.INE/p.DCE` 到产品宇宙和每月 AI eligibility，不重新训练，不重排 AI。
- 策略/归因口径：
  - A：`stage372_500k_risk001_plus_ni_ag_sc_p_maxpos4`
  - C：`stage372_500k_risk001_plus_ni_ag_sc_p_maxpos23`

## 结果

### 全周期

| 指标 | A risk001 maxpos4 | C risk001 maxpos23 | C-A |
| --- | ---: | ---: | ---: |
| 期末权益 | `1,320,205` | `1,308,895` | `-11,310` |
| 总收益 | `164.0410%` | `161.7790%` | `-2.2620pp` |
| 最大回撤 | `-19.0309%` | `-19.2553%` | `-0.2244pp` |
| Sharpe | `0.9250` | `0.9047` | `-0.0203` |
| 总滑点 | `36,490` | `37,870` | `+1,380` |
| 总交易次数 | `326` | `330` | `+4` |
| 胜率 | `49.5690%` | `49.5690%` | `0.0000pp` |
| broker10保证金峰值 | `61.8745%` | `62.5300%` | `+0.6554pp` |
| 2x成本最大回撤 | `-19.5963%` | `-19.8559%` | `-0.2596pp` |
| 3x成本最大回撤 | `-20.1729%` | `-20.4702%` | `-0.2973pp` |

### 多周期

- `since_2021`：C 收益少 `4.7680pp`，回撤相同，Sharpe 少 `0.0056`。
- `since_2022`：C 收益少 `0.3520pp`，回撤相同，Sharpe 少 `0.0038`。
- `since_2023`：C 收益少 `1.0120pp`，回撤劣化 `0.0846pp`，Sharpe 少 `0.0073`。
- `since_2024/since_2025/since_2026_hist/YTD2026`：A/C 基本完全相同。
- `phase_2020_2021`：C 收益少 `1.8720pp`，回撤劣化 `0.2694pp`，Sharpe 少 `0.0812`。
- `phase_2022_2023`：C 收益少 `0.3520pp`，回撤相同。

### 资金占用

| 指标 | A risk001 maxpos4 | C risk001 maxpos23 |
| --- | ---: | ---: |
| active_days | `623` | `623` |
| active_rate | `40.6658%` | `40.6658%` |
| 平均占用（全日） | `4.6062%` | `4.7027%` |
| 平均占用（有仓日） | `11.3271%` | `11.5643%` |
| p95 | `27.1130%` | `27.5716%` |
| 峰值 | `61.8745%` | `62.5300%` |
| `>30%` 天数 | `34` | `38` |
| `>50%` 天数 | `5` | `6` |
| `>70%/>90%/>100%` 天数 | `0/0/0` | `0/0/0` |

### 滚动窗口

- 63日 p05：A `-8.4365%`，C `-8.5469%`。
- 126日 p05：A `-10.5489%`，C `-10.6820%`。
- 252日 p05：A `-12.8630%`，C `-13.0244%`。
- C 的滚动左尾仍全部略差。

### 新增品种贡献

- A/C 新增品种贡献相同：`ag +106,860`，`ni +398,980`，`p -12,880`，`sc -62,300`，合计 `+430,660`。
- `risk0.01` 相对 `risk0.05` 四品种版本，`ni/ag` 一手趋势贡献明显放大，同时 `sc` 仍是拖累项。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_report_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_summary_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_comparison_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_margin_usage_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_chart_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_decision_stage673_stage372_500k_risk001_ni_ag_sc_p_no_maxpos_v1.json`

## 结论

- 本阶段结论：`stage372_500k_risk001_plus_four_no_maxpos_rejected`。在 `risk_multiplier=0.01` 下，放宽持仓限制仍没有提高收益，反而略微降低收益、Sharpe 和滚动左尾，并增加滑点和资金占用。
- 是否进入下一步：不进入“直接放宽并发限制”方向。
- 下一步：`risk0.01 maxpos4` 本身值得归因，但不能直接晋级；必须先解释为什么低风险倍率反而高收益，重点看最小 1 手、恢复仓 sleeve、`ni/ag` 贡献集中和 `sc/p` 拖累。

## 过拟合反思

- 运行前判断：有过拟合风险。`0.05` 失败后继续改到 `0.01` 属于风险倍率扫描，必须严控解释，不能因为结果好看就推广。
- 运行后判断：放宽并发继续失败；`risk0.01 maxpos4` 的好结果也不能直接推广。
- 原因：结果主要来自离散手数和少数品种贡献，尤其 `ni/ag`，不是连续风险预算的稳定提升证据。

## 继续价值反思

- 运行前判断：有价值但风险高。它可以验证极低风险倍率是否形成更防守的组合。
- 运行后判断：直接放宽并发无价值；`risk0.01 maxpos4` 有归因价值。
- 原因：收益、Sharpe 高于 Stage384 的 `risk0.05` 四品种版本，但保证金峰值也更高，且逻辑反直觉，必须先做机制归因。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，记录放宽并发仍失败，以及 `risk0.01` 需要归因不可直接推广。
