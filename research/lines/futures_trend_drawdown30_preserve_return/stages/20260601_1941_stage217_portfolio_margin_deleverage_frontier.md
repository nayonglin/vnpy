# Stage217 组合保证金主动降杠杆粗前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 19:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 结构实验；固定 Stage079/C3 信号、品种池和 Stage103 xsmom true leg，只测试持仓期保证金治理。
- 是否重要突破：否，但是否决一个重要方向：当前“组合保证金压力触发后滞后砍仓”的主动降杠杆，仍不能通过 exact margin。
- 是否触发A/B：是。该能力属于资金/保证金治理层，若通过可能成为部署候选；本阶段失败不晋级。

## 外部调研与判断

- 参考资料：
  - SHFE investor clearing / settlement：交易保证金、结算准备金、风险处置是实盘硬约束。
  - CFFEX rules：保证金、限仓、强平、风险控制是期货实盘约束。
  - vn.py / VeighNa GitHub：事件驱动框架适合把风险控制接入下单和持仓管理层。
- 我的判断：Stage216 反证静态 sizing cap 后，值得验证持仓期主动治理；但治理必须最后经 exact position margin 验收，不能只相信策略内部估算保证金。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无。
- 新增默认关闭参数：
  - `enable_portfolio_margin_deleverage`
  - `portfolio_margin_deleverage_start_ratio`
  - `portfolio_margin_deleverage_full_ratio`
  - `portfolio_margin_deleverage_min_pressure`
  - `portfolio_margin_deleverage_layer_kinds`
  - `portfolio_margin_deleverage_broker_multiplier`
- 修改参数：无正式策略参数修改；本阶段只在实验脚本内启用粗档。
- 删除参数：无。

## 预声明通过标准

- 正常成本最大回撤 `>= -40%`。
- exact broker10 保证金/权益全程 `<= 100%`；强通过要求 `<= 90%`。
- 2x 成本压力最大回撤 `>= -40%`。
- 硬通过后，再要求收益保留接近或超过 Stage079 部署收益的 `50%`，否则只是工程可行但资本效率弱。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：`615,000` 账户口径，其中 C3 回测引擎 `500,000`，xsmom true leg 复用 Stage208/209 冻结日度真实成交路径。
- 成本口径：1x/2x/3x 滑点压力；broker10 保证金按 exact position margin 乘 `1.10`。
- 样本过滤：无日期/品种过滤；全周期、起始年、分段、63/126/252/504 任意持有窗口。
- 候选粗档：
  - `r060_legacy_nocap_control`
  - `r070_legacy_nocap_control`
  - `r070_pm_add_80_100`
  - `r070_pm_all_90_110`
  - `r080_pm_all_80_100`
  - `r070_cluster35`
  - `r070_cluster35_pm_add_80_100`
  - `r080_cluster35_pm_all_80_100`

## 结果

### 对照与最优弱形状

- `r060_legacy_nocap_control`：
  - 期末权益 `20,682,740`
  - 总收益 `3263.0472%`
  - 最大回撤 `-36.2870%`
  - Sharpe `1.5114`
  - Ulcer `15.5580`
  - 总滑点 `1,231,020`
  - 总交易次数约 `978`
  - 非零日胜率 `52.8614%`
  - broker10 exact 最大保证金/权益 `138.9327%`
  - 穿 100% 天数 `17`
- `r070_legacy_nocap_control`：
  - 期末权益 `21,210,535`
  - 总收益 `3348.8675%`
  - 最大回撤 `-38.5861%`
  - Sharpe `1.4353`
  - Ulcer `16.6764`
  - 总滑点 `1,228,400`
  - 总交易次数约 `973`
  - 非零日胜率 `52.4887%`
  - broker10 exact 最大保证金/权益 `140.3161%`
  - 穿 100% 天数 `25`
- 相对最优弱形状 `r070_cluster35`：
  - 期末权益 `17,676,595`
  - 总收益 `2774.2431%`
  - 相对 Stage079 收益保留 `56.0764%`
  - 最大回撤 `-38.2323%`
  - Sharpe `1.4667`
  - Ulcer `15.4214`
  - 总滑点 `1,034,010`
  - 总交易次数约 `980`
  - 非零日胜率 `53.1627%`
  - broker10 exact 最大保证金/权益 `127.6314%`
  - 穿 100% 天数 `11`
  - 2x 成本最大回撤 `-41.6213%`

### 主动降杠杆形状

