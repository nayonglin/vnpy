# Stage390 Stage372 50万 risk_ratio 0.02 plus24 鸡蛋 no-AI 消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 18:11 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage389 之后的 AI product pool filter 关闭消融，对照 AI selector 是否是主要拖累。
- 是否重要突破：否，是重要反证和归因澄清，不进入正式候选。
- 是否触发A/B：是，按 A/C/C2 口径审计，但不修改正式配置。

## 外部调研与判断

- 参考资料：
  - AQR `A Century of Evidence on Trend-Following Investing`：长期趋势跟踪的核心证据来自跨市场、跨资产、多周期的分散暴露，而不是事后挑市场。
  - AQR `Trends Everywhere`：趋势证据可以扩展到更多资产和合约，但需要 out-of-sample 验证和组合层风险控制。
  - `pysystemtrade` backtesting 文档：工程实践中更偏固定资本、风险贡献和 instrument diversification multiplier，选品/权重必须做消融。
- 我的判断：用户要求“AI 整体关掉”是正确的消融实验。它能区分 Stage389 失败到底是 `jd`/plus24 池本身坏，还是现有 AI selector 把账户级路径排坏。关闭 AI 本身不是过拟合；但如果看到结果后继续按单品种、月份、rank、topN 去修补，就会过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `EXTRA_PRODUCTS=(ni.SHFE, ag.SHFE, sc.INE, p.DCE, jd.DCE)`
  - `enable_ai_product_pool_filter=False`
  - `TARGET_TRADE_RISK_RATIO=0.02`
  - `TARGET_NO_MAXPOS_VARIANT=stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos24`
- 修改参数：
  - plus 宇宙从 Stage372 官方池扩为 `24` 个产品，但不读取 AI eligibility 作为入场过滤。
  - A/C/C2 均使用同一 no-AI plus24 宇宙。
- 删除参数：
  - 删除 AI product pool filter 的实际约束效果；`ai_product_pool_eligibility_path` 和 `ai_product_pool_strategy` 在策略内不再参与过滤。

## 回测/归因参数

- 数据区间：历史窗口 `2020-01-01` 至 `2026-04-30`；YTD runner 为 `2026-01-01` 至 `2026-06-05`。
- 账户规模：`500,000`
- 成本口径：正常成本、2x 成本、3x 成本压力。
- 样本过滤：no-AI，所有 plus24 产品都由原趋势逻辑、风险资金和 `maxpos` 约束决定是否交易。
- 策略/归因口径：
  - A：`stage372_500k_trade_risk004_no_ai_plus24_jd_maxpos4`
  - C：`stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos4`
  - C2：`stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos24`

## 结果

- A 全周期：期末权益 `2,635,205`，总收益 `427.0410%`，最大回撤 `-55.8621%`，Sharpe `0.9030`，总滑点 `436,400`，总交易次数 `1,145`，胜率 `50.7647%`，broker10 峰值 `74.3386%`，2x/3x 成本 DD `-59.8156%/-65.2201%`。
- C 全周期：期末权益 `1,293,925`，总收益 `158.7850%`，最大回撤 `-46.6154%`，Sharpe `0.6557`，总滑点 `220,730`，总交易次数 `1,072`，胜率 `50.7636%`，broker10 峰值 `73.8618%`，2x/3x 成本 DD `-55.2377%/-64.5268%`。
- C2 全周期：期末权益 `1,233,455`，总收益 `146.6910%`，最大回撤 `-48.3450%`，Sharpe `0.6034`，总滑点 `233,720`，总交易次数 `1,379`，胜率 `50.5400%`，broker10 峰值 `86.8082%`，2x/3x 成本 DD `-56.7806%/-66.7599%`。
- C 相对 A：收益少 `268.2560pp`，最大回撤改善 `9.2467pp`，Sharpe 少 `0.2473`，滑点少 `215,670`，但仍远破 DD30。
- C2 相对 C：收益少 `12.0940pp`，最大回撤恶化 `1.7296pp`，交易多 `307`，保证金峰值高 `12.9464pp`，放宽并发失败。
- C 多周期：
  - `since_2021`：`588,460/17.6920%/-41.0096%/Sharpe0.2519`
  - `since_2022`：`369,680/-26.0640%/-34.1949%/Sharpe-0.3778`
  - `since_2023`：`456,730/-8.6540%/-28.2766%/Sharpe-0.0716`
  - `since_2024`：`487,080/-2.5840%/-25.8902%/Sharpe0.0118`
  - `since_2025`：`689,050/37.8100%/-17.6534%/Sharpe1.0990`
  - `phase_2022_2023`：`365,825/-26.8350%/-34.1949%/Sharpe-0.9554`
  - `weak_2021_drawdown`：`470,540/-5.8920%/-15.8311%/Sharpe-0.9553`
  - `ytd_2026_latest_ai`：`504,010/0.8020%/-11.3760%/Sharpe0.2003`。注意该窗口名沿用 runner 历史标签，实际策略已经关闭 AI filter。
