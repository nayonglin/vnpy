# Stage022 C3叠加条件触发风险簇热度门禁验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 21:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：第78-1回撤30以内保收益线的真实引擎结构验证
- 是否重要突破：否
- 是否触发A/B：是；候选若通过可能接入正式第78-1风险治理，但本阶段失败不晋级

## 外部调研与判断

- 参考资料：
  - 已参考趋势跟踪组合常见的相关暴露控制、risk overlay、portfolio heat/risk budget 思路。
  - 结合 Stage020/021 的本地归因：剩余最大回撤不是单一品种噪声，而是相关风险簇同步亏损。
- 我的判断：
  - 条件热度门禁比永久品种/产业限制更符合穿越周期原则，因为它只在拥挤或同步亏损时触发。
  - 但如果该机制不能在预声明参数下改善全样本最大回撤，就不应继续围绕阈值小数救结果。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage322_c3_conditional_heat_gate_validation.py`
- 修改脚本：
  - 无
- 删除脚本：
  - 无
- 新增参数：
  - `enable_risk_cluster_heat_gate=True`
  - `risk_cluster_heat_gate_contexts=flat_entry,reverse_entry,rollover_reopen`
  - `risk_cluster_heat_gate_contexts=flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add`
  - `risk_cluster_heat_gate_weight_floor=0.35`
- 修改参数：
  - 无
- 删除参数：
  - 无

## 回测/归因参数

- 数据区间：
  - 全样本：`2020-01-01` 到 `2026-04-30`
  - 多周期：`since_2022`、`since_2023`、`since_2024`、`phase_2024_2025`、`ytd_2026`
- 账户规模：`500,000`
- 成本口径：沿用第78-1当前回测滑点和手续费口径，手续费为0，滑点进入 `total_slippage`
- 样本过滤：不改AI池、不改品种池、不做单品种黑名单
- 策略/归因口径：
  - `C_pressure040`
  - `C3_supply_headwind`
  - `C3_new_exposure_heat_gate`
  - `C3_all_entry_heat_gate`

## 结果

全样本结果：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `C_pressure040` | `25,429,055` | `4985.811%` | `-31.0767%` | `1.2650` | `2,047,490` | `862` | `45.0346%` |
| `C3_supply_headwind` | `30,925,650` | `6085.130%` | `-31.0767%` | `1.3663` | `1,556,750` | `757` | `45.3826%` |
| `C3_new_exposure_heat_gate` | `21,540,600` | `4208.120%` | `-38.6072%` | `1.2995` | `1,256,840` | `781` | `45.2926%` |
| `C3_all_entry_heat_gate` | `21,540,600` | `4208.120%` | `-38.6072%` | `1.2995` | `1,256,840` | `781` | `45.2926%` |

多周期关键信号：

- `since_2022`：热度门禁版本最大回撤改善到 `-27.9241%`，但收益从 C3 的 `695.676%` 降到 `583.167%`。
- `since_2023`：热度门禁版本最大回撤改善到 `-21.4240%`，但收益从 C3 的 `694.350%` 降到 `461.517%`。
- `since_2024`：热度门禁版本最大回撤改善到 `-24.7749%`，但收益从 C3 的 `204.202%` 降到 `188.855%`。
- `phase_2024_2025`：热度门禁版本最大回撤改善到 `-24.7749%`，但收益从 C3 的 `244.120%` 降到 `167.375%`。
- `ytd_2026`：热度门禁版本收益从 `-14.782%` 改善到 `-11.292%`，最大回撤从 `-28.4063%` 小幅改善到 `-28.0148%`。

其他关键指标：

- 严格通过数：`0`
- 研究通过数：`0`
- 全样本热度门禁收益保留：
  - 相对 `C_pressure040`：`84.4019%`
  - 相对 `C3`：`69.1542%`
- 全样本热度门禁最大回撤：`-38.6072%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage322_c3_conditional_heat_gate_validation_report_stage322_c3_conditional_heat_gate_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage322_c3_conditional_heat_gate_validation_summary_stage322_c3_conditional_heat_gate_validation_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage322_c3_conditional_heat_gate_validation_comparison_stage322_c3_conditional_heat_gate_validation_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage322_c3_conditional_heat_gate_validation_curves_stage322_c3_conditional_heat_gate_validation_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage322_c3_conditional_heat_gate_validation_manifest_stage322_c3_conditional_heat_gate_validation_v1.json`

## 结论

- 本阶段结论：`fail_do_not_promote`
- 是否进入下一步：不沿着条件热度门禁继续微调；可以沿着组合层低相关收益源或更本质的危机状态识别继续。
- 下一步：
  - 不继续扫 `risk_cluster_heat_gate_weight_floor`、触发上下文或类似热度阈值。
  - 当前最强中间版本仍是 `C3_supply_headwind`，但它只改善收益效率，没有解决 `-31.0767%` 最大回撤。
  - 若继续追求30以内且收益不显著降低，应转向组合层低相关收益源，或者重新定义可接受的收益保留下限。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段验证本身不是过拟合，但继续救这个结构会过拟合。
- 原因：
  - 本阶段只测试两个预声明结构，没有为了结果调阈值。
  - 全样本失败且收益显著受损后，如果继续围绕热度门禁改小数，实质是在拟合历史路径。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：这条具体热度门禁方向继续价值下降，但总研究线仍有价值。
- 原因：
  - 它证明“限制新增同簇风险”能改善部分后验窗口，却不能解决全样本核心回撤。
  - 这进一步指向：单策略内部风控的边界很硬，下一步更可能来自低相关策略组合或更强的外生状态识别，而不是继续压同一套趋势仓。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为本轮失败方向的收束摘要
