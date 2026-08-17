# Stage225：生产数据回执精确下一交易日契约修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：C9/15w 正式实盘安装前执行链路修复
- 记录时间：2026-08-18 02:37（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_production_live` / `codex/stage223-stage902-iso-bf6f`
- 阶段性质：生产数据契约与 fail-closed 门禁修复，不改策略 alpha
- 是否重要突破：否；修复的是 Stage173 前瞻数据与 daily receipt 的语义错配
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本问题是仓库内部 Stage173、Stage947、production asset inventory 和 daily receipt 的专有契约冲突；使用当前生产日志、真实只读数据和源码追踪定位，不以外部资料替代生产证据。
- 我的判断：完整交易日信号目标应继续严格绑定 `target_cutoff_date`；主力映射和数据库允许最多领先到交易日历声明的“精确下一交易日”，因为夜盘会预先出现下一交易日映射/日线行。任何超过下一交易日、两份映射最大日不一致、已完成行情日期落后或前瞻日历无效仍应 fail-closed。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `qmt_roll_official_live_production_assets.py`：拆分已完成目标日字段与映射最大日字段；映射最大日仅允许目标日或精确下一交易日，且 CSV/Stage173 summary 必须一致。
  - `qmt_roll_official_live_daily_data_receipt.py`：数据库最大日仅允许目标日或 inventory 已验证的精确下一交易日。
  - `tests/test_stage179_production_assets.py`：新增映射/数据库精确下一交易日允许与越界拒绝回归。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：本阶段不跑策略回测；生产回执目标日 `2026-08-17`，精确下一交易日 `2026-08-18`。
- 账户规模：15 万正式口径。
- 成本口径：不涉及。
- 样本过滤：不涉及。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，未改信号、品种、方向、手数、0.5R 止损或一次重试。

## 结果

- 期末权益：不适用（未回测）。
- 总收益：不适用（未回测）。
- 最大回撤：不适用（未回测）。
- Sharpe：不适用（未回测）。
- 总滑点：不适用（未回测）。
- 总交易次数：0（本阶段未调用订单 API）。
- 胜率：不适用（未回测）。
- 其他关键指标：TDD 两个真实正向用例均先以预期 freshness mismatch 失败再修复；22 项 production asset 测试通过；32 个正式生产测试套件 `848 passed + 692 subtests passed`；真实生产只读构建探针通过，target=`2026-08-17`、mapping/database max=`2026-08-18`、next session=`2026-08-18`。

## 输出文件

- report：本 stage 记录。
- summary：待独立复审、两次正式只读 qualification 与 Stage948 激活后补充运行态结论。
- orders：无；send/cancel/order API 均为 0。
- daily：现有旧 daily receipt 仍因旧 commit/manifest 绑定无效；新候选通过资格认证后由正式 Stage947 support job 重发。
- quality：当前代码回归全绿，生产 7 个 launchd job 已在无 PID 前提下受控 bootout。

## 结论

- 本阶段结论：根因不是 AP/SI 信号或 CTP，而是 target-day 回执把合法的 exact-next-session 数据误判为未来污染；最小修复保留了越界 fail-closed。
- 是否进入下一步：是。
- 下一步：独立复审；提交 clean HEAD；两次正式只读 qualification；Stage948 prepare/activate；正式 postclose-precompute 生成新 daily receipt；核验 AP/SI 和 0.5R/一次重试监管已武装且初始订单 API 为 0。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只修数据时间语义和执行门禁，不依据收益、单品种表现或单日结果挑参；允许范围由交易日历的精确下一交易日决定，不是宽松 TTL 或任意未来日。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：不修复则 Stage947 永远无法为新 release 生成 daily receipt，Stage945 会持续正确地 fail-closed，AP/SI 与日内止损无法自动运行；修复后仍保留超过下一交易日的硬拒绝。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；待实盘激活和运行态证据闭环后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；这是单线生产控制面修复，待正式激活后再决定是否摘要。
