# Stage290 低单笔风险扩池 selector edge 门槛审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 00:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读门槛审计；不修改策略、不做新收益回测、不生成交易白名单。
- 是否重要突破：否；但属于“减少单笔风险、扩大品种池、避免高相关、选对品种”路线的重要门槛结论。
- 是否触发 A/B：否。本阶段没有形成可接入正式版本的新策略候选，只定义未来 selector 必须跨过的材料性门槛。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen `Time Series Momentum`：趋势效应跨多类流动期货/远期市场存在，分散组合比单市场更稳健。
  - Fidelity managed futures 资料：成熟 managed futures 通过跨股指、利率、货币、商品的多空趋势捕捉与低相关性提供组合价值。
  - `pysystemtrade` 文档：趋势组合工程强调 instrument universe、instrument weights、correlation/diversification multiplier、risk target，而不是简单增加品种数量。
  - 2024 年商品趋势扩散研究提示：扩大 commodity universe 的价值来自更高异质性和趋势倾向，但需要避免把历史赢家直接当成实盘池。
- 参考链接：
  - https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf
  - https://clearingcustody.fidelity.com/insights/topics/investing-ideas/managed-futures-as-a-powerful-portfolio-diversifier
  - https://raw.githubusercontent.com/pst-group/pysystemtrade/develop/docs/backtesting.md
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4871376
- 我的判断：
  - 用户提出的方向在第一性原理上成立：趋势收益稀疏，低单笔风险 + 更多低相关机会能提高“每年抓到部分趋势”的概率。
  - 但本地 Stage257/264/276 已证明，简单宽池和上一年为正 selector 都不能改善 Stage526；所以本阶段要量化“selector edge 到底要多强”，而不是继续扫宽池 `risk/cap/corr/maxpos` 小数。
  - 相关性约束只能降低拥挤风险，不能制造 alpha；真正瓶颈是 point-in-time 选品证据。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage590_breadth_selector_edge_threshold_audit.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增审计参数：
  - `RANDOM_RUNS=20000`
  - `RNG_SEED=590`
  - `P0_PRODUCTS=lu.INE/v.DCE/y.DCE/ao.SHFE/c.DCE`
  - `MATERIAL_ACTUAL_SLEEVE_PNL=50000`
  - random selector：`random_all_k3/k6`、`random_familycap_k3/k6`
  - 对照篮子：`p0_fixed_watchlist`、`hindsight_top3`、`hindsight_top6`、`all_noncore_equal`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 审计输入

- Stage541 单品种年度机会矩阵：
  - `qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv`
- Stage550 产品机会几何与特征 IC：
  - `qmt_roll_stage550_product_opportunity_geometry_audit_annual_matrix_stage550_product_opportunity_geometry_audit_v1.csv`
  - `qmt_roll_stage550_product_opportunity_geometry_audit_annual_selection_stage550_product_opportunity_geometry_audit_v1.csv`
- Stage574 扩池边界：
  - `qmt_roll_stage574_low_single_risk_breadth_selector_boundary_risk_shell_boundary_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
  - `qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- Stage588 P0 证据矩阵：
  - `qmt_roll_stage588_p0_selector_evidence_priority_audit_evidence_matrix_stage588_p0_selector_evidence_priority_audit_v1.csv`

## 结果

- 决策：`breadth_selector_edge_required_no_promotion`
- `promotion_allowed=false`
- `paper_selector_audit_allowed=false`
- `trading_whitelist_allowed=false`
- gate：`4/7` 通过；hard gate：`2/5` 通过。

### 关键数值

| 指标 | 数值 | 判断 |
| --- | ---: | --- |
| P0 固定篮子历史机会 | `226,295` | 有历史材料性，值得继续 forward collection |
| hindsight top6 历史机会 | `428,660` | 只作为上限，不可部署 |
| P0 捕获 hindsight top6 | `52.7913%` | 不足以支持晋级 |
| 全非核心机会合计 | `166,070` | 宽池被尾部亏损抵消 |
| random familycap k6 中位机会 | `19,342.5` | 几乎没有材料性 |
| random familycap k6 p95 机会 | `91,535.75` | 仍远低于材料性机会代理线 |
| 达到 5万 actual sleeve 所需 top6 捕获 | `92.5840%` | selector 门槛很高 |
| Stage256 upper actual sleeve PnL | `54,005` | 历史上界刚过材料性线 |
| 全非核心 actual sleeve PnL | `9,395` | 不通过 |
| P0 top product share | `38.6708%` | 超过 `35%` 偏好线，主要由 `lu.INE` 支撑 |

### 随机 selector 分布

| 模式 | p05 | p50 | p95 | PnL>=50k概率 | 正收益年份>=5概率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| random_all_k3 | `-29,325.5` | `9,792.5` | `66,700.25` | `10.73%` | `6.47%` |
| random_all_k6 | `-33,790.5` | `23,040` | `95,617.5` | `25.64%` | `19.025%` |
| random_familycap_k3 | `-28,701` | `9,487.5` | `66,140.25` | `10.56%` | `5.90%` |
| random_familycap_k6 | `-36,918.5` | `19,342.5` | `91,535.75` | `23.235%` | `15.12%` |

