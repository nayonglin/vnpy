# Stage822 Stage813 20w/30w/50w月度3年滚动窗口回测

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-12 15:25
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金规模压力测试 / 月度 rolling 3y 稳健性验证
- 是否重要突破：否，但属于重要稳健性反证
- 是否触发A/B：是，属于 Stage813 50w、Stage819 30w、Stage817 20w 的资金部署口径对照；不触发正式配置替换

## 外部调研与判断

- 参考资料：
  - Interactive Brokers Campus walk-forward analysis：`https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/`，滚动窗口可减少单一幸运验证期带来的虚假信心。
  - vn.py 官方 GitHub README：`https://github.com/vnpy/vnpy/blob/master/README_ENG.md`，组合策略模块支持多合约策略历史回测和自动交易。
- 我的判断：
  - 相比 Stage821 年度起点，月度起点能更细地暴露路径依赖，尤其能检验年度窗口是否偶然站在有利起点上。
  - 本次不寻找新 alpha，只检验同一 Stage813 逻辑在 20w/30w/50w 三个资金口径下的路径稳健性。
  - 月度结果比年度结果更保守，不能用年度 7 窗口的 30w 优势直接推广。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage822_stage813_capital_monthly_rolling3y.py`
- 修改脚本：修正热力图 colorbar 布局，不重跑回测。
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG = stage822_stage813_capital_monthly_rolling3y_v1`
  - `ROLL_YEARS = 3`
  - `EXACT_MONTH_STARTS = 2018-01 至 2023-05`
  - `TERMINAL_START = 2023-06-01`
  - `CAPITALS = 50w / 30w / 20w`
- 修改参数：
  - 50w：`account_capital/c3_capital = 500000`
  - 30w：`account_capital/c3_capital = 300000`
  - 20w：`account_capital/c3_capital = 200000`
- 删除参数：无
- 保持不变：
  - Stage813 的 `AM41`
  - 基础风险 `0.40`
  - `OI上升+价格沿方向` 命中恢复到 `0.80`
  - 旧正式 AI 选品池
  - `maxpos4`
  - 多头更紧初始止损
  - `RSI95` 半平
  - 关闭连败缩放和 recovery sleeve
- 正式配置/CTP/下单：不改官方配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 窗口口径：
  - 完整 3 年月度窗口：`2018-01-01 -> 2020-12-31` 起，逐月滚动至 `2023-05-01 -> 2026-04-30`，共 `65` 个。
  - 末端补充窗口：`2023-06-01 -> 2026-05-29`，共 `1` 个，不满 3 年但覆盖当前数据终点。
- 总回测次数：`66` 个窗口 × `3` 个资金口径 = `198` 次。
- 账户规模：20w、30w、50w。
- 成本口径：沿用 Stage813 / QMT roll 组合回测成本口径，按脚本输出累计滑点。
- 策略/归因口径：Stage813 逻辑不变，只比较资金口径在月度 rolling 3y 中的收益、回撤、Sharpe、保证金和胜出分布。

## 结果

### 聚合结果

| 资金口径 | 正收益窗口 | 中位收益 | p10收益 | 最小收益 | 最大收益 | 中位回撤 | 最差回撤 | DD30失败 | DD40失败 | DD50失败 | 中位Sharpe | p10 Sharpe | 总滑点 | 总交易次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20w | 63/66 | 549.4113% | 73.8650% | -15.5825% | 4105.3775% | -37.8016% | -52.1290% | 49 | 30 | 1 | 1.6955 | 0.6811 | 7,199,835 | 17,189 |
| 30w | 66/66 | 643.7725% | 75.4383% | 28.9200% | 3659.4817% | -37.6836% | -56.7501% | 52 | 25 | 2 | 1.6939 | 0.7328 | 10,976,430 | 17,530 |
| 50w | 66/66 | 803.4980% | 84.7875% | 54.1720% | 2678.2980% | -35.5641% | -56.6470% | 52 | 24 | 6 | 1.7441 | 0.8382 | 17,928,670 | 17,645 |

- 三臂均无 broker10 超100、无权益跌破0。
- 20w 出现 `3` 个负收益窗口，30w/50w 全部窗口正收益。
- 50w 的中位收益、p10收益、中位回撤、中位 Sharpe、p10 Sharpe 均为三者最好；但 DD50 失败最多。
- 30w 的正收益覆盖和 DD50 比 50w 好，但中位收益与 p10 Sharpe 没有超过 50w。

### 配对统计

