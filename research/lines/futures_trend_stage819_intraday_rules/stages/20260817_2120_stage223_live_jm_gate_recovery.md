# Stage223 jm 夜盘实盘闸门恢复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：日盘；直接生产 checkout 修复，激活前禁止报单/撤单 API
- 记录时间：2026-08-17 21:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_production_live` / detached HEAD
- 生产基线提交：`9c0df9d86d4851cd78843334f274b7c28d73f899`
- 当前候选提交：`5354e85e834c713d80f700fea24e64413eb47287`
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
  - `qmt_roll_official_live_submit_authorization.py`：授权凭证允许记录并验证唯一候选合约行情水位，同时保留全局行情未全部就绪的原始状态。
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：授权接纳和 leased intent 复验新增 `vt_symbol` 精确身份绑定。
  - `tests/test_stage179_stage260_execution_profile.py`：新增生产 ISO 时间、未来时间、超 TTL 和非法时间回归。
  - `tests/test_stage179_submit_authorization.py`：新增候选行情证据完整/不完整回归。
  - `tests/test_stage930_fast_lane.py`：新增候选 jm、候选 SI、transport 未就绪、精确水位选择和端到端 warm authorization 回归。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 价格逻辑：不改 Stage931 二次询价；真实 API 调用前仍重新取候选合约最新买卖盘，受既有滑点 tick、涨跌停、最小变动价位和新鲜度限制。
- 激活后补充修复：Stage902 对带时区 ISO 只读快照执行 naive-aware datetime 相减，触发 `TypeError`；现与 Stage260 一致按输入时区生成当前时间后计算 age，future/invalid 继续 fail-closed。

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
  - 首轮独立审查发现 `P1`：最终提交闸门虽已候选化，但 warm authorization 仍使用全品种行情总闸门；已用端到端失败测试复现并修复。
  - 二次独立审查发现 `P1`：授权意图与候选行情证据未交叉绑定 `vt_symbol`，错误品种证据可通过内部校验；已升级授权 schema v5，并新增错误品种和禁止精确通道回退全局就绪的负测。
  - Stage260/submit-authorization/930/persistent-authorization 回归：`127/127 passed`，耗时 `17.483s`。
  - Stage260/submit-authorization/930/931/945/948 联合回归：`276/276 passed`，耗时 `38.189s`。
  - 最终扩展联合回归（含授权 guard 与 executor serve）：`331/331 passed`，耗时 `35.685s`；`py_compile` 与 `git diff --check` 通过。
  - 首次 Stage948 激活成功后，Stage260 为 `3 executable / 0 blocked`，但 Stage902 复现 `TypeError: can't subtract offset-naive and offset-aware datetimes`，因此零报单退出；新增回归旧代码 `1 ERROR`，修复后相关模块 `118/118 passed`。
  - Stage902 增量独立审查发现 `P1`：未来时间戳得到负 age 后仍满足旧的 `age<=TTL`；新增实际 gate 的双边界测试并改为 `0<=age<=TTL`，相关模块 `119/119 passed`。
  - 订单 API：实现和测试阶段 `send_order=0`、`cancel_order=0`；未连接真实 CTP、未生成 jm 委托。

## 输出文件

- design：`docs/superpowers/specs/2026-08-17-jm-live-gate-recovery-design.md`
- plan：`docs/superpowers/plans/2026-08-17-jm-live-gate-recovery.md`
- report：本阶段记录文件。
- summary：待 Stage948 qualification/activation 后生成。
- orders：当前无 jm 委托。
- daily：不适用。
- quality：Stage902 补充修复后相关模块 `119/119 passed`；新候选仍需独立复审、完整 qualification、Stage948 再激活和券商对账。

## 结论

- 本阶段结论：两个原始代码级根因、两轮授权链 P1 及首次激活暴露的 Stage902 ISO 时区缺陷均已由 TDD 复现并修复；Stage902 补充候选尚未重新完成 qualification/激活。
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

## 2026-08-17 22:36 补充：Stage902 动态生产授权接线

