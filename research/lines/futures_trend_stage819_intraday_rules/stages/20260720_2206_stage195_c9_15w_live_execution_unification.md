# Stage195 C9/15万实盘执行口径统一与冷启动减耗

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：实盘执行可靠性与 production-readonly 候选冻结；未连接 CTP，未报单
- 记录时间：2026-07-20 22:06（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_master_merge` / `codex/stage179-master-merge`
- 阶段性质：执行身份、价格不变量、启动链路和部署入口统一
- 是否重要突破：否。没有修改 alpha，只消除实盘口径分裂和执行可靠性缺口
- 是否触发A/B：否。本阶段不比较或调整策略收益参数

## 外部调研与判断

- 参考资料：
  - vn.py `BaseGateway`：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py
  - vn.py `MainEngine` / `EventEngine`：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py
  - vn.py CTP gateway：https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py
- 我的判断：行情进入 gateway/event 队列前的单调时钟戳才是因果边界；CTP 下游会直接使用上层 `OrderRequest.price`，因此 C9 三类正式 source 必须共同经过 Q2 后新鲜 CTP tick、同会话合约/pricetick、盘口、涨跌停和最终 tick 对齐硬门，不能依赖理论价或文件行情回退。

## 本次变更

- 新增脚本：
  - `provision_qmt_roll_c9_launchd_directories.py`
  - C9/15万只读日盘、夜盘、收盘预计算三个 launchd plist
  - C9 launchd 目录隔离测试和 Stage934 只读健康检查测试
- 修改脚本：
  - 共享 execution profile、Stage260/659/901/902/903/905/909/914/929/930/931/934、release manifest builder、canary auditor、启动 SOP 与对应测试
  - Stage930 owner watchdog 和 supervisor 的纯标准库辅助进程使用 Python `-S`，避免重复加载 vn.py
  - Stage909 → Stage901 的 summary、signal、positions、pending、report 全部遵从同一隔离 `OFFICIAL_LIVE_SIGNAL_INPUT_DIR`；Stage901 顶层身份绑定 canonical C9/15万 profile，防止 Stage902 因路径/身份错位等待到慢周期
  - C9 三类 source 的第二次 O-P-O 最终重定价只接受严格晚于第二次 Q2 的 CTP event tick；非法 retry trigger、Stage904 lineage 伪装和 SHFE/INE 子单价格漂移全部 fail-closed，阻断时还原原始 request price
  - Stage901 初始开仓拒绝携带任何 Stage904 专属人工干预、P1/迁移、监控时间和成交谱系字段；即使 source/role/cycle 被同时伪装，artifact gate 与最终 child gate 仍共同阻断
  - Stage934 对 C9/15万、production-readonly、canonical launchd provenance 和 send/cancel/aggregate 完整证据做严格绑定；缺失或畸形的“0/0”不能再冒充健康
- 删除脚本：
  - 删除仓库内旧 `local.qmt-roll.official-live.15w.c9-day-session.plist`
  - 删除仓库内旧 `local.qmt-roll.official-live.15w.c9-night-session.plist`
- 新增参数：
  - canonical execution profile：`c9-15w`
  - `STAGE930_SUPERVISOR_PGID_HANDSHAKE_ATTEMPTS`，默认 100 次（约 5 秒），超时仍失败关闭
  - C9 只读 launchd 固定 `production-readonly + dry-run + submit disabled + warm + release manifest`
- 修改参数：
  - 账户规模统一为 `150000` / `15w`
  - `real_submit_default` 从 enabled 改为 `fail_closed`
  - shared CLI 默认从 Stage372/20万切到 C9/15万
  - release manifest API 默认仅允许 `offline`、`production-readonly`
  - 任何 `live-real` Stage930 启动都必须使用 warm executor + persistent detector；当前 persistent detector fast lane 仍是 no-submit，因此该约束不构成 production-live 资格
- 删除参数：
  - 运行时不再接受 `c9-15w-historical`；该名字仅保留 import 兼容，不能生成新授权、清单或启动参数
  - 禁止 `legacy-once + live-real` 绕过 Stage179 warm manifest/activation gate

## 回测/归因参数

- 数据区间：未运行策略回测
- 账户规模：C9/15万（`150000`）
- 成本口径：未修改
- 样本过滤：未修改
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 结果

- 期末权益：未新增、未修改、未删除（本阶段未回测）
- 总收益：未新增、未修改、未删除
- 最大回撤：未新增、未修改、未删除
- Sharpe：未新增、未修改、未删除
- 总滑点：未新增、未修改、未删除
- 总交易次数：未新增、未修改、未删除
- 胜率：未新增、未修改、未删除
- 其他关键指标：
  - 最新执行链聚焦回归：`258 passed, 124 subtests passed`
  - 最新 Stage931 价格/因果聚焦回归：`77 passed, 58 subtests passed`
  - 最新全量筛选回归：`1229 passed, 6 deselected, 331 subtests passed`
  - 6 个 deselected 均为已复现的基线/环境项：4 个 Alpha101 `cast_to_int` 既有缺失、1 个硬编码 worktree 目录名、1 个缺少历史 backtest output；`git diff origin/master` 对这些文件为 0
  - 第一轮全量筛选曾有 1 个真实 SIGTERM 子进程 5 秒启动标记超时；该单测立即复跑通过，去掉临时 pycache 环境后的完整筛选集也通过，判定为压力时序抖动而非本轮逻辑回归
  - manifest/readonly/launchd 冻结回归：`54 passed, 36 subtests passed`
  - Stage930 受监管子进程冷启动探针：约 `7.3s -> 3.0s`
  - CTP 连接：0；报单 API：0；撤单 API：0
  - 本机旧 armed C9 日/夜 label：持久 disabled、未加载、无进程；旧 plist 已移至 `~/Library/LaunchAgents.disabled-stage179-c9-legacy-20260720/` 并去除写权限

## 输出文件

- report：本阶段记录
- summary：`examples/portfolio_backtesting/release_manifests/stage179/c9-15w-candidate.json`
  - source commit：`79bfb1c6067ab7e10a06d4cefe941a5db9cbf7d9`
  - manifest SHA256：`92188d607bdbe36a444cc175a6371bcdd3a1a494166f5e755c86642e7e90a0c1`
  - profile/capital：`c9-15w / 150000 / 15w`
  - runtime allow-list：`offline`、`production-readonly`
  - strategy semantics：`blocked`
- orders：无
- daily：无
- quality：聚焦/全量 pytest、`py_compile`、`bash -n`、`plutil -lint`、`git diff --check`

## 结论

- 本阶段结论：代码、默认身份、价格硬门、只读部署入口和运维 SOP 已统一到 C9/15万；旧 armed 入口已从仓库和本机登录目录移除。当前资格仍是 production-readonly，不能把“代码可合入”表述为“production-live 已验证”。
- 对今天 21:00 延迟的结论：Stage909 与 Stage901 的隔离路径错位会让收盘预计算落回仓库默认目录、夜盘 Stage930 找不到产物；本轮已修复这条确定性原因，因此能消除同类 `target_not_ready` 等待。它不等于已经完成线上真实窗口验收。
- 独立终审新边界：persistent detector 会在约 50ms 内生成并 durable commit 止损/重进场意图，但当前 fast lane 明确 `submit_disabled`；新意图的真实 Stage931 authorization/wake 仍依赖下一轮 slow cycle。故本轮只能合入 readonly 代码，不能声称实时止损/重进场已获得 production-live 延迟资格。
- 独立终审分级：C9/15万 production-readonly 为 `GO`，当前增量 `P0=0、P1=0`；production-live 为 `NO-GO`，另有 persistent no-submit 与账本预留后授权失效造成平仓约 30 秒重试锁两项阻断，必须在下一独立阶段关闭。
- 是否进入下一步：是
- 下一步：推送 master。之后在独立干净运行目录做 CTP 只读 0/0 canary；另立阶段补 persistent detector → fresh gate → bounded authorization/wake 的实时提交闭环，在 SimNow/真实只读证据前不签发 activation receipt、不启动真实报单。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：没有修改入场、出场、AI 排名、风险倍率或任何收益参数；只统一身份与资金口径，并把价格和生命周期不变量设为跨策略可复用的 fail-closed 约束。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：口径分裂、旧 armed plist、理论价回退和重复 Python 冷启动都会直接影响实盘准点与价格安全；修复后继续做只读 CTP canary 有价值，继续堆离线规则的边际价值较低。

## 合入建议

- 是否更新本线 `LINE.md`：否。同一研究线存在并行工作，按规则只写唯一 stage 文件，合入者后续统一整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否。本轮先以 stage + release manifest 冻结；正式只读资格通过后再做重要合入摘要
