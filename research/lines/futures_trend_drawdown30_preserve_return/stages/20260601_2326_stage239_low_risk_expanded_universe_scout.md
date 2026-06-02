# Stage239 / Stage539 低单笔风险扩池与相关性预算 scout

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 23:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 结构 scout；围绕“减少单笔风险、扩大品种池、避免高相关风险、每年抓到部分趋势”的假设做隔离回测。
- 是否重要突破：否，未产生可晋级版本；但产生明确方向裁剪。
- 是否触发A/B：是，已读取 `skills/version-ab-experiment/SKILL.md`。本阶段涉及可能接入 Stage526 的结构候选，因此按 A/C 隔离记录；结果不进入正式 A/B。

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟随长期证据与跨市场分散研究：`https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing`
  - Moskowitz/Ooi/Pedersen time-series momentum 跨资产研究：`https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data`
  - Bailey/Lopez de Prado 关于 backtest overfitting / PBO 的警示：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253`
- 我的判断：
  - “扩池 + 降低单笔风险”在第一性原理上成立：趋势收益高度不均匀，跨品种分散可降低单一品种路径依赖。
  - 但扩池不能按历史收益挑品种，也不能让新产品挤掉原本高 convexity 的趋势腿；否则本质是用更多低质量震荡噪音稀释主 alpha。
  - 品种选择应坚持事前结构约束：流动性、单合约保证金可承载、趋势效率、波动/区间结构、同向相关性与产业链拥挤度，而不是历史总收益排名。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage539_low_risk_expanded_universe_scout.py`
- 修改脚本：同上；运行中修正报告字段，并追加两个隔离组：
  - `exp24_all_r080_pc25_maxpos4`：纯扩池、接近 Stage526 风险框架。
  - `static18_r060_pc20_maxpos6`：只保留 Stage78 静态强池 + `fu.SHFE`，降低单笔风险，不引入新增产品。
- 删除脚本：无。
- 新增参数：
  - 扩池品种池来自既有全市场结构预筛 `24` 品种。
  - AI top12 / simple top12 / static18 三类 eligibility。
  - `risk_multiplier=0.50/0.60/0.70/0.80`、`product_cap_ratio=0.15/0.20/0.25`、`maxpos=4/6/8`、`max_single_trade_capital_usage_ratio=0.22/0.25/0.70`。
  - 同向相关性门控沿用 `lookback=20/start=0.60/full=0.80/floor=0.35`。
- 修改参数：无正式策略参数修改；仅研究脚本 variants。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30，沿用当前研究线权威可比区间。
- 账户规模：`615,000` 账户口径，C3 下单权益 `500,000`，外部现金 `115,000`。
- 成本口径：正常成本 `1x`，压力成本 `2x/3x`。
- 执行口径：完整日K确认后，所有订单下一真实窗口成交；exact position margin；xsmom 真实成交承载；fallback 已由前序阶段清零。
- 样本过滤：
  - 扩池宇宙来自全市场结构预筛，不按历史 PnL 筛选。
  - 2022 前动态选择只允许 Stage78 静态池 + `fu.SHFE`，避免未来可见扩池污染早期。
- 策略/归因口径：
  - 不改入场/出场 alpha。
  - 只变资金预算、品种池、动态品种 eligibility、相关性预算。
  - 同表对照 Stage526 `r080_pc25_maxpos4`。

## 结果

### 总览

