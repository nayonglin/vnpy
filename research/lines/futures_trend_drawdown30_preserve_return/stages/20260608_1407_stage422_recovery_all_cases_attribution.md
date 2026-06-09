# Stage422 Stage372 all-cases recovery 只读归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 14:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage421 all-cases recovery 的只读归因；解释 2022-2025 改善和 2026 独立启动失败，不新增交易规则。
- 是否重要突破：否，但明确了下一步不能沿 `case3/2026` 做补丁调参。
- 是否触发A/B：否。本阶段是归因，不是新候选。

## 外部调研与判断

- 参考资料：趋势跟踪和 CTA 风控资料普遍强调：连败/回撤期应降低暴露、控制风险预算和保证金压力，同时避免错过稀疏右尾；没有可靠资料支持“按某个历史失败 case 或单一年份做恢复仓过滤”。参考 Man Group trend-following 市场分散、AQR trend-following、Concretum position sizing、以及 CTA 风控资料。
- 我的判断：Stage421 的 all-cases recovery 看起来像通用机制，但 Stage422 不能为了 2026 失败去过滤 `long_case3`、`ru/MA` 或具体日期。归因的价值是判断失败是否来自普遍机制缺陷，还是短样本路径噪声；不是生成新规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage708_recovery_all_cases_attribution.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增归因窗口 `phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`。
- 修改参数：无。
- 删除参数：无。
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 回测/归因参数

- A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
- C：Stage421 候选 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_stage707`。
- 归因窗口：`2022-2023` 独立启动、`2024-2025` 独立启动、`2026-01-01` 至 `2026-04-30` 独立启动。
- 账户规模：`200,000`。
- 成本口径：正常成本。
- 输出口径：阶段权益、产品 PnL 差、开仓手数差、`loss_streak>=3` 开仓、`streak_entry_structure_risk_recovery_applied` 明细。

## 结果

- 决策：`read_only_attribution_no_promotion`。
- hard_finding：`2026 independent-start attribution remains negative`。
- `phase_2022_2023`：A `200,595/0.2975%/-28.0550%/Sharpe0.1053`；C `366,070/83.0350%/-24.3359%/Sharpe1.1102`；C 相对 A 期末权益 `+165,475`，交易 `+57`，滑点 `+6,590`。
- `phase_2024_2025`：A `266,535/33.2675%/-29.4347%/Sharpe0.6398`；C `480,535/140.2675%/-29.4347%/Sharpe1.3488`；C 相对 A 期末权益 `+214,000`，交易 `+11`，滑点 `+4,290`。
- `phase_2026_latest`：A `202,290/1.1450%/-16.3027%/Sharpe0.2783`；C `194,090/-2.9550%/-17.5348%/Sharpe-0.1388`；C 相对 A 期末权益 `-8,200`，交易 `0`，滑点 `0`。
- 2022-2023 主要改善：`jm +47,790`、`oi +46,360`、`hc +32,490`、`ap +26,410`、`sp +16,000`、`rb +10,590`。主要拖累：`sa -8,480`、`fu -7,970`、`cu -6,700`、`si -5,900`。
- 2024-2025 主要改善：`jm +141,930`、`si +32,750`、`fu +14,460`、`FG +11,800`、`lc +10,640`、`lh +6,480`。主要拖累：`rb -3,050`、`sp -1,980`、`oi -1,180`、`ru -800`。
- 2026 失败归因：负差主要来自 `ru -6,300`、`MA -4,750`，被 `sh +2,250`、`sa +600` 部分抵消。A/C 总交易数同为 `19`、总滑点同为 `1,350`、最大 broker10 保证金峰值同为 `55.1058%`，所以失败不是交易次数或保证金压力突然增加。
- 开仓归因：
  - `phase_2022_2023`：A 开仓 `39`、选中手数 `129`、recovery applied `8`；C 开仓 `68`、选中手数 `319`、recovery applied `9`。
  - `phase_2024_2025`：A 开仓 `55`、选中手数 `388`、recovery applied `4`；C 开仓 `59`、选中手数 `478`、recovery applied `7`。
  - `phase_2026_latest`：A/C 都开仓 `10`、选中手数 `51`；A recovery applied `3`，C recovery applied `4`。C 多出来的关键恢复仓是 `2026-02-04 ru long_case3` 和 `2026-04-07 MA long_case3`，路径较差。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_report_stage708_recovery_all_cases_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_summary_stage708_recovery_all_cases_attribution_v1.csv`
- product_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_product_delta_stage708_recovery_all_cases_attribution_v1.csv`
- entry_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_entry_summary_stage708_recovery_all_cases_attribution_v1.csv`
- recovery_detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_recovery_detail_stage708_recovery_all_cases_attribution_v1.csv`
- recovery_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_recovery_summary_stage708_recovery_all_cases_attribution_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_decision_stage708_recovery_all_cases_attribution_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage708_recovery_all_cases_attribution_product_delta_chart_stage708_recovery_all_cases_attribution_v1.png`

## 结论

- Stage421 all-cases recovery 的正面效果不是单品种偶然：2022-2025 的改善来自多品种、多阶段右尾恢复，尤其是 `jm/oi/hc/ap/si/fu/FG/lc`。
- 2026 失败也不是资金、交易次数、滑点或保证金恶化导致，而是短样本内 `ru/MA long_case3` 恢复仓路径较差。
- 这恰好说明不能继续做 `case3` 黑名单、`ru/MA` 黑名单或 2026 日期过滤；这会把一个通用风控线索变成窗口补丁。
- 当前结论仍是：Stage421 不晋级正式版；all-cases recovery 可保留为强线索，下一步只做 paper/forward watch 或预声明季度验证。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只读归因，不新增规则。
- 运行后判断：归因本身不是过拟合，但用归因结果去过滤 `long_case3`、`ru/MA` 或 2026 日期就是过拟合。
- 原因：`long_case3` 在 2026 是拖累，但同一 broad recovery 机制在 2022-2025 多品种显著改善；不能用一个短窗口否定或定制一个 case。

## 继续价值反思

- 运行前判断：有价值，因为 Stage421 是当前最强但未晋级的简单风控线索，需要知道失败是否可解释。
- 运行后判断：继续价值从“继续回测调参”转为“paper/forward 验证”。不建议再做回测救参。
- 原因：我们已经知道它的机制优点和失败来源；继续从历史里找过滤条件会降低穿越周期能力。

## 合入建议

- 是否更新本线 `LINE.md`：是，作为 Stage421 的归因补充。
- 是否更新 `research/registry.md`：否，正式默认未变。
- 是否追加根目录 `memory.md/back_log.md`：是，作为后续禁止按 case3/2026 补丁调参的经验。
