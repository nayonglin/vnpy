# Stage221 C9 实盘 0.5R 状态与单笔手数对齐结果

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：实盘执行语义修复（仅本地代码与测试）
- 记录时间：2026-08-08 22:56
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式版实盘 P0 修复结果
- 是否重要突破：否；属于回测/实盘语义对齐
- 是否触发A/B：否；未修改策略 alpha

## 外部调研与判断

- 参考资料：
  - https://github.com/vnpy/vnpy
  - https://www.vnpy.com/forum/topic/3905-vnpy-trader-converter-py-dai-ma-yi-wen
- 调研结论：vn.py 的订单转换/执行层负责交易接口语义，不会替策略保存“是否先触达 +0.5R”这一业务状态；该状态必须由策略执行层自行持久化。官方资料不直接规定本策略的 0.5R 规则，具体状态机仍以正式回测逻辑和本项目约束为准。
- 我的判断：使用已有 append-only execution ledger 保存状态，比新增一个无锁 JSON 状态文件更可审计；读取必须 strict + 共享锁，写入必须独占锁 + flush + fsync。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `qmt_roll_official_live_execution_ledger.py`
  - `qmt_roll_official_live_phase_d_config.py`
  - `run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
  - `run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- 新增测试：`test_stage219_c9_live_progress_state_unlimited_volume.py`
- 新增参数/状态：`c9_initial_progress_confirmed` ledger event、`entry_epoch`、`first_trade_at`、`first_threshold_event`。
- 修改参数：`max_single_order_volume: 20 -> 0`，其中 `0` 表示取消本地单笔手数 cap。
- 删除参数：无。

## 实现结果

1. `+0.5R` 只由真实成交价字段确认，不再由 long ask / short bid 的未成交报价确认。
2. tick 先按真实首笔开仓成交时间截断，再按时间戳稳定排序；先 progress 则永久禁用本次开仓的初始止损，先 adverse 则平仓，同时间戳无法证明先后时 adverse 优先。
3. progress 状态绑定 `target_date + vt_symbol + direction + entry_epoch`，跨轮询、进程重启保留；同日新的 entry epoch 不继承旧状态。
4. Stage931 将 `first_trade_at` 写入成交 ledger；Stage904 的时间优先级为 ledger 实际成交时间、broker 真实成交时间、shadow 时间、最后才是 ledger 生成时间。
5. ledger 默认 strict 读取并使用共享锁；坏 JSON 抛错。append 和 reservation 都使用独占锁、flush、fsync。
6. Stage905 仅在 `max_single_order_volume > 0` 时执行本地手数 cap；500/503 手可生成一个 dry-run intent。合约最大/最小手数、整数手数、Stage902/260、持仓、active/unknown order、日订单数等既有 gate 未绕过。

## 回测/测试结果

- 本阶段未运行收益回测；原因：本次仅修复实盘执行语义，不修改收益路径或 alpha，避免把不可靠的旧全周期回测当作验证依据。
- Stage219 定向测试：`17 passed`。
- 当前研究线全套测试：`105 passed in 21.83s`。
- `py_compile`：通过。
- `git diff --check`：通过。
- CTP 连接次数：0。
- send/cancel order API 调用次数：0。
- 独立 reviewer 最终结论：当前 scoped diff 未发现新 P0。

## 回测指标

- 期末权益：不适用（未运行回测）
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 已知剩余风险

- 用户明确选择 500/503 手整单且不拆单；因此本次不新增资金/逐单保证金/流动性参与率/拆单 gate。券商或交易所仍可能拒绝、部分成交或造成较大冲击成本，这是已接受的实盘风险，不是本次实现遗漏的 20 手限制。
- P1：Stage904 子进程 strict 失败时，Stage903 展示层可能读取同日期旧 summary；Stage905/931 自身 strict 会阻止真实报单，因此不构成实际下单 P0，后续单独修复编排可观测性。
- 用户指定本轮暂不处理：SHFE/INE 平今平昨及 retry 执行差异。

## 结论

- 本阶段结论：已完成用户确认的两项改动，并关闭复核中发现的会改变 0.5R 实盘路径的 P0。
- 是否进入下一步：代码与测试范围可以收口；尚未启动 daemon 或连接 CTP。
- 下一步：如要启用实盘，应另按实盘 SOP 做只读账户/持仓 gate 和受控 dry-run，不在本次自动执行。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有根据历史收益筛选参数，仅修复事件顺序、状态持久化、成交时间和执行限制差异。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：本轮目标已完成，继续在同一范围追加规则价值低。
- 原因：两个用户指定差异已经实现并通过独立复核；后续问题属于新的执行安全或编排课题，应单独立项。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线存在并行研究，按约定仅写唯一 stage 文件。
- 是否更新 `research/registry.md`：否；由后续合入者统一更新。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未启用正式实盘，也未形成新的回测正式候选。

