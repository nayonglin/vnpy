# Stage223 C9 实盘成交时间与手数对齐正式激活

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：C9/15万 production-live 发布与安装后验收
- 记录时间：2026-08-10 15:34 CST
- 候选工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage221_production_live` / `codex/stage221-production-live`
- 线上稳定目录：`/Users/bytedance/Desktop/person/vnpy_production_live`
- 正式提交：`9c0df9d86d4851cd78843334f274b7c28d73f899`
- 阶段性质：执行语义修复的正式生产发布，不修改 alpha
- 是否重要突破：是；Stage222 候选首次完成稳定目录资格认证和 Stage948 激活
- 是否触发 A/B：否；不属于新策略或参数优化

## 外部调研与判断

- 参考 vn.py 官方对象定义：`TradeData.datetime` 表示成交回报时间，`ContractData.max_volume` 表示合约单笔最大委托量。
- 判断：入场日 `0.5R` 监控应从真实最早成交时间开始；取消本地固定 20 手上限后，仍保留合约上限、整数手、持仓、活动/未知委托、readiness 和日内次数闸门。
- 本次只发布 Stage222 已冻结并独立审查的执行修复，不调整信号、R 倍数、品种池、仓位风险倍率或回测样本。

## 本次变更

- 新增脚本：无。
- 修改脚本：沿用正式提交 `9c0df9d8...` 的 Stage904/905/931、execution ledger 和 Phase-D 配置修复。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：`max_single_order_volume=0`，关闭本地固定 20 手上限。
- 删除参数：无；字段继续保留，未来正数仍可启用本地上限。
- 生产安装：通过 Stage948 原子 prepare/activate，将 stable HEAD、qualification、manifest、activation receipt 和精确 7 个 launchd 任务切换到同一提交。

## 回测/归因参数

- 数据区间：不适用；本阶段未运行回测。
- 账户规模：`150000`，不改变资金口径。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。

## 结果

- 期末权益：不适用；未运行回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 稳定目录 qualification：`813 passed / 0 failed / 0 skipped`，32 个规定套件全部通过。
  - 两次正式 CTP 只读抓取：`status=qualified`、`capture_count=2`、broker trading day=`20260810`；账户、持仓、委托和成交查询均 complete。
  - 独立审查：`P0/P1/P2=0/0/1`；唯一 P2 为测试夹具理论跨午夜，不影响生产逻辑。
  - qualification evidence：`4f9d8b77542327a3d211f1786c27236eba25d09da190261a04416d994d398241`。
  - release manifest：`ad80c22915ab29ee54287bc7326c068cde7ae4f136a477074ffa66c007a7b207`。
  - activation receipt：`e6cf539bd29f64e24b78db33003f7ee84da36158f3d3f34d96cd99f9fb9e460f`。
  - Stage948：`production_launchd_activated_no_ctp_connection`；disk/domain/loaded 均为精确 7 个，冲突任务 `0`，rollback invocation `0`。
  - 安装和验收订单 API：`send_order=0`、`cancel_order=0`、`order_api=0`。
  - 安装后 Stage946：HEAD、manifest、qualification、receipt 和 launchd surface 全部一致；唯一 blocker 为 `production_daily_data_receipt_invalid`，原因是旧回执仍绑定提交 `368042e0...`。16:35 的 qualified `postclose-precompute` 已加载，等待自动生成新提交回执。
  - 首次候选目录 qualification 已通过，但 Stage948 正确拒绝其绝对 cwd provenance；自动回滚后改为在稳定目录重新生成资格。一次性能测试在旧进程并发时瞬时失败，独立原命令复跑通过，稳定目录完整资格也通过，未修改阈值或代码。
  - 旧 day-session 因上午磁盘不足后延迟启动，固定时长会延续到盘后；15:26 在 `post_close`、活动委托为空且订单 API 为 0 时受控 bootout，2 秒内主进程和子进程全部退出，再进入稳定目录资格与 Stage948 激活。

## 输出文件

- qualification：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json`
- release：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json`
- activation：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/activation/latest.json`
- runtime receipt：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/runtime/state/activation_receipt.json`
- health：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/health/latest.json`
- 可恢复备份：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/archive/stage222-final-install-20260810_153205`

## 结论

- 正式安装已完成，新线上提交为 `9c0df9d8...`。
- 当前处于 `post_close`，7 个任务全部 loaded 且未运行；系统在 16:35 新日回执生成前按预期 fail-closed。
- 下一步：观察 16:35 `postclose-precompute` 自动重签 `data-readiness/latest.json`，随后重跑 Stage946；20:55 再观察 night-session 的 CTP、行情和订单闸门。不得手工 kickstart 交易会话。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有调整任何 alpha、历史窗口、品种、方向、R 参数或风险倍率；全部工作是执行因果时序、证据绑定和原子发布。

## 继续价值反思

- 运行前判断：是；候选只有进入正式资格和线上安装才产生实际价值。
- 运行后判断：开发扩张暂无价值；继续观察 16:35 日回执和 20:55 夜盘真实运行有价值。
- 原因：代码和控制面已安装，剩余最有信息量的证据来自自动化任务和真实时段，而不是继续堆离线变体。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线仍有并行工作区，按规则先写唯一 stage 文件。
- 是否更新 `research/registry.md`：否；由后续合入者统一整理。
- 是否追加根目录 `memory.md/back_log.md`：否；先等 16:35 日回执和安装后健康完全恢复，再决定是否写重要合入摘要。
