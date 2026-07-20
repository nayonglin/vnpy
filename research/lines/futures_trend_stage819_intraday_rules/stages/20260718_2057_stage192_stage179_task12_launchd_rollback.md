# Stage192 Stage179 Task12 LaunchAgent 隔离、进程组回收与回滚闸门

## 基本信息

- 改动时间：2026-07-18 20:57 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`61dd1e603`
- 代码提交：`789a62c9e53bd4e514c425540f14dfe738763594`
- 是否重要突破版本：否。Task12 关闭了部署所有权、supervisor 退出和 V1/V2 回滚分级缺口，但尚未完成 Task13 全故障矩阵、60 秒性能门、真实只读 CTP 或 SimNow，因此只具备 P0 候选条件，不具备实盘激活条件。
- 实盘边界：未安装、加载或启动任何 LaunchAgent；未加载真实 env，未连接 CTP/SimNow，未调用真实报单或撤单 API；全部验证为离线 `send=0/cancel=0`。

## 外部调研与判断

执行前复核：

- Python 3.11 `subprocess` 的 `start_new_session`/process group 语义：<https://docs.python.org/3/library/subprocess.html>
- Python 3.11 `os.setsid`、`os.killpg`：<https://docs.python.org/3/library/os.html>
- macOS 本机 `launchd.plist(5)`/`launchctl(1)` 对 `AbandonProcessGroup` 与 `ExitTimeOut` 的生命周期语义。

判断结论：首次生产发布继续由 launchd 直接拥有 Stage930 Python 进程，不能让未完成 canary 的 shell supervisor 替换生产 owner。候选 supervisor 必须让 daemon PID 等于 PGID，TERM/INT 作用于负 PGID，有限等待后升级 KILL；只杀父 PID 无法覆盖忽略 TERM 的孙进程。no-submit canary 必须有独立 label、输出根、Stage179 runtime/state/spool/ledger/readiness 和日志，且 P0 不安装、不自动调度。

## 本次改动

### 新增

- 新增 direct `production-readonly` 与 supervisor `offline` 两份 no-submit canary plist；均无 `RunAtLoad`/日历调度、无 `live-real`、无激活确认，且使用相互独立的输出/runtime/log 根。
- 新增 `run_qmt_roll_stage930_supervisor_child.py`，在 exec daemon 前调用 `setsid()`，形成 `PID == PGID` 的可验证进程组身份。
- 新增 supervisor cooperative TERM 与忽略 TERM 子孙进程测试；后者必须触发 TERM 超时、整组 KILL、无重启。
- 新增只读 `build_qmt_roll_stage179_rollback_guard.py`：无 V2、仅 V2 reservation/safe-terminal、已有 API slot/send/cancel/fill/unknown 三类分别输出允许 V1 回滚、要求 broker 快照且保留 V2 reader、禁止回退并对账 roll-forward。
- 新增 `OFFICIAL_LIVE_OUTPUT_DIR` import-time 覆盖，用于 canary 隔离 Stage930/608/904/905 等官方 artifact；默认路径完全不变。

### 修改

- day/night 生产 plist 恢复 `.py311/bin/python + Stage930 daemon` 直接所有权，保留 `AbandonProcessGroup=false`，新增 `ExitTimeOut=15`，移除 supervisor 专用 env；没有加入 warm 或 Stage179 激活参数。
- Stage930 新增 `legacy-once|warm` 选择，默认仍为 `legacy-once`；warm 模式只创建一个 Stage931 child，按 readiness 检查并通过 Unix socket 唤醒，shutdown 先撤销 executor readiness 再进入统一 TERM/KILL。
- Stage931 支持显式 Stage179 runtime root；production-live 仍受 manifest、receipt、激活确认、CTP 与资金/版本口径门禁约束。
- supervisor 默认 TERM 5 秒、KILL wait 5 秒；spawn gap、restart delay 和 TERM/INT 全部失败关闭，未知 PGID identity 不得重启。

### 删除

- 删除生产 day/night plist 对 shell supervisor 的依赖。
- 删除生产 plist 的 supervisor restart env。
- 未删除或修改任何 alpha、AI 池、止损、重进场、选品、资金或仓位参数。

## 参数变化

- 新增 Stage930 参数：`--stage179-execution-mode`、`--runtime-profile`、`--release-manifest`、`--activation-receipt`、`--stage179-runtime-root`、`--confirm-stage179-activation`。
- 新增 supervisor env：`STAGE930_SUPERVISOR_CHILD_HELPER`、`STAGE930_SUPERVISOR_TERM_TIMEOUT_SECONDS`、`STAGE930_SUPERVISOR_KILL_WAIT_SECONDS`。
- 新增 canary-only env：`OFFICIAL_LIVE_OUTPUT_DIR`。
- 修改参数：生产 plist 新增 `ExitTimeOut=15`；生产 daemon 原交易参数不变。
- 删除参数：生产 plist 移除 supervisor restart env；策略参数无删除。

## 验证结果

- Task12 生命周期/manifest/Stage930 联合回归：`56/56`，耗时 `19.701s`；复验 `56/56`，耗时 `19.608s`。
- 忽略 TERM 的 child/grandchild：`PID == PGID`，TERM 超时后整组 KILL，supervisor 退出 `143`，启动次数 `1`，无重启。
- cooperative child：TERM 内退出，不升级 KILL，supervisor 退出 `143`，无重启。
- `plutil -lint`：8 份 launchd plist 全部通过。
- `bash -n`：通过。
- `py_compile`：通过。
- 新增文件 `ruff check`：通过；扩大文件集只报告 Stage930/test 既有 B010/E402/UP012/UP031，不是本阶段新增。
- `git diff --check`：通过。
- 订单 API：send `0`、cancel `0`。

## 回测结果

本阶段没有改变策略 alpha，也没有运行回测；以下指标均为不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

## 反思与后续

- 开始前是否过拟合：否。目标是进程所有权、超时回收、状态目录隔离和副作用回滚分级，不使用任何单品种/单晚收益样本。
- 完成后是否过拟合：否。生命周期与 rollback 分类只依赖进程组和 ledger 副作用证据，适用于全部品种和订单类型。
- 是否仍值得继续：是。Task12 使代码部署和激活解耦，但没有 60 秒负载与全故障矩阵就无法证明今晚 21:00 延迟路径在负载下仍满足 SLA。
- 下一步：执行 Task13 全故障矩阵、20 合约/2000 tick/s/60 秒性能门、不可变 manifest、扩大回归和独立终审。
- 硬门禁：Stage372/20万与 Stage847-C9/15万口径冲突未澄清；P1 真实只读 CTP、P2 SimNow/券商测试、P3 一手生产 canary 均未执行。代码可合入与实盘激活必须继续分开表述。
- 记录隔离：本工作区只新增唯一 Stage192 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
