# Stage115 Stage929 单产品cap命名澄清

## 基本信息

- 时间：2026-06-22 20:27 CST
- 研究线：futures_trend_stage819_intraday_rules
- 阶段性质：实盘报告文案修正，不改变策略逻辑，不连接 CTP，不调用下单
- 当前实盘版本：official_live_stage847_c9_15w_stage819_05r_stop_retry_once

## 本次结论

用户确认当前实盘继续沿用单产品 25% 保证金上限口径，不切换到黑色/能化等行业集群 cap。

rb2610.SHFE 在当前实盘风控映射中归到 rb.SHFE，因此这层 cap 对 rb 来说就是单产品保证金上限。

## 改动内容

- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py` 的邮件和本地报告展示标签：
  - `品种/集群` 改为 `单产品`
  - `品种/集群cap` 改为 `单产品保证金上限`
  - `品种/集群cap金额` 改为 `单产品上限金额`
  - `品种/集群上限手数` 改为 `单产品上限手数`
  - `品种/集群前手数` 改为 `单产品限制前手数`
  - `品种/集群后手数` 改为 `单产品限制后手数`
- 修改邮件字段说明，明确“单产品保证金上限是当前实盘采用的产品级 cap，例如 rb2610 归到 rb.SHFE；这不是黑色、能化等行业集群 cap”。
- 内部 `risk_cluster_*` 字段不重命名，保持策略通用风控模块和 CSV 兼容。

## 参数变化

- 新增参数：无
- 修改参数：无
- 删除参数：无
- 风控逻辑变化：无
- 下单闸门变化：无

## 验证结果

- `py_compile` 检查 Stage929：通过。
- `git diff --check` 检查空白问题：通过。
- 20:29 Stage929 dry-run 邮件：通过，`wrapper_exit_code=0`，`order_api_called_count=0`。
- dry-run `.eml` 解码检查：
  - `contains_品种集群=False`
  - `contains_单产品保证金上限=True`
  - `contains_行业集群cap说明=True`
- 邮件正文已显示：
  - `单产品：rb.SHFE`
  - `单产品保证金上限：25%`
  - `单产品上限金额：37,500`
  - `单产品上限手数：11`
  - `单产品限制前手数：33`
  - `单产品限制后手数：11`

## 反过拟合判断

否。本阶段只修正文案，保持既有单产品 25% 风控口径，不根据 rb 当前信号调整参数、品种或集群。

## 继续价值判断

有价值。邮件是实盘执行前的人读界面，把“单产品 cap”和“行业集群 cap”区分清楚，可以避免误判 rb 11 手的缩手原因。
