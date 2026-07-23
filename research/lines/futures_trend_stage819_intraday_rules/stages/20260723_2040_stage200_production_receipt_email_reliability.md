# Stage200 production receipt/email 可靠性修复与离线验证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-07-23 21:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_production_live` / `codex/stage200-production-reliability-repair`
- 阶段性质：production-live 控制面可靠性修复；不改策略 alpha、价格、手数或 CTP 下单路径
- 是否重要突破：否（不是策略突破；是进入 production qualification 前的可靠性候选）
- 是否触发A/B：否；没有新增或修改策略参数

## 外部调研与判断

- 参考资料：
  - VeighNa 官方仓库 README：<https://github.com/vnpy/vnpy/blob/master/README.md>
  - VeighNa 官方 `EventEngine`：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>
  - VeighNa 官方 `BaseGateway`：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>
- 调研结论：官方结构把事件分发、gateway 报单接口和应用启动边界分开；本次缺信号邮件发生在 Stage945/947 向下游 `execve` 交接前，因此兜底通知应留在 production launcher 控制面，不能塞进 `EventEngine`、CTP gateway 或策略价格/手数计算链。
- 我的判断：本次修复方向正确。它解决的是“首日 shadow 统计退化、resolver 启动过重、控制/数据根混用、下游邮件尚未接管时静默失败”四个根因，不是用重试掩盖症状，也没有扩大交易权限。

## 本次变更

- 基线提交：`e3ecda6991440354ff86f50dcb127276a0c2903b`
- 当前代码提交：`4e484c27205d73dc55c862a701b89a549e826624`
- 当前未提交修正：Stage945 低磁盘测试把时变的“当前可用空间 + 1”改成确定性 `sys.maxsize`；将在本记录提交中一并冻结。
- 阶段提交：
  - `a993596af20b5f582a7c66b28fd771cf852f74bc`：Stage200 设计。
  - `9501bf58d0d418bb78bc11042c7f9b8bc884e8e8`：只读资格边界澄清。
  - `15b4fee7330ad0fa9e4d7fc3df47cd097a607301`：实施计划。
  - `f40e54f95a9f76027d8f3965dcd67ad7b4618a4c`：首日 Sharpe 有限值与 strict JSON 修复。
  - `0b1ba04c4e93b9bc85343e1a22d4b1c2398fe3b4`：轻量 live context。
  - `0e6d15f12338e953bcdd0bae743476c0a174bd32`：Stage922 标准库 resolver。
  - `26030f02f8147cb21f1a32cd0674ee2d6c05a15b`：Stage935 control/data 根隔离。
  - `141e815d9e2fa130d73575b483ff6034d0a4e9ab`：带 flock、原子状态与冷却的安全失败通知器。
  - `e3e283cd3ae11d6364b1ae765f16561a430040a6`：Stage945/947 交接前失败归属与通知。
  - `4e484c27205d73dc55c862a701b89a549e826624`：production release/qualification 文件覆盖。
- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py`
  - `examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py`
- 修改脚本：
  - `analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py`：单样本/非有限标准差返回 Sharpe `0.0`，保证首日报告可 strict JSON 持久化。
  - `qmt_roll_official_live_config.py`：复用轻量上下文的官方身份与路径常量。
  - `qmt_roll_official_live_email_notify.py`：异常审计只保留异常类型，不写原始异常文本。
  - `run_qmt_roll_stage922_official_live_target_date_resolver.py`：移除 pandas/回测/Stage173 重依赖，改为标准库纯解析。
  - `run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`：控制输出与正式数据资产根分离。
  - `run_qmt_roll_stage945_official_live_production_session_launcher.py`：仅规范 launchd owner 在 `execve` 前失败时发送一次兜底；成功/预期跳过/手工运行不发。
  - `run_qmt_roll_stage947_official_live_production_support_launcher.py`：适配 resolver typed error，识别 Stage935 邮件归属，月更后 receipt 刷新失败使用独立边界。
  - `build_qmt_roll_stage179_release_manifest.py`：把 Stage650、轻量上下文、邮件/失败通知器及其测试纳入 immutable release 和 trusted suite。
- 删除脚本：无。
- 新增策略参数：无。
- 修改策略参数：无。
- 删除策略参数：无。
- 新增控制面常量：失败指纹、允许任务/边界、30 分钟冷却、终态/邮件状态集合；均不参与交易决策。

## 回测/归因参数

- 数据区间：不适用；未运行回测。
- 账户规模：C9/15万身份只作 production profile 校验；本阶段未连接账户。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：只修控制面与单样本统计退化语义；没有重算或调整 alpha。

## 结果

- 期末权益：不适用（未运行回测）
- 总收益：不适用（未运行回测）
- 最大回撤：不适用（未运行回测）
- Sharpe：不适用（未运行回测）
- 总滑点：不适用（未运行回测）
- 总交易次数：不适用（未运行回测）
- 胜率：不适用（未运行回测）
- 离线基线：变更前全仓 `1461 passed / 6 failed / 4 warnings / 799 subtests`；6 个失败为 Alpha101 缺 `cast_to_int` 四项、worktree 目录名硬编码一项、隔离 worktree 缺历史 research CSV 一项。
- 聚焦 production 回归：`154 passed / 71 subtests`。
- Stage945/947 完整 launcher 回归：`46 passed / 30 subtests`。
- release manifest 回归：`33 passed / 25 subtests`。
- 显式并发回归：`5 passed / 8 deselected / 4 subtests`；既有 lease/CAS 和新增 notifier fork 均执行 100 轮，发送赢家各自唯一。
- 最终全仓离线：`1495 passed / 6 failed / 4 warnings / 821 subtests`，失败集合与变更前完全相同，无 Stage200 新失败。
- 测试稳定性修正：第一次最终全仓额外出现一次 `test_low_disk_blocks_before_exec` 偶发失败；根因为测试两次读取磁盘空间之间有后台文件释放。改用确定性极大阈值后单测通过，第二次全仓不再复现。
- Stage922 冷启动观察：新临时 control/signal 根、fresh `python -S` 子进程，exit `0`，wall `0.124269s`，禁载重模块集合 `[]`；control、signal、正式 data 根均符合预期。该时间只作观察，不新增 timing gate。
- 静态检查：8 个 Python 文件 `py_compile` 通过；Stage930 supervisor `bash -n` 通过；7 个 production plist `plutil -lint` 全部 `OK`；`git diff --check` 通过；8 个运行时关键文件全部由 Git 跟踪。
- 安全边界：没有连接 CTP，没有读取/打印实盘密码，没有真实 SMTP 发送，没有调用 `launchctl`，没有 send/cancel/order API 调用。

## 输出文件

- report：本记录。
- summary：无新增生产 summary；验证输出仅在测试 stdout 和临时目录。
- orders：无。
- daily：无。
- quality：正式 production qualification bundle 尚未生成。

## 结论

- 本阶段结论：Stage200 离线实现候选已完成。首日 shadow 不再因 NaN Sharpe 无法持久化；Stage922 启动依赖闭包收窄；Stage935 不再把正式数据资产误指向 control 根；Stage945/947 在下游邮件接管前可由唯一 launchd owner 做一次安全兜底，并抑制重复/手工/health 通知。
- 是否进入下一步：是；进入独立全面 review。
- 下一步：独立 reviewer 覆盖 Spec、并发原子性、秘密脱敏、resolver 等价、邮件归属和 release coverage；修完 P0/P1 后冻结 exact commit，再做 production qualification、合入 master、激活和 operational readback。
- 当前边界：独立 review、正式 production qualification、master fast-forward、production activation、CTP 只读资格和运行读回在本提交上都尚未执行；本阶段不能声明新代码已在线上生效。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；只修控制面与单样本统计退化语义。
- 原因：没有扫策略参数、日期、品种、方向或 R 倍数；Sharpe `0.0` 是单样本无可估波动的确定语义，其他改动均为执行边界、路径、并发和可观测性。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是；进入独立 review 与 production qualification，不继续扩展 alpha。
- 原因：本轮已把今天“邮件静默”和首日 receipt 失败的根因变成可重复测试，且没有扩大真实报单能力；剩余价值在独立证伪和正式部署读回，而不是继续堆离线规则。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；待独立 review 与最终部署事实完成后统一更新。
- 是否更新 `research/registry.md`：暂不更新；尚未形成新的线上稳定事实。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；待 Stage200 完成 review、qualification、激活和读回后再作为正式里程碑摘要。
