# Stage397 Stage395 no-loss-streak 单笔风险1%消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-07 04:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：用户指定单点风险比例消融；非正式候选。
- 是否重要突破：否
- 是否触发A/B：否。已读取 `skills/version-ab-experiment/SKILL.md`，本次属于小数风险比例单点复核，不作为正式 A/B/C 推广。

## 外部调研与判断

- 参考资料：
  - Pomegra fixed fractional sizing：固定比例 sizing 用账户权益的一定百分比除以每笔交易风险，风险比例随权益动态调整。
  - Stator fixed fractional position sizing：固定风险分数 sizing 的合约数核心公式是 `N = f * Equity / TradeRisk`，且建议用路径/Monte Carlo 估计未来回撤风险。
  - NexusFi/TradeAlgo 等期货风控文章：期货常见单笔风险尺度约为 `1%-2%`，但必须和波动率、止损距离、最小合约单位匹配。
- 我的判断：`0.01` 是常见风险尺度，不是离谱参数；但本仓库的关键约束是中国商品期货最小一手、共享账户风险预算、连败机制关闭后的路径质量。仅把 `0.005` 改到 `0.01` 不解决 selector/机会质量问题，只是在低质量路径上放大仓位。本次可作为用户指定单点消融，但不应继续扫 `0.0075/0.0125/0.015`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage684_stage395_no_loss_streak_trade_risk001.py`
- 修改脚本：无正式策略脚本修改；Stage684 后续补充曲线 CSV 和 PNG 输出。
- 删除脚本：无
- 新增参数：
  - `TARGET_TRADE_RISK_RATIO = 0.01`
  - `TARGET_VARIANT = stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_no_loss_streak_maxpos25`
  - 输出 `curves` 和 `chart`
- 修改参数：
  - 相对 Stage396：全部 `risk_ratio_*` 从 `0.005` 改为 `0.01`
  - 保留 `streak_risk_multipliers=1.0,1.0,1.0,1.0`
  - 保留 plus25/PVC、no-AI、`short_case1a/2/3`、`maxpos25`
- 删除参数：无
- 正式配置：未修改
- CTP/下单：未连接 CTP，未调用 order API

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：500,000
- 成本口径：正常成本，同时输出 2x/3x 成本压力
- 样本过滤：沿用 Stage395/396 全周期口径
- 策略/归因口径：
  - 基于 Stage395 no-loss-streak C2
  - 关闭 AI product pool filter
  - plus25 含 PVC `v.DCE`
  - 允许 `short_case1a/short_case2/short_case3`
  - 关闭连败风险降档：`streak_risk_multipliers=1.0,1.0,1.0,1.0`
  - 仅把单笔风险比例调为 `0.01`

## 结果

- 期末权益：`613,860`
- 总收益：`22.7720%`
- 最大回撤：`-40.1898%`
- Sharpe：`0.2692`
- 总滑点：`104,850`
- 总交易次数：`1,767`
- 胜率：`49.7319%`
- broker10 资金占用：
  - 峰值：`59.5076%`
  - p95：`31.5303%`
  - 超 90/100 天数：`0/0`
- 强制保证金降仓：`7` 次，合计 `51` 手
- 部署闸门：`deployable_pass=0`，主要因为最大回撤跌破 `-40%` 边界
- 成本压力：
  - 2x：期末权益 `509,010`，总收益 `1.8020%`，最大回撤 `-48.5104%`，Sharpe `0.1224`
  - 3x：期末权益 `404,160`，总收益 `-19.1680%`，最大回撤 `-58.0307%`，Sharpe `-0.0182`

## 对比结论

- 相对 Stage396 no-loss-streak `risk0.005`：
  - 交易次数 `1,687 -> 1,767`，只增加 `80` 笔
  - 期末权益 `851,565 -> 613,860`，减少 `237,705`
  - 总收益 `70.3130% -> 22.7720%`，减少 `47.541pp`
  - 最大回撤 `-21.6946% -> -40.1898%`，恶化 `18.4952pp`
  - Sharpe `0.5941 -> 0.2692`，减少 `0.3248`
  - 2x/3x 成本 DD 从 `-24.4118%/-27.3360%` 恶化到 `-48.5104%/-58.0307%`
- 相对 Stage395 no-loss-streak `risk0.02`：
  - 期末权益少 `141,435`
  - 最大回撤浅 `1.9897pp`
  - Sharpe 少 `0.1128`
  - 交易少 `343`
  - 2x/3x 成本 DD 改善，但正常成本收益不足
- 相对 Stage393 C2：
  - 期末权益少 `914,845`
  - 总收益少 `182.969pp`
  - 最大回撤仅浅 `2.6814pp`
  - Sharpe 少 `0.4444`
  - 交易少 `245`

## 年度结果

- 2020：`+125,840`
- 2021：`-64,485`
- 2022：`-85,015`
- 2023：`-60,670`
- 2024：`+70,465`
- 2025：`+127,185`
- 2026截至4月：`+540`

## 候选与归因

- 候选层：
  - `opened=848`
  - `sizing_zero_volume=390`
  - `supply_demand_headwind_blocked=170`
  - 所有候选 `1,408`
  - `risk_multiplier_0.1_count=0`
  - `loss_streak_ge3_count=397`
  - `contracts_by_risk_zero_margin_positive_count=389`
- 0 手候选：
  - `count=390`
  - 其中 `contracts_by_risk=0` 且 `contracts_by_margin>0` 为 `340`
  - 中位 `target_risk_amount=1,953.342`
  - 中位 `risk_per_contract=3,870`
  - 中位 `contracts_by_margin=8`
- 打开候选主要仍由风险预算约束：
  - `risk=825`
  - `margin=5`
  - `single_trade_cap=13`
  - 其他混合约束合计 `5`
- 品种贡献：
  - 主要正贡献：`fg +136,740`，`lh +92,400`，`ap +83,840`，`oi +75,130`
  - 主要负贡献：`ma -71,460`，`ag -58,800`，`sm -43,470`，`au -41,420`
  - PVC `v=-18,360`
- 相对 `0.005` 的品种恶化：
  - `ag -82,980`
  - `lh -74,640`
  - `fu -63,390`
  - `hc -56,190`
  - `sa -29,040`
  - `v -20,865`
  - `ma -18,600`
  - `sm -17,580`
  - 主要改善为 `fg +56,160`、`ap +52,630`、`ni +22,490`，但无法抵消亏损腿放大。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_report_stage684_stage395_no_loss_streak_trade_risk001_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_summary_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_cost_stress_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_comparison_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_annual_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_monthly_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_curves_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_chart_stage684_stage395_no_loss_streak_trade_risk001_v1.png`
