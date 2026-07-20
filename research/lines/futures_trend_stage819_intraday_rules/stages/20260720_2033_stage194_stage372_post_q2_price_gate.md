# Stage194 Stage372 post-Q2 实盘最终价格闸门

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：Stage372/20万执行可靠性与只读发布候选；生产提交保持禁止
- 记录时间：2026-07-20 20:14-20:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_master_merge` / `codex/stage179-master-merge`
- 阶段性质：实盘执行安全修复、发布清单重冻结；不是 alpha 研究
- 是否重要突破：否；这是必须补齐的价格安全边界，不改变策略收益来源
- 是否触发A/B：否；没有调整策略、AI 池、资金、手数、止损或信号参数

## 外部调研与判断

- 参考资料：
  - vn.py 官方 CTP gateway：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>
  - vn.py 官方交易对象定义：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py>
  - vn.py 官方主引擎：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py>
- 调研结论：CTP gateway 会把上游 `OrderRequest.price` 原样写入 CTP `LimitPrice`，不会替策略选择买一/卖一、补最小价位或修正涨跌停；`TickData` 提供盘口和涨跌停，`ContractData` 提供 `pricetick`，因此最终价格正确性必须在 Stage931 调用 broker API 前完成。
- 我的判断：Stage372 原链路把盘后回放的 `theoretical_price` 传到 Stage905，再作为 `limit_price` 进入 Stage931；原 post-Q2 重定价只覆盖 C9 的 Stage904 close/retry source，`stage260_stage372_daily` 会被无阻断跳过。这是 production-live 的 P1，不是运行耗时问题。正确修复是只接受同一 CTP 会话的 Q2 后行情和合约元数据，异常一律失败关闭，而不是继续使用理论价。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：新增 Stage372 post-Q2 最终价格闸门。
  - `build_qmt_roll_stage179_release_manifest.py`：把本次价格安全测试加入 critical files。
- 修改测试：
  - `test_stage931_post_reprice_final_gate.py`：新增 Stage372 long/short、open/close、完整 final-state gate、Q2 因果、CTP gateway/contract 身份、pricetick、盘口、涨跌停、MAX_FLOAT、浮点可表示性和停板边界测试。
  - `test_stage179_release_manifest.py`：要求发布清单冻结上述价格测试。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 定价不变量：
  - 行情必须是同一 Stage931 进程在 Q2 完成后收到的 fresh `EVENT_TICK`，禁止 Stage608 文件 fallback。
  - tick 与 contract 的 `gateway_name` 必须为 `CTP`，contract `vt_symbol` 必须与请求一致。
  - live contract `pricetick` 为权威；intent `pricetick` 必须为有限正数且与其精确一致。
  - bid/ask/limit_down/limit_up 必须有限、为正、拒绝 CTP MAX_FLOAT，且满足 `limit_down <= bid <= ask <= limit_up`。
  - 买单以 ask、卖单以 bid 为基准，最多增加既有 `max_slippage_ticks=5` 的保护；最终价格必须 finite、positive、marketable、on-tick、within-limits。
  - 任一字段缺失、不一致、交叉盘口、非 CTP 来源、不可表示价位或无合法停板价位都保留原请求价但阻断 broker API，不允许拿原价继续发送。

## 回测/归因参数

- 数据区间：未运行新回测；只刷新并检查 2026-07-20 官方日常 shadow。
- 账户规模：代码目标为 Stage372/20万；当前日常 shadow 实际解析为 Stage847-C9/15万，口径冲突继续作为上线阻断，不擅自改资金。
- 成本口径：未变更。
- 样本过滤：未变更。
- 策略/归因口径：不修改 alpha，仅修执行价格与发布证据。

## 结果

- 期末权益：不适用/未变更。
- 总收益：不适用/未变更。
- 最大回撤：不适用/未变更。
- Sharpe：不适用/未变更。
- 总滑点：不适用/未变更；实盘保护仍使用既有最多 5 tick。
- 总交易次数：不适用/未运行回测。
- 胜率：不适用/未运行回测。
- TDD 红灯：修复前 Stage372 完整 post-Q2 盘口仍返回 `skipped_not_stage904_intraday_close`，新增测试 `11 failed`，证明原价无阻断穿透。
- 定向回归：最终本地价格/manifest 扩展集 `84 passed, 47 subtests passed`。
- 执行链扩大回归：最终冻结源码 `764 passed, 269 subtests passed`，耗时 `71.56s`。
- 随机价格不变量探针：5000 组正常价位全部满足 finite/positive/on-tick/within-limits/marketable；没有连接 CTP、没有调用订单 API。
- 独立终审：代码审查与数学对抗审计均为 `P0=0/P1=0/P2=0`；数学审计另覆盖 85 个确定性反例和 20,800 组带盘口浮点扰动随机用例，`0 exception/0 invariant violation`。
- 2026-07-20 数据更新：19/19 合约保存成功，失败 0、空数据 0，最新日期为 2026-07-20。
- 2026-07-20 官方 shadow：`target_signal_count=0`、`pending_order_count=0`、`current_position_count=0`、`send/cancel=0/0`；今晚没有理论可执行订单。

## 输出文件

- data update summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`
- shadow decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_decision_stage901_stage847_c9_2026_ytd_live_shadow_v1.json`
- pending audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`，0 行。
- release manifest：`examples/portfolio_backtesting/release_manifests/stage179/stage372-candidate.json`；source commit `9c0aa78737ca27d8f679c0a61f47423e022b4a34`，release id `stage179-stage372-readonly-9c0aa7873`，69 个 critical files，manifest digest `854f2a23da9aaff71c505e984c1c5e6990105ccd57b47da12df260c7f46db6ff`，文件 SHA-256 `8724069207518dde2eec4d5f3b5068a44eade1716611635e1085d3268d9e8c25`。
- manifest 实际校验：offline、production-readonly ACCEPT；SimNow、broker-test、production-live 均以 `release_manifest_runtime_profile_not_allowed` REJECT；strategy semantics 保持 `blocked`。

