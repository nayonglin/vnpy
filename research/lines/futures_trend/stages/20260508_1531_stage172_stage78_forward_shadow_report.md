# Stage172 Stage78前向影子盘日报

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 15:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结Stage78前向影子盘信号日报
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - PyPI `vnpy_tqsdk` 项目说明：https://pypi.org/project/vnpy-tqsdk/
  - vn.py GitHub 组织说明：https://github.com/vnpy
- 我的判断：前向日报只能证明“本地数据链和冻结策略能追到目标日”，不能证明实盘可下单；QMT 只读账户、真实T+1代理价、真实持仓/成交对账仍未接入。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage172_stage78_forward_shadow_report.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--target-date`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-05-07`
- 账户规模：回测本金`200,000`；影子风控资金边界`300,000`
- 成本口径：沿用冻结Stage78滑点口径；真实手续费/QMT成交尚未接入
- 样本过滤：官方 Stage78 宇宙
- 策略/归因口径：`official_stage78_defensive_v1`，只生成前向信号日报，不改参数

## 结果

- 期末权益：`4,565,700`
- 总收益：`2,182.85%`
- 最大回撤：`-36.99%`
- Sharpe：`1.2848`
- 总滑点：`262,820`
- 总交易次数：`784`
- 胜率：本阶段未重新统计日报展示胜率
- 其他关键指标：目标日`2026-05-07`理论信号1条；当日净盈亏`-44,110`；目标日风险级别`stop`；允许影子盘记录`1`；允许真实新增开仓`0`；触发原因`daily_loss_no_new_orders`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage172_stage78_forward_shadow_report_report_stage172_stage78_forward_shadow_report_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage172_stage78_forward_shadow_report_summary_stage172_stage78_forward_shadow_report_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage172_stage78_forward_shadow_report_signal_plan_stage172_stage78_forward_shadow_report_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage172_stage78_forward_20260507_daily.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage172_stage78_forward_shadow_report_daily_report_stage172_stage78_forward_shadow_report_v1.md`

## 结论

- 本阶段结论：已经生成 2026-05-07 的最新前向影子日报；但按30万影子资金风控，当日理论亏损触发停止新增真实开仓，因此当前只适合记录和对账，不适合真实新增订单。
- 是否进入下一步：是
- 下一步：补 T+1 开盘/日盘开盘代理价，并接 QMT 只读账户、持仓、委托、成交对账。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：冻结Stage78和固定资金风控阈值，只把前向数据跑通，没有根据目标日结果修改规则。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：日报已经追到真实目标日，下一步进入真实执行环境对账，比继续调参更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待QMT只读对账稳定后再更新状态
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加
