# Stage391 Stage372 50万 risk_ratio 0.02 plus24 鸡蛋 no-AI 放宽空头case

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-06 19:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage390 no-AI plus24 鸡蛋口径下，放宽新开空信号白名单，从只允许 `short_case1a` 改为允许 `short_case1a/short_case2/short_case3`。
- 是否重要突破：否。`maxpos24` 暴露出短空case有 alpha 线索，但主候选 `maxpos4` 明确失败，不能推广。
- 是否触发A/B：是，按 A/C/C2 对照审计。

## 外部调研与判断

- 参考资料：
  - AQR `Trends Everywhere`：趋势跟踪证据可以扩展到更多市场和合约，但需要跨资产、跨周期、不同市场环境验证。
  - AQR `A Century of Evidence on Trend-Following Investing`：长期趋势跟踪核心在于跨市场 long/short 期货暴露和风险控制，不是单个入场形态。
  - `pysystemtrade`：系统化趋势跟踪实践中更重视 forecast diversification、instrument diversification 和成本/风险预算，而不是事后筛某个 MA case。
- 我的判断：放宽 short case 有结构理由，因为只允许 `MA5` 下穿 `MA10` 可能过窄，漏掉 `10/20`、`20/40` 和 MACD death 的下跌趋势；但这也会增加反复交易和趋势后段信号，需要全周期、起点年、成本压力和 `maxpos` 冲突一起验证。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `ALLOWED_SHORT_SIGNALS={short_case1a, short_case2, short_case3}`
  - `enable_ai_product_pool_filter=False`，沿用 Stage390 no-AI 口径
  - `TARGET_TRADE_RISK_RATIO=0.02`
  - `TARGET_NO_MAXPOS_VARIANT=stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24`
- 修改参数：
  - `_can_open_short_signal()` 仅在 Stage679 脚本运行期 monkeypatch 为允许 `short_case1a/2/3`。
  - plus 宇宙仍为 Stage372 官方池 + `ni.SHFE/ag.SHFE/sc.INE/p.DCE/jd.DCE` 共 `24` 个产品。
- 删除参数：无。

## 回测/归因参数

- 数据区间：历史窗口 `2020-01-01` 至 `2026-04-30`；YTD runner 为 `2026-01-01` 至 `2026-06-05`。
- 账户规模：`500,000`
- 成本口径：正常成本、2x 成本、3x 成本压力。
- 样本过滤：no-AI，所有 plus24 产品都由原趋势逻辑、风险资金、空头 case 白名单和 `maxpos` 决定。
- 策略/归因口径：
  - A：`stage372_500k_trade_risk004_no_ai_plus24_jd_short_cases123_maxpos4`
  - C：`stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4`
  - C2：`stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24`

## 结果

- A 全周期：期末权益 `1,215,420`，总收益 `143.0840%`，最大回撤 `-63.3145%`，Sharpe `0.5712`，总滑点 `325,480`，总交易次数 `1,514`，胜率 `50.0336%`，broker10 峰值 `62.2702%`，2x/3x 成本 DD `-72.0657%/-81.5166%`。
- C 全周期：期末权益 `601,605`，总收益 `20.3210%`，最大回撤 `-52.3961%`，Sharpe `0.2589`，总滑点 `179,670`，总交易次数 `1,366`，胜率 `49.9327%`，broker10 峰值 `92.0737%`，2x/3x 成本 DD `-62.7933%/-75.0310%`。
- C2 全周期：期末权益 `3,465,220`，总收益 `593.0440%`，最大回撤 `-33.5078%`，Sharpe `1.0047`，总滑点 `496,710`，总交易次数 `2,114`，胜率 `50.8632%`，broker10 峰值 `83.0646%`，2x/3x 成本 DD `-38.8700%/-48.8843%`。
- C 相对 A：收益少 `122.7630pp`，最大回撤改善 `10.9184pp`，但收益保留失败且仍远破 DD30。
- C2 相对 C：收益多 `572.7230pp`，回撤改善 `18.8884pp`，Sharpe 高 `0.7458`，但交易多 `748`、滑点多 `317,040`，且正常成本仍破 DD30，2x/3x 成本压力继续失败。
- C 多周期：
  - `since_2021`：`622,765/24.5530%/-50.8584%/Sharpe0.2962`
  - `since_2022`：`1,377,490/175.4980%/-29.2086%/Sharpe0.9428`
  - `since_2023`：`1,450,560/190.1120%/-25.5089%/Sharpe1.3236`
  - `since_2024`：`1,428,160/185.6320%/-16.5154%/Sharpe1.8446`
  - `since_2025`：`677,495/35.4990%/-20.7729%/Sharpe0.8795`
  - `phase_2020_2021`：`594,865/18.9730%/-32.8493%/Sharpe0.4418`
  - `phase_2022_2023`：`535,945/7.1890%/-26.6656%/Sharpe0.2711`
  - `phase_2024_2025`：`1,256,675/151.3350%/-16.5154%/Sharpe1.9042`
  - `weak_2021_drawdown`：`455,510/-8.8980%/-20.4768%/Sharpe-1.4231`
  - `ytd_2026_latest_ai`：`431,140/-13.7720%/-25.9275%/Sharpe-0.9226`。注意该窗口名沿用 runner 历史标签，实际策略已 no-AI。