注意：这里的随机分布是 standalone annual opportunity proxy，不等同真实 sleeve PnL；即使 p95 有 `91,535.75`，距离按 Stage256 转换效率推导的 `396,870.66` 机会代理线仍很远。

### P0 产品结构

| 产品 | 总机会 | 正年份 | 最差年份 | 最好年份 | 与 Stage526 日PnL绝对相关 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `lu.INE` | `87,510` | `3` | `-1,730` | `56,400` | `0.1543` |
| `v.DCE` | `50,705` | `6` | `0` | `14,320` | `0.0647` |
| `y.DCE` | `38,140` | `4` | `0` | `17,620` | `0.0072` |
| `ao.SHFE` | `28,840` | `3` | `0` | `13,400` | `0.0159` |
| `c.DCE` | `21,100` | `6` | `-2,650` | `15,910` | `0.0160` |

## 图表视觉复盘

- 左上年度机会图：P0 在 2021/2022/2026 有明显贡献，2023 恰好覆盖 hindsight top6，但 2020 捕获很低，2024/2025 也只覆盖约一半。这说明 P0 不是年度稳定“自动抓趋势”，仍需要更强动态 selector。
- 上中随机分布图：`random_all_k6` 和 `random_familycap_k6` 箱体都集中在低位，p95 也远低于红色材料性机会代理线；这直接否定“只要扩池且同族分散就自然能抓趋势”的想法。
- 右上 P0 热力图：`lu.INE` 的 2026 深绿色块非常突出，P0 总机会被单品种/单年份拉高；`v.DCE` 更均匀，反而更像可持续 selector 的候选底座。
- 左下实际壳图：Stage256 upper 的卫星 PnL `54,005` 刚过线，但全非核心和上一年为正壳都低于或为负；风险壳本身无法替代选品。
- 中下门槛比例图：只有 Stage256 upper 超过 `1`，P0 capture、random p95、all noncore sleeve 和 P0 concentration 都是红色，说明 P0 当前只能继续收集证据，不能晋级。
- 右下 gate 图：通过项集中在“年度机会存在、随机不够、P0历史机会有材料性、门槛已定义”；失败项集中在 P0 route、event coverage 和 paper selector allowed。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage590_breadth_selector_edge_threshold_audit.py`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_report_stage590_breadth_selector_edge_threshold_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_decision_stage590_breadth_selector_edge_threshold_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_chart_stage590_breadth_selector_edge_threshold_audit_v1.png`
- annual edge：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_annual_edge_stage590_breadth_selector_edge_threshold_audit_v1.csv`
- random distribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_random_distribution_stage590_breadth_selector_edge_threshold_audit_v1.csv`
- P0 annual matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_p0_annual_matrix_stage590_breadth_selector_edge_threshold_audit_v1.csv`
- thresholds：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_thresholds_stage590_breadth_selector_edge_threshold_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage590_breadth_selector_edge_threshold_audit_gates_stage590_breadth_selector_edge_threshold_audit_v1.csv`

## 结论

- “降低单笔风险 + 扩大品种池 + 避免高相关 + 选对品种”方向继续保留，但结论更严格：selector 必须接近 top6 机会捕获，弱 selector 或随机 family-cap 远远不够。
- P0 的历史机会足够支持继续 forward collection，但不支持 paper selector audit、交易白名单或 A/B 启动。
- 当前最有价值的 P0 不是直接交易 `lu`，而是补齐 `v/ao/lu` 的事件/舆情账本、`ao/lu` basis 或替代 route，并冻结 `y/c` 同族同向 tie-break。
- 下一步在选品侧仍是 Stage588/590 的同一条路：补 `3/5 -> 5/5` route-ready，补 `2/5 -> 5/5` event-ready，累计 Stage561 `20/20` 合格 forward samples；未达标前禁止任何 P0 收益回测。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只用固定既有输出和固定随机种子做门槛审计，没有修改交易规则、没有用未来收益生成新白名单。
  - 对 P0 的历史优势没有晋级，而是把它降为 forward evidence collection；对 `lu.INE` 这种高历史贡献但 core corr 较高、2026 贡献较重的品种明确标记为集中风险。
  - 若后续为了让 P0 过线去调产品名单、删 2020、调 family cap 或相关阈值，则会转为过拟合。

## 继续价值反思

- 运行前判断：有继续价值。
- 运行后判断：有继续价值，但路径更窄。
- 原因：
  - 年度机会真实存在，P0 历史机会也有材料性；这说明方向不是空想。
  - 但随机 family-cap 和全宽池均证明“增加品种数量”不够；继续价值在 point-in-time selector 证据，而不是风险壳参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage290 摘要。
- 是否更新 `research/registry.md`：是，当前线最新阶段刷新为 Stage290。
- 是否追加根目录 `back_log.md`：是，作为低单笔风险扩池路线的重要门槛结论。
- 是否追加根目录 `memory.md`：否。本阶段不是正式候选或重要突破。
