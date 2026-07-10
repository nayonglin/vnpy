# Stage123 C9 品种盈利能力账本审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-09 13:41 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；统计当前 C9/15w 已实际交易品种的盈利能力。
- 是否重要突破：否，归因证据，不是策略候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：pysystemtrade / PyTrendFollow / futures trend following 资料都支持在多市场系统里做 instrument-level performance attribution，不能只看价格趋势强度。
- 我的判断：先统计 C9 实际 closed_lots，回答“策略在这些品种上是否赚钱”；未交易的全市场品种需要另开逐品种真实引擎重跑，不能从本账本直接得出。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage123_c9_product_profitability_inventory.py`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`LOSS_WINDOW=2022-03-09..2022-06-29`、`FULL_2022=2022-01-01..2022-12-31`、`MATERIAL_TRADE_COUNT=3`、`MATERIAL_PROFIT_FACTOR=1.10`。
- 修改参数：无策略参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：closed_lots 覆盖 `2018-01-15` 到 `2026-05-07`。
- 账户规模：沿用源账本 C9/15w，不重新回测。
- 成本口径：沿用源账本已实现盈亏。
- 样本过滤：按 exit_date 和 entry_date 分 period；主表以 exit_date 口径为准。
- 策略/归因口径：当前 C9/15w Stage847 stop/retry 真实引擎 closed_lots。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：源账本内已体现在 realized_pnl，未单独重算。
- 总交易次数：full sample `19` 个产品、closed lots 见明细。
- 胜率：见 product summary。
- 其他关键指标：loss window exit 产品 `8` 个，正收益 `4` 个，材料性正收益 `0` 个，总净 PnL `-1304480.00`；full 2022 exit 正收益 `7/15`；full sample 正收益 `13/19`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage123_c9_product_profitability_inventory/rebuilt_c9_v2_stage123_c9_product_profitability_inventory_report_stage123_c9_product_profitability_inventory_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage123_c9_product_profitability_inventory/rebuilt_c9_v2_stage123_c9_product_profitability_inventory_product_period_summary_stage123_c9_product_profitability_inventory_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage123_c9_product_profitability_inventory/rebuilt_c9_v2_stage123_c9_product_profitability_inventory_closed_lots_with_period_stage123_c9_product_profitability_inventory_v1.csv`

## 结论

- 本阶段结论：`c9_product_profitability_is_concentrated_not_equivalent_to_trend_inventory`。
- 是否进入下一步：`False`。
- 下一步：若要回答未入池品种是否能赚钱，需要另开逐品种 C9 真实引擎重跑；本阶段不能直接扩池。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只读既有 closed_lots，不按结果改池子、改参数或生成交易规则。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但下一步应是逐品种真实引擎而非看趋势表。
- 原因：它能区分“有趋势”与“策略实际能赚钱”，但对未交易品种还没有证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录归因结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非突破。