## 结论

- 本阶段结论：Stage372 价格 P1 已按 fail-closed 原则修复并通过本地扩大回归；初始 Stage179 集成已以 merge commit `9610df2d9c8260a5f41917c3fea9f49c25415bd8` 推送到 `origin/master`。价格源码提交为 `9c0aa78737ca27d8f679c0a61f47423e022b4a34`，独立终审与 manifest 重建均已完成，待把最终 manifest 子提交推送 master。
- production-live 结论：NO-GO。价格代码修复不等于实盘资格；发布清单仍禁止 submit，Stage372/20万与当前 C9/15万官方口径冲突未解决，生产目录尚未安全部署新 master，5 场真实 0/0 canary、完整重连和 broker 只读快照仍缺失。
- 是否进入下一步：是，进入干净 source commit、manifest 重冻结、独立终审和 master 推送；之后只能做 production-readonly 验收，不能越级真实报单。
- 下一步：在真实交易服务窗口完成严格 0/0 CTP 只读、5 场日夜 canary 与 authoritative reconnect v2；明确官方 Stage372/20万口径后再讨论 SimNow，production-live 仍需单独资格晋级。

## 2026-07-20 20:49 生产 CTP 严格只读与旧任务降级

- 使用 `ctp_live.local.env`（权限 `0600`）和正式 `vnpy_ctp/api/libs` framework 优先级，从最终 master 工作树执行 Stage174 严格只读探针；没有加载 submit adapter，没有发送或撤销委托。
- TD/MD 前置连接、授权、登录、结算确认、order/trade/position/account/contract 查询均完成；broker trading day 为 `20260721`，query bundle `complete=true`，同一 connection generation 的完整快照成立。
- broker 结果：账户行 1、持仓 0、订单 0、成交 0，`position_snapshot_state=confirmed_flat`；合约归一化 507 行。所有 `send_order/cancel_order/native mutation` attempted 与 called 计数均为严格 `0`。
- 输出 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`，SHA-256 `be2b8d2997e3d76d957fa8c951cf3bac4ee36fd0bbb499baa0760f7353d8d53e`。
- query bundle manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_query_bundle_manifest_stage174_ctp_vnpy_readonly_probe_v1.json`，SHA-256 `14bcc5c9f63d82731386154354647ea62c9d356a513f71daa9acf7f4311a64a9`。
- 运行态冲突：发现已安装的旧 C9/15万 day/night LaunchAgent 分别计划 08:55/20:55 从 `/Users/bytedance/Desktop/person/vnpy` 脏旧工作区以 `live-real` 和真实提交环境启动，不包含本阶段 Stage372 价格闸门。
- 安全处置：broker 已确认空仓后，对两份旧 C9 day/night live-real job 执行可逆 `launchctl bootout`；plist 未删除，未停止任何持仓管理进程。复查两 job 均不在 launchctl domain、无 Stage903/904/905/914/927/930/931 进程；保留只读快照、月更与报告任务。
- 最终判断：生产 CTP 当前可读且账户空仓，但单场 one-shot 只读不计入 5 场 canonical launchd canary，也没有重连证明；因此 production-readonly 证据增加，但 production-live 继续 NO-GO。让旧 live-real 任务自动启动反而会违反“交易价格正确”的目标。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有根据 JM 单晚盈亏、成交结果或某一品种调参；改动是时间因果、数据来源、价位表示和交易所价格边界的通用不变量。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：CTP 不会替上游修正价格，补齐最终价格闸门直接降低错价委托风险；继续价值已从堆离线规则转为真实只读证据和口径澄清。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线并行阶段只写唯一 stage 文件，合入整理时再统一更新。
- 是否更新 `research/registry.md`：否；研究线未变化。
- 是否追加根目录 `memory.md/back_log.md`：暂否；待真实只读/口径资格形成正式候选后再追加重要摘要。
