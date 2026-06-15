# Stage027 Stage851 PDEG-v0 只读反事实审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 00:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读代理反事实审计；不改策略、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否。否决 Stage026/PDEG-v0 当前形状，但不是全研究线终局。
- 是否触发A/B：否。本阶段不产生可接入候选版本，不进入官方候选，不触发 A/B。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 外部资料仍只支持原则：仓位、保证金和止损要分层管理；它们不提供可直接复制的低自由度 alpha/风控规则。
  - Stage026 的 PDEG-v0 必须先被只读反证，不能因为它听起来符合“产品方向敞口”就直接进引擎。
  - 若一个规则能命中压力段，但同时覆盖大量全样本 big winner，它就不是生存线，而是机械降杠杆。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage851_stage850_pdeg_proxy_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage851_stage850_pdeg_proxy_audit_v1`
  - `C9_VARIANT=stage847_stage819_c4_05r_stop_retry_once_2018`
  - 匹配窗口：entry_risk 日期到 lot entry 日期 `0 -> 5` 天内；只用于只读匹配，不是策略参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage847 C9 全周期 `2018-01` 起点至 `2026-05-29`，并重点对 Stage849 pressure paired lots 做匹配。
- 账户规模：沿用 Stage819 候选 `300,000` 口径。
- 成本口径：不新增成本压力；读取既有 C9 closed lots、trades、entry_risk、curve。
- 样本过滤：
  - 全样本审计读取 C9 `entry_risk` 共 `331` 行。
  - closed lots 匹配 C9 全样本 `373` 笔，其中代理匹配 `370` 笔。
  - 压力 paired lots 读取 Stage849 的 `8` 对。
- 策略/归因口径：
  - 规则代理：`drawdown_mode=true`、下单后该 key 为最大产品方向敞口、按最近 key-flat 权益预算会压低手数。
  - 这是只读近似代理，不是成交级真实引擎；它只检验 PDEG-v0 当前形状是否值得写引擎。

## 结果

- 期末权益：未新增；沿用 Stage847 C9 `37,395,131.2`。
- 总收益：未新增；沿用 Stage847 C9 `12365.0437%`。
- 最大回撤：未新增；沿用 Stage847 C9 `-53.2418%`。
- Sharpe：未新增；沿用 Stage847 C9 `1.4910`。
- 总滑点：未新增；沿用 Stage847 C9 `2,610,040`。
- 总交易次数：未新增；沿用 Stage847 C9 `730`。
- 胜率：未新增；沿用 Stage847 C9 `53.3156%`。
- 其他关键指标：
  - 决策标签：`stage851_pdeg_proxy_catches_pressure_but_too_broad_no_engine`。
  - entry_risk rows：`331`。
  - PDEG-v0 proxy flagged entry rows：`157`，触发率 `47.4320%`。
  - pressure pairs：`8`，matched `8`，flagged `7`。
  - pressure flagged pair PnL delta：`-289,040`；unflagged pair PnL delta：`-97,920`。
  - pressure flagged volume reduce proxy：`1,303` 手。
  - closed lots：`373`，matched `370`，flagged `187`，closed flag rate `50.5405%`。
  - flagged closed-lot PnL：`+27,580,024.6`。
  - unflagged closed-lot PnL：`+11,529,001.6`。
  - flagged big winner count：`17`，unflagged big winner count：`11`。
  - flagged big winner PnL：`+24,065,430`，unflagged big winner PnL：`+8,082,770`。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_report_stage851_stage850_pdeg_proxy_audit_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_summary_stage851_stage850_pdeg_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_entry_audit_stage851_stage850_pdeg_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_pressure_pair_match_stage851_stage850_pdeg_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_closed_lot_match_stage851_stage850_pdeg_proxy_audit_v1.csv`
- orders：无。
- daily：无新增。
- quality：
  - `py_compile` 通过。
  - Stage851 脚本完整运行成功。
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage851_stage850_pdeg_proxy_audit_decision_stage851_stage850_pdeg_proxy_audit_v1.json`

## 结论

- 本阶段结论：
  - PDEG-v0 当前形状不能接真实引擎。
  - 它能命中 `7/8` 个 Stage849 pressure pairs，说明“产品方向预算冻结”确实碰到了压力机制；但它同时触发 `47.43%` entry rows、`50.54%` matched closed lots，并覆盖 `17` 个 big winners 和 `+24,065,430` big-winner PnL。
  - 这不是精准的持仓后生存线，而是过宽的机械降风险。若直接实现，大概率会砍掉 Stage819/C9 的右尾来源。
- 是否进入下一步：不进入 PDEG-v0 引擎。
- 下一步：
  - 停止 PDEG-v0 当前形状；不得通过新增小数阈值、产品名、年份、方向或 `1.35x` 手数比救它。
  - 若仍继续本研究线，只能重新寻找更强的一阶预算锚，或回到更完整的分钟K数据覆盖/视觉证据；不能把 Stage851 结果包装成可交易规则。

## 过拟合反思

- 运行前判断：中等风险。
- 运行后判断：若继续沿 PDEG-v0 救参，会变成高风险过拟合。
- 原因：
  - 代理确实命中了压力段，但同时命中了大量右尾；若继续通过阈值把 `157` 次触发压到少数压力事件，就是典型事后筛选。
  - 本阶段没有这么做，而是按预声明失败条件否决当前形状。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：本分支继续价值低；研究线整体还有有限价值。
- 原因：
  - Stage851 证明当前预算冻结形状太宽，不值得接引擎。
  - 但这个失败本身有信息量：C9 的右尾和压力段共享“账户回撤中大产品方向敞口”状态，单靠账户/产品方向预算变量很难区分好坏。
  - 若继续，必须引入更本质的实时价格路径证据或更完整分钟K覆盖，而不是继续在账户状态上加阈值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage027 否决 PDEG-v0 当前形状。
- 是否更新 `research/registry.md`：否。本阶段是研究线内部子分支否决，不是正式候选、重要突破或整条路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选或跨线结论。
