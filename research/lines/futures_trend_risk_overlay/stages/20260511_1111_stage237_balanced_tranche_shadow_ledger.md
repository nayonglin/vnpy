# Stage237 balanced_tranche_v1 影子盘资金分层账本

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-11 11:11 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：部署账本模板落地
- 是否重要突破：是，风险线从“研究结论”进入“可执行部署工具”
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料：
  - 账户资金分层 / tranche 的核心思想是把同一底层收益路径拆成不同风险权益层，而不是继续追求单一“完美中间态”。
  - 系统交易资本校正更重要的是治理“风险资本如何随账户变化”，而不是不断微调策略参数。
- 我的判断：
  - 对当前仓库，最有价值的不是再做策略层覆盖参数，而是把 `balanced_tranche_v1` 变成可执行账本。
  - 部署工具必须和 `Stage232/233` 保持同口径，不能混入新的历史路径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage237_balanced_tranche_shadow_ledger.py`
- 修改脚本：无正式策略脚本修改
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 基准：`78-1` / `official_stage78_1_defensive_50w_no_sizing_cap`
- 部署制度：`balanced_tranche_v1`
  - 生产账户超过 `5,000,000`
  - 提取超额部分 `50%`
  - 其中 `60%` 进锁盈账户，`40%` 进扩张储备
- 历史场景：直接复用 `Stage232 curves` 中 `balanced_tranche_v1 + since_2020`
- 冷启动场景：`Stage186 2026-01-01 -> 2026-04-30 50w cold start daily`
- 输出：汇总表、逐日账本、提款/回补事件表、Markdown 报告

## 结果

- 期末权益：
  - 历史场景：`15,473,580`
  - 冷启动场景：`450,540`
- 总收益：
  - 历史场景：`2994.7161%`
  - 冷启动场景：`-9.8920%`
- 最大回撤：
  - 历史场景：`-40.0607%`
  - 冷启动场景：`-28.5861%`
- Sharpe：
  - 历史场景：`1.3726`
  - 冷启动场景：`-0.4970`
- 总滑点：本阶段不新增撮合统计，沿用原始输入口径
- 总交易次数：本阶段不新增撮合统计，沿用原始输入口径
- 胜率：本阶段不新增交易胜率统计
- 其他关键指标：
  - 历史场景首次提款日期：`2023-07-31`
  - 历史场景累计提款：`10,482,787`
  - 历史场景期末锁盈：`6,289,672`
  - 历史场景期末扩张储备：`4,193,115`
  - 历史场景期末生产账户：`4,990,793`
  - 冷启动场景当前离首次提款阈值还差：`4,549,460`
  - 冷启动场景当前仍是纯生产账户：锁盈 `0`、扩张储备 `0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage237_balanced_tranche_shadow_ledger_report_stage237_balanced_tranche_shadow_ledger_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage237_balanced_tranche_shadow_ledger_summary_stage237_balanced_tranche_shadow_ledger_v1.csv`
- ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage237_balanced_tranche_shadow_ledger_ledger_stage237_balanced_tranche_shadow_ledger_v1.csv`
- transfers：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage237_balanced_tranche_shadow_ledger_transfers_stage237_balanced_tranche_shadow_ledger_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage237_balanced_tranche_shadow_ledger_manifest_stage237_balanced_tranche_shadow_ledger_v1.json`

## 结论

- 本阶段结论：`balanced_tranche_v1` 已从研究候选推进为可执行部署账本工具。
- 是否进入下一步：是。
- 下一步：
  - 把该账本工具接到影子盘日报链路，形成“信号日报 + 三账户账本日报”双输出。
  - 若要更贴近实盘，可后续接入真实 QMT 账户余额读取，而不是只用回放/影子盘权益。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只把已确认的部署制度工具化，没有根据结果回调策略参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：它直接回答了部署层最关键的问题：当前账户是否已触发提款、历史上何时触发过、离下一次触发还有多远。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage237 已完成。
- 是否更新 `research/registry.md`：是，将下一步从“做账本模板”推进为“接日报链路”。
- 是否追加根目录 `memory.md/back_log.md`：是，记录风险线从研究走向可执行部署工具。