- `r070_pm_add_80_100` 与 no-cap 完全重合，触发次数 `0`，说明高保证金风险不是只靠砍 `add/donchian` 层就能解决。
- `r070_pm_all_90_110` 触发 `9` 次：
  - 期末权益 `14,526,775`
  - 总收益 `2262.0772%`
  - 收益保留 `45.7238%`
  - 最大回撤 `-37.6796%`
  - broker10 exact 最大 `127.2622%`
  - 穿100% `15` 天
  - 2x 成本最大回撤 `-40.5327%`
- `r080_cluster35_pm_all_80_100` 触发 `14` 次：
  - 期末权益 `14,258,435`
  - 总收益 `2218.4447%`
  - 收益保留 `44.8419%`
  - 最大回撤 `-41.6884%`
  - broker10 exact 最大 `126.7116%`
  - 穿100% `3` 天
- `r080_pm_all_80_100` 明显失败：
  - 总收益只剩 `441.9585%`
  - 最大回撤 `-51.3188%`
  - 收益保留 `8.9334%`

## 图表视觉复盘

- NAV 面板显示两类失败：`r070_cluster35` 还能保留一部分复利，但远低于 no-cap；`r070_pm_all_90_110` 和 `r080_cluster35_pm_all_80_100` 被主动砍仓压低，接近“降杠杆换平滑”。
- 回撤面板显示主动降杠杆没有稳定改善水下体验：`r070_pm_all_90_110` 仍接近 `-37.68%`，`r080_cluster35_pm_all_80_100` 跌破 DD40。
- 保证金面板和散点图是关键：没有任何点落在 `broker10<=100%` 区域，最好的 `r070_cluster35` 仍高达 `127.63%`。
- `add/donchian` 版本不触发，说明风险主要来自基础层和整组暴露，不是可轻易砍掉的加仓层。
- `all layers` 版本虽然触发，但仍没压住 exact margin，同时收益保留跌到 `45.72%` 或更低；它是滞后砍仓，不是有效贡献治理。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_report_stage517_portfolio_margin_deleverage_frontier_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_chart_stage517_portfolio_margin_deleverage_frontier_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_decision_stage517_portfolio_margin_deleverage_frontier_v1.json`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_summary_stage517_portfolio_margin_deleverage_frontier_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_cost_stress_stage517_portfolio_margin_deleverage_frontier_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_rolling_holding_stage517_portfolio_margin_deleverage_frontier_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_margin_daily_stage517_portfolio_margin_deleverage_frontier_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage517_portfolio_margin_deleverage_frontier_positions_stage517_portfolio_margin_deleverage_frontier_v1.csv`

## 结论

- 本阶段决策：`portfolio_margin_deleverage_not_ready`。
- 没有任何版本同时满足 `DD40 + broker10<=100 + 2x成本DD40`。
- 当前最好的 `r070_cluster35` 只是弱形状：收益保留 `56.08%`、DD `-38.23%`，但 exact margin `127.63%` 和 2x 成本 DD `-41.62%` 失败。
- 不继续扫 `0.80/0.90/1.00/1.10` 阈值小数；这会变成历史路径拟合。

## 后续规划和 TODO

- TODO 1：停止当前“组合总压力量化后滞后砍仓”小参数救援。
- TODO 2：若继续持仓治理，只能做更底层的逐日持仓保证金贡献排序/目标保证金削减仿真，且必须证明不是按历史赢家/输家黑名单。
- TODO 3：优先转向保证金轻、低相关、真实可执行的独立收益源；这比继续挤压同一套趋势仓更有价值。

## 过拟合反思

- 运行前判断：否。规则只使用当时可见的估算保证金、权益和通用风险簇，不筛日期/品种。
- 运行后判断：否。本阶段为粗档负结果；但如果继续扫阈值小数，会转为过拟合。
- 原因：失败来自 exact margin 与收益保留的基本矛盾，不是某个小阈值没调好。

## 继续价值反思

- 运行前判断：是。Stage216 反证静态 cap 后，必须验证主动持仓治理。
- 运行后判断：继续有价值，但不在当前滞后砍仓方向。
- 原因：当前证据说明同一趋势仓内部治理很难同时守 exact margin 和保留收益；下一步价值在低保证金独立收益源，或真正按保证金贡献排序的执行层仿真。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage217 当前状态。
- 是否更新 `research/registry.md`：是，当前研究线最新阶段从 Stage216 更新到 Stage217。
- 是否追加根目录 `memory.md/back_log.md`：是。本阶段否决主动组合保证金滞后砍仓方向，是后续避免重复试错的重要结论。
