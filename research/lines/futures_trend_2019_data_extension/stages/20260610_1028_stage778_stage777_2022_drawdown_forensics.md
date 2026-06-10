# Stage778 Stage777 2022 最大回撤归因

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-10 10:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / 机制复盘
- 是否重要突破：否，但属于 Stage777 失败机制的重要解释
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Open Interest：OI 上升通常用于确认趋势参与度，但需要和其他分析配合使用。
  - AQR 风险缓释/趋势类资料：趋势跟随的收益和回撤保护来自跨市场趋势延续，但宏观冲击后的反转和震荡会造成路径压力。
  - vn.py GitHub `ArrayManager`：技术指标预热和窗口缓存是正常机制，本阶段没有改 AM 逻辑。
- 我的判断：OI 是参与度/趋势确认线索，不是单独的普世 alpha；在高波动反转期，OI 上升可能代表拥挤和分歧增强，不能直接等同为低风险机会。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`SELECTED_TOP_DD_COUNT=5`、`FORCED_SELECTED_STARTS=(2018-01,2021-09,2022-01)`、`REPLAY_PROFILES=(oi_restore_am40,no_oi_am40)`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage777 逐月曲线 `2018-01` 至 `2026-05`，统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 / vn.py 回测成本
- 样本过滤：先对全部 `101` 个逐月起点定位最大回撤峰谷；再复跑最差回撤代表起点和 `2018-01/2022-01`
- 策略/归因口径：`AM41 + OI0.8`，对照 `no_oi/am41`

## 结果

- 期末权益：不适用，本阶段为归因；引用 Stage777 全样本结果为中位收益 `170.7890%`
- 总收益：不适用
- 最大回撤：Stage777 全样本最差 `-50.1325%`
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：Stage777 全样本逐月累计 `29,862`
- 胜率：不适用
- 其他关键指标：
  - `101` 个逐月起点中，最大回撤谷值落在 `2022` 的有 `52` 个。
  - 全部 `47` 个 DD40 失败都落在 `2022`。
  - 最差回撤代表样本共同峰谷：`2022-03-09 -> 2022-06-29`。
  - `no_oi/am41` 代表起点同窗口最大回撤约 `-37.3714%` 到 `-39.0582%`；`oi_restore/am41` 放大到 `-49.4213%` 到 `-50.1325%`。
  - OI 版本代表起点峰谷窗口聚合亏损：`fu.SHFE -4,555,150`、`MA.CZCE -3,449,760`、`AP.CZCE -2,642,550`、`au.SHFE -2,340,240`、`sp.SHFE -1,966,300`、`jm.DCE -1,014,720`。
  - 不开 OI 对照聚合亏损：`fu.SHFE -2,618,330`、`MA.CZCE -1,333,240`、`sp.SHFE -948,700`、`AP.CZCE -598,050`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage778_stage777_2022_drawdown_forensics_report_stage778_stage777_2022_drawdown_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage778_stage777_2022_drawdown_forensics_dd_windows_stage778_stage777_2022_drawdown_forensics_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage778_stage777_2022_drawdown_forensics_closed_lots_around_dd_stage778_stage777_2022_drawdown_forensics_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage778_stage777_2022_drawdown_forensics_year_attribution_stage778_stage777_2022_drawdown_forensics_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage778_stage777_2022_drawdown_forensics_entry_oi_summary_stage778_stage777_2022_drawdown_forensics_v1.csv`

## 结论

- 本阶段结论：2022 是 Stage777 的共同最大回撤年份；回撤本体来自趋势策略在 `2022-03-09 -> 2022-06-29` 的多品种反转/震荡压力，OI0.8 把同一压力窗口进一步放大。
- 是否进入下一步：单 OI 放大仓位不进入下一步；OI 可进入多因子只读评分研究。
- 下一步：若继续，只能设计多因子质量评分，要求同时约束 OI、波动收敛、价格路径顺畅度和同向相关性/拥挤度；不能继续扫 OI 倍率。

## 过拟合反思

- 运行前判断：低过拟合，原因是只读归因，不调参。
- 运行后判断：低过拟合，结论来自 `101` 个逐月起点共同落点和代表起点交易复盘，不是挑单个窗口救参。
- 原因：没有新增交易规则或收益筛选，只解释已经失败版本的风险来源。

## 继续价值反思

- 运行前判断：有价值，因为需要明确 Stage777 是单品种事故、数据事故还是机制事故。
- 运行后判断：有价值但仅限归因和新特征设计。
- 原因：已确认 Stage777 失败不是数据 bug，也不是单品种；是趋势本体回撤叠加 OI 单因子仓位放大。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`
