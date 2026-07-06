# Stage092 保证金压力上限代理

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 18:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金/保证金治理曲线级 proxy，A/C 前置筛查
- 是否重要突破：否
- 是否触发A/B：否；已读取 A/B 纪律，但本阶段没有形成可合入候选，仅为正式 A/B 前置筛查

## 外部调研与判断

- 参考资料：UBS managed futures risk targeting、Quantpedia robust trend-following、conditional volatility targeting 资料。
- 我的判断：风险预算/压力上限是结构性思路，但本线已反证简单回撤后刹车；本阶段只筛查前一日保证金压力上限，失败就停止，不按具体坏窗口救参。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage092_margin_pressure_cap_proxy.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`broker10_cap80_proxy`、`broker10_cap70_proxy`、`broker10_cap60_proxy`
- 修改参数：无正式交易参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage167 正式 C9/15w 多起点曲线，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 成本口径：沿用 Stage167 曲线；proxy 按风险缩放日 PnL 与 slippage，不生成真实成交。
- 样本过滤：重点 `2020-01` 至 `2026-01` 逐半年起点。
- 策略/归因口径：前一日 `broker10_margin_to_equity_pct` 超过 cap 时，下一交易日 PnL 乘以 `cap / pressure`；不前视，但不是正式真实引擎。

## 结果

| sample           | version                   | variant_label         |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_active_days |   min_mean_multiplier |   total_slippage_sum |   total_trade_count_sum | passes_new_goal_vs_official   |
|:-----------------|:--------------------------|:----------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|---------------------:|----------------------:|---------------------:|------------------------:|:------------------------------|
| starts_2020_2026 | broker10_cap60_proxy      | Broker10 cap 60 proxy |            13 |               13 |          1.90107 |             126.199 |          3655.41 |                     0.940616 |                        0.999554 |             -57.6067 |               -24.469 |                      501 |                          20 |                                  387 |                    2 |              0.992476 |          1.83014e+06 |                    3673 | False                         |
| starts_2020_2026 | broker10_cap70_proxy      | Broker10 cap 70 proxy |            13 |               13 |          1.90107 |             126.199 |          3863.54 |                     0.994174 |                        1        |             -55.7176 |               -24.469 |                      500 |                          20 |                                  387 |                    0 |              0.998345 |          1.84684e+06 |                    3673 | False                         |
| starts_2020_2026 | broker10_cap80_proxy      | Broker10 cap 80 proxy |            13 |               13 |          1.90107 |             126.199 |          3875.51 |                     0.997252 |                        1        |             -55.5471 |               -24.469 |                      500 |                          20 |                                  387 |                    0 |              0.99976  |          1.85251e+06 |                    3673 | False                         |
| starts_2020_2026 | official_c9_15w_reference | Official C9 15w       |            13 |               13 |          1.90107 |             126.199 |          3886.19 |                     1        |                        1        |             -55.3701 |               -24.469 |                      500 |                          20 |                                  387 |                    0 |              1        |          1.85368e+06 |                    3673 | False                         |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage092_margin_pressure_cap_proxy/rebuilt_c9_v2_stage092_margin_pressure_cap_proxy_report_stage092_margin_pressure_cap_proxy_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage092_margin_pressure_cap_proxy/rebuilt_c9_v2_stage092_margin_pressure_cap_proxy_variant_summary_stage092_margin_pressure_cap_proxy_v1.csv`
- orders：不适用
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage092_margin_pressure_cap_proxy/rebuilt_c9_v2_stage092_margin_pressure_cap_proxy_curves_stage092_margin_pressure_cap_proxy_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage092_margin_pressure_cap_proxy/rebuilt_c9_v2_stage092_margin_pressure_cap_proxy_retention_vs_official_stage092_margin_pressure_cap_proxy_v1.csv`

## 结论

- 本阶段结论：`stage092_margin_pressure_cap_proxy_not_promoted`。
- 是否进入下一步：`False`。
- 下一步：停止保证金压力 cap proxy 救参，转向真实暴露归因或外生收益腿。

## 独立 Agent 评估

- 评估 agent：`019f31d5-088e-70a2-b67b-a58f52c05b47`。
- 结论：未发现会推翻 Stage092 输出表的严重统计 bug、前视或实盘触碰证据；当前 `stage092_margin_pressure_cap_proxy_not_promoted` 成立。
- 置信度：`0.82`。
- 复核摘要：输出曲线 `73,980` 行，等于 `18,495` 输入日线 x `4` 版本；17 个起点，终点 `2026-06-30`；权益递推最大误差约 `3.7e-09`，multiplier 规则最大误差约 `1.1e-16`。
- 审查意见：Stage092 只能作为不晋级粗筛，不能替代 path-consistent true engine；`proxy_trade_count` 保留官方交易数，不应解读为 cap 后真实成交次数；“水下天数”应明确为“低于初始本金天数”。
- 已处理：将本记录的 A/B 表述从“触发A/B”修正为“未触发正式A/B，仅前置筛查”。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。负结果后不继续扫更细 cap。
- 原因：固定 3 个粗粒度 cap 做筛查；不按单一坏窗口、品种或日期救参。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有限
- 原因：若 proxy 未能同时改善水下、回撤和收益保留，真实引擎优先级不足。

## 合入建议

- 是否更新本线 `LINE.md`：否，等待独立审查后再决定。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段未形成正式 A/B 候选或重要突破。