| 版本 | 期末权益 | 总收益 | 相对Stage079收益保留 | 相对Stage526收益 | 最大回撤 | Sharpe | broker10最大 | 2x成本DD | 3x成本DD | 总滑点 | 交易次数 | 胜率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage526 `r080_pc25_maxpos4` | 23,369,505 | 3699.9195% | 74.7872% | 100.0000% | -36.2670% | 1.6385 | 99.7299% | -39.0565% | -42.0555% | 1,342,190 | 905 | 53.6330% | 仍第一 |
| `static18_r060_pc20_maxpos6` | 3,433,080 | 458.2244% | 9.2622% | 12.3847% | -39.6030% | 1.0910 | 84.9353% | -42.4105% | -45.4072% | 413,810 | 1,301 | 51.2161% | 降风险隔离组最好，但收益保留严重不足 |
| `exp24_all_r050_pc20_maxpos6` | 2,329,110 | 278.7171% | 5.6338% | 7.5331% | -38.4952% | 0.8693 | 84.0642% | -41.7707% | -49.2257% | 340,910 | 1,556 | 50.8615% | 全扩池低风险失败 |
| `exp24_all_r080_pc25_maxpos4` | 2,204,990 | 258.5350% | 5.2258% | 6.9876% | -50.7912% | 0.7281 | 105.5350% | -55.3987% | -65.8744% | 481,610 | 1,380 | 53.3195% | 纯扩池同风险失败 |
| `exp24_ai12_r070_pc20_maxpos6` | 1,931,005 | 213.9846% | 4.3253% | 5.7835% | -34.6378% | 0.7919 | 67.8015% | -40.9796% | -47.9654% | 259,490 | 1,092 | 49.5658% | 动态选择收益不足 |
| `exp24_ai12_r060_pc15_maxpos8` | 1,850,220 | 200.8488% | 4.0598% | 5.4285% | -30.4836% | 0.8418 | 68.5477% | -35.8663% | -41.5712% | 212,800 | 1,112 | 50.3943% | 曲线更浅但复利被切掉 |
| `exp24_simple12_r060_pc20_maxpos6` | 1,809,815 | 194.2789% | 3.9270% | 5.2509% | -44.3326% | 0.8388 | 64.9738% | -47.5693% | -51.0069% | 212,160 | 1,098 | 51.5919% | 简单选择失败 |
| `exp24_ai12_r060_pc20_maxpos6` | 1,795,755 | 191.9927% | 3.8808% | 5.1891% | -35.3022% | 0.7988 | 64.9738% | -41.1818% | -47.4304% | 230,170 | 1,082 | 49.7832% | 核心设想失败 |

### 3/6个月持有体验

| 版本 | 63日p05收益 | 63日中位收益 | 63日正收益率 | 126日p05收益 | 126日中位收益 | 126日正收益率 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage526 | -18.2169% | 14.2303% | 76.7869% | -10.9700% | 27.5593% | 86.3442% | 左尾较深，但中位和正收益率明显最好 |
| `static18_r060_pc20_maxpos6` | -13.5904% | 6.7223% | 74.4044% | -15.4560% | 17.1879% | 76.1735% | 3个月左尾改善，6个月劣化 |
| `exp24_ai12_r060_pc15_maxpos8` | -11.4411% | 3.2021% | 61.6746% | -14.9151% | 7.7024% | 67.9232% | 左尾更浅但体验中枢塌陷 |
| `exp24_all_r080_pc25_maxpos4` | -19.8745% | 5.6463% | 61.8108% | -26.3628% | 14.5093% | 69.4168% | 同风险扩池显著更差 |

### 年度趋势捕捉与品种归因

- Stage526 年度正收益率 `87.5%`，扩池/低风险组最高仅 `75.0%`，多数为 `50.0%-62.5%`。
- Stage526 的大收益来自少数高 convexity 趋势腿：
  - 2023 年 `OI.CZCE +2,307,420`，全年组合 `+3,894,000`。
  - 2024 年 `ru.SHFE +1,078,500`，全年组合 `+2,449,560`。
  - 2025 年 `jm.DCE +6,309,540`，全年组合 `+10,938,915`。
  - 2026 年 `lh.DCE +2,805,600`，阶段组合 `+2,237,695`。
- 扩池组没有把趋势收益分散到更多品种，反而错过核心大腿：
  - `exp24_ai12_r060_pc20_maxpos6` 中 `jm.DCE` 全周期为 `-162,990`，Stage526 为 `+7,808,190`。
  - `exp24_ai12_r060_pc15_maxpos8` 中 `jm.DCE` 为 `-130,440`，Stage526 为 `+7,808,190`。
  - `exp24_all_r080_pc25_maxpos4` 同风险扩池在 2022/2024/2026 均为负，最大回撤扩大到 `-50.7912%`，且 broker10 打穿 `105.5350%`。