- `bf6f7223e` 候选的正式 qualification 已完成：生产要求测试 `826/826 passed`；两次正式 CTP 只读 capture 的账户/持仓/委托/成交查询均完整，`send_order=0`、`cancel_order=0`、`order_api=0`。
- Stage948 prepare/activate 已成功加载精确 7 个生产 label，冲突 label `0`、回滚 `0`、激活阶段订单 API `0`；随后 post-close 正式 job 重建了绑定新 commit/manifest 的 `2026-08-17` 数据凭据。
- 新夜盘首轮运行中，Stage902 的 ISO 时区异常已消失，Stage930 连续两轮无 cycle error，Stage260 为 `3 executable / 0 blocked`，jm tick 新鲜；但 Stage902 仍被静态 `execution_policy.real_submit_default=fail_closed` 阻断，说明原先的显式生产 env 与确认文本未接入该静态策略检查。
- 独立审查要求保留静态 policy 与运行时 env/确认文本两把独立钥匙；因此正式 C9/15w profile 的静态 policy 改为 `explicit_live_real_enabled`，Stage902 原有 env、精确确认、session daemon、adapter、risk、readonly 等独立门禁均不删除。
- Stage906 被复现出与 Stage902 相同的 aware/naive `TypeError`，并且未来时间负 age 会误过 TTL；现统一按输入时区计算 age，实际 gate 改为 `0 <= age <= TTL`，覆盖 legacy/naive/aware/future/invalid/边界。
- Stage927 不再依赖 production output 中自由漂移的 Stage912/913/916/921/926 JSON；Stage945→Stage930→Stage927 显式传递 release manifest、qualification、activation receipt，Stage927 复用正式 validator 验证 source-commit/tree/manifest/receipt 绑定。Stage903、Stage906、Stage923/924、实时 controller heartbeat、broker/tick/order 证据仍逐轮必需；Stage932 继续只作 warning，未运行真实 submit-cancel。
- 曾启动旧 Stage912 runner，但独立审查指出它会扰动 production output 后已立即中止；kill switch 恢复为不存在，所有子进程归零，未连接 CTP、未调用订单 API。后续不再用漂移 JSON 补门禁。
- 当前仍未报单；夜盘已受控停止，等待完整联合测试、独立复审、重新 qualification 与 Stage948 激活。
- 过拟合判断：否；只修生产授权状态机的不可达分支，不改变 alpha、AI 池、合约、方向、手数、0.5R 或重试规则。
- 继续价值判断：是；若不闭环该接线和 Stage927 证据，即使真实候选与行情均有效也会被永久 fail-closed。

## 2026-08-17 23:18 补充：Stage927 v2 消费边界与本轮重验

- 独立复审发现两个 P1：Stage930 只读取 Stage927 顶层 permit，未验证 schema v2、`scope_evidence_digest` 与三类 capability；Stage927 本轮失败或超时时还可能读取同目标旧 summary，重验期间 persistent fast lane 也可能继续用旧授权。
- Stage930 现对 reduce-close、retry-open、initial-open 三条 lane 统一要求 schema v2、内部 schema v2、完整 capability、digest 正确、capability 的 `permit_field` 精确、三个顶层 permit 与 digest 内 `permitted` 全部一致；旧 schema、极简 permit、任一篡改均 fail-closed。
- 每次 Stage927 重验前先撤销 Stage931 提交授权；若锁内存在 in-flight 而不能撤销，则不启动 Stage927 并直接阻断。本轮 Stage927 的 exit code、timeout、summary 文件 mtime、model、target、freshness、schema 与 digest 均需通过，失败时内存 summary 置空，不再复用旧文件。
- Stage927 重验期间 fast lane 保持行情与持久 detector 监控，但 legacy 和 persistent 两条路径均禁止发布或唤醒提交授权。
- production-live 的 qualification evidence 与 Stage179 runtime root 改为 Stage930 启动前必填；缺参时不启动 warm Stage931，不连接 CTP。
- TDD 红灯：新增 5 个定向测试初始为 `3 FAIL + 2 ERROR`；实现后定向测试通过。Stage930 单文件 `97/97 passed`，四模块联合 `146/146 passed`。扩展 338 项首次仅 3 个旧测试 fixture 因仍使用 schema v1 被正确拒绝；fixture 升级为真实 v2 digest-bound evidence 后 `338/338 passed`，耗时 `45.895s`。
- 订单 API：本轮仅代码与单元测试，`send_order=0`、`cancel_order=0`、`order_api=0`；电脑重启后只读核对 7 个生产 job 均无 PID，Stage930/931/CTP 无残留进程。
- 过拟合判断：否；这是证据完整性、TOCTOU 和启动顺序修复，不改变任何策略参数或行情阈值。
- 继续价值判断：是；两个 P1 位于真实授权消费边界，必须在 qualification/Stage948 激活前闭环。
