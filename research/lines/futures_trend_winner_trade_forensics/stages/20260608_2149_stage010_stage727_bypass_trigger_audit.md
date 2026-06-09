# Stage010 - Stage727 bypass触发审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage727 候选触发层审计；只读归因，不作为正式候选。
- 是否重要突破：否，关键否定证据。
- 是否触发A/B：否。候选无真实触发，不进入正式 A/B。

## 外部调研与判断

- 参考资料：
  - Meta-labeling 概念：`https://en.wikipedia.org/wiki/Meta-Labeling`
  - 近期 meta-labeling 风险提示：`https://stockalpha.ai/alpha-learning/meta-labeling-for-trade-selection-filtering-signals-by-context-not-confidence`
  - 趋势跟随回测与风控参考：`https://www.futuresbacktest.com/docs/strategies/trend/`
  - 开源趋势跟随参考：`https://github.com/amstrdm/mlm-trend-following`
- 我的判断：外部资料支持用“上下文过滤”做二级机会质量判断，但也明确提醒这类过滤容易学到 regime 噪音。本阶段不继续造新条件，只审计 Stage727 是否真实触发；如果没有触发，就不能把 A/C 指标一致误判为稳健通过。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage728_stage727_bypass_trigger_audit.py`
- 修改脚本：重生成该脚本一次，收窄 `relevant_entry_risk` 输出，只保留真正进入 structure/sleeve/bypass 的行，并新增触发条件分解字段。
- 删除脚本：无。
- 新增参数：无正式参数；审计窗口为 `full_2020_20260430`、`since_2022`、`phase_2022_2023`、`since_2026`。
- 修改参数：无正式参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - `full_2020_20260430`：`2020-01-01` 至 `2026-04-30`
  - `since_2022`：`2022-01-01` 至 `2026-04-30`
  - `phase_2022_2023`：`2022-01-01` 至 `2023-12-31`
  - `since_2026`：`2026-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：复用 Stage727/正式 Stage372 成本。
- 样本过滤：只看 Stage727 候选 `stage526_200k_force95_to80_official_sleeve_edge60_bypass_stage727` 的 `entry_risk` 与 `entry_candidates` 诊断。
- 策略/归因口径：保留官方 `recovery_sleeve`；统计 `recovery_sleeve_normal_risk_bypassed` 是否触发，并拆分 `directional_edge60` 与账户回撤 `<=5%` 两个条件。

## 结果

### Stage727路径指标引用

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 recovery sleeve | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% |
| C Stage727 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% |

### 触发审计

| 窗口 | entry risk | opened candidates | structure recovery | sleeve applied | directional_edge60通过 | DD<=5%通过 | 两条件同时通过 | bypass触发 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full_2020_20260430 | 315 | 293 | 13 | 13 | 7 | 0 | 0 | 0 |
| since_2022 | 102 | 98 | 19 | 19 | 11 | 0 | 0 | 0 |
| phase_2022_2023 | 39 | 38 | 8 | 8 | 4 | 0 | 0 | 0 |
| since_2026 | 10 | 10 | 3 | 3 | 3 | 0 | 0 | 0 |
| 合计 | 466 | 439 | 43 | 43 | 25 | 0 | 0 | 0 |

- `total_structure_recovery_applied_count=43`
- `total_sleeve_applied_count=43`
- `total_directional_edge60_pass_count=25`
- `total_account_drawdown_5pct_pass_count=0`
- `total_both_bypass_condition_pass_count=0`
- `total_bypass_trigger_count=0`
- 43 笔 sleeve 行的账户回撤分布：最小 `8.1901%`，中位数约 `19.1292%`，最大 `31.5981%`。因此不是 directional edge 完全无效，而是官方 sleeve 触发时账户已经不在 `DD<=5%` 的健康区。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_report_stage728_stage727_bypass_trigger_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_summary_stage728_stage727_bypass_trigger_audit_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_entry_risk_stage728_stage727_bypass_trigger_audit_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_entry_candidates_stage728_stage727_bypass_trigger_audit_v1.csv`
- relevant_entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_relevant_entry_risk_stage728_stage727_bypass_trigger_audit_v1.csv`
- reasons：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_reasons_stage728_stage727_bypass_trigger_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage728_stage727_bypass_trigger_audit_decision_stage728_stage727_bypass_trigger_audit_v1.json`

## 结论

- 本阶段结论：`stage727_empty_pass_no_bypass_trigger_not_promoted`。
- Stage727 的 A/C 完全一致不是稳健通过，而是正常风险 bypass 没有触发。
- `directional_edge60` 在官方 recovery sleeve 行中确实有 `25/43` 次方向通过，但账户健康条件 `DD<=5%` 为 `0/43`，两者没有交集。
- 因此，`directional_edge60 + DD<=5%` 在“保留官方 sleeve 的正式结构”中不是可交易化的高质量机会豁免特征。
- 正式版继续保持 Stage372/20万 `1,1,1,0.1 + recovery_sleeve`，不修改官方配置。

## 过拟合反思

- 运行前判断：否。审计只是解释 Stage727 的无效果，不新增可交易阈值。
- 运行后判断：继续扫 `DD 5/10/15%` 或 `edge60` 阈值会过拟合。
- 原因：当前证据显示触发交集为 0；为了制造交易差异去放宽账户回撤阈值，本质是在历史 sleeve 样本上反推触发点，而不是发现稳健质量特征。

## 继续价值反思

- 运行前判断：有价值。否则 Stage727 的全绿检查容易被误读成“策略稳健通过”。
- 运行后判断：本形状没有继续价值；总目标仍有价值，但必须换特征来源或验证方式。
- 原因：现有历史字段和 `directional_edge60/DD` 组合已经连续被 Stage721/722/724/725/727/728 约束住，继续在同一字段堆条件只会提高拟合风险。

## 后续规划

- 不合入正式版，不开正式 A/B。
- 不扫 `DD` 阈值、`edge60` 周期、close-position 阈值、RSI/OI/volume、品种或年份补丁。
- 若继续寻找高质量机会豁免，只能转：
  - 账户级 selector：目标直接对齐账户收益、回撤、成本、保证金、右尾保留。
  - 预声明 forward watch：先积累真实 OOS 触发样本。
  - 新外生特征：必须在入场时点可得，且通过分段、冷启动、成本压力和样本覆盖约束。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为当前“高质量机会豁免尚未找到可靠特征”的边界证据。
