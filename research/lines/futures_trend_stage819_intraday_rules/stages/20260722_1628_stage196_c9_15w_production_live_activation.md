# Stage196 C9/15万 production-live 正式激活

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：C9/15万 production-live 发布与运行态验收
- 记录时间：2026-07-22 16:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_production_live` / `codex/stage179-production-live`
- 阶段性质：正式生产发布、定时任务切换与 fail-closed 健康验收
- 是否重要突破：是；Stage179 执行可靠性改造首次完成 C9/15万 production-live 安装
- 是否触发A/B：否；不修改 alpha，不进行策略 A/B

## 外部调研与判断

- 参考资料：Apple `launchd` 官方文档；Python `time` 与 `gc` 官方文档；vn.py/CTP 既有调用链和仓库内实盘 SOP。
- 我的判断：本次只处理执行、状态持久化、价格/委托安全、资格证据和 launchd 事务安装，不改变信号、风险倍率、品种池或任何 alpha 参数，因此不是过拟合。上线价值成立，但必须以 exact commit、两次 CTP 只读、独立 review、原子安装和运行态 health 全部通过为边界。

## 本次变更

- 新增脚本：Stage945 production session launcher、Stage946 health、Stage947 support launcher、Stage948 installer，以及 production qualification/release/activation receipt 资产。
- 修改脚本：Stage179/903/905/914/927/930/931 执行与授权链，intent spool/ledger/launchd surface；最终补丁将 `launchctl print gui/<uid>` 的词法校验限定在真实 `services` 块，正确排除 `disabled services` 偏好残留，同时保留未知 loaded service 的 fail-closed。
- 删除脚本：无。
- 新增参数：production-live manifest、qualification、activation receipt、正式 env/runtime identity、launchd provenance 与 daily data receipt 绑定参数。
- 修改参数：官方执行口径统一为 `Stage847-C9-15w`、本金 `150000`；OPEN 使用 FAK，CLOSE 使用 LIMIT；正式性能闸门使用 `/usr/sbin/taskpolicy -a`。
- 删除参数：无 alpha 参数删除；旧 Stage372/20万和旧 C9 定时任务仅从当前 launchd surface 卸载，不删除历史研究入口。

## 回测/归因参数

- 数据区间：本阶段未新增回测；上线预计算目标日为 `2026-07-21`。
- 账户规模：`150000`（C9/15万）。
- 成本口径：沿用正式 C9/15万冻结口径，本阶段未改。
- 样本过滤：沿用 Stage847-C9-15w 正式口径，本阶段未改。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。

## 结果

- 期末权益：未新增回测，不适用。
- 总收益：未新增回测，不适用。
- 最大回撤：未新增回测，不适用。
- Sharpe：未新增回测，不适用。
- 总滑点：未新增回测，不适用。
- 总交易次数：未新增回测，不适用。
- 胜率：未新增回测，不适用。
- 其他关键指标：
  - exact commit：`5c98f0f59c4f322ff8787d180f388ad0b35e7253`；Git tree：`82063233b28112901c821ecd93e2b42f5d3ea7c2`。
  - 独立 review：P0/P1/P2=`0/0/0`；canonical report SHA-256=`b9f498809b216b1a944c165706ad23d6d50006ed62d9a03ab1a9248bf2e2f52a`。
  - production qualification：28 个规定套件，`698 passed / 0 failed / 0 skipped`；两次正式 CTP 只读采集均 qualified，broker trading day=`20260722`，send/cancel/order API=`0/0/0`。
  - qualification evidence id：`e4646c4ec9729dd209a2badcbfb05431b1891b628e59526d9e09e49bf0510c02`。
  - release manifest id：`d986f7fed3327836c525e0557e0c4896d1ad456fa6bb903d3facd256b579136f`；activation receipt id：`8bbd26dd44d5287f18626fe4808f93f57a2f3b6f89af495de97cceea1fab108f`。
  - Stage948 激活状态：`production_launchd_activated_no_ctp_connection`；旧 4 个任务已卸载，新 7 个任务在 disk/domain/individual 三套证据中精确一致，未知/冲突任务为 0，rollback invocation=`0`。
  - 首次 health 在 postclose-precompute 完成前因 daily receipt 缺失而 fail-closed；预计算退出 `0` 并生成 receipt 后，第二次 health 又因磁盘余量约 1.9 GiB 低于 2 GiB 闸门而 fail-closed。清理仅限 `/tmp` 中历史 Stage179 性能测试缓存后余量约 3.2 GiB，最终 health=`healthy_production_live_scheduled`、blockers=`[]`、send/cancel/order API=`0/0/0`。
  - 当前为 `post_close` 非交易窗口，day/night session RunAtLoad 均按预期退出 `0`；下一夜盘由 `20:55` launchd 定时启动。

## 输出文件

- report：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/independent-review/final-review.json`
- summary：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/health/latest.json`
- orders：两次 qualification CTP 只读采集，订单 API 计数 `0`；本阶段无真实委托。
- daily：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/data-readiness/latest.json`
- quality：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/qualification-bundle/qualification.json`
- release：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/release-manifest.json`
- activation：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/activation/latest.json`

## 结论

- 本阶段结论：C9/15万 production-live 已完成 exact commit 资格认证、发布证据签发、旧任务原子替换、新 7 个 launchd 任务加载和 post-close 运行态健康验收。当前安装已生效，但“下一交易时段会真实成交”仍必须由当时的交易日、daily receipt、CTP、行情、授权、资金、价格和风险闸门共同决定，继续 fail-closed。
- 是否进入下一步：是，仅进入运行观察，不再扩展代码。
- 下一步：`20:55` 观察 night session launcher/Stage930 heartbeat、CTP 与行情 gate；`21:03` 查看 health；若产生委托，立即核对交易价格、成交、撤单、账户持仓与 ledger。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有改变任何 alpha、阈值、品种、方向或样本窗口；所有修改都针对执行确定性、证据绑定和生产事务安全。

## 继续价值反思

- 运行前判断：是；未激活前优化无法进入实盘。
- 运行后判断：开发继续扩张已无价值；保留下一交易时段的只读运行观察有价值。
- 原因：production-live 安装和 post-close health 已完成，后续最有价值的证据来自真实时段的行情/CTP/委托链，而不是继续堆离线规则。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；避免在本次生产收尾中扩大长文件冲突面。
- 是否更新 `research/registry.md`：暂不更新；由后续总账合入者统一整理。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；本 Stage196 已完整记录，后续真实交易时段验收后再写重要合入摘要。