- C 滚动窗口：
  - 63日：p05 `-19.1595%`，min `-37.3875%`
  - 126日：p05 `-23.2586%`，min `-36.3831%`
  - 252日：p05 `-26.7428%`，min `-38.2214%`
- C 资金占用：active days `1,318`，active rate `86.0313%`，avg all `18.5542%`，active day avg `21.5668%`，p95 `45.7405%`，max `73.8618%`，`>30%` `337` 天，`>50%` `46` 天，`>70%` `2` 天，`>90/>100` 均 `0`。
- C 扩展品种贡献：`ag +155,055`，`jd -59,650`，`ni -310,520`，`p +57,200`，`sc -76,800`，合计 `-234,715`；总滑点 `35,630`，扩展品种交易 `288`。
- 与 Stage389 AI plus24 C 对照：Stage389 为 `757,270/51.4540%/-60.9205%/Sharpe0.3988`，Stage390 no-AI C 为 `1,293,925/158.7850%/-46.6154%/Sharpe0.6557`。关闭 AI 明显恢复收益和回撤，但仍不过 DD30。
- 与 Stage388 AI plus23 C 对照：Stage388 为 `1,118,385/123.6770%/-50.9778%/Sharpe0.6544`，Stage390 no-AI C 略高收益、略浅回撤。
- 与 Stage387 固定四品种 C 对照：Stage387 为 `4,634,210/826.8420%/-25.3045%/Sharpe1.3707`，Stage390 no-AI plus24 仍显著更差。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_report_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_summary_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_comparison_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_rolling_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_margin_usage_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv`
- activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_extra_activity_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_decision_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.json`

## 结论

- 本阶段结论：`stage372_500k_trade_risk002_no_ai_plus24_jd_rejected`。
- 是否进入下一步：不作为正式候选，不 A/B，不改官方实盘。
- 下一步：停止 plus24 鸡蛋 no-AI 裸跑路线；若继续，只能研究更低自由度的账户级 selector/风险槽，或者回到 Stage387 固定四品种口径做保证金峰值和品种贡献归因。

## 过拟合反思

- 运行前判断：否。关闭 AI 是干净的消融实验，有明确第一性原理目的。
- 运行后判断：本次实验本身不是过拟合；但如果根据 `ni/sc/jd` 的历史亏损去做黑名单、月份过滤或 rank 调整，就是过拟合。
- 原因：结果显示 AI selector 是 Stage389 的重要拖累来源，但 no-AI 全池仍然有账户级路径风险，不能用事后品种筛选修补。

## 继续价值反思

- 运行前判断：有价值。它能判断是否应该完全放弃 AI selector，还是只需要重训 selector。
- 运行后判断：当前 no-AI plus24 候选无推广价值；AI selector 重构仍有价值。
- 原因：no-AI C 比 AI plus24 C 好，但仍远破 DD30，说明问题不是单纯“AI 开或关”，而是扩池后的账户级风险预算、并发约束和选品目标没有统一。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage390 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加关键反证和后续约束。
