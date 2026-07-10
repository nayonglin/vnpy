# Stage122 2022 全品种趋势库存审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-09 13:27 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；统计 2022 最大回撤窗口和全年全品种趋势强度。
- 是否重要突破：否，归因证据，不是策略候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：pysystemtrade / PyTrendFollow / ADX / Donchian 与时序动量资料都支持用价格趋势强度、路径效率和突破/动量类指标做趋势库存审计。
- 我的判断：先用低自由度趋势库存回答“池子有没有趋势”，不能直接据此扩池或上线。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage122_2022_full_market_trend_inventory.py`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`LOSS_WINDOW=2022-03-09..2022-06-29`、`FULL_2022=2022-01-01..2022-12-31`、`MIN_COVERAGE=0.80`。
- 修改参数：无策略参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：查询 `2021-01-01` 到 `2022-12-31` 日线，统计 `2022-03-09..2022-06-29` 与 `2022` 全年。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：full-market tradable eligibility `57` 个品种，产品窗口覆盖率至少 `80%` 才进入强趋势统计。
- 策略/归因口径：连续主力日线；趋势分数由绝对收益、整窗路径效率、20日路径效率、ADX14、ADX>=25占比、20日最大绝对动量和20日方向一致性组成。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：loss window 全市场强趋势 `12/50`，static18 强趋势 `4/15`；结论 `full_market_had_trends_but_static_pool_also_had_enough_trend_not_simple_no_trend_pool`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage122_2022_full_market_trend_inventory/rebuilt_c9_v2_stage122_2022_full_market_trend_inventory_report_stage122_2022_full_market_trend_inventory_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage122_2022_full_market_trend_inventory/rebuilt_c9_v2_stage122_2022_full_market_trend_inventory_product_period_summary_stage122_2022_full_market_trend_inventory_v1.csv`
- orders：不适用。
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage122_2022_full_market_trend_inventory/rebuilt_c9_v2_stage122_2022_full_market_trend_inventory_product_daily_stage122_2022_full_market_trend_inventory_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage122_2022_full_market_trend_inventory/rebuilt_c9_v2_stage122_2022_full_market_trend_inventory_universe_period_summary_stage122_2022_full_market_trend_inventory_v1.csv`

## 结论

- 本阶段结论：`full_market_had_trends_but_static_pool_also_had_enough_trend_not_simple_no_trend_pool`。
- 是否进入下一步：`False`。
- 下一步：如要研究扩池，只能把本阶段作为候选来源，再做 PIT 规则和真实引擎验证；不能直接按 2022 赢家补品种。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做全品种趋势库存和归因，不按结果写交易规则、不扫阈值、不扩正式池。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有但仅限归因。
- 原因：它能回答 2022 是否缺趋势品种；但扩池需要单独的点时选择规则和真实引擎，不能从这张表直接上线。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录归因结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非突破。
