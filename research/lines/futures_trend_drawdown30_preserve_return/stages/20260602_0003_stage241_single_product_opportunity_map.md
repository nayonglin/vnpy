# Stage241 单品种机会地图

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-02 00:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：产品选择诊断；57个可交易产品逐个独立运行，寻找 core 之外是否存在真实可成交、低相关、低保证金、多年度有贡献的产品。
- 是否重要突破：是，出现了比 Stage540 new5 更有材料性的非核心产品集合，但仍不是可晋级策略版本。
- 是否触发A/B：否。Stage241 只是单品种机会地图，不是组合接入版本；后续若接入组合，需另做 A/C。

## 外部调研与判断

- 参考资料：
  - AQR《A Century of Evidence on Trend-Following Investing》：趋势跟随收益依赖跨市场分散，但分散必须来自可交易且有趋势结构的市场。
  - AQR Time-Series Momentum 原始数据页：时间序列动量的核心是多市场、长期、低共振的趋势机会集合。
  - managed futures / crisis alpha 相关研究：扩市场有意义，但要同时控制交易成本、保证金和相关性。
- 我的判断：
  - Stage540 的 new5 失败不能否定“选对品种”，只能说明当前结构预筛过窄或筛错。
  - 真正该问的是：在 core 之外，是否有产品独立跑起来就有多年正贡献，并且和 Stage526 日PnL低相关。
  - 本阶段只做机会地图，不把全样本表现直接变成实盘选品规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage541_single_product_opportunity_map.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 单品种 sleeve 资金：`115000`
  - 单品种风险倍率：`risk_multiplier=0.50`
  - 每次只允许一个产品运行：`max_concurrent_positions=1`
  - 候选材料性定义：非核心产品、总PnL `>= max(账户1%, sleeve10%)`、正贡献活跃年份 `>=3`、与 Stage526 日PnL绝对相关 `<=0.30`、broker10 sleeve保证金 `<=80%`、活跃年份 `>=3`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：每个产品独立 `115000` sleeve。
- 成本口径：当前真实下一窗口成交口径，正常滑点；本阶段先做产品机会图，不做组合成本压力。
- 样本过滤：读取 `qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv` 的 `57` 个 eligible 产品。
- 策略/归因口径：每个产品单独用 Stage526 同类趋势逻辑、真实下一窗口成交运行；输出 total PnL、年度PnL、与 Stage526 日PnL相关、坏窗口贡献和 exact margin。

## 结果

- 覆盖产品：`57`
- Stage526 核心产品：`19`
- 非核心产品：`38`
- 非核心赚钱产品：`13`
- 材料性候选：`6`

### 材料性候选

| 产品 | PnL | 收益 | 最大回撤 | Sharpe | 正贡献活跃年/活跃年 | corr(Stage526日PnL) | 2021-2022坏窗 | 2022坏窗 | broker10最大 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lu.INE | 87,510 | 76.0957% | -16.8376% | 0.8018 | 3/4 | 0.1543 | 0 | 0 | 44.9181% |
| v.DCE | 50,705 | 44.0913% | -10.3448% | 0.6892 | 6/6 | 0.0647 | -5,390 | 12,215 | 53.3356% |
| al.SHFE | 51,925 | 45.1522% | -11.4886% | 0.7299 | 3/3 | 0.0184 | 14,375 | -3,425 | 68.3500% |
| y.DCE | 38,140 | 33.1652% | -8.3772% | 0.6564 | 4/4 | 0.0072 | 15,760 | 4,280 | 60.4723% |
| c.DCE | 21,100 | 18.3478% | -10.8733% | 0.3910 | 6/7 | 0.0160 | -520 | 12,750 | 62.4459% |
| ao.SHFE | 28,840 | 25.0783% | -7.8417% | 0.9972 | 3/3 | 0.0159 | 0 | 0 | 28.9071% |

### 年度特征

- `v.DCE` 最稳：2020-2025 连续正贡献，2026暂未贡献，最大年度 `14,320`。
- `c.DCE` 活跃年份最多，7个活跃年中6年为正，且 2022 坏窗口贡献 `+12,750`。
- `y.DCE` 在 2020-2023 为正，2021 和 2022 对坏窗口有帮助。
- `lu.INE` 总贡献最高，但很大一部分来自 2026，且 2024 有 `-1,730`，需要警惕近端样本权重。
- `al.SHFE` 与 `ao.SHFE` 低相关、低回撤，但活跃年份较少。

## 图表视觉复盘

- 散点图显示多数产品挤在零收益附近；真正突出的是少数非核心品种，相关性大多在 `0~0.16`，说明它们不是简单复制 Stage526。
- 年度热力图显示 `v/c/y` 比 `lu` 更像“多年小趋势捕捉”；`lu` 更像少数年份大贡献，尤其 2026。
- 保证金-PnL图显示高保证金产品并不自动带来收益，`v/c/lu/ao` 的资金效率更好。
- 这张图最关键的信息不是“买这6个”，而是 Stage540 的结构预筛确实漏掉了更有潜力的产品。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_report_stage541_single_product_opportunity_map_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_summary_stage541_single_product_opportunity_map_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_daily_stage541_single_product_opportunity_map_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_positions_stage541_single_product_opportunity_map_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_decision_stage541_single_product_opportunity_map_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage541_single_product_opportunity_map_chart_stage541_single_product_opportunity_map_v1.png`

## 结论

- 本阶段结论：`single_product_candidates_found_for_next_sleeve_test`
- 是否进入下一步：进入下一步，但只能做 hindsight 上限验证，不能直接晋级。
- 下一步：用 `lu/v/al/y/c/ao` 做非挤占式 sleeve 上限验证；如果有效，再研究如何用事前特征选择这些产品。

## 过拟合反思

- 运行前判断：否。本阶段先全产品逐个跑图，不改策略，也不直接形成交易规则。
- 运行后判断：Stage241 结果本身不能晋级，直接按这6个产品实盘会过拟合。
- 原因：候选来自全样本表现，虽然有多年度和低相关约束，但仍然使用了未来收益信息。

## 继续价值反思

- 运行前判断：有价值。Stage540 证明 new5 不行，但没有回答 full market 里是否有其他可用产品。
- 运行后判断：有价值。出现了 `lu/v/al/y/c/ao` 这组材料性非核心产品，说明“选对品种”不是空方向。
- 原因：它们在单品种真实成交下有可见收益、低相关和可承受保证金，值得做上限验证和事前选择器研究。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`，因为还没有形成正式执行规则。