- 静态低风险组是扩池外最好的对照，但收益只保留 Stage526 的 `12.3847%`，说明单纯降低单笔风险会切掉复利凸性。

### 视觉复盘

- 图表文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_chart_stage539_low_risk_expanded_universe_scout_v1.png`
- 视觉判断：
  - 左上权益曲线：Stage526 在 2023 后、尤其 2025 后段形成明显凸性；扩池组和低风险组全部贴近底部，未复制主趋势收益。
  - 右上收益保留 vs broker10：Stage526 是唯一接近收益保留硬线的版本；扩池组全部集中在 `3.88%-9.26%` 的极低收益保留区。
  - 左下年度正贡献产品数：扩池组正贡献品种数有时更多，但组合净 PnL 更低，说明“更多品种赚钱”不等于“抓到关键趋势”。
  - 右下 3/6个月 p05：部分低风险组 63日左尾更浅，但 126日左尾、中位收益和正收益率明显不如 Stage526，属于用收益中枢换浅亏，不是有效体验提升。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_report_stage539_low_risk_expanded_universe_scout_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_summary_stage539_low_risk_expanded_universe_scout_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_cost_stress_stage539_low_risk_expanded_universe_scout_v1.csv`
- rolling holding：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_rolling_holding_stage539_low_risk_expanded_universe_scout_v1.csv`
- annual product harvest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_annual_product_harvest_stage539_low_risk_expanded_universe_scout_v1.csv`
- entry summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_entry_summary_stage539_low_risk_expanded_universe_scout_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_positions_stage539_low_risk_expanded_universe_scout_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_chart_stage539_low_risk_expanded_universe_scout_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage539_low_risk_expanded_universe_scout_decision_stage539_low_risk_expanded_universe_scout_v1.json`

## 结论

- 本阶段结论：`expanded_low_risk_scout_no_promotion_yet`。
- 是否进入下一步：当前形状不进入候选、不进入 A/B、不替代 Stage526。
- 我的判断：
  - “减少单笔风险 + 扩大品种池”有理论价值，但当前实现不成立。
  - 失败不是因为相关性预算不够，而是扩池和动态选择没有保住 Stage526 的主趋势腿；它让策略更像低斜率、多噪音、弱凸性的组合。
  - “选对品种”是关键，但这里的“选对”不能是历史赢家列表，也不能是简单 top12；更可能需要保留核心趋势腿的优先权，再用新产品做不挤占核心仓位的独立 sleeve。
- 下一步：
  1. 不继续扫 `top_n=10/14`、`risk=0.55/0.65`、`cap=0.18/0.22` 这类小数。
  2. 若继续扩池，只允许做“核心池不被替换 + 新品种独立低保证金 sleeve + 只在低相关/高趋势效率状态启用”的结构，而不是把所有品种放进同一竞争池。
  3. 对 `jm/OI/ru/lh/FG/au/si/lc` 这类 Stage526 主贡献腿做“为何被扩池组错过”的入场候选级复盘，判断是风险预算太低、动态选择器挡掉、还是新增品种占用了槽位。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段使用事前结构预筛扩池、固定 top12 / static18 对照、固定相关性门控，没有按收益窗口调参。
  - 结果主动拒绝所有扩池候选，包括看起来短期左尾更浅的 `exp24_ai12_r060_pc15_maxpos8`，没有按目标硬凑。
  - 反而发现纯扩池同风险组 `exp24_all_r080_pc25_maxpos4` 明确劣化，这降低了后续过拟合扩池的诱惑。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但方向收窄。
- 原因：
  - 有价值：证明“选对品种”确实比“品种越多越好”重要；也证明静态强池低风险优于动态扩池低风险，但收益仍不足。
  - 方向收窄：不要继续朴素扩池、动态 topN、小数风险扫参；应转为“保留主趋势 convexity + 新品种只做非挤占式分散”的结构。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage539 反证和下一步方向。
- 是否更新 `research/registry.md`：是，当前研究线最新阶段应从 Stage238 更新到 Stage239。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 重要合入摘要；不追加 `memory.md`，因为不是正式候选或长期规则迁移。
