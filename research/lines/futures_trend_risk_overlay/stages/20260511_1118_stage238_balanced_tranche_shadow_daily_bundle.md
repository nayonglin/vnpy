# Stage238 balanced_tranche 三账户部署日报

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-11 11:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：部署日报链路接线
- 是否重要突破：是，风险线从“账本工具”推进到“可日更部署日报”
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料：
  - [Capital correction (pysystemtrade)](https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html?m=1) 强调风险资本管理应独立于信号逻辑，账户高水位后的资本治理应通过明确规则执行，而不是临时主观判断。
- 我的判断：
  - `balanced_tranche_v1` 的价值不在曲线图本身，而在于它能否进入日报，成为每天可执行的部署纪律。
  - 因此本阶段不改策略、不改阈值，而是把 `Stage186` 信号日报和 `Stage237` 三账户账本拼成统一部署日报。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage238_balanced_tranche_shadow_daily_bundle.py`
- 修改脚本：无正式策略脚本修改
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 基准：`78-1` / `official_stage78_1_defensive_50w_no_sizing_cap`
- 日报信号源：`Stage186 2026 cold start`
- 账本源：`Stage237 balanced_tranche shadow ledger`
- 交易日：`2026-04-30`
- 部署制度：`balanced_tranche_v1`

## 结果

- 期末权益：`450,540`
- 总收益：`-9.8920%`
- 最大回撤：`-28.5861%`
- Sharpe：`-0.6975`
- 总滑点：`4,660`
- 总交易次数：`27`
- 胜率：`16.6667%`
- 其他关键指标：
  - 当日理论信号数：`1`
  - 风险级别：`watch`
  - 当前生产账户：`450,540`
  - 当前锁盈账户：`0`
  - 当前扩张储备：`0`
  - 离首次提款阈值还差：`4,549,460`
  - 历史首次提款日期：`2023-07-31`
  - 历史累计提款：`10,482,787`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage238_balanced_tranche_shadow_daily_bundle_daily_report_20260430_stage238_balanced_tranche_shadow_daily_bundle_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage238_balanced_tranche_shadow_daily_bundle_summary_20260430_stage238_balanced_tranche_shadow_daily_bundle_v1.json`

## 结论

- 本阶段结论：已经形成“信号日报 + 三账户账本日报”的组合输出，`balanced_tranche_v1` 正式进入日常部署链路。
- 是否进入下一步：是。
- 下一步：
  - 接真实 QMT 账户余额，替代当前回放/影子盘权益。
  - 若接到实盘只读数据，再增加“账户实值 vs 回放权益偏差”监控栏。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只是日报接线，没有改任何策略、风险或部署阈值。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：部署日报比单一信号日报更接近实盘治理需要，能直接支撑账户纪律执行。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage238 已完成。
- 是否更新 `research/registry.md`：是，将下一步推进为真实账户余额接线。
- 是否追加根目录 `memory.md/back_log.md`：是，记录风险线已形成日更部署日报。
