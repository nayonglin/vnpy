# Stage211 Stage208鲁棒性与持有体验审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 18:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读鲁棒性审计；直接读取 Stage208 daily/order/target ledger，不重新调参、不新增交易规则。
- 是否重要突破：否。重要结论是把 Stage208 主候选定性为“有价值但脆弱的工程候选”，不能直接最终部署。
- 是否触发A/B：否。本阶段没有新策略版本；只是对 Stage208 固定候选做持有体验、冷启动、成本、保证金代理和坏窗口复核。

## 外部调研与判断

- 参考资料：
  - FuturesBacktest 趋势跟随资料强调趋势策略依赖跨市场分散和长期收益异常，而不是单品种短期形态补丁：https://www.futuresbacktest.com/docs/strategies/trend/
  - ATR/动态止损在趋势策略中常见，但公开研究和实践资料都提示止损可能显著增加 whipsaw，削弱大波段收益：https://www.priceactionlab.com/Blog/2023/05/dynamic-stops-trend-following/
  - Backtesting.py / Backtrader 等开源框架提供日线或事件驱动回测能力，但多数公开样例没有本仓库的分钟成交、整数手和保证金 ledger 约束：https://www.mintlify.com/kernc/backtesting.py/introduction
- 我的判断：
  - 当前不应立刻加 ATR/K线形态，因为本线已有 Stage029/030 早期 MAE/ATR 早停反证、Stage032 持仓释放反证、Stage039 分层锁盈 sizing 反证、Stage054 单笔风险上限反证，盈利锁线 Stage007-009 也反证标准 ATR/Chandelier 与放松 prev2day_stop。
  - K线形态路线也已有独立 `futures_swing_no_lower_shadow` 研究线反证：严格无下影线/无上影线形态样本小、首日止损拖累，不能直接嫁接到第78趋势策略。
  - 因此本阶段先审 Stage208 的真实坏窗口和承载厚度，比新增策略本体规则更低过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage510_stage208_robustness_audit.py`
- 修改脚本：无正式策略脚本修改；仅生成 Stage211 审计输出。
- 删除脚本：无。
- 新增参数：无交易参数；新增审计维度 `30/60/90/126/180/252/504` 任意启动持有、月度/季度/年度冷启动、保证金代理、坏窗口贡献。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：`615,000` 账户口径；参照 Stage208。
- 成本口径：读取 Stage208 成本输出，并复核 `1x/2x/3x/5x` 滑点压力。
- 样本过滤：无日期过滤、无品种过滤、无坏窗口剔除。
- 策略/归因口径：
  - 主候选：`stage079_next_real_risk070_clean_plus_stage103_xsmom_true`。
  - 保守对照：`stage079_next_real_risk060_clean_plus_stage103_xsmom_true`。
  - 保证金代理：用 Stage402 `start_2020` 的 `c3_margin` 按风险倍率缩放，再加 Stage208 true xsmom margin，乘以 broker10；该项是保守代理，不替代真实券商保证金回放。

## 结果

- 主候选期末权益：`21,210,535`
- 主候选总收益：`3348.8675%`
- 主候选收益保留：`67.6914%`
- 主候选最大回撤：`-38.5861%`
- 主候选 Sharpe：`1.1674`
- 主候选 Ulcer：`16.5824`
- 总滑点：参见 Stage208/Stage211 cost 输出；`2x/3x/5x` 成本压力最大回撤为 `-41.4962%/-44.6059%/-62.3079%`。
- 总交易次数：参见 Stage208；xsmom 真承载腿换手 `460`。
- 胜率：本阶段以任意启动窗口正收益率替代逐笔胜率；主候选 90日/180日/252日正收益率为 `72.81%/84.23%/90.77%`。
- 其他关键指标：
  - 主候选月度冷启动 DD40 通过率 `100%`，但 DD30 通过率仅 `60%`，最差月度冷启动回撤 `-38.5861%`。
  - 主候选任意持有 `30/60/90/126/180/252/504` 天 DD40 破例率均为 `0`。
  - 主候选 90日 p05 收益 `-17.7617%`、180日 p05 `-7.8275%`、252日 p05 `-8.6385%`，短持有左尾仍明显。
  - broker10 保证金代理：主候选穿 `100%` 共 `8` 天，穿 `90%` 共 `24` 天；保守对照穿 `100%` 为 `0` 天。
  - 保守对照结果为 `20,682,740/3263.0472%/-36.2870%/Sharpe1.2291/Ulcer15.4730`，收益更低但保证金和回撤更稳。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage510_stage208_robustness_audit_report_stage510_stage208_robustness_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage510_stage208_robustness_audit_summary_stage510_stage208_robustness_audit_v1.csv`
- orders：沿用 Stage208 order ledger；本阶段无新订单。
- daily：沿用 Stage208 daily；本阶段输出 horizon/cold_start/bad_windows。
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage510_stage208_robustness_audit_margin_proxy_stage510_stage208_robustness_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage510_stage208_robustness_audit_chart_stage510_stage208_robustness_audit_v1.png`
- decision：`stage208_primary_candidate_but_fragile_need_more_review`

## 图表视觉复盘

- NAV：主候选和保守对照都显著低于 Stage079 同日 baseline，Stage079 原曲线仍不是真实收益承诺。
- Underwater：`risk070 + true xsmom` 在 2021-2022 深水段未破 -40%，但贴近 -38% 到 -39%，属于贴线通过。
- 持有箱线：30/60/90日持有左尾明显为负，短持有体验并未根治；504日大多转正，但坏启动窗口仍会长时间水下。
- 月度冷启动：全部在 DD40 内，但 2020-2022 多个启动点贴近 -40%，不是厚安全垫。

## 结论

- 本阶段结论：`stage208_primary_candidate_but_fragile_need_more_review`。
- 是否进入下一步：是，但不是直接部署晋级。
- 下一步：
  1. 先做 Stage208 坏窗口逐笔复盘，尤其是 `2021-11` 至 `2022-02` 的 90日坏窗口和 `2021-05` 至 `2022-09` 的 504日坏窗口。
  2. 若逐笔复盘显示失败来自少数可解释、低自由度的结构，例如已有仓位过度集中、止损信号无法及时释放、或 xsmom 激活空档，才考虑策略本体规则。
  3. 禁止基于本阶段结果去扫 `risk070` 小数、xsmom 窗口/权重、ATR 倍数、K线形态阈值或坏日期过滤。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只读固定候选账本，没有根据坏窗口修改规则。若下一步直接调 ATR 倍数、K线形态阈值、风险倍率小数或坏窗口日期过滤，就会转为过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向要收窄。
- 原因：Stage208 是当前真实可成交边界里最有价值的工程候选，但安全垫不厚；继续价值在逐笔复盘和低自由度结构归因，不在快速堆规则。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage208 候选风险边界。
