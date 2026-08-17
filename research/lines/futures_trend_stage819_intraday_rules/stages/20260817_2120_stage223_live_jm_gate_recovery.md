# Stage223 jm 夜盘实盘闸门恢复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：日盘；直接生产 checkout 修复，激活前禁止报单/撤单 API
- 记录时间：2026-08-17 21:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_production_live` / detached HEAD
- 生产基线提交：`9c0df9d86d4851cd78843334f274b7c28d73f899`
- 当前候选提交：`2080797da311d230451ae652003789d5a866fd1d`
- 阶段性质：生产执行闸门兼容修复，不修改 alpha
- 是否重要突破：否；修复两项已复现的生产阻断
- 是否触发A/B：否；不属于新策略、仓位或参数优化

## 外部调研与判断

- 参考资料：Python 官方 `datetime.fromisoformat()` 文档，Python 3.11 可解析带 `T`、微秒和时区偏移的 ISO-8601 时间：
  - https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
- 我的判断：Stage174 输出合法 ISO-8601 时间，Stage260 不应继续只识别旧格式；行情闸门应绑定 durable spool 当前候选合约，不应让非候选品种的闭市 tick 状态阻断行情新鲜的 jm。全局诊断信息继续保留，不伪造 AP/SI 行情。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`：兼容 ISO-8601 时间并统一 aware/naive datetime 后计算快照年龄。
  - `run_qmt_roll_stage930_official_live_c9_session_daemon.py`：新开仓行情阻断改为检查 transport 和 durable spool 当前候选 `vt_symbol`；非候选 AP/SI 缺 tick 不再阻断 jm。
  - `tests/test_stage179_stage260_execution_profile.py`：新增生产 ISO 时间回归。
  - `tests/test_stage930_fast_lane.py`：新增候选 jm、候选 SI、transport 未就绪三类回归。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 价格逻辑：不改 Stage931 二次询价；真实 API 调用前仍重新取候选合约最新买卖盘，受既有滑点 tick、涨跌停、最小变动价位和新鲜度限制。

## 回测/归因参数

- 数据区间：不适用；本阶段未运行回测。
- 账户规模：官方 C9/15w，未改变资金口径。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：只修生产执行闸门，不改变 AI 池、选品、方向、手数、0.5R 止损或一次重试。

## 结果

- 期末权益：不适用；未运行回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - ISO 时间回归旧代码：`1 FAIL`，实际 `snapshot_age_seconds=None`，与生产故障一致。
  - ISO 最小实现后：Stage260 `11/11 passed`。
  - 候选行情闸门新用例旧代码：`3/3 FAIL`，分别复现无关品种误伤、候选自身阻断消息和 transport 阻断。
  - 最小实现后：Stage930/持久授权 `91/91 passed`。
  - Stage260/930/931/945/948 联合回归：`251/251 passed`，耗时 `35.762s`。
  - 订单 API：实现和测试阶段 `send_order=0`、`cancel_order=0`；未连接真实 CTP、未生成 jm 委托。

## 输出文件

- design：`docs/superpowers/specs/2026-08-17-jm-live-gate-recovery-design.md`
- plan：`docs/superpowers/plans/2026-08-17-jm-live-gate-recovery.md`
- report：本阶段记录文件。
- summary：待 Stage948 qualification/activation 后生成。
- orders：当前无 jm 委托。
- daily：不适用。
- quality：`251/251 passed`；生产激活和券商对账仍待完成。

## 结论

- 本阶段结论：两个代码级根因均已由 TDD 复现并修复，相关执行、最终询价、launcher 和 installer 回归通过；源码候选尚未等同于生产已激活。
- 是否进入下一步：是；先审查候选，再按 Stage948 做资格和原子激活。
- 下一步：只读核对 7 个 launchd job、daemon/warm executor、账户持仓、活跃委托和成交；若现有生产进程仍存活，未取得明确重启权限前不得并行启动新执行器。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：改动由生产格式合同和精确候选身份驱动，没有按历史收益、单一行情价格、品种盈利或策略阈值调参；候选级闸门适用于任意合约。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：两个缺陷已经在真实夜盘阻断合法 jm 意图，且修复保持了 stale snapshot、候选 stale tick、transport、授权和最终价格 fail-closed。

## 合入建议

- 是否更新本线 `LINE.md`：否；先等待正式资格和激活证据。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；候选尚未正式激活和完成券商对账。
