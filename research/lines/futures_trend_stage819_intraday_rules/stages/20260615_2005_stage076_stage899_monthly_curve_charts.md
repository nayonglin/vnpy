# Stage076 Stage899逐月起点资金曲线图

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-15 20:05 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：既有 Stage899 曲线输出的可视化，不重跑回测
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段未新增外部资料检索；任务是读取已有 `rebased_nav`/`account_equity` 曲线并生成图，不涉及新策略设计或参数选择。
- 我的判断：逐月资金曲线应优先看归一净值，因为不同起点绝对权益不可直接比较；全周期曲线收益跨度很大，因此主图使用 log 纵轴，冷启动前 180 天另用线性纵轴观察回本前波动。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage899，逐月起点 `2018-01` 到 `2026-05`，统一统计到 `2026-05-29`
- 账户规模：沿用 C9 / Stage819 30万口径
- 成本口径：沿用 Stage899 / C9 回测输出
- 样本过滤：`101` 个逐月起点，曲线行数 `103,684`
- 策略/归因口径：读取 Stage899 `curves` 和 Stage075 派生统计，用 `rebased_nav` 画归一净值，用 `account_equity` 画绝对权益补充

## 结果

- 期末权益：不适用，本阶段未重跑组合回测
- 总收益：不适用，图中沿用 Stage899 曲线
- 最大回撤：图中标注 Stage075 的转正前最大浮亏窗口 `2022_04_to_2026_05_29` 和全窗口最大回撤窗口 `2020_07_to_2026_05_29`
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：生成 `4` 张 PNG，像素统计非空；其中 `3` 张为归一净值，`1` 张为绝对权益补充。

## 输出文件

- report：无新增
- summary：无新增
- orders：无
- daily：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_curves_stage899_c9_monthly_time_to_positive_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/stage899_monthly_curve_charts/stage899_c9_monthly_rebased_nav_all_log.png`
  - `examples/portfolio_backtesting/backtest_outputs/stage899_monthly_curve_charts/stage899_c9_monthly_rebased_nav_by_start_year.png`
  - `examples/portfolio_backtesting/backtest_outputs/stage899_monthly_curve_charts/stage899_c9_monthly_rebased_nav_first180d.png`
  - `examples/portfolio_backtesting/backtest_outputs/stage899_monthly_curve_charts/stage899_c9_monthly_account_equity_all_log.png`

## 结论

- 本阶段结论：逐月资金曲线已经输出；从图形上看，长期窗口的右尾复利非常强，但不同起点之间早期波动差异明显，`2022-04` 是冷启动前 180 天内最需要心理承受的样本。
- 是否进入下一步：是，但下一步仍不应调参。
- 下一步：若继续看持有体验，应补一张逐月起点的最大回撤热力图或按年度截面汇总；若要提高可信度，仍优先补齐 Stage898 的 `8` 笔 entry-day 分钟K缺口后重跑。

## 过拟合反思

- 运行前判断：否。本阶段只是可视化既有曲线，不改变策略和参数。
- 运行后判断：否。图中高亮最差窗口只是风险说明，不用于反推规则。
- 原因：没有新增自由度，也没有用图形结果筛选版本。

## 继续价值反思

- 运行前判断：有价值。资金曲线能直观看出逐月冷启动的持有体验。
- 运行后判断：有价值。
- 原因：归一净值图能把“最终收益”和“启动后先亏多少、多久走出来”同时暴露出来，适合判断是否能真实拿住。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage076 简要结论。
- 是否更新 `research/registry.md`：否，非跨线重要状态变更。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选变更。
