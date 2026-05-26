# Stage057 供需数据2020-2022补齐可得性探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 16:47 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：供需外生数据补齐前的数据源可得性探针
- 是否重要突破：否，是补齐路线的前置确认
- 是否触发A/B：否。本阶段不改策略、不生成候选版本，只验证历史数据源是否能支撑下一步 A/C 回测。

## 外部调研与判断

- 参考资料：
  - AKShare GitHub 仓库和期货数据文档确认存在 `futures_spot_price`、`futures_inventory_99`、`futures_shfe_warehouse_receipt`、`futures_warehouse_receipt_dce/czce`、`futures_gfex_warehouse_receipt` 等期货数据接口。
  - AKShare 文档样例显示部分库存/仓单接口历史可回溯，且函数层支持按日期查询交易所仓单。
- 我的判断：
  - 2020-2022 补齐不是调参，是减少 Stage316/318 对 2021 回撤无覆盖的盲区。
  - 但补齐前必须先确认历史接口行为；如果交易所仓单历史不完整，供需因子应允许组件缺失并记录覆盖，而不是把缺失误当成中性强证据。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage357_supply_demand_backfill_feasibility.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 抽样日期：`20200102/20200601/20210104/20210512/20210702/20220309/20221207/20221230`
  - 数据源：Stage316 同源 `futures_spot_price`、`futures_shfe_warehouse_receipt`、`futures_warehouse_receipt_czce`、`futures_gfex_warehouse_receipt`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：抽样覆盖 2020、2021、2022；重点包含 C3 最大回撤峰谷日 `2021-05-12/2021-07-02` 和 Stage001 旧回撤边界 `2022-03-09/2022-12-07`。
- 账户规模：无。本阶段不是回测。
- 成本口径：无。本阶段不是回测。
- 样本过滤：不修改 C3、Stage017/018 供需公式、`-0.35` 阈值或任何交易逻辑。
- 策略/归因口径：只判断数据源是否可用于下一步全量 raw cache 补齐和点时化重建。

## 结果

- 期末权益：无
- 总收益：无
- 最大回撤：无
- Sharpe：无
- 总滑点：无
- 总交易次数：无
- 胜率：无
- 其他关键指标：
  - 基差数据：`8/8` 抽样日返回成功，关键回撤日 `4/4` 返回成功。
  - 仓单数据：至少一个交易所仓单数据 `8/8` 抽样日返回成功，关键回撤日 `4/4` 返回成功。
  - 交易所层细节：`warehouse_czce` 为 `8/8`；`warehouse_shfe` 为 `0/8`；`warehouse_gfex` 为 `0/8`。
  - 判定：`sample_supports_basis_backfill_but_warehouse_exchange_gaps`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage357_supply_demand_backfill_feasibility_report_stage357_supply_demand_backfill_feasibility_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage357_supply_demand_backfill_feasibility_summary_stage357_supply_demand_backfill_feasibility_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage357_supply_demand_backfill_feasibility_decision_stage357_supply_demand_backfill_feasibility_v1.json`

## 结论

- 本阶段结论：可以继续全量补齐 `2020-2022`，但必须标记“SHFE/GFEX 仓单历史抽样为空”的覆盖缺口。
- 是否进入下一步：是。
- 下一步：
  - 新增 Stage358：复制 Stage316 数据构建逻辑，但日期范围改为 `20200101-20221231`，输出独立 raw cache/features/signals。
  - 不改供需公式和 `-0.35` 强逆风阈值。
  - 全量补齐后先看覆盖表，尤其是 `hc/rb/fu/ru/sp` 等 SHFE 品种是否只有基差组件。
  - 若覆盖足够，再构建 2020-2026 合并信号并复跑 C3；若 SHFE 仓单仍缺失，则先保留基差组件，不做仓单 fallback 调参。

## 过拟合反思

- 运行前判断：不是过拟合。抽样日期包含年度边界和历史回撤边界，用来判断数据接口可用性，不改变规则。
- 运行后判断：不是过拟合。结果只说明数据源覆盖形态，没有选择有利参数。
- 原因：所有策略参数、阈值和公式均保持冻结；结论主要是“能否补数据”和“哪些组件缺失”。

## 继续价值反思

- 运行前判断：有价值。Stage316 数据从 2023 开始，天然无法解释 2021 回撤。
- 运行后判断：有价值，但需带着覆盖缺口继续。基差数据对黑色链 2021 回撤区间可用，供需路线值得进入全量补齐；SHFE 仓单缺口意味着不能过度解读三组件完整因子。
- 原因：本阶段把“没数据”与“因子无效”拆开，下一步可以用冻结公式验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage357 可进入全量补齐但有仓单交易所缺口。
- 是否更新 `research/registry.md`：是，当前线最新阶段改为 Stage057。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是前置探针，不是重要突破或路线废弃。
