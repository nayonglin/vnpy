# Stage440 MA609 21:00:01 一手开仓定时 wrapper

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-11 18:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘执行工具增强；不改 alpha、不改影子盘信号、不连接 CTP、不调用订单 API。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 交易时间资料显示郑商所甲醇夜盘通常为 `21:00-23:00`，夜盘集合竞价申报为 `20:55-20:59`、撮合为 `20:59-21:00`。
  - 法定节假日前一工作日无夜盘，最终仍需以 CTP 登录后的合约状态、交易日和有效 tick 为准。
- 我的判断：
  - 今晚若执行 `MA609.CZCE` 买开 `1` 手，更稳妥的结构不是 `20:55` 盲挂集合竞价，而是 `20:55` 做只读账户/连通检查，`21:00:01` 等有效盘口后用 Stage367 的实盘一手闸门发限价买开。
  - 由于 Stage367 默认要求账户快照 `300` 秒内新鲜，Stage440 在真实提交模式下增加一次 `submit_at - 90s` 的只读快照刷新，避免 `20:55` 首次快照到 `21:00:01` 刚好过期。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage440_ma609_timed_one_lot_open.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage367_live_one_lot_order.py`
  - `examples/portfolio_backtesting/run_ctp_stage655_readonly_account_margin_probe.py`
- 删除脚本：无
- 新增参数：
  - Stage440 新增 `--mode dry-run-only|submit-open`，默认 `dry-run-only`。
  - Stage440 新增 `--check-at`、`--submit-at`、`--refresh-seconds-before-submit`、`--env-file`、`--max-submit-late-seconds` 等一次性定时参数。
  - Stage440 真实提交仍必须提供 `--enable-live-submit-env`、`--confirm-submit I_UNDERSTAND_THIS_SENDS_REAL_CTP_LIVE_ORDER` 与 `--confirm-residual-position I_UNDERSTAND_THIS_LEAVES_A_REAL_POSITION`。
- 修改参数：
  - Stage367 `CONTRACT_SPECS` 增加 `MA.CZCE`：`volume_multiple=10`、`price_tick=1`、`margin_ratio=0.12`。
  - Stage367 与 Stage440 `run_id` 从秒级升级为微秒级，避免快速重复运行覆盖输出。
  - Stage655 增加 `account_query_received` 与 `position_query_completed` 字段；只有收到持仓查询 `last=True` 才认为持仓快照完整。
  - 独立 agent review 后继续加严：Stage655 增加 `position_query_error_id`、`position_query_error_msg`、`position_query_ok`；Stage367/Stage440 gate 要求 `position_query_ok=True`，避免 CTP 返回“持仓查询完成但带错误”时被误判为空仓。
  - Stage367 的 fresh readonly gate 增加 `account_query_received=True`、`position_query_completed=True`、`position_query_ok=True`，不再只凭 `position_rows==0` 判断空仓。
  - Stage440 的 Stage655 检查/刷新也增加完整登录、账户、持仓查询成功、显式保证金和账户空仓校验。
  - Stage367 在调用 `send_order`/`cancel_order` 前先更新对应 API 计数，避免 API 调用抛异常时审计计数误报 `0`。
  - Stage367 增加 CTP gateway import/setup 阻断落盘，并保护 `main_engine.close()` 异常，提升失败路径可追踪性。
  - 独立 agent review 后调整撤单终态：Stage367 在撤单后重新检查成交量和最新委托状态；Stage440 不再把 `cancel_attempted` 归类为 completed，改为 `review_submit_cancel_outcome_uncertain` 或 `review_submit_not_filled_cancel_confirmed_needs_reconcile`。
  - Stage440 对 Stage655 returncode 非 0/失败路径也先归档固定输出，再返回阻断，降低失败证据被后续探针覆盖的风险。
  - 本轮自审继续加严：
    - Stage440 增加官方 pending audit 闸门，运行前必须确认 `qmt_roll_official_shadow_pending_audit_<target_date>_summary.json` 中存在当前官方版本、目标日、`MA609.CZCE Long Open` pending order、opened candidate、影子持仓为空。
    - Stage440 对 `--step-timeout-seconds` 增加下限校验，避免真实 submit 子进程在发单后被过短 timeout 外部杀掉。
    - Stage440 归档 Stage655 固定输出时只复制本次 step 开始后更新过的文件，避免失败/timeout 时误归档旧快照。
    - Stage367 成交统计改为优先按 `vt_orderid/orderid` 归属，避免同一 symbol/direction/offset 的外部手工单被误计入本脚本订单。
    - Stage655 记录 `account_query_request_ret`、`position_query_request_ret`，并在全局 `onRspError` 对持仓查询 reqid 归因；`position_query_ok` 同时要求持仓查询完成、同步请求返回 `0`、异步错误码 `0`。
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：不适用；执行时由 Stage655/Stage367 读取实盘账户快照。
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：当前官方 Stage372/20w 影子盘已给出 `MA609.CZCE Long Open` 理论信号；本阶段只做一手执行工具封装。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 语法编译通过：`.py311/bin/python -m py_compile examples/portfolio_backtesting/run_ctp_stage367_live_one_lot_order.py examples/portfolio_backtesting/run_ctp_stage440_ma609_timed_one_lot_open.py`
  - `submit-open` 缺少 `--enable-live-submit-env` 时即时阻断，未等待、未连接、未调用订单 API。
  - Stage440 已改为解析 Stage367/Stage655 子进程完整 stdout 中的业务 JSON，不再只看 return code，避免把 `blocked_no_tick` 等业务阻断误判为 `completed`。
  - Stage440 会把 Stage655 固定输出归档为本次 run_id 下的独立 `readonly_check/pre_submit_refresh` 证据，避免 20:58 刷新覆盖 20:55 快照证据。
  - Stage440 增加 `submit_at > check_at` 排程校验。
  - 新增无连接验证：
    - `position_query_completed` 缺失时 Stage367 `_readonly_gate(...).passed=False`。
    - `position_query_completed=True` 且其他字段完整时 Stage367 `_readonly_gate(...).passed=True`。
    - Stage440 `_stage655_gate_failure(...)` 对缺失持仓查询完成返回 `position_query_completed_not_confirmed`，对持仓非空返回 `broker_position_not_flat`。
    - `position_query_error_id!=0` 或 `position_query_ok=False` 时 Stage367/Stage440 均 fail closed。
    - `.py311/bin/python -m py_compile` 覆盖 Stage440、Stage367、Stage655 三个脚本并通过。
    - 官方 pending audit gate 对 `2026-06-11` 返回通过，并匹配 `MA609.CZCE`；对 `2026-06-12` 在连接前以 `pending_audit_summary_missing` 阻断。
    - 低 `--step-timeout-seconds=10` 在连接前以 `blocked_step_timeout_too_short` 阻断。
    - Stage367 `_matching_trade_volume` 只统计目标 `vt_orderid=CTP.abc` 的成交，不统计同 symbol 的 `CTP.other`。
  - 本阶段 `send_order_api_called_count=0`、`cancel_order_api_called_count=0`。

## 输出文件

- report：无
- summary：无正式执行 summary；阻断测试 summary 已删除，避免混入今晚证据。
- orders：无
- daily：无
- quality：无

## 2026-06-11 20:33 复审补充

- 复审范围：
  - Stage440 外层 wrapper 的官方 pending audit 闸门、确认文本、submit env 开关、timeout 下限、Stage655 输出归档。
  - Stage367 一手实盘闸门的 readonly gate、合约规格、成交归属、撤单后状态映射、异常落盘。
  - Stage655 只读探针的账户/持仓查询完成性与错误码记录。
- 新增验证：
  - 三个脚本 `.py311/bin/python -m py_compile` 通过。
  - Stage440 `_official_signal_gate(2026-06-11)` 通过并匹配 `MA609.CZCE`；`2026-06-12` 在连接前以 `pending_audit_summary_missing` 阻断。
  - Stage440 对 `position_query_ok=False` 返回 `position_query_ok_not_confirmed`，不会把持仓查询错误误判为空仓。
  - Stage440 timeout 下限保持 `readonly=50s`、`submit=76s`，避免真实发单阶段被过短外层 timeout 杀掉。
  - Stage367 `_readonly_gate` 对损坏 JSON fail closed；对字符串数值 `"1.0"` 可正常解析并通过。
  - Stage367 `_matching_trade_volume` 按本地 vn.py 枚举真实值 `Long/Open` 复验，只统计目标 `vt_orderid=CTP.abc`，不统计同品种其他订单。
- 复审结论：
  - 未发现新的 blocking bug。
  - 一个非阻断残余风险仍需保留：真实 CTP 回调字段必须等今晚实连后确认；当前代码已把无法确认的成交/撤单状态归到 `review/uncertain`，不会静默当作完成。

## 2026-06-11 21:01 实盘前 gate 结果

- 用户在 `20:55` 后要求启动今晚一手 MA609 执行；先按默认 `dry-run-only` 路径运行。
- `20:55:59` 首次 Stage440 dry-run：
  - 官方 pending audit 通过，匹配 `MA609.CZCE Long Open`，影子当前持仓为空。
  - Stage655 只读检查等待 `35s` 后 `front_connected=False`、`account_rows=0`、`position_rows=0`。
  - Stage440 状态：`blocked_readonly_check_failed`，`send_order_api_called_count=0`。
- `20:56:50` 第二次 Stage440 dry-run，延长 Stage655 到 `90s`：
  - Stage655 仍为 `front_connected=False`。
  - Stage440 状态：`blocked_readonly_check_failed`，`send_order_api_called_count=0`。
- 用户随后明确授权“9点准时下单一手”；执行上没有跳过账户/持仓闸门，而是启动带真实授权参数的 Stage440 submit-open gate：
  - 命令目标：`check_at=21:00:00`，`submit_at=21:00:35`，`refresh_seconds_before_submit=-1`，`readonly_wait_seconds=25`。
  - `21:00:00` Stage655 只读 gate 启动，`21:00:26` 返回 `front_connected=False`。
  - Stage440 状态：`blocked_readonly_check_failed`；未进入 Stage367；没有真实下单。
- 额外只读诊断：
  - TCP 层可连接 TD/MD host:port，说明不是简单端口不通。
  - Stage608 vn.py gateway 只读探针连接 real env 时，MD 返回 `4040 CTP:API Front shake hand err: decode err`，随后本地 native CTP 库 `Segmentation fault: 11`。
- 本次执行 API 计数：
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
- 结论：
  - 今晚自动 CTP 通路未能完成实盘前只读账户/持仓 gate，不能自动开仓。
  - 当前失败更像 CTP 前置/API 兼容或环境配置问题，而不是策略信号问题。
  - 如用户仍决定交易，只能改为券商客户端手动下单；自动链路在修复 CTP 连接前不得继续真实发单。

## 2026-06-11 21:05 历史跑通版本复核

- 用户指出之前已有版本跑通下单；复核结论：属实。
- 历史证据：
  - Stage366 `2026-06-04 22:17:47`：同一 `ctp_live.local.env` 下，Stage655 TD-only 只读成功，`front/auth/login/settlement=true`，账户 `1` 行，持仓 `0` 行。
  - Stage368 `2026-06-04 22:38:47`：Stage367 真实 CTP 实盘 `FG609.CZCE` 买开 `1` 手成交，`send_order_api_called_count=1`，`cancel_order_api_called_count=0`，成交价 `1029.0`，`vt_orderid=CTP.17_-1913117655_1`。
  - Stage369 `2026-06-04 22:43:33`：后续平仓也形成真实成交，但同时记录并修复了 `dry-run-close` 初始缺陷。
- 当前差异：
  - `ctp_live.local.env` 文件修改时间仍为 `2026-06-04 22:17:04 CST`，权限 `0600`，TD/MD 地址仍为 `116.228.52.242:11207/11215`，配置文件本身没有显示被改过。
  - 今晚 Stage655 TD-only 对同一 TD 地址等待 `35s/90s/25s` 均未收到 `onFrontConnected`。
  - 今晚 raw MD-only 对同一 MD 地址返回 `ErrorID=4040 CTP:API Front shake hand err: decode err` 与 `Decrypt handshake data failed`。
  - 今晚 vn.py gateway 只读探针也返回 MD `4040 decode err` 后发生 native `Segmentation fault: 11`。
- 复核判断：
  - 不是“历史没有跑通”，而是历史跑通的同一实盘链路今晚在 CTP 前置握手/运行库兼容层失败。
  - 因为当前连只读账户/持仓 gate 都无法完成，仍不得为了准时而跳过 gate 直接报单。

## 2026-06-11 21:10 CTP runtime 根因定位与修复

- 根因：
  - Stage440 wrapper 和 Stage655 shell 里 `DYLD_FRAMEWORK_PATH` 顺序错误，把 `.py311/lib` 的 `v6.7.7_MacOS_CP_20240716` 评测/CP framework 放在了 `vnpy_ctp/api/libs` 的 `v6.7.2_MacOS_20231016` 正式/prod framework 前面。
  - 当前生产前置 `116.228.52.242:11207/11215` 应优先使用 `vnpy_ctp 6.7.2.1` 自带的正式 framework；`v6.7.7_MacOS_CP` 只适合 broker 明确要求的 `414xx/CP` 评测路径。
- 复现：
  - 旧顺序 raw MD-only 对生产 MD 前置复现 `ErrorID=4040 CTP:API Front shake hand err: decode err` 与 `Decrypt handshake data failed`。
- 修复：
  - Stage440 `_env_bash_command(...)` 改为 `CTP_LIB_DIR` 优先、`.py311/lib` 仅 fallback。
  - Stage655 shell 同步改为 `CTP_LIB_DIR` 优先。
- 验证：
  - 修复后 raw MD-only 成功登录并收到 `MA609` tick。
  - 修复后 Stage655 TD-only 成功完成 `front/auth/login/settlement/account/position`，`send_order_api_called_count=0`。
  - `.py311/bin/python -m py_compile` 覆盖 Stage440、Stage367、Stage655 并通过。
  - Stage440 dry-run 已能进入只读 gate，但因券商账户当前已有 `MA609` 多头持仓 `10` 手，被正确阻断为 `broker_position_not_flat`，未调用订单 API。
- 当前券商快照要点：
  - account：`Balance=180025.317713`，`Available=123387.317713`，`CurrMargin=54738.0`。
  - position：`MA609`，方向 `2`，持仓 `10`，今仓 `10`，占用保证金 `54738.0`，持仓盈亏 `1900.0`。
- 结论：
  - 今晚 21:00 前后的失败不是“历史链路没跑通过”，而是这次新 wrapper 启动时错误优先加载了 CP/评测版 runtime。
  - 修复后 CTP 只读链路恢复；但因为账户已非空仓，自动一手买开必须继续 fail closed，不能再追加开仓。

## 2026-06-11 21:18 实盘账户只读快照

- 用户确认已有 `MA609` 10 手为手动下单；本阶段只拉取账户状态，不发单、不撤单。
- 操作说明：
  - 第一次直接运行 Stage655 shell 时默认读取 `ctp_broker_test.local.env`，非本次实盘账户，30 秒未收到 front 回调；该次 `send_order_api_called_count=0`。
  - 随后显式读取 `ctp_live.local.env`，并保持正式 framework 优先顺序，直接运行 Stage655 Python 只读探针。
- 连接状态：
  - `front_connected=true`
  - `auth_ok=true`
  - `login_ok=true`
  - `settlement_ok=true`
  - `account_query_received=true`
  - `position_query_completed=true`
  - `position_query_ok=true`
- 账户快照：
  - 生成时间：`2026-06-11 21:18:22`
  - 快照时间：`2026-06-11 21:18:21`
  - 账户权益/动态权益 `Balance=181125.317713`
  - 可用资金 `Available=123387.317713`
  - 当前保证金 `CurrMargin=54738.0`
  - 冻结保证金/资金/手续费均为 `0.0`
  - 平仓盈亏 `CloseProfit=0.0`
  - 持仓盈亏 `PositionProfit=3000.0`
  - 手续费 `Commission=33.522287`
  - 上日结存 `PreBalance=178158.84`
- 持仓快照：
  - `MA609`，方向 `2`，持仓 `10`，今仓 `10`，昨仓 `0`
  - 占用保证金 `54738.0`
  - 持仓成本 `304100.0`
  - 持仓盈亏 `2900.0`
- API 计数：
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
- 结论：
  - 当前账户已有 `MA609` 多头今仓 `10` 手，且无冻结资金/冻结手续费。
  - 后续所有自动执行逻辑必须以该券商持仓为准；若策略需要调整，只能进入“对账/止损/平仓或减仓计划”，不能按空仓逻辑继续开仓。

## 结论

- 本阶段结论：
  - 已具备“20:55 只读检查、21:00:01 等有效 tick 后一手买开 MA609”的一次性 wrapper。
  - 默认运行只会 dry-run，不会真实下单。
  - 真实下单必须显式 `--mode submit-open --enable-live-submit-env`，并通过 Stage655 快照、Stage367 合约/盘口/一手限制、环境开关和两段确认文本。
  - 已修复两个 P1 执行闸门风险：
    - 旧逻辑可能在账户查询成功但持仓查询未完整返回时，把 `position_rows=0` 误当成 broker flat；新逻辑要求持仓查询完成、查询无错误且空仓。
    - 旧逻辑把“撤单已尝试”作为 completed；新逻辑把撤单未最终确认路径归入 review/uncertain，要求后续只读对账。
  - 本轮自审新增修复三个执行审计风险：官方信号缺失仍可手动运行 wrapper、过短 step timeout 可能杀掉真实发单子进程、同品种外部成交可能污染 fill 统计。
- 是否进入下一步：可以进入今晚 dry-run 或显式授权后的真实一手执行。
- 下一步：
  - 推荐先运行 Stage440 默认 dry-run-only，确认 20:55 只读检查与 21:00:01 Stage367 dry-run 都通过。
  - 若用户明确授权真实提交，再用同一 wrapper 切换 `--mode submit-open --enable-live-submit-env`，执行后立即读取 Stage440 summary、Stage367 summary/orders/trades/positions/accounts、Stage655 归档快照做对账。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段是执行时点与安全闸门封装，不改变策略信号、风险参数、选品或止损口径。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：今晚若需要真实一手跟随影子盘信号，必须用可审计的一次性执行器替代人工口头操作或无限后台循环，降低误触发、重复下单和快照过期风险。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等今晚 dry-run/真实执行结果后统一整理。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，当前只是执行工具准备；若真实一手成交或失败，再追加重要执行摘要。