- product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_product_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- candidate_status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_candidate_status_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- candidate_product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_candidate_product_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- sizing_limit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_sizing_limit_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- risk_breakdown：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_risk_breakdown_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_positions_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_entry_candidates_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- risk ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_entry_risk_stage684_stage395_no_loss_streak_trade_risk001_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage684_stage395_no_loss_streak_trade_risk001_decision_stage684_stage395_no_loss_streak_trade_risk001_v1.json`

## 结论

- 本阶段结论：`stage395_no_loss_streak_trade_risk001_ablation_only_not_promoted`
- 核心判断：`0.01` 没有实现“风险比 0.005 高一点、机会更多、收益恢复”的预期。它只比 `0.005` 多 `80` 笔，但把回撤从 `-21.6946%` 放大到 `-40.1898%`，收益反而少 `237,705`，说明新增/放大的是低质量路径而非有效机会。
- 是否进入下一步：否，不推广、不 A/B。
- 下一步：
  - 停止继续扫 `0.0075/0.0125/0.015` 这类风险小数。
  - 若目标仍是“新增品种带来更多机会”，应转为新品种独立 sleeve / 独立风险预算 / 非挤占式风险槽，而不是共享主账户风险比例微调。
  - 如果继续做 selector，应重对齐训练目标到组合路径质量，而不是事后用单品种或年份筛选救援。

## 过拟合反思

- 运行前判断：有过拟合风险。用户指定 `0.01` 可跑作单点复核，但我们已经知道连续小数调参是过拟合高危形状。
- 运行后判断：是，继续沿这条线会过拟合。
- 原因：`0.01` 的失败说明收益/回撤差异不是一个平滑可调的风险比例函数，而是由低质量候选、共享风险池、整数手约束和弱环境路径共同决定。继续找某个小数救结果，本质是在历史路径上贴合噪声。

## 继续价值反思

- 运行前判断：有有限价值。它能回答 `0.005` 是否太保守、`0.01` 是否能恢复机会。
- 运行后判断：直接继续本形状无价值。
- 原因：`0.01` 相对 `0.005` 只增加少量交易却显著恶化路径，且相对 Stage393/Stage395 均无推广价值。更有价值的方向是结构性隔离风险预算，而不是风险比例小数搜索。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage397 摘要。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：是，追加本次用户指定回测和路线收束结论。
