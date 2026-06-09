# Stage394 Stage393 PVC 交易次数减少归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-06 20:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / 诊断回放
- 是否重要突破：否，但修正了“资金够却交易减少”的机制理解
- 是否触发A/B：否；本阶段不是候选推广，只解释 Stage393 相对 Stage391 C2 的交易次数和资金占用变化

## 外部调研与判断

- 参考资料：
  - CME Group Performance Bonds/Margins: https://www.cmegroup.com/solutions/risk-management/performance-bonds-margins.html
  - Interactive Brokers Futures & FOPs Margin Overview: https://www.interactivebrokers.com/en/trading/margin-futures-fops.php
- 我的判断：外部资料只用于复核概念边界。期货保证金是持仓履约/风险保证金，能否开仓还取决于账户内部风险预算、止损距离、单笔上限和组合约束。本地引擎的主开仓手数由 `min(contracts_by_risk, contracts_by_margin, contracts_by_single_trade_cap, max_position_size)` 决定，所以“保证金足够”不等于“策略风险预算允许开更多手”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage681_stage393_pvc_trade_count_attribution.py`
- 修改脚本：无策略逻辑修改；新增脚本仅复用 Stage679/Stage680 配置并导出诊断
- 删除脚本：无
- 新增参数：无策略参数；新增诊断输出 `entry_candidates/entry_risk/product_trade_delta/candidate_status/sizing_limit/year_end/monthly_delta`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 Stage391/Stage393 正常成本与本地 broker10 保证金审计
- 样本过滤：不做新品种月份、年份、方向、rank 或 case 筛选
- 策略/归因口径：
  - Stage391 C2：`stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24`
  - Stage393 C2：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos25`
  - 两者均关闭 AI product pool filter，允许 `short_case1a/short_case2/short_case3`，`risk_ratio_*=0.02`

## 结果

- Stage393 C2 期末权益：`1,528,705`
- Stage393 C2 总收益：`205.7410%`
- Stage393 C2 最大回撤：`-42.8712%`
- Stage393 C2 Sharpe：`0.7136`
- Stage393 C2 总滑点：`273,780`
- Stage393 C2 总交易次数：`2,012`
- Stage393 C2 胜率：`51.3351%`
- Stage391 C2 对照：`3,465,220 / 593.0440% / -33.5078% / Sharpe 1.0047 / 滑点 496,710 / 交易 2,114`
- 交易次数差异：Stage393 相对 Stage391 少 `102` 笔。
- 候选层：总候选数从 `1,354` 增至 `1,413`，说明 PVC 确实增加了信号机会；但实际打开候选从 `988` 降至 `964`，`sizing_zero_volume` 从 `197` 增至 `278`。
- 手数层：总 `selected_volume_sum` 从 `15,183` 降至 `9,194`，减少 `5,989` 手，约 `-39.45%`。
- 保证金不是主约束：Stage391 打开候选中 `risk` 约束 `960/988`，`margin` 约束 `20/988`；Stage393 打开候选中 `risk` 约束 `935/964`，`margin` 约束 `19/964`。打开候选里 `contracts_by_risk < contracts_by_margin` 的比例分别为 `97.2672%` 与 `97.1992%`。
- “资金够但不开”的直接证据：Stage393 的 `sizing_zero_volume` 中 `256/278` 个候选是 `contracts_by_risk=0` 且 `contracts_by_margin>0`，`contracts_by_margin<=0` 为 `0`；也就是保证金够一手，但风险预算不够一手。
- 打开候选中位数：Stage391 `contracts_by_risk=8 / contracts_by_margin=87 / selected_volume=7 / estimated_equity=1,059,472.5`；Stage393 `contracts_by_risk=7 / contracts_by_margin=65 / selected_volume=5.5 / estimated_equity=718,670`。
- 风险预算为什么小：
  - 主要原因是连败档位触发。Stage393 的 `sizing_zero_volume` 中 `203/278` 个候选处于 `risk_multiplier=0.1`，Stage391 为 `154/197`。
  - Stage393 的 `sizing_zero_volume` 中 `loss_streak>=3` 为 `194/278`，Stage391 为 `140/197`；`streak_risk_multipliers` 最后一档会把风险预算压到原来的 `10%`。
  - 失败记忆微调不是原因：`failure_memory_micro_sizing_applied=0`，且 reason 全为 `disabled`。
  - 组合过热冷却不是原因：`portfolio_overheat_cooldown_scale=1.0`，未触发降风险。
  - 结构恢复/恢复仓没有救起这些 0 手候选：Stage393 0 手候选中 `streak_entry_structure_risk_recovery_applied=4`，但 `recovery_sleeve_applied=0`，主要 reason 为 `signal_not_allowed=212`、`portfolio_not_flat=62`、`cooldown=4`。
  - PVC 后权益更低也放大了这个效果。Stage393 0 手候选中位数为 `target_risk_amount=1,062 / risk_per_contract=3,341 / estimated_equity=649,990 / limited_balance=459,453`；Stage391 为 `1,516 / 3,836 / 874,570 / 585,639`。所以不是只有连败机制，而是“连败 0.1 倍率 + 更低权益路径 + 单手风险大于预算”共同造成。
