# Stage131 Stage115低保证金股指选择审计

- 时间：2026-05-28 02:02 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：固定结构 A/B/C 审计；不改 Stage079/Stage103，不扫窗口、不扫保证金小数。
- 是否重要突破：否。重要反证：低保证金选择不能把 Stage115 修成绝对保证金干净的主候选。
- 是否触发 A/B：是。已补读 `skills/version-ab-experiment/SKILL.md`。A=Stage079；C0=Stage103；C1=Stage115 最强动量1手；C2=最低保证金1手；C3=动量/保证金效率1手。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage431_stage115_margin_light_index_overlay.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage431_stage115_margin_light_index_overlay_report_stage431_stage115_margin_light_index_overlay_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage431_stage115_margin_light_index_overlay_chart_stage431_stage115_margin_light_index_overlay_v1.png`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage431_stage115_margin_light_index_overlay_decision_stage431_stage115_margin_light_index_overlay_v1.json`

## 开始前反思

- 是否在过拟合：低到中。不是救股指窗口、单指数或保证金小数，只测试两个非参数资金预算原则；但它仍然靠近 Stage115 路线，必须严格失败即停。
- 是否仍有价值继续做：有。Stage115 是当前短持有体验最强路径，主要缺陷是绝对保证金和贡献日集中；若低保证金结构能解决执行缺陷且保留分数，会有现实价值。

## 外部调研与判断

- 调研参考：
  - 时间序列动量和波动缩放研究提示，TSMOM 的有效性不仅来自方向信号，也来自仓位和风险预算方式。
  - 期货 position sizing / margin 管理资料强调合约乘数、保证金和账户权益缓冲是能否落地的核心约束。
  - GitHub/公开趋势跟随实现仍未发现可直接迁移到本地中国期货、整数手、保证金和61.5万账户的现成更优实现。
- 我的判断：
  - `best1` 是“信号最强”原则，`min_margin1` 是“资金最轻”原则，`mom_per_margin1` 是“单位保证金信号效率”原则。
  - 这三者是不同资金预算哲学，不是小数扫描；如果仍失败，就不应继续救 Stage115 股指路线。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage431_stage115_margin_light_index_overlay.py`
- 新增输出：
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_summary_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_horizon_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_score_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_fresh_start_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_cost_stress_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_margin_audit_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_top_edge_day_ablation_stage431_stage115_margin_light_index_overlay_v1.csv`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_report_stage431_stage115_margin_light_index_overlay_v1.md`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_chart_stage431_stage115_margin_light_index_overlay_v1.png`
  - `qmt_roll_stage431_stage115_margin_light_index_overlay_decision_stage431_stage115_margin_light_index_overlay_v1.json`
- 新增参数：
  - `index_tsmom_min_margin1`：四个股指 60日TSMOM 有信号时，每天取保证金最低的一手。
  - `index_tsmom_mom_per_margin1`：四个股指 60日TSMOM 有信号时，每天取 `abs(momentum) / margin_per_contract` 最高的一手。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 基准与候选

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 | `31,040,650` | `4947.2602%` | `-29.7007%` | `1.3188` | `15.0874` | `100.0000` | `100.0000` | baseline |
| Stage103 | `31,730,915` | `5059.4984%` | `-28.9792%` | `1.3681` | `14.3132` | `121.2041` | `134.4513` | 当前主候选 |
| Stage115 best1 | `33,607,695` | `5364.6659%` | `-23.5184%` | `1.4810` | `12.0786` | `183.4601` | `210.3930` | 仍是最高分，但绝对保证金不过 |
| min_margin1 | `31,676,495` | `5050.6496%` | `-34.7175%` | `1.3401` | `14.6029` | `111.6619` | `123.9922` | 硬失败 |
| mom_per_margin1 | `33,277,355` | `5310.9520%` | `-27.4388%` | `1.4335` | `12.8059` | `162.3016` | `193.4488` | 研究闸门过，但保证金不过 |

## 关键反证

- `min_margin1`：
  - 最大回撤打到 `-34.7175%`，破坏 Stage079 硬约束。
  - rolling252/504 破30回撤率升到 `0.1029/0.2566`，年度/季度通过率降到 `80.00%/77.27%`。
  - 结论：单纯低保证金不是低风险，反而容易选到弱风险暴露。
- `mom_per_margin1`：
  - 全周期和 3/6个月体验仍强，3个月/6个月改善 `7/8` 与 `8/8`。
  - 但 `1.10x` 保证金审计在 `start_2025` 相对 Stage079/Stage103 都变差，最大保证金/权益 `110.5694%`，需额外约 `72,843.86` 元。
  - 顶部贡献日剔除后，相对 Stage103 剔除最大 `1` 个相对贡献日即转负：调整后总收益 `5023.02%`，低于 Stage103。
- Stage115 best1：
  - 本轮复算仍是最高分并通过 execution-relative，但绝对保证金仍无改善，`start_2020` 仍有 `1` 天穿线。

## 决策

- 决策 JSON：`no_margin_light_promotion`
- 研究闸门通过：Stage115 best1、`mom_per_margin1`
- execution-relative 通过：仅 Stage115 best1
- absolute margin 通过：无
- margin-light ready：无

结论：低保证金/保证金效率选择没有解决 Stage115 的根本问题。股指TSMOM 仍只能作为 paper/观察，不应继续围绕保证金选择、单指数、日期、贡献日、保证金小数或 `60/120` 窗口救援。

## 后续规划和 TODO

1. 主执行相对候选继续固定 Stage103。
2. Stage115 / `mom_per_margin1` 只保留为 paper 对照，不进入主执行候选。
3. 若继续主动研究，只能找新的低自由度风险源；不要继续在股指 TSMOM 内部做选择规则变体。

## 结束后反思

- 是否在过拟合：否。本阶段没有用失败结果继续改阈值，且主动拒绝了高分但保证金不干净的 `mom_per_margin1`。
- 是否还有价值继续做：总目标仍有价值；但 Stage115 低保证金修复路线继续价值低。下一步应回到 Stage103 落地验证，或换全新风险源。
