# futures_trend - 期货趋势策略

## 定位

- 资产：商品期货。
- 策略类型：趋势/组合选择/资金约束。
- 正式基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`。
- 重要隔离：这是趋势线，不能被震荡策略研究直接修改。

## 当前状态

- Stage78-1是默认正式基准，当前口径为50万本金、关闭100万sizing封顶：
  - 期末权益`25,542,885`
  - 总收益`5008.5770%`
  - 最大回撤`-40.0607%`
  - Sharpe`1.1295`
  - 总滑点`1,968,150`
  - 交易`880`
  - 胜率待专项复跑确认
- Stage225已完成`78-1` AI选品开/关消融：
  - AI ON主回测期末权益`25,542,885`，总收益`5008.5770%`，最大回撤`-40.0607%`，Sharpe`1.1295`
  - AI OFF主回测期末权益`7,588,545`，总收益`1417.7090%`，最大回撤`-46.6939%`，Sharpe`0.7214`
  - AI ON在11个多周期窗口收益全部优于AI OFF，确认AI选品是`78-1`正式基准的有效组成
  - Monte Carlo显示AI降低亏损概率和回撤概率，但trade-block路径风险仍高，不能替代资金暴露治理
- Stage111是40万部署候选，不替代Stage78纯alpha基准：
  - 期末权益`2,766,945`
  - 总收益`591.7363%`
  - 最大回撤`-21.6475%`
  - Sharpe`1.4757`

## 继续方向

- Stage78-1准实盘复盘，默认使用50万本金、无sizing封顶口径。
- 执行、滑点、成交稳定性。
- AI品种池切换稳定性。
- Stage240 已明确最小可上线真实执行架构：
  - `Signal Scheduler -> Deployment Gate -> Broker Adapter/Executor -> Reconcile Worker -> Supervisor`
  - 推荐先做 `Phase A 只读常驻` 和 `Phase B 半自动执行`
  - 不允许把回测/影子盘脚本直接改成真实发单脚本
- Stage241 已明确 `Phase B` 半自动执行流程：
  - `自动生成信号 + 自动生成委托草案 + 人工 approve/reject + 系统执行 + 系统对账`
  - Phase B 不是人工去柜台手敲单，而是“人工放行，系统执行”
- Stage242/243 已落地 `Phase B` 原型：
  - 新增 `build_qmt_roll_stage242_phaseb_order_draft.py`
  - 新增 `run_qmt_roll_stage243_phaseb_approval.py`
  - 已用 `2026-04-30` 样例信号把状态从 `pending_manual_approval` 跑到 `approved_waiting_precheck`
  - 当前仍未接真实 submit，下一步应先做 `pre-submit broker-state check`
- Stage244 已落地 `pre-submit broker-state check`：
  - 新增 `run_qmt_roll_stage244_phaseb_pre_submit_check.py`
  - 已对 `PHASEB-20260430-001` 执行提交前校验
  - 结果为 `failed / can_submit=0 / broker_account_snapshot_missing`
  - 说明当前系统具备 `fail-closed` 能力，但还不能接真实 `submit_order()`
- Stage245 已补齐 `Phase B` 两道附加安全校验：
  - 新增 `run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py`
  - `same-intent duplicate order check` 已通过
  - `target position already reached check` 因真实持仓快照缺失暂为 `not_checked`
  - 当前最终阻断原因仍为 `broker_account_snapshot_missing`
- Stage246 已收敛 SimNow 快照根因：
  - 新增 `debug-simnow-snapshot-probe.md` 调试会话
  - `run_ctp_stage177_simnow_readonly_probe.sh` 已修复外部 `SIMNOW_FRONT/CTP_TD_ADDRESS/CTP_MD_ADDRESS` 被本地 env 覆盖的问题
  - `run_ctp_stage174_readonly_probe.py` 已增强 `connection_target + log_analysis` 输出
  - 当前外部阻塞已明确为：`交易服务器登录失败 code 140：首次登录必须修改密码`
- 月度AI品种池SOP：`research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md`。
- Stage111/旧30万有封顶版本只作为历史对照，不替代当前Stage78-1正式口径。

## 禁止事项

- 不用震荡策略结果直接改第78。
- 不继续利润回吐保护、恢复阈值、弱窗口补丁等已证伪方向。
- 不在接近80%保证金红线附近做小数级资金参数优化。
