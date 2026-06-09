# Stage395 Stage393 C2 关闭连败降风险消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-06 20:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读消融 / 回测归因
- 是否重要突破：否，但明确反证“直接关闭连败机制”
- 是否触发A/B：否；本阶段只是用户指定的机制关闭回测，不作为正式候选或 A/B 候选

## 外部调研与判断

- 参考资料：
  - NexusFi consecutive loss protocols: https://nexusfi.com/a/risk-management/consecutive-loss-protocols
  - TradingView/Pine 风控函数说明转述：`strategy.risk.max_cons_loss_days()`，参考 https://pinewizards.com/strategy-functions/strategy-risk-max_cons_loss_days-function/
  - GitHub/开源搜索未找到可直接复用且适合本仓库期货组合路径的连败降仓实现。
- 我的判断：连败后降仓/停手是常见风控思想，但不是无条件更优规则。对趋势组合而言，降仓会挡住亏损期继续扩大，也可能错过恢复期右尾；是否保留必须用账户级路径、成本压力和候选日志验证。本阶段只做消融，不用外部资料决定收益判断。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage682_stage393_c2_no_loss_streak.py`
- 修改脚本：无策略逻辑修改
- 删除脚本：无
- 新增参数：无正式参数；脚本内新增 no-streak 消融覆盖 `streak_risk_multipliers="1.0,1.0,1.0,1.0"`
- 修改参数：仅在 Stage682 回测运行期把 Stage393 C2 的连败风险倍率从默认 `1.0,1.0,1.0,0.1` 改为 `1.0,1.0,1.0,1.0`
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 Stage393 C2 正常成本与 2x/3x 成本压力
- 样本过滤：不做月份、年份、方向、rank、品种筛选
- 策略/归因口径：
  - baseline：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos25`
  - no-streak：`stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_no_loss_streak_maxpos25`
  - 其他保持 Stage393 C2：plus25 含 PVC、no-AI、`risk_ratio_*=0.02`、`short_case1a/2/3`、`maxpos25`

## 结果

- no-streak 期末权益：`755,295`
- no-streak 总收益：`51.0590%`
- no-streak 最大回撤：`-42.1795%`
- no-streak Sharpe：`0.3820`
- no-streak 总滑点：`188,680`
- no-streak 总交易次数：`2,110`
- no-streak 胜率：`51.1968%`
- no-streak broker10 峰值：`60.2934%`
- no-streak p95 broker10：`42.6928%`
- no-streak 2x/3x 成本 DD：`-52.4450% / -64.6389%`
- 相对 Stage393 C2 baseline：
  - 期末权益 `1,528,705 -> 755,295`，少 `773,410`
  - 总收益 `205.7410% -> 51.0590%`，少 `154.682pp`
  - 最大回撤 `-42.8712% -> -42.1795%`，正常成本只浅 `0.692pp`
  - Sharpe `0.7136 -> 0.3820`，少 `0.3316`
  - 交易 `2,012 -> 2,110`，多 `98`
  - 滑点 `273,780 -> 188,680`，少 `85,100`
  - broker10 峰值 `76.4689% -> 60.2934%`，低 `16.1755pp`
  - 2x成本 DD `-48.2339% -> -52.4450%`，恶化 `4.2111pp`
  - 3x成本 DD `-54.4592% -> -64.6389%`，恶化 `10.1797pp`
- 候选层：
  - baseline Stage393：打开候选 `964`，`sizing_zero_volume=278`
  - no-streak：打开候选 `1,023`，`sizing_zero_volume=214`
  - 关闭连败机制确实让开仓候选增加 `59`，0 手候选减少 `64`
- no-streak 风险拆解：
  - `risk_multiplier_0_1_count=0`，全部候选都为 `risk_multiplier=1.0`
  - 但 `sizing_zero_volume` 仍有 `214` 个，其中 `177` 个仍是 `contracts_by_risk=0` 且 `contracts_by_margin>0`
  - no-streak 0 手候选中位数：`target_risk_amount=4,012`，`risk_per_contract=7,191`，`estimated_equity=337,600`，`contracts_by_margin=5`
  - 说明关闭 0.1 档后仍有部分合约单手风险过大，尤其在权益路径更低时仍开不了
- 年度 no-streak：
  - 2020 `+190,630`
  - 2021 `+56,150`
  - 2022 `-168,305`
  - 2023 `-24,690`
  - 2024 `+120,975`
  - 2025 `+81,020`
  - 2026截至4月 `-485`
- 品种贡献 no-streak：
  - PVC `v` 从 baseline 的 `-51,410` 变为 `+7,400`
  - 但 `ag=-89,625`、`jd=-54,820`、`ma=-105,570`、`sm=-33,640`、`sp=-35,080`、`sa=-23,100` 等拖累扩大
  - 强项主要是 `fg=+246,540`、`oi=+104,880`、`jm=+97,710`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_report_stage682_stage393_c2_no_loss_streak_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_summary_stage682_stage393_c2_no_loss_streak_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_comparison_stage682_stage393_c2_no_loss_streak_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_annual_stage682_stage393_c2_no_loss_streak_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_monthly_stage682_stage393_c2_no_loss_streak_v1.csv`
- product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage682_stage393_c2_no_loss_streak_product_stage682_stage393_c2_no_loss_streak_v1.csv`
- candidate/status/risk：`candidate_status`、`candidate_product`、`sizing_limit`、`risk_breakdown`、`entry_candidates`、`entry_risk` 均已输出

## 结论

- 本阶段结论：关闭连败降风险确实增加交易次数和开仓候选，但不修复 Stage393 C2，反而显著损害收益和 Sharpe，并让 2x/3x 成本压力更差。该消融不推广、不接正式、不 A/B。
- 是否进入下一步：不沿着“直接关闭连败机制”继续。
- 下一步：如果目标是增加新品种机会，应研究“非挤占式小风险 sleeve + 独立失败记忆/独立风险预算”，而不是把主策略连败保护整体关掉。

## 过拟合反思

- 运行前判断：不是典型过拟合，因为只做一个明确机制消融，没有扫阈值。
- 运行后判断：仍不是过拟合，但结果不能被拿来继续扫 `0.2/0.3/0.5` 连败倍率。
- 原因：关闭机制后的收益大幅下降，说明问题不是单一阈值过窄，而是共享风险池在亏损期扩仓会破坏账户右尾捕获。

## 继续价值反思

- 运行前判断：有价值，因为它能验证 Stage394 归因里连败机制是否“误杀机会”。
- 运行后判断：直接关闭无继续价值；结构化分层有继续价值。
- 原因：交易多了但收益更差，证明连败机制虽然挡掉部分机会，也在挡坏交易；下一步价值在给新增品种单独小预算，而不是取消主账户保护。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage395 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加机制结论。
