# Stage222 C9 实盘成交时间与手数对齐候选

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：日盘；线上稳定版隔离候选，禁止报单/撤单 API
- 记录时间：2026-08-09 14:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage221_production_live` / `codex/stage221-production-live`
- 基线提交：`368042e0f145cad80bdee5d0fc8f0c22074650ac`
- 阶段性质：生产语义修复与发布候选，不修改 alpha
- 是否重要突破：否；关闭已识别的回测/实盘语义偏差
- 是否触发A/B：否；不属于新策略或参数优化

## 外部调研与判断

- 参考资料：vn.py 官方 `vnpy/trader/object.py` 中 `TradeData.datetime` 是成交对象时间字段；`ContractData.max_volume` 是合约单笔最大委托量字段：
  - https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py
  - https://github.com/vnpy/vnpy/blob/master/CHANGELOG.md
- 我的判断：账本的 `generated_at` 只能代表本地落盘/观察时间，不能替代真实成交时间；入场后行情回放边界必须优先使用成交回报时间。取消本地固定 20 手限制后，仍必须保留合约 `max_volume`、整数手、Stage902/Stage931 readiness、持仓、活动委托、未知委托和日内次数闸门。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `qmt_roll_official_live_phase_d_config.py`：`max_single_order_volume=0`，明确 0 表示取消本地固定手数上限。
  - `run_qmt_roll_stage905_official_live_executor_dry_run.py`：仅当本地限制大于 0 时执行该限制。
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：从去重后的有价成交回报中提取最早真实成交时间；初始成交、撤单后迟到成交、最终对账三条聚合账本路径均写入 `first_trade_at`。
  - `qmt_roll_official_live_execution_ledger.py`：对同一 position epoch/cycle 的全部部分成交再次聚合全局最早时间，兼容 `first_trade_at`、旧 `broker_trade_at` 和 `trade_at`。
  - `run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`：行情回放入口优先级改为 broker epoch、账本真实成交时间、broker/shadow 成交时间，历史账本才回退到 `generated_at`；不再用纯日期作为入场 cutoff；同 epoch cutoff 变化、账本损坏均在状态变更前 fail-closed；WAL 改为先 fsync 再替换内存 store。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：`PhaseDHardLimits.max_single_order_volume: 20 -> 0`。
- 删除参数：无；保留字段用于兼容可配置正数上限。
- 测试变更：新增真实成交早于账本落盘、最早分笔成交时间、21 手放行且 101 手被合约 max=100 阻断的回归测试。
- 资格测试修复：`test_retry_archives_original_receipt_and_binds_retry_identity` 不再把 `schedule_date` 永久写死为 2026-08-03；夹具改为运行当天，但生产代码的跨日 retry fail-closed 合同保持不变。

## 回测/归因参数

- 数据区间：不适用；本阶段未运行回测。
- 账户规模：线上 C9/15w 口径，不改变资金参数。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：只修复实盘执行语义，不改变 C9 0.5R 阈值、重试次数、止损价格或选品逻辑。

## 结果

- 期末权益：不适用；未运行回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - TDD 红灯：4 个新语义用例修复前 `2 FAIL + 2 ERROR`。
  - 最小实现后新用例：`4/4 passed`。
  - 首轮精确提交独立审查发现 `P0=5`：跨事件最早成交时间、旧账本纯日期回退、既有 state cutoff 迁移、损坏账本、WAL 失败后 store 污染；均已先复现红灯后修复，首轮候选已作废。
  - Stage904/905/931 与 execution-ledger 原生产回归及新增资格套件用例：`232/232 passed`。
  - 首次完整资格编排在进入 CTP 前被生产资产测试阻断：隔离 worktree 缺 `.vntrader/database.db`；补齐隔离运行资产后，剩余唯一失败是 Stage947 测试硬编码 2026-08-03 的过期夹具。生产跨日阻断未放宽，修复后 Stage947 `38 passed + 25 subtests passed`。
  - 资格包要求的完整测试、两次正式 CTP 只读抓取、独立审查、发布清单和激活回执必须在候选提交冻结后生成；此文件不伪造尚未生成的发布证据。
  - 订单 API：`send_order=0`、`cancel_order=0`；本阶段只执行本地测试和只读检查。

## 输出文件

- report：本阶段记录文件。
- summary：提交冻结后生成外部生产 qualification bundle。
- orders：无。
- daily：无。
- quality：提交冻结后生成独立审查 JSON、双次正式 CTP 只读证据、release manifest 与 activation receipt。

## 结论

- 本阶段结论：生产候选的最小修复方向成立。线上原有 durable state、账本锁、校验和和 fail-closed 结构全部保留；未把开发分支旧实现整体覆盖到线上。
- 是否进入下一步：是；先冻结候选提交，再完成独立审查和正式资格包。只有 `P0=0/P1=0` 且双次 CTP 只读验证通过才允许 Stage948 安装。
- 下一步：构建资格包，生成 manifest/receipt，确认线上 7 个任务静默后通过 Stage948 prepare/activate，不手工 bootstrap/kickstart。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有根据历史收益、日期、品种、方向或 R 参数调优；改动来自回测/实盘因果时序合同和用户明确的手数一致性要求。新增测试使用合成边界条件，不选择盈利样本。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：真实成交到本地落盘之间的数秒窗口会直接决定初始止损是否漏触发，属于生产正确性问题；取消固定 20 手限制同时保留交易所/合约和运行态闸门，符合用户要求且不扩展 alpha。

## 合入建议

- 是否更新本线 `LINE.md`：否；同一研究线还有开发工作区并行记录，按规则只写唯一 stage 文件，合入者后续统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；候选尚未完成正式资格和激活，当前不写重要合入摘要。
