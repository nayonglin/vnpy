# Stage227 正式 shadow 刷新与运行态恢复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：正式 C9/15w 生产影子盘只读恢复与收盘信号复核
- 记录时间：2026-08-26 18:27（Asia/Shanghai）
- 工作区/分支：生产稳定根 `/Users/bytedance/Desktop/person/vnpy_production_live`，HEAD `09aa96a03fb91124be90bd69861be3f834ab6299`；本记录写入主研究工作区当前分支
- 阶段性质：运行态修复、正式信号刷新、只读券商闸门复核；不修改 alpha、参数、品种池或报单逻辑
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSDK 官方仓库与 `tqsdk/api.py`；Requests 官方 issue #4568、#4771 关于响应体不完整时的 `ChunkedEncodingError`。
- 我的判断：16:37 的 `IncompleteRead -> ChunkedEncodingError` 属于上游 HTTP 响应中断，不能据此改策略或绕过正式刷新链路；同一官方 Stage909 路径在 18:20 重试后正常完成。Requests 对这类响应体中途断流并不保证自动重试，因此生产侧继续以 fail-closed、受控整链重跑为正确处理。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 运行态修复：原 `activation/latest.json` 绑定的 7 个 launchd plist `device=16777234`，当前文件系统报告 `device=16777230`；内容 SHA256、权限、inode、size、mtime 与 7/7 label 集合均一致。对同一 HEAD、同一 release manifest 执行 Stage948 prepare/activate，重新绑定当前文件系统指纹。
- 第一次重激活因同一 manifest 的历史 quarantine 目录已存在而失败；Stage948 自动回滚完整，`rollback_failure_count=0`、7/7 label 恢复、订单 API 为 0。逐项核对历史 quarantine 内 7 个 plist 与当前安装文件 SHA256 一致后，将其完整移动到可恢复审计目录：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/runtime/recovery-audit/20260826_1819-stage948-same-manifest-quarantine`，未删除证据；第二次 Stage948 激活成功。
- 成功激活证据：`production_launchd_activated_no_ctp_connection`，生产 label `7/7`，冲突 `0`，rollback `0`，激活阶段 CTP/send/cancel/order API 均为 `0`。
- 通过正式 launchd owner 运行 `postclose-precompute`；直接调用 Stage947 被 `production_support_requires_canonical_launchd_owner` 正确拒绝，未绕过所有权门禁。
- 正式流水线成功完成 `refresh-market-data -> refresh-shadow -> issue-daily-data-receipt -> generate-postclose-report`，目标日 `2026-08-26`，daily receipt SHA256 `d3708cb31bc71311ca1f55c29be29e4e1cefb7bb17a7cef752f334fe1249f8e3`。
- 18:24 通过正式 launchd owner 运行 production-live CTP 只读刷新；使用 `ctp_live.local.env` 与正式 `vnpy_ctp/api/libs` 优先路径。30 秒窗口内无 CTP progress，结果 `readonly_refresh_blocked / position_query_not_available`，broker query bundle 不完整；send/cancel/order API 均为 `0`。

## 回测/归因参数

- 数据区间：正式 shadow `2026-07-23 -> 2026-08-26`。
- 账户规模：`150000`，`c9-15w`。
- 成本口径：沿用正式版本，不改。
- 样本过滤：沿用正式 AI 池，最新评估日 `2026-07-31`。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；本阶段没有运行新策略回测。

## 结果

- 期末权益：不适用；未运行新回测。
- 总收益：不适用；未运行新回测。
- 最大回撤：不适用；未运行新回测。
- Sharpe：不适用；未运行新回测。
- 总滑点：不适用；未运行新回测。
- 总交易次数：不适用；未运行新回测。
- 胜率：不适用；未运行新回测。
- 其他关键指标：Stage901 `target_signal_count=0`、`pending_order_count=1`、`target_close_event_count=1`、`target_entry_candidate_count=0`、`target_opened_candidate_count=0`、风险级别 `normal`。
- 唯一理论动作：`fu2611.SHFE`，多头平仓 `1` 手，理论价 `3622`，原因 `long_prev2day_stop`，目标日 `2026-08-26`。
- 执行门禁：18:23 Stage260/905 将该动作 blocked；最近可用的 15:12 broker 快照中 `fu2611.SHFE` 匹配多头为 `0`，且到 18:23 已超过 freshness 上限。18:24 只读刷新又因非交易连接窗口无 CTP progress 而未获得新快照，所以当前不能把理论平仓视为今晚可执行委托。
- 安全证据：整个修复、重算、导出与只读刷新链路 send/cancel/order API 均为 `0`。

## 输出文件

- report：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/postclose-pipeline/latest.json`
- summary：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/readonly-audits/qmt_roll_c9_15w_official_shadow_audit_20260826_summary.json`
- orders：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/readonly-audits/qmt_roll_c9_15w_official_shadow_audit_20260826_pending_orders.csv`
- daily：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/data-readiness/latest.json`
- quality：正式身份、qualification、activation、daily receipt、Stage901 cohort 一致；7/7 launchd 精确、冲突 0；券商只读 freshness 未通过，执行保持 fail-closed。

## 结论

- 本阶段结论：正式信号链已修复并成功重跑。8 月 26 日产生 1 条 `fu2611.SHFE` 平多 1 手理论动作，没有新开仓；但券商快照不新鲜且最新只读刷新失败，当前可执行动作数仍为 0。今晚 20:55 交易窗口必须重新获得 fresh broker snapshot；只有券商确有匹配 `fu2611.SHFE` 多头且其余门禁全绿时才允许进入平仓链，否则跳过。明早沿用同一条未完成动作的门禁判断，不新增开仓。
- 是否进入下一步：是，仅进入交易窗口 fresh readonly + reconciliation 复核，不改策略、不手工补单。
- 下一步：20:55 后由正式 night-session/Stage907 获取 300 秒内 broker snapshot，再跑 Stage260/902/905/906；持续要求 send/cancel/order API 审计闭合。另行排期修复 Stage948 同 manifest quarantine 重用与纯 `st_dev` 指纹漂移的可维护性问题，但不得在生产稳定根热补丁。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只恢复正式数据、身份和只读门禁，没有根据当日盈亏修改参数、品种或方向。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但范围仅限执行证据闭环。
- 原因：同日 receipt 与 Stage901 信号已经恢复，继续扫策略或重跑回测没有价值；交易窗口刷新 broker 持仓并判断理论平仓是否真实可执行仍有直接安全价值。

## 合入建议

- 是否更新本线 `LINE.md`：否；本次没有策略研究状态变化。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；不是新正式版本或策略突破。
