# Stage207 第78 2015起点多周期复跑

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 04:23
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：第78正式基准从2015起点的多周期复验与数据覆盖门禁
- 是否重要突破：否，属于正式基准复验
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py PortfolioStrategy 官方文档：组合策略回测/实盘均依赖历史K线初始化与 `on_bars` 驱动。
  - vn.py GitHub portfolio backtesting 示例：标准流程为设置参数、添加策略、加载数据、运行回测、计算结果。
- 我的判断：
  - 本轮不需要引入外部实现；仓库已有 Stage194 审计脚本更符合第78口径。
  - 长样本验证必须先过数据覆盖门禁，不能把2015-2019缺失合约造成的低交易段当作穿越周期证据。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：请求起点 `2015-01-05`，回测终点 `2026-04-30`，数据库最新K线 `2026-05-08`
- 账户规模：`200,000`
- 成本口径：沿用第78正式滑点，手续费为当前框架默认 `0`
- 样本过滤：第78正式配置 `official_stage78_defensive_v1`
- 策略/归因口径：运行 `analyze_qmt_roll_stage194_stage78_2015_multicycle_viability.py`，先做覆盖率门禁，只对覆盖通过窗口做正式回测汇总
- 运行目录要求：必须从仓库根目录 `/Users/bytedance/Desktop/person/vnpy` 启动，确保 vn.py 使用仓库内 `.vntrader/database.db`
- 纠错说明：04:23首次从 `examples/portfolio_backtesting` 目录启动，误读 `~/.vntrader/database.db` 用户级旧库，得到 `63.4105%` 错误覆盖率；04:34已从仓库根目录重跑并覆盖产物。

## 结果

- 数据覆盖：
  - 2015起点请求窗口覆盖率 `98.1151%`，高于 `95%` 门禁，PASS
  - 2015-2017早期子段覆盖率 `94.5927%`，略低于 `95%` 门禁，FAIL
  - 2018-2019过渡段覆盖率 `98.0505%`，PASS
  - 2020-2026正式可信窗口覆盖率 `99.2722%`，PASS
- 2020-2026正式可信窗口：
  - 期末权益：`4,637,530`
  - 总收益：`2,218.7650%`
  - 最大回撤：`-36.9907%`
  - Sharpe：`1.2922`
  - 总滑点：`261,740`
  - 总交易次数：`782`
  - 胜率：`42.1053%`
- 可信多周期窗口：
  - 2015起点请求窗口：期末权益 `4,412,810`，总收益 `2,106.4050%`，最大回撤 `-36.1290%`，Sharpe `0.9581`
  - 2018-2019过渡段：期末权益 `190,420`，总收益 `-4.7900%`，最大回撤 `-9.3439%`，Sharpe `-0.4241`
  - 2020-2021：期末权益 `1,384,905`，总收益 `592.4525%`，最大回撤 `-36.9907%`，Sharpe `1.6313`
  - 2022-2026：期末权益 `2,900,825`，总收益 `1,350.4125%`，最大回撤 `-37.5422%`，Sharpe `1.3023`
  - 2024-2025：期末权益 `964,180`，总收益 `382.0900%`，最大回撤 `-31.1166%`，Sharpe `1.4577`
  - 2026最新窗口：期末权益 `205,665`，总收益 `2.8325%`，最大回撤 `-35.4516%`，Sharpe `0.0629`
- 起点敏感性：
  - 2016起点：总收益 `2,106.4050%`，最大回撤 `-36.1290%`，Sharpe `0.9873`
  - 2017起点：总收益 `2,106.4050%`，最大回撤 `-36.1290%`，Sharpe `1.0394`
  - 2018起点：总收益 `2,106.4050%`，最大回撤 `-36.1290%`，Sharpe `1.1007`
  - 2019起点：总收益 `2,106.4050%`，最大回撤 `-36.1290%`，Sharpe `1.1740`
  - 2021起点：总收益 `1,981.7100%`，最大回撤 `-42.3203%`，Sharpe `1.1931`
  - 2022起点：总收益 `1,427.1425%`，最大回撤 `-36.7687%`，Sharpe `1.2461`
  - 2023起点：总收益 `877.8125%`，最大回撤 `-39.4397%`，Sharpe `1.3295`
  - 2024起点：总收益 `415.2975%`，最大回撤 `-31.1166%`，Sharpe `1.3126`
  - 2025起点：总收益 `360.0475%`，最大回撤 `-28.8813%`，Sharpe `1.6813`
