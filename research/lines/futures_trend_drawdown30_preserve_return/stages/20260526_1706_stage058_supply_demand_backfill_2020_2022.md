# Stage058 供需数据2020-2022全量补齐

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 17:06 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：供需外生数据全量补齐与覆盖审计
- 是否重要突破：否，是进入合并信号回测前的数据准备
- 是否触发A/B：否。本阶段不运行策略 A/C 回测，只生成 2020-2022 供需特征和信号。

## 外部调研与判断

- 参考资料：
  - AKShare GitHub/文档确认期货基差、库存和交易所仓单接口存在，并提供按日期或品种查询能力。
  - Stage357 抽样确认 2020-2022 关键交易日基差可用，CZCE 仓单可用，SHFE/GFEX 仓单历史抽样为空。
- 我的判断：
  - 补齐 2020-2022 数据不是为了调参，而是解决 Stage316 只从 2023 开始、天然无法覆盖 C3 2021 最大回撤的问题。
  - 全量补齐后必须先做覆盖审计，再合并到 2020-2026 信号并用冻结阈值复跑，不允许因为补齐结果不理想而调供需权重或阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage358_supply_demand_backfill_2020_2022.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `FETCH_START_DAY=20200101`
  - `FETCH_END_DAY=20221231`
  - `MODEL_TAG=stage358_supply_demand_backfill_2020_2022_v1`
- 修改参数：仅将 Stage316 数据构建入口重定向到 2020-2022 独立输出；供需公式、滚动窗口、最大信号年龄和权重均不变。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2022-12-31`
- 账户规模：无。本阶段不是回测。
- 成本口径：无。本阶段不是回测。
- 样本过滤：沿用 Stage316 的候选匹配和外生信号 join 逻辑。
- 策略/归因口径：供需外生质量探针；不改变第78-1/C3交易规则。

## 结果

- 期末权益：无
- 总收益：无
- 最大回撤：无
- Sharpe：无
- 总滑点：无
- 总交易次数：无
- 胜率：无
- 其他关键指标：
  - 外生信号行数：`22,684`
  - 特征行数：`11,342`
  - 候选样本数：`953`
  - 实际开仓候选数：`315`
  - 候选命中外生信号数：`387`
  - 实际开仓命中外生信号数：`169`
  - 候选命中率：`40.6086%`
  - 实际开仓命中率：`53.6508%`
  - 判定：`fail_insufficient_oos_coverage`

## 覆盖审计

- CZCE：`CF/FG/MA/OI/SA/SM` 多数为接近三组件；`AP` 只有仓单类组件，平均可用组件数 `1.0`。
- SHFE：`au/cu/fu/hc/rb/ru/sp` 覆盖 `728` 天，但平均仓单增减为空，平均可用组件数 `2.0`，实际主要依赖基差水平和基差变化。
- DCE：`jm/lh` 有基差覆盖，平均可用组件数 `2.0`，仓单增减为空。
- 关键影响：2021 最大回撤相关 `hc/rb/jm` 已有基差组件，但仓单组件缺失，后续 C3 复跑不能把它解释成三组件完整供需因子。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_report_stage358_supply_demand_backfill_2020_2022_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_features_stage358_supply_demand_backfill_2020_2022_v1.csv`
- external_signals：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_external_signals_stage358_supply_demand_backfill_2020_2022_v1.csv`
- joined_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_joined_candidates_stage358_supply_demand_backfill_2020_2022_v1.csv`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_coverage_stage358_supply_demand_backfill_2020_2022_v1.csv`
- bucket_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_bucket_summary_stage358_supply_demand_backfill_2020_2022_v1.csv`
- source_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage358_supply_demand_backfill_2020_2022_source_summary_stage358_supply_demand_backfill_2020_2022_v1.csv`

## 结论

- 本阶段结论：2020-2022 供需数据已补齐到独立信号文件，但历史仓单覆盖不完整，尤其 SHFE/DCE 黑色链主要只有基差组件。
- 是否进入下一步：是。
- 下一步：合并 Stage358 `2020-2022` 与 Stage316 `2023-2026` 信号，固定 `supply_demand_headwind_threshold=-0.35`，复跑 C3 对比，重点看 full/start_2021/start_2022 最大回撤是否下降到30以内。

## 过拟合反思

- 运行前判断：不是过拟合。只补数据，不调因子公式和阈值。
- 运行后判断：不是过拟合。输出显示覆盖缺口，没有选择性筛掉坏数据。
- 原因：本阶段没有根据收益结果改变任何策略参数；`fail_insufficient_oos_coverage` 来自切分样本不足，不是策略效果判断。

## 继续价值反思

- 运行前判断：有价值。2021 是 C3 剩余最大回撤核心窗口，原 Stage316 无数据覆盖。
- 运行后判断：仍有价值，但需要马上进入合并信号回测；单独 2020-2022 分桶没有足够 OOS 样本，不应独立下结论。
- 原因：数据已补齐，下一步可以直接验证“供需信号缺失是否导致 C3 2021 回撤未被过滤”。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是数据准备，不是突破或路线废弃。
