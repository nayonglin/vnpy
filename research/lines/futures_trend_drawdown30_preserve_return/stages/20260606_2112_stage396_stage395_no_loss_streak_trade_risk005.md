# Stage396 Stage395 no-loss-streak 单笔风险0.5%消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-06 21:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：用户指定单点消融 / 风险比例降低
- 是否重要突破：否；提供防守边界，但不恢复收益
- 是否触发A/B：否；基于 Stage395 失败分支的单点归因，不作为正式候选或 A/B 候选

## 外部调研与判断

- 参考资料：
  - CrossTrade Position Sizing: https://crosstrade.io/learn/risk-management/position-sizing
  - NexusFi trade management for futures traders: https://nexusfi.com/a/strategies/trade-management-futures-traders
  - Rulebook futures risk calculator: https://rulebook.trade/futures-risk-calculator/
- 我的判断：0.5% 单笔风险属于常见保守 fixed-fractional 档位，但期货整数手会让低风险比例更容易出现“风险预算不够一手”。本阶段只测试用户指定的 `0.005`，不继续扫 `0.0075/0.01/0.0125` 等小数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage683_stage395_no_loss_streak_trade_risk005.py`
- 修改脚本：无策略逻辑修改
- 删除脚本：无
- 新增参数：无正式参数；脚本内新增 `TARGET_TRADE_RISK_RATIO=0.005`
- 修改参数：基于 Stage395 no-loss-streak C2，把全部 `risk_ratio_*` 从 `0.02` 改为 `0.005`
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：500,000
- 成本口径：正常成本 + 2x/3x 成本压力
- 样本过滤：不做月份、年份、方向、rank、品种筛选
- 策略/归因口径：
  - baseline1：Stage393 C2 `risk_ratio_*=0.02`，默认连败倍率 `1,1,1,0.1`
  - baseline2：Stage395 no-loss-streak `risk_ratio_*=0.02`，连败倍率 `1,1,1,1`
  - target：Stage396 no-loss-streak `risk_ratio_*=0.005`，连败倍率 `1,1,1,1`
  - 其他保持：plus25 含 PVC、no-AI、`short_case1a/2/3`、`maxpos25`

## 结果

- target 期末权益：`851,565`
- target 总收益：`70.3130%`
- target 最大回撤：`-21.6946%`
- target Sharpe：`0.5941`
- target 总滑点：`98,340`
- target 总交易次数：`1,687`
- target 胜率：`50.6057%`
- target broker10 峰值：`53.8118%`
- target p95 broker10：`30.0505%`
- target 2x/3x 成本 DD：`-24.4118% / -27.3360%`
- 相对 Stage395 no-loss-streak risk0.02：
  - 期末权益 `755,295 -> 851,565`，多 `96,270`
  - 收益 `51.0590% -> 70.3130%`，多 `19.254pp`
  - 最大回撤 `-42.1795% -> -21.6946%`，改善 `20.4849pp`
  - Sharpe `0.3820 -> 0.5941`，多 `0.2120`
  - 交易 `2,110 -> 1,687`，少 `423`
  - 2x成本 DD `-52.4450% -> -24.4118%`，改善 `28.0332pp`
  - 3x成本 DD `-64.6389% -> -27.3360%`，改善 `37.3029pp`
- 相对 Stage393 C2：
  - 期末权益 `1,528,705 -> 851,565`，少 `677,140`
  - 收益 `205.7410% -> 70.3130%`，少 `135.428pp`
  - 最大回撤 `-42.8712% -> -21.6946%`，改善 `21.1767pp`
  - Sharpe `0.7136 -> 0.5941`，少 `0.1196`
  - 交易 `2,012 -> 1,687`，少 `325`
  - 2x成本 DD `-48.2339% -> -24.4118%`，改善 `23.8221pp`
  - 3x成本 DD `-54.4592% -> -27.3360%`，改善 `27.1232pp`
- 候选层：
  - 打开候选 `805`
  - `sizing_zero_volume=436`
  - `supply_demand_headwind_blocked=170`
  - 相对 Stage395，打开候选 `1,023 -> 805`，0手候选 `214 -> 436`，说明 `0.005` 明显导致整数手开仓不足
- 风险拆解：
  - 全部候选 `risk_multiplier=1.0`，没有连败 0.1 档
  - 全部候选中 `contracts_by_risk_zero_margin_positive_count=423`
  - 0手候选中位数：`target_risk_amount=1,824`，`risk_per_contract=3,341`，`contracts_by_margin=15`
  - 打开候选中位数：`target_risk_amount=1,987`，`risk_per_contract=702`，`selected_volume=2`
- 年度：
  - 2020 `+57,650`
  - 2021 `-51,250`
  - 2022 `+55,630`
  - 2023 `-8,715`
  - 2024 `+132,260`
  - 2025 `+179,750`
  - 2026截至4月 `-13,760`
- 品种贡献：
  - 正贡献较大：`lh +167,040`、`fg +80,580`、`oi +76,250`、`fu +69,670`
  - PVC `v +2,505`，基本不是主要贡献
  - 拖累：`ma -52,860`、`au -37,860`、`sm -25,890`、`cf -21,850`、`jm -16,200`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_report_stage683_stage395_no_loss_streak_trade_risk005_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_summary_stage683_stage395_no_loss_streak_trade_risk005_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_comparison_stage683_stage395_no_loss_streak_trade_risk005_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_annual_stage683_stage395_no_loss_streak_trade_risk005_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_monthly_stage683_stage395_no_loss_streak_trade_risk005_v1.csv`
- product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage683_stage395_no_loss_streak_trade_risk005_product_stage683_stage395_no_loss_streak_trade_risk005_v1.csv`
- candidate/status/risk：`candidate_status`、`candidate_product`、`sizing_limit`、`risk_breakdown`、`entry_candidates`、`entry_risk` 均已输出

## 结论

- 本阶段结论：`risk_ratio_*=0.005` 明显修复 Stage395 no-loss-streak 的风险暴露，回撤和成本压力都变好；但它没有恢复收益，相对 Stage393 C2 少 `677,140` 期末权益，且交易次数下降到 `1,687`，和“增加机会”的初衷冲突。该版本只能作为防守边界观察，不推广、不 A/B。
- 是否进入下一步：不沿着 no-loss-streak + 低风险小数继续扫。
- 下一步：如果继续，应回到结构设计：新品种独立 sleeve、独立风险预算或事前 selector；不继续扫 `0.0075/0.01/0.0125`。

## 过拟合反思

- 运行前判断：有过拟合风险，因为这是在失败分支上调整单笔风险小数；可接受的原因是用户指定单点且 `0.5%` 是常见保守档位。
- 运行后判断：继续扫小数会过拟合。
- 原因：本次已证明降到 `0.005` 主要是防守降档，不是恢复 alpha 或增加机会；若继续调小数，本质是在找历史收益/回撤折中点。

## 继续价值反思

- 运行前判断：有价值，因为它检验“更多机会 + 更低单笔风险”能否替代连败保护。
- 运行后判断：直接路线价值有限；结构化 sleeve 仍有价值。
- 原因：回撤被压住但收益不够，且大量候选重新因为整数手风险预算不足而开不了，说明共享池里调风险比例不能同时满足“更多机会”和“高收益保留”。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage396 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加防止继续扫小数的结论。
