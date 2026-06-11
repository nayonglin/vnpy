# Stage791 Stage777 旧 AI 老师年度多周期资金曲线

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-10 18:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：年度起点抽取、资金曲线绘图、只读对照
- 是否重要突破：否
- 是否触发A/B：否。本阶段没有新增策略参数，不重跑策略逻辑，只从 Stage777 已完成的逐月启动结果中抽取年度起点。

## 外部调研与判断

- 参考资料：
  - sklearn `TimeSeriesSplit` 文档：https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
  - vn.py `ArrayManager` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - 时间序列 AI 必须保持 point-in-time / walk-forward 口径，不能用未来月份修正历史选品。
  - vn.py `ArrayManager` 的窗口语义说明 AM41 仍是策略信号预热/指标完整性约束；本阶段不改 AM、OI、风控，只确认旧正式 AI 池在 Stage777 target 上的年度路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage791_stage777_old_ai_yearly_curves.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：从 Stage777 月度回测文件抽取 `2018-01`、`2019-01`、...、`2026-01` 年度起点，统一终点 `2026-05-29`。
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 已产出的逐月回测成本口径。
- 样本过滤：仅取 `start_month` 以 `-01` 结尾的年度启动样本。
- 策略/归因口径：Stage777 AM41，基础等效风险 `0.40`，命中 `OI上升 + 价格沿方向` 恢复到 `0.80`，继承旧正式 AI 品种池。

## 结果

### 年度起点明细

| start_month | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总交易次数 | 总滑点 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018-01 | 18,251,265 | 3550.253% | -49.4213% | 1.3671 | 648 | 1,145,460 | 52.3089% |
| 2019-01 | 21,189,950 | 4137.990% | -49.3661% | 1.5261 | 602 | 1,295,330 | 53.4722% |
| 2020-01 | 12,614,810 | 2422.962% | -49.1145% | 1.4717 | 512 | 844,660 | 53.6391% |
| 2021-01 | 6,133,635 | 1126.727% | -48.6695% | 1.3478 | 382 | 380,570 | 52.5466% |
| 2022-01 | 1,106,350 | 121.270% | -35.3554% | 0.7607 | 262 | 55,960 | 50.7719% |
| 2023-01 | 1,397,565 | 179.513% | -22.1100% | 1.2604 | 178 | 58,990 | 53.9615% |
| 2024-01 | 911,940 | 82.388% | -23.3469% | 1.0578 | 122 | 30,530 | 52.2013% |
| 2025-01 | 919,160 | 83.832% | -16.2147% | 1.4744 | 69 | 19,840 | 53.2258% |
| 2026-01 | 475,130 | -4.974% | -15.5310% | -0.1741 | 22 | 3,780 | 53.4884% |

### 聚合指标

- 全部年度起点：`9` 个，正收益 `8/9`，收益中位数 `179.513%`，p10 `64.9156%`，最小收益 `-4.974%`，最大回撤中位数 `-35.3554%`，最差回撤 `-49.4213%`，DD40 失败 `4/9`，DD50 失败 `0/9`，交易合计 `2,797`。
- 成熟年度起点 `>=252d`：`8` 个，正收益 `8/8`，收益中位数 `653.120%`，p10 `83.3988%`，最小收益 `82.388%`，最大回撤中位数 `-42.0124%`，最差回撤 `-49.4213%`，DD40 失败 `4/8`，DD50 失败 `0/8`，交易合计 `2,775`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_report_stage791_stage777_old_ai_yearly_curves_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_summary_stage791_stage777_old_ai_yearly_curves_v1.csv`
- daily/curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_curves_stage791_stage777_old_ai_yearly_curves_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_aggregate_stage791_stage777_old_ai_yearly_curves_v1.csv`
- charts：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_equity_grid_stage791_stage777_old_ai_yearly_curves_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_equity_overlay_stage791_stage777_old_ai_yearly_curves_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage791_stage777_old_ai_yearly_curves_nav_overlay_stage791_stage777_old_ai_yearly_curves_v1.png`

## 结论

- 本阶段结论：Stage777 旧正式 AI 老师池是强右尾版本。成熟年度起点全部正收益，但 2018-2021 四个早期起点最大回撤均接近 `-49%`，说明它不是低回撤正式替代，而是后续新 AI 老师池必须超越的高收益高回撤基准。
- 是否进入下一步：可以继续，但方向不是直接推广 Stage777；应继续做 AI 拦截样本归因，解释旧 AI 为什么保留右尾、新老师为什么砍掉部分右尾。
- 下一步：若继续 AI 路线，优先比较旧 AI 池、新 AM41 no-OI 老师池、新 AM41 OI0.8 老师池在同一年度起点下拦截了哪些品种/方向/case，以及被拦截样本的后验 R 分布。

## 过拟合反思

- 运行前判断：过拟合风险低，因为没有新参数、没有按结果调规则，只是抽取已有 Stage777 年度起点。
- 运行后判断：过拟合风险仍低，但不能把 2018-2021 的巨大收益当作可推广的低风险优势。
- 原因：收益主要来自早期大右尾和复利底座，同期回撤接近 `-49%`；这更像高波动趋势暴露，而不是更普世的 AI 质量过滤证明。

## 继续价值反思

- 运行前判断：有价值，因为用户需要明确旧 AI 老师在 Stage777 target 下的年度多周期资金曲线。
- 运行后判断：仍有价值，尤其能作为 Stage788/789 新老师 AI 池的对照基准。
- 原因：旧 AI 池在收益端明显更强，但回撤端很硬；新老师池若要晋级，必须解释并避免“砍掉右尾”或“继承 OI 高回撤”的问题。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是只读抽取和绘图，不改变正式策略路线。
