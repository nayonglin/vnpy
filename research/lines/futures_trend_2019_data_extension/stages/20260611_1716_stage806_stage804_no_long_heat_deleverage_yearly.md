# Stage806 Stage804关闭多头风险簇热度去杠杆 年度多起点验证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 17:16 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage804 后续研究验证；A/B/C 年度多起点
- 是否重要突破：否
- 是否触发A/B：是

## 外部调研与判断

- 参考资料：
  - Man Group, Trend Following and Drawdowns: Is This Time Different? https://www.man.com/insights/is-this-time-different
  - Graham Capital, Trend-Following Primer https://www.grahamcapital.com/blog/trend-following-primer/
  - Invesco, Navigating momentum crashes in a trend-following strategy https://www.invesco.com/content/dam/invesco/emea/en/pdf/RRE_2024_Q2_NavigatingMomentum.pdf
- 我的判断：
  - 趋势跟随的收益结构依赖右偏尾部，风控不能机械剪掉刚启动的赢家。
  - 但趋势/动量在反转和拥挤阶段会产生 momentum crash 式回撤，完全关闭账户/风险簇降杠杆也可能释放坏尾部。
  - 因此本次只做“long 侧热度去杠杆关闭”的年度多起点验证，不扫阈值、不按 2025-07 单窗口救参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`disable_long_risk_cluster_heat_deleverage=True`
- 修改参数：
  - C 继承 Stage804 的 `long_tighter_initial_stop=True`
  - C 仅当持仓方向为 `long` 时跳过 `_process_risk_cluster_heat_deleverage`
  - `short_risk_cluster_heat_deleverage` 保持原逻辑
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01`、`2019-01`、`2020-01`、`2021-01`、`2022-01`、`2023-01`、`2024-01`、`2025-01`、`2026-01`，统一终点 `2026-05-29`
- 账户规模：50万
- 成本口径：沿用 Stage777/804 回测成本和滑点口径
- 样本过滤：年度独立启动；成熟样本排除 `2026-01`
- 策略/归因口径：
  - A：`official_candidate_stage777_50w_am41_oi08_old_ai_v1` 年度缓存
  - B：Stage804，A + 多头更紧初始止损
  - C：Stage806，B + 只关闭 `long_risk_cluster_heat_deleverage`
  - 保持不变：AM41、基础等效风险 `0.40`、OI 命中恢复 `0.80`、旧正式 AI 池、maxpos4、关闭连败缩放和 recovery sleeve

## 结果

- 期末权益：
  - C `2018-01` 起点：`21,510,750`
  - C `2019-01` 起点：`28,005,695`
  - C `2020-01` 起点：`26,916,055`
  - C `2021-01` 起点：`9,828,445`
  - C `2022-01` 起点：`1,333,760`
  - C `2023-01` 起点：`1,733,485`
  - C `2024-01` 起点：`997,630`
  - C `2025-01` 起点：`928,725`
  - C `2026-01` 起点：`438,360`
- 总收益：
  - C `2018-01`：`4202.150%`
  - C `2019-01`：`5501.139%`
  - C `2020-01`：`5283.211%`
  - C `2021-01`：`1865.689%`
  - C `2022-01`：`166.752%`
  - C `2023-01`：`246.697%`
  - C `2024-01`：`99.526%`
  - C `2025-01`：`85.745%`
  - C `2026-01`：`-12.328%`
- 最大回撤：
  - C `2018-01`：`-61.0852%`
  - C `2019-01`：`-56.1205%`
  - C `2020-01`：`-58.1409%`
  - C `2021-01`：`-58.7904%`
  - C `2022-01`：`-46.2948%`
  - C `2023-01`：`-23.6921%`
  - C `2024-01`：`-21.2918%`
  - C `2025-01`：`-17.9172%`
  - C `2026-01`：`-16.6451%`
- Sharpe：
  - C `2018-01`：`1.2135`
  - C `2019-01`：`1.3973`
  - C `2020-01`：`1.5051`
  - C `2021-01`：`1.3407`
  - C `2022-01`：`0.7861`
  - C `2023-01`：`1.2600`
  - C `2024-01`：`1.0559`
  - C `2025-01`：`1.3795`
  - C `2026-01`：`-1.0924`
- 总滑点：
  - C `2018-01`：`1,693,490`
  - C `2019-01`：`2,329,130`
  - C `2020-01`：`2,176,170`
  - C `2021-01`：`751,890`
  - C `2022-01`：`90,740`
  - C `2023-01`：`97,840`
  - C `2024-01`：`44,840`
  - C `2025-01`：`29,790`
  - C `2026-01`：`6,200`
- 总交易次数：
  - C `2018-01`：`669`
  - C `2019-01`：`620`
  - C `2020-01`：`525`
  - C `2021-01`：`387`
  - C `2022-01`：`271`
  - C `2023-01`：`181`
  - C `2024-01`：`124`
  - C `2025-01`：`72`
  - C `2026-01`：`24`
- 胜率：
  - C `2018-01`：`52.5974%`
  - C `2019-01`：`53.9336%`
  - C `2020-01`：`54.4466%`
  - C `2021-01`：`53.3166%`
  - C `2022-01`：`51.3514%`
  - C `2023-01`：`53.2468%`
  - C `2024-01`：`50.7987%`
  - C `2025-01`：`53.4483%`
  - C `2026-01`：`50.0000%`
- 其他关键指标：
  - vs Stage804 全样本：C 收益胜出 `6/9`，回撤胜出 `3/9`，Sharpe 胜出 `6/9`，收益+回撤双胜 `3/9`
  - vs Stage804 成熟样本：C 收益胜出 `5/8`，回撤胜出 `2/8`，Sharpe 胜出 `5/8`
  - vs Stage804 成熟样本收益中位差 `+31.0665pp`，回撤中位差 `-2.1109pp`
  - vs Stage804：DD40 失败 `4 -> 5`，DD50 失败 `2 -> 4`
  - vs Stage777 成熟样本：收益胜出 `8/8`，但回撤胜出仅 `1/8`，DD50 失败 `0 -> 4`
  - 2025-06-16 到 2025-07-25：C 修复 Stage804 在 `2021/2022/2023/2024` 起点的右尾捕捉，其中 `2021` C-B `+3,893,490`、`2023` C-B `+668,860`
  - 但 C 的最大回撤主要在 `2022-06-29` 被放大：`2018` 起点 `-61.0852%`，`2021` 起点 `-58.7904%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_report_stage806_stage804_no_long_heat_deleverage_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_summary_stage806_stage804_no_long_heat_deleverage_yearly_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_curves_stage806_stage804_no_long_heat_deleverage_yearly_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_comparison_vs_stage804_stage806_stage804_no_long_heat_deleverage_yearly_v1.csv`
- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_equity_curves_stage806_stage804_no_long_heat_deleverage_yearly_v1.png`
- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_return_delta_vs_stage804_bar_stage806_stage804_no_long_heat_deleverage_yearly_v1.png`
- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly_dd_delta_vs_stage804_bar_stage806_stage804_no_long_heat_deleverage_yearly_v1.png`