- 品种组交易变化：
  - 核心老品种：交易 `1,635 -> 1,503`，少 `132` 笔，净 PnL 少 `1,102,530`
  - 旧新增组 `ag/ni/sc/p/jd`：交易 `479 -> 415`，少 `64` 笔，净 PnL 少 `782,575`
  - PVC `v`：新增 `94` 笔，但自身净 PnL `-51,410`
- 品种组选中手数：
  - 核心老品种 `12,741 -> 6,994`
  - 旧新增组 `2,442 -> 1,392`
  - PVC 新增 `808`
- 年末权益比例 `Stage393/Stage391`：2020 `98.17%`，2021 `85.81%`，2022 `73.57%`，2023 `70.91%`，2024 `71.24%`，2025 `50.51%`，2026截至4月 `44.12%`。权益路径变差后，后续每笔 `risk_ratio * limited_balance` 都同步缩小。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage681_stage393_pvc_trade_count_attribution_report_stage681_stage393_pvc_trade_count_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage681_stage393_pvc_trade_count_attribution_decision_stage681_stage393_pvc_trade_count_attribution_v1.json`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage681_stage393_pvc_trade_count_attribution_monthly_delta_stage681_stage393_pvc_trade_count_attribution_v1.csv`
- quality：`candidate_status / candidate_product / sizing_limit / entry_candidates / entry_risk` 诊断 CSV 已输出

## 结论

- 本阶段结论：用户说“看起来资金完全足够开仓”是对的，但这里的资金是保证金维度。交易次数和资金占用减少的主因不是现金/保证金不够，而是 PVC 进入同一个账户风险预算后，前期权益路径变差，`risk_ratio * limited_balance` 缩小；同时 PVC 自身新增 `94` 笔交易，挤不回核心老品种减少的 `132` 笔和旧新增组减少的 `64` 笔。
- 是否进入下一步：不进入 PVC 救援，也不推广 Stage393。
- 下一步：若目标是“尝试更多机会”，正确方向不是继续把新品种塞进同一个共享风险池，而是做非挤占式小风险 satellite/sleeve 或事前 selector，只允许新增品种使用独立且有限的风险预算，不能挤掉原 C2 的老品种右尾机会。

## 过拟合反思

- 运行前判断：否。本阶段只做 Stage391 vs Stage393 的只读归因，没有新增交易规则或筛选条件。
- 运行后判断：否，但如果继续按 PVC 的月份、方向、年份、rank 或并发整数补丁去救结果，会转为明显过拟合。
- 原因：结论来自候选日志、风险/保证金手数拆解和权益路径对照，不来自选择性挑窗口。

## 继续价值反思

- 运行前判断：有价值。用户的问题是机制问题，不拆清楚会误把“保证金够”理解成“系统应该开更多”。
- 运行后判断：有价值，但价值转向结构设计，不在 PVC 单品种救援。
- 原因：已经证明新增品种增加了候选数，却在共享风险预算里降低总选中手数和核心右尾捕获；下一步若做，应验证非挤占式 sleeve 是否能把新增品种变成真正增量机会。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage394 归因摘要。
- 是否更新 `research/registry.md`：否，研究线定义不变。
- 是否追加根目录 `memory.md/back_log.md`：是，追加一条重要机制记忆与阶段摘要。