- 年度收益：
  - 2020 `122.1325%`
  - 2021 `211.7295%`
  - 2022 `19.1605%`
  - 2023 `47.1962%`
  - 2024 `19.8189%`
  - 2025 `57.0800%`
  - 2026截至 `2026-04-30` 为 `1.4358%`
- 滑点压力：
  - `1.0x`：总收益 `2,218.7650%`，最大回撤 `-36.9907%`，Sharpe `1.4550`
  - `2.0x`：总收益 `2,087.8950%`，最大回撤 `-38.4655%`，Sharpe `1.3864`
  - `3.0x`：总收益 `1,957.0250%`，最大回撤 `-40.2491%`，Sharpe `1.3191`
  - `5.0x`：总收益 `1,695.2850%`，最大回撤 `-44.5009%`，Sharpe `1.1888`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_report_stage194_stage78_2015_multicycle_viability_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_summary_stage194_stage78_2015_multicycle_viability_v1.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_summary_stage194_stage78_2015_multicycle_viability_v1.json`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_coverage_stage194_stage78_2015_multicycle_viability_v1.csv`
- annual_returns：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_annual_returns_stage194_stage78_2015_multicycle_viability_v1.csv`
- slippage_stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_slippage_stress_stage194_stage78_2015_multicycle_viability_v1.csv`
- equity_html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_equity_curves_stage194_stage78_2015_multicycle_viability_v1.html`

## 结论

- 本阶段结论：
  - Stage196补数据已经生效；从仓库根目录读取项目级 `.vntrader/database.db` 时，2015起点总窗口覆盖率为 `98.1151%`，可作为长样本参考。
  - 2015-2017早期子段仍略低于覆盖门槛，主要残留在`fu.SHFE`和少量`SM.CZCE`，不能单独确认早期周期表现。
  - 2020以后覆盖通过窗口仍保持强收益和较高Sharpe，但 2021 起点最大回撤达到 `-42.3203%`，3倍滑点压力也突破 `-40%`，风险边界需要继续审计。
  - 2026最新窗口小幅正收益但Sharpe很低，说明短期状态不是明显顺风期，适合继续影子盘和T+1执行审计，不适合据此调参。
- 是否进入下一步：是
- 下一步：
  - 固化回测启动目录检查，避免再次误读用户级旧数据库。
  - 对2015-2017残留缺口继续区分`fu`历史制度问题和`SM`数据问题。
  - 推进第78 T+1成交审计、真实数据接入和影子盘日报。
  - 如果继续补早期数据，只优先补真实合约K线覆盖，不做连续复权替代正式执行口径。

## 过拟合反思

- 运行前判断：否。本轮固定第78参数，只做多周期和覆盖门禁复验。
- 运行后判断：否，但需要避免数据覆盖外推。
- 原因：
  - 本轮没有按结果调整参数，也没有选择性保留窗口。
  - 真正风险在于把2015-2017残留缺口外推为完全穿越周期，因此必须继续保留早期子段黄灯。

## 继续价值反思

- 运行前判断：有价值。它直接回答第78是否能从2015开始被可信复验。
- 运行后判断：有价值，但价值不在继续优化早期窗口。
- 原因：
  - 2015总窗口已可作为长样本参考，2020以后结果支持第78仍可作为正式基准继续做实盘前验证。
  - 2015-2017的主要矛盾是残留数据覆盖和合约级AM冷启动，不是策略参数优化问题。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，Stage78正式基准核心指标未改变；后续可补充“2015总窗口通过、2015-2017早期子段黄灯”说明。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