## 结论

- 本阶段结论：
  - 关闭多头热度去杠杆确实验证了 Stage805 的归因：Stage804 的部分右尾缺失来自 `long_risk_cluster_heat_deleverage` 过早清仓。
  - 但“完全关闭 long 热度去杠杆”不是可推广解法，因为它把 2022 类拥挤反转尾部显著放大，DD50 失败从 Stage804 的 `2` 个起点扩大到 `4` 个起点。
  - 因此 Stage806 不升级、不接官方候选。
- 是否进入下一步：不进入“直接关闭 long heat deleverage”的逐月推广。
- 下一步：
  - 如果继续，只能做结构化替代：例如热度去杠杆只对亏损/未确认趋势层生效，或把 sizing 风险距离与 heat 风险距离解耦；不要按 `jm/si/2025-07` 补丁化。

## 过拟合反思

- 运行前判断：中等风险。
- 运行后判断：直接关闭 long heat deleverage 若继续推广会过拟合。
- 原因：
  - 正面收益主要来自恢复 2025-07 右尾捕捉，这一点和提出动机强相关。
  - 多起点显示它同时释放 2022-06 坏尾部，且回撤失败数显著增加。
  - 继续扫压力阈值、方向、品种或时间窗口将落入救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前形态无继续价值，但机制问题有继续价值。
- 原因：
  - 本次实验证明 Stage804 的“多头更紧止损扩大手数”和“风险簇热度去杠杆”之间存在真实耦合。
  - 继续价值在于设计更细的结构隔离，而不是关闭风控。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段为负结论，不改变当前线状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
