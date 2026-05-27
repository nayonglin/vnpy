# Stage059 C3补齐供需信号真实引擎验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 17:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：供需数据补齐后的真实引擎验证；路线反证
- 是否重要突破：否，重要反证
- 是否触发A/B：是，C3补齐供需信号有可能影响正式候选，按既有A/B隔离原则只做独立验证，不改正式78-1

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档：`get_receipt` 注册仓单、`futures_spot_price`/`futures_spot_price_daily` 现货价格和基差。
  - AKShare GitHub 文档：注册仓单是交易所日级数据，可反映库存变化；基差是商品期货重要基本面因素。
- 我的判断：
  - 2023年前并不是“市场没有供需数据”，而是本地当前供需信号工程在 Stage316 之前只覆盖了 2023-2026；2020-2022 需要单独补齐。
  - 补齐是必要的数据审计动作，避免把“缺数据”误当成“没有逆风信号”；但补齐后的规则必须沿用冻结公式和阈值，不能边补数据边调参。
  - SHFE/DCE/GFEX 的可用字段不一致，特别是 `hc/rb/jm/fu/ru/sp` 等弱窗口相关品种多数只有基差组件，不能假设仓单三组件完整。

## 本次变更

- 新增脚本：无。本阶段使用 `examples/portfolio_backtesting/analyze_qmt_roll_stage359_c3_backfilled_supply_signal_validation.py`。
- 修改脚本：修复 Stage359 manifest 写法，改为先调用 `build_official_stage78_manifest()` 再追加本阶段元数据。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30，并做 `start_2021/start_2022/since_2023/phase_2024_2025/ytd_2026` 多窗口。
- 账户规模：50万，保持 Stage78-1/C3 当前研究口径。
- 成本口径：沿用当前真实引擎默认成本/滑点口径。
- 样本过滤：合并 Stage358 `2020-2022` 与 Stage316 `2023-2026` 点时化供需信号。
- 策略/归因口径：
  - `C_pressure040`
  - `C3_existing_2023plus`
  - `C3_backfilled_2020_2026`
  - 固定供需强逆风阈值 `-0.35`、最大信号年龄 `7` 天，不调公式、不调阈值、不改AI池和品种池。

## 结果

- `C_pressure040` 全样本：期末权益 `25,429,055`，总收益 `4985.8110%`，最大回撤 `-31.0767%`，Sharpe `1.2650`，总滑点 `2,047,490`，总交易次数 `862`，胜率 `45.0346%`。
- `C3_existing_2023plus` 全样本：期末权益 `30,925,650`，总收益 `6085.1300%`，最大回撤 `-31.0767%`，Sharpe `1.3663`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。
- `C3_backfilled_2020_2026` 全样本：期末权益 `5,256,505`，总收益 `951.3010%`，最大回撤 `-48.0183%`，Sharpe `0.8920`，总滑点 `407,070`，总交易次数 `612`，胜率 `46.7532%`。
- `start_2021`：现有C3 `5782.0950%/-31.2389%`，补齐供需C3 `532.5990%/-44.5559%`，收益保留仅 `9.2112%`。
- `start_2022`：现有C3 `695.6760%/-34.9148%`，补齐供需C3 `161.6030%/-41.9400%`，收益保留 `23.2296%`。
- `since_2023`、`phase_2024_2025`、`ytd_2026`：补齐前后等同或几乎等同，说明新增 2020-2022 信号主要改变早期路径。
- 组合供需信号行数：`51,524`。
- 决策：`fail_backfilled_supply_does_not_solve_drawdown30`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_report_stage359_c3_backfilled_supply_signal_validation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_summary_stage359_c3_backfilled_supply_signal_validation_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_comparison_stage359_c3_backfilled_supply_signal_validation_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_curves_stage359_c3_backfilled_supply_signal_validation_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_decision_stage359_c3_backfilled_supply_signal_validation_v1.json`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage359_c3_backfilled_supply_signal_validation_manifest_stage359_c3_backfilled_supply_signal_validation_v1.json`

## 结论

- 本阶段结论：2020-2022 供需数据应该补齐，且已经补齐并复跑；但补齐后的 C3 供需强逆风过滤没有降低最大回撤，反而显著压掉早期高收益交易并恶化回撤。
- 是否进入下一步：当前“补齐供需后直接套 C3 强逆风过滤”不进入下一步。
- 下一步：不要继续调 `-0.35` 阈值或供需权重小数。若继续外生数据方向，只允许转为“解释层/分层诊断”或寻找真正独立收益源；当前可执行边界仍是 Stage055 的正常成本外部现金部署方案。

## 过拟合反思

- 运行前判断：不是过拟合；只补点时化历史数据，冻结 C3 规则和阈值。
- 运行后判断：不是过拟合；失败原因来自补齐信号改变了早期交易选择，而不是调参失败。
- 原因：没有新增可搜索参数，没有利用结果反向调阈值；但如果继续围绕 `-0.35`、7天有效期或组件权重做小数救援，就会转为过拟合。

## 继续价值反思

- 运行前判断：有价值；必须确认 2020-2022 供需缺口是不是 C3 剩余回撤的解释来源。
- 运行后判断：该具体路线继续价值低，总研究线仍有价值。
- 原因：供需补齐已经把“缺数据假象”排除，但结果显示它不能承担回撤30以内保收益目标。后续应停止把当前供需强逆风过滤作为主路径。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为供需补齐路线废弃和后续禁区。
