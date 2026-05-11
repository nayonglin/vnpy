# Stage246 SimNow 账户快照根因收敛

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 15:52 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：运行时调试与根因收敛
- 是否重要突破：是，从“静默无快照”收敛到“wrapper 覆盖前置 + SimNow 首次改密阻塞”
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 调试目标

- 解释为什么 `Stage174/SimNow` readonly probe 一直拿不到 `account/position` 快照。

## 证据链

### pre-fix

- 现象：
  - probe summary 只有 `connected_or_attempted_readonly`
  - log CSV 只有 `连接登录 -> CTP`
- 插桩证据：
  - 即使外部传入 `SIMNOW_FRONT=trading`，debug log 里仍显示：
    - `td_address=tcp://182.254.243.31:40001`
    - `md_address=tcp://182.254.243.31:40011`
- 结论：
  - 实际并没有打到 `trading` 前置，而是被 wrapper 覆盖回了 `7x24`

### post-fix

- 本地修复：
  - `run_ctp_stage177_simnow_readonly_probe.sh` 先保存调用方传入的 `SIMNOW_FRONT/CTP_TD_ADDRESS/CTP_MD_ADDRESS`，在 `source ctp_simnow.local.env` 后再恢复。
- 修复后证据：
  - debug log 已显示：
    - `td_address=tcp://182.254.243.31:30001`
    - `md_address=tcp://182.254.243.31:30011`
  - 某次完整复现中，`CTP` 明确返回：
    - `交易服务器连接成功`
    - `行情服务器连接成功`
    - `交易服务器授权验证成功`
    - `行情服务器登录成功`
    - `交易服务器登录失败，代码：140，信息：首次登录必须修改密码`

## 根因判断

- 本地根因：`Stage177` wrapper 环境变量优先级错误，导致前置切换失效。
- 外部阻塞：真正打到 `trading` 前置后，SimNow 账号因“首次登录必须修改密码”被柜台拒绝。
- 因此：
  - 拿不到 `account/position` 快照的直接原因不是 probe 没订阅事件
  - 而是从未真正打到目标前置，且在打到正确前置后又被账号状态阻塞

## 本次本地收敛

- 新增运行时调试会话文件：
  - `debug-simnow-snapshot-probe.md`
- 保留插桩：
  - `run_ctp_stage174_readonly_probe.py`
- 本地修复：
  - `run_ctp_stage177_simnow_readonly_probe.sh`
- probe summary 增强：
  - 新增 `connection_target`
  - 新增 `log_analysis`
  - 可将模糊状态细分为：
    - `readonly_trading_login_failed`
    - `readonly_connected_no_login_outcome`
    - `readonly_logs_without_ctp_progress`
    - `readonly_snapshots_received`

## 结论

- 当前 Phase B 和 SimNow 接线的主要瓶颈，已经从“本地不明问题”收敛成“外部账号状态问题”。
- 在完成 SimNow 首次改密前，不应继续投入到 submit 链路。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段是运行时调试和执行链路修复，不涉及策略收益优化。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：根因已收敛，后续工作不再盲查。

## 下一步建议

1. 先在 SimNow 侧完成首次改密。
2. 改密后重跑 `Stage177/174` readonly probe。
3. 若此时仍无快照，再继续排查 query 回调与账户查询时序。
