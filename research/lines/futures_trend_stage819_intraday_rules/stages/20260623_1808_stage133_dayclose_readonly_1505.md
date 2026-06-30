# Stage133 日盘收后只读快照提前到15:05

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-23 18:08 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：官方实盘自动化时序微调
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 上期所官方交易时间页面：日盘第三节为 `13:30-15:00`，夜盘品种从上一工作日 `21:00` 开始。
  - 大连商品交易所官方交易时间页面：日盘第三节为 `13:30-15:00`。
  - 郑商所官方夜盘专题：夜盘品种交易日从前一工作日夜盘开始至当天日盘结束。
  - 本地 Stage130/132 记录、Stage907/174 只读刷新写文件方式、Stage934 launchd 健康检查。
- 我的判断：15:01 理论上已经在交易所日盘结束之后，但不适合作为唯一只读快照时点。原因是 Stage174 使用固定 latest 文件输出；如果过早刷新失败，会覆盖已有可用快照。更稳妥的折中是把唯一 day-close readonly 从 `15:08` 提前到 `15:05`，既给 CTP/broker 持仓与回报收尾留出缓冲，又比原来多 3 分钟时间。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py`
- 修改 launchd：
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.day-close-readonly.plist`
  - `/Users/bytedance/Library/LaunchAgents/local.qmt-roll.official-live.15w.day-close-readonly.plist`
- 修改 skill：
  - `skills/futures-live-automation-startup/SKILL.md`
- 删除脚本：无。
- 新增参数：无。
- 修改参数/时序：
  - `local.qmt-roll.official-live.15w.day-close-readonly` 从 `15:08` 改为 `15:05`。
  - Stage934 健康检查新增 repo/installed `StartCalendarInterval` 对比，避免只比对 ProgramArguments 而漏掉触发时间漂移。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不涉及回测。
- 账户规模：当前实盘口径 `150000`。
- 成本口径：不涉及。
- 样本过滤：不涉及。
- 策略/归因口径：只改只读快照调度时间和健康检查，不改 Stage901 信号、AI池、手数、止损、Stage260/902/927/931 下单闸门。

## 结果

- 期末权益：不涉及。
- 总收益：不涉及。
- 最大回撤：不涉及。
- Sharpe：不涉及。
- 总滑点：不涉及。
- 总交易次数：不涉及。
- 胜率：不涉及。
- 其他关键指标：
  - `plutil -lint` 通过。
  - `py_compile` 通过。
  - `git diff --check` 通过。
  - 已复制 repo plist 到 `/Users/bytedance/Library/LaunchAgents/` 并 `bootout/bootstrap/enable`。
  - `launchctl print` 显示 `StartCalendarInterval Hour=15 Minute=5`。
  - Stage934 健康检查通过：`health_status=healthy_stage930_live_real_daemon_running_submit_blocked`，`blockers=[]`，`warnings=[]`。
  - Stage934 已确认 day-close readonly repo/installed 触发时间均为 `15:05` 且 match。
  - 订单 API 调用 `0`。

## 输出文件

- Stage934 latest summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage934_official_live_automation_health_check_latest_summary.json`
- launchd repo plist：`examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.day-close-readonly.plist`
- installed plist：`/Users/bytedance/Library/LaunchAgents/local.qmt-roll.official-live.15w.day-close-readonly.plist`

## 结论

- 本阶段结论：不建议把唯一 day-close readonly 改成 `15:01`；当前已改为 `15:05`。这个时点比 `15:08` 更早，但仍保留收盘后 5 分钟缓冲，减少 CTP/broker 侧未完成回调或快照不稳定的概率。
- 是否进入下一步：进入观察。
- 下一步：下一次完整交易日观察 15:05 Stage907 是否能拿到账户/持仓/合约快照，以及 16:35 邮件是否用该快照提前显示 broker/shadow 对账。若 15:05 仍稳定失败，再考虑 15:08 或增加“失败不覆盖已有可用快照”后做多时点重试。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只调整只读快照调度时间和健康检查字段，不使用收益、品种、方向或信号结果反向改策略。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：提前对账可以减少 20:55 前的排障压力，但必须保持只读、单次、fail-closed，避免过早失败覆盖成功快照或污染真实提交闸门。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