- C 滚动窗口：
  - 63日：p05 `-21.4059%`，min `-33.8091%`
  - 126日：p05 `-28.5575%`，min `-35.8527%`
  - 252日：p05 `-30.7270%`，min `-37.9234%`
- C 资金占用：active days `1,439`，active rate `93.9295%`，avg all `22.9881%`，active day avg `24.4738%`，p95 `54.2492%`，max `92.0737%`，`>30%` `460` 天，`>50%` `106` 天，`>70%` `13` 天，`>90%` `1` 天，`>100%` `0` 天。
- C 扩展品种贡献：`ag +17,130`，`jd +9,480`，`p +37,880`，`ni -167,320`，`sc -94,100`，合计 `-196,930`。
- C2 扩展品种贡献：`ag +678,945`，`jd +47,630`，`ni +323,320`，`p +126,960`，`sc -212,400`，合计 `+964,455`。
- 与 Stage390 no-AI C 对照：Stage390 C 为 `1,293,925/158.7850%/-46.6154%/Sharpe0.6557`；Stage391 C 为 `601,605/20.3210%/-52.3961%/Sharpe0.2589`，放宽 short case 在 `maxpos4` 主候选下明显更差。
- 与 Stage390 no-AI C2 对照：Stage390 C2 为 `1,233,455/146.6910%/-48.3450%/Sharpe0.6034`；Stage391 C2 为 `3,465,220/593.0440%/-33.5078%/Sharpe1.0047`，说明放宽 short case 在更大并发下有 alpha 线索，但仍不过 DD30 且成本压力不稳。
- 与 Stage387 固定四品种 C 对照：Stage387 C 为 `4,634,210/826.8420%/-25.3045%/Sharpe1.3707`，仍明显更强。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_report_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_summary_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_comparison_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_rolling_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_margin_usage_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv`
- activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_extra_activity_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_decision_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.json`

## 结论

- 本阶段结论：`stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_rejected`。
- 是否进入下一步：不进正式，不 A/B，不改官方实盘。
- 下一步：不要把 `short_case2/3` 直接并入 `maxpos4`；若继续，只能做只读归因，拆分 `short_case2`、`short_case3` 在 C2 中的真实贡献和风险槽冲突，再决定是否有低自由度组合层风险槽方案。

## 过拟合反思

- 运行前判断：不是典型过拟合，因为放宽 short case 是结构性消融，检验当前空头入口是否过窄。
- 运行后判断：当前主候选失败；如果继续扫 `case2 only/case3 only/按年份/按品种/按月份`，会迅速过拟合。
- 原因：`maxpos4` 下放宽 case 明显损害路径；`maxpos24` 的好结果说明信号可能有 alpha，但它依赖更大并发和更高成本/保证金暴露，不能直接推广。

## 继续价值反思

- 运行前判断：有价值。它能回答用户提出的“其他 case 是否应该允许”。
- 运行后判断：直接允许其他 case 无推广价值；作为机制归因有价值。
- 原因：C 失败，C2 有信号但未过 DD30/成本压力，说明真正问题是空头 case 与风险槽容量、并发限制、账户级 selector 的交互，不是简单开关。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage391 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加关键反证和后续约束。