- 30w vs 50w：收益胜出 `30/66`，回撤胜出 `32/66`，Sharpe胜出 `35/66`，收益+回撤双胜 `18/66`；中位收益差 `-6.8268pp`，中位回撤差 `-0.0398pp`，中位Sharpe差 `+0.0102`。
- 20w vs 50w：收益胜出 `27/66`，回撤胜出 `40/66`，Sharpe胜出 `31/66`，收益+回撤双胜 `23/66`；中位收益差 `-34.4770pp`，中位回撤差 `+0.4809pp`，中位Sharpe差 `-0.0146`。
- 30w vs 20w：收益胜出 `41/66`，回撤胜出 `18/66`，Sharpe胜出 `38/66`，收益+回撤双胜 `15/66`；中位收益差 `+30.8008pp`，中位回撤差 `-0.7646pp`，中位Sharpe差 `+0.0374`。

### 年份聚合关键观察

- 2018 起点组：50w 中位收益 `892.8365%`，30w `696.0050%`，20w `855.8025%`；三者均无 DD40。
- 2019 起点组：20w 中位收益最高 `2371.1163%`，但 50w/30w/20w 均有明显 DD40；50w DD50 `4` 个，30w DD50 `2` 个。
- 2020 起点组：50w 中位收益最高 `1390.0200%`，但 50w DD50 `2` 个；30w/20w 无 DD50。
- 2022 起点组：50w 的中位收益 `104.6320%`、中位回撤 `-33.4949%`、中位 Sharpe `0.9005` 都优于 30w/20w；20w 有 `3` 个负收益窗口和 `1` 个 DD50。
- 2023 起点组：30w 最强，中位收益 `204.4583%`，回撤控制也较好；但样本只有 6 个窗口。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_summary_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_curves_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_comparison_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_pairwise_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_aggregate_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- pairwise_aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_pairwise_aggregate_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- year_aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_start_year_aggregate_stage822_stage813_capital_monthly_rolling3y_v1.csv`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_report_stage822_stage813_capital_monthly_rolling3y_v1.md`
- return_heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_return_heatmap_stage822_stage813_capital_monthly_rolling3y_v1.png`
- dd_heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_dd_heatmap_stage822_stage813_capital_monthly_rolling3y_v1.png`
- sharpe_heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_sharpe_heatmap_stage822_stage813_capital_monthly_rolling3y_v1.png`
- winner_heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage822_stage813_capital_monthly_rolling3y_winner_heatmap_stage822_stage813_capital_monthly_rolling3y_v1.png`

## 结论

- 本阶段结论：`stage822_30w_watch_not_promoted`。
- 是否进入下一步：30w 继续保留观察臂，但不升级正式候选，不改变当前实盘默认。
- 核心理由：
  - 月度 66 窗口下，30w 不再稳定领先 50w；相对 50w 收益胜出仅 `30/66`，中位收益差反而 `-6.8268pp`。
  - 50w 的中位收益、p10收益、中位回撤和中位 Sharpe 更强，说明 Stage821 年度窗口对 30w 有起点选择偏乐观。
  - 30w 相对 20w 仍有收益/Sharpe 优势，但回撤只赢 `18/66`，说明 30w 是更好的执行颗粒度，不是更好的防守结构。
  - 50w DD50 更多，说明 50w 仍是高收益高尾部风险口径，不适合作为当前实盘默认防守版。
- 下一步：
  - 不继续扫本金。
  - 若继续，应做 `2019` 与 `2020` 起点组 DD50 来源归因，以及 `2022` 起点组弱收益/负收益窗口归因。
  - 与当前实盘默认 Stage372 20w 做同样月度 rolling 3y 公平对照，才是实盘切换判断的下一步。

## 过拟合反思

- 运行前判断：不是过拟合；月度 rolling 3y 是预声明的固定评估框架，资金臂也是外生部署参数。
- 运行后判断：仍不是过拟合；结果没有被用于修改交易规则或继续扫本金。
- 原因：本次扩大了验证密度，反而压低了年度窗口下对 30w 的乐观判断；这是反过拟合验证。

## 继续价值反思

- 运行前判断：有价值；年度 7 窗口不足以判断资金口径稳定性。
- 运行后判断：有价值且结论明确；30w 不是正式替代，50w 仍是 Stage813 当前最强研究/候选口径，但尾部风险高。
- 原因：月度起点把资金颗粒度效应、市场段效应和起点选择效应拆得更清楚；继续价值在风险归因和 Stage372 公平对照。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，Stage822 不是正式候选替换。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；不更新 `memory.md`。
