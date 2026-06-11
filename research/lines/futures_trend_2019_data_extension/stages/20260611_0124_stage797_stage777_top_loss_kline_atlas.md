# Stage797 Stage777候选版亏损比例Top5 K线复盘

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-11 01:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读法证画图；不修改策略、不修改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段没有新增外部策略资料；任务是对仓库内已登记候选版本做本地成交复盘和K线可视化。
- 我的判断：这类图谱只能用于发现候选结构和提出待检验假设，不能直接拿前5笔亏损反推阈值，否则会变成明显事后过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage797_stage777_top_loss_kline_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`TOP_N=5`，`PRE_BARS=50`，`POST_BARS=50`，`START=2020-01-01`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 候选版本地回放成本口径；本阶段不做成本压力变体。
- 样本过滤：只看 closed lots；按 `theory_loss_pct = -theory_return_pct` 从大到小取前5笔亏损比例交易。
- 策略/归因口径：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`，即 Stage777：50万、AM41、基础风险 `0.40`、命中 `OI上升 + 价格沿方向` 恢复到 `0.80`、旧正式AI池、关闭连败缩放和 recovery sleeve。

## 结果

- 期末权益：本阶段未新增权益指标，以 Stage777 候选版既有 `2020-01` 全周期结果为准。
- 总收益：本阶段未新增。
- 最大回撤：本阶段未新增。
- Sharpe：本阶段未新增。
- 总滑点：本阶段未新增。
- 总交易次数：本阶段 closed lots `261` 笔；其中理论亏损 `131` 笔。
- 胜率：本阶段未新增日级胜率；closed lots 理论亏损占比约 `50.19%`。
- 其他关键指标：
  - Top5 最差理论亏损比例分别为 `9.2195%`、`6.3561%`、`5.9242%`、`5.6523%`、`5.4140%`。
  - Top5 中 `2/5` 命中 OI 放大。
  - K线缺失 `0` 笔。

| rank | lot_id | 合约 | 方向 | 入场 | 出场 | 理论亏损 | 实际PnL | R | risk_multiplier | OI放大 | signal | exit |
| ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 163 | `jm2301.DCE` | long | 2022-08-29 | 2022-08-31 | 9.2195% | -306,180 | -1.7419 | 2.0 | 1 | `long_case1a` | `long_prev2day_stop` |
| 2 | 176 | `fu2305.SHFE` | long | 2023-01-31 | 2023-02-03 | 6.3561% | -77,440 | -3.1930 | 1.0 | 0 | `long_case2` | `long_prev2day_stop` |
| 3 | 115 | `lh2201.DCE` | long | 2021-11-01 | 2021-11-02 | 5.9242% | -192,000 | -2.9931 | 1.0 | 0 | `long_case2` | `long_base_stop` |
| 4 | 191 | `fu2310.SHFE` | long | 2023-08-22 | 2023-08-25 | 5.6523% | -141,370 | -1.1722 | 1.0 | 0 | `long_case3` | `long_prev2day_stop` |
| 5 | 58 | `ru2105.SHFE` | long | 2020-12-03 | 2020-12-07 | 5.4140% | -42,500 | -1.7347 | 2.0 | 1 | `rollover_reopen` | `long_prev2day_stop` |

## 输出文件

- report：无单独 report
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_summary_stage797_stage777_top_loss_kline_atlas_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_top_losses_stage797_stage777_top_loss_kline_atlas_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_closed_lots_stage797_stage777_top_loss_kline_atlas_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_top5_kline_stage797_stage777_top_loss_kline_atlas_v1.png`

## 结论

- 本阶段结论：候选版最大亏损比例前5笔全部是多单，集中在煤焦、燃油、生猪、橡胶等高波动窗口；最大单笔按价格比例亏损 `9.22%`，但按R并非最差，说明“价格亏损比例”和“初始止损R倍数”不是同一个风险维度。
- 是否进入下一步：可以作为视觉复盘材料进入下一步，但不能直接用这5笔设计参数。
- 下一步：若要从这些图提特征，应预声明可因果计算的候选特征，例如入场前趋势效率、入场前ATR/振幅分位、跳空/长实体反转、OI放大但价格路径不顺滑等，再做年度/逐月起点验证。

## 过拟合反思

- 运行前判断：低过拟合；本阶段只画图，不调策略。
- 运行后判断：低过拟合用于复盘，高过拟合风险用于决策。
- 原因：Top5 是事后极端样本，适合暴露失败形态，但不代表整体分布；任何过滤规则都必须跨起点、跨年份、跨品种复验。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值。
- 原因：图上能看到多笔是短期反向大波动/追高后快速止损形态，其中 OI 命中并不能保证路径顺滑；这和 Stage796 的“高波动、低趋势效率、高相关性”结论一致。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段只是只读图谱。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否

## 2026-06-11 01:27 追加：MA40可视化增强

- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage797_stage777_top_loss_kline_atlas.py`
- 修改内容：
  - 输出版本从 `stage797_stage777_top_loss_kline_atlas_v1` 升级为 `stage797_stage777_top_loss_kline_atlas_v2`。
  - K线图均线从 `MA5/MA10/MA20` 增加为 `MA5/MA10/MA20/MA40`，其中 MA40 使用黑灰色线。
  - 复用 v1 closed lots 缓存，不重跑策略逻辑。
- 新输出：
  - summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_summary_stage797_stage777_top_loss_kline_atlas_v2.csv`
  - top_losses：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_top_losses_stage797_stage777_top_loss_kline_atlas_v2.csv`
  - chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage797_stage777_top_loss_kline_atlas_top5_kline_stage797_stage777_top_loss_kline_atlas_v2.png`
- 结果：Top5 交易不变，closed lots `261`，理论亏损 `131`，Top5 中 OI 放大 `2/5`，K线缺失 `0`。
- 过拟合反思：低；只增加 MA40 图层，不改变策略、不调整样本、不新增筛选阈值。
- 继续价值反思：有；MA40 能帮助肉眼判断入场时是否处在中期趋势线附近或远离中期均线，但不能直接凭这5笔设阈值。
