# Stage043 Official-Open Scan Replay Repair Audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 02:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：replay semantics 修复审计 / 不生成交易规则
- 是否重要突破：否，属于分钟 replay 基础设施修复，不是收益突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order 文档：`https://www.backtrader.com/docu/order/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - 郑商所夜盘 FAQ：`https://www.czce.com.cn/cn/ypzt/cjwtjd/webinfo/2014/11/1415698818009586.htm`
- 我的判断：
  - 成熟回测框架要求成交、bar 时间戳和事件处理顺序严格一致；否则会把时间口径差异误当成策略信号。
  - Stage042 已说明 raw timestamp 的夜盘时间与 official open 是两个不同角色：raw timestamp 可以解释成交价来源，但不必然等于 official intraday diagnostics 的事件扫描起点。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage043_official_open_scan_replay_repair_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增 replay 审计变体 `raw_price_official_open_scan`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage042 / Stage041 / Stage010 官方 C9/15w 输出
- 账户规模：`150000`
- 成本口径：沿用官方曲线，`total_slippage=2,730,130`
- 样本过滤：Stage042 `timestamp_ready=1` initial orders，共 `219` 笔
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 修复变体：成交价使用 raw/engine proxy price；C9/C2 事件扫描从 official open 的 Stage861 bar 开始。
  - 不改变开仓、平仓、手数、资金路径；same-exit 曲线只用于审计。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - timestamp-ready orders：`219`
  - raw stitched ready orders：`204`
  - raw stitched event match：`178/219 = 81.2785%`；若按 raw ready 口径为 `178/204 = 87.2549%`
  - repair event match：`215/219 = 98.1735%`
  - raw stitched mismatch：`41`，其中 `15` 为 missing raw timestamp，`26` 为 ready mismatch
  - repair residual mismatch：`4`
  - Stage042 pre-official mismatch：`18`
  - pre-official mismatch resolved by official-open scan：`16`
  - missing raw timestamp bar：`15/15` 在 official-open scan 口径下可复现官方事件
  - repair same-exit 期末权益：`39,176,437.60`
  - repair same-exit 最大回撤：`-45.0827%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_report_stage043_official_open_scan_replay_repair_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_summary_stage043_official_open_scan_replay_repair_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_replay_ledger_stage043_official_open_scan_replay_repair_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_path_chart_stage043_official_open_scan_replay_repair_audit_v1.png`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_event_diagnostic_stage043_official_open_scan_replay_repair_audit_v1.csv`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage043_official_open_scan_replay_repair_audit/qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_atlas_manifest_stage043_official_open_scan_replay_repair_audit_v1.csv`

## 结论

- 本阶段结论：
  - Stage043 证明 Stage041/042 的大部分 raw replay mismatch 是扫描起点口径问题：raw proxy price 可保留为成交价来源，但 official intraday event scan 应从 official open anchor 开始审计。
  - match 从 raw-ready `87.2549%` 修复到全样本 `98.1735%`，与 Stage041 official-open anchor 子集一致。
  - 剩余 `4` 笔 residual mismatch 全部是 replay 在 `09:00` 首根判成 `c2_stop`，而官方为 `no_intraday_event`。这指向首根 bar 内触发顺序、开仓首根是否允许 C2 stop、或 planned stop/layer stop 同步语义，不是策略信号。
- 是否进入下一步：进入下一阶段 replay 语义审计；不进入候选策略、不触发 A/B。
- 下一步：
  - 只审计剩余 `4` 笔 residual：同 bar open/high/low/close 顺序、C2 stop 是否跳过开仓首根、官方 planned stop 与 replay stop 的同步。
  - 在 event match 未达到可接受稳定前，继续暂停新增分钟进出场候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调参、没有筛品种/方向/年份、没有用最终盈亏选样本。
  - 只是把上一阶段的时间口径差异固定成一个可复验的 replay convention，并检查是否更接近官方事件账本。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - 一致性从 raw-ready `87.2549%` 推进到 `98.1735%`，说明 replay 基础设施在接近官方引擎。
  - 剩余误差集中到 `4` 笔 09:00 首根 C2 stop，问题足够聚焦，下一步有明确工程审计价值。
  - 这仍然是为后续普世分钟进出场规则打地基，而不是收益优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage043 结论与下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内 replay 修复，不是重要合入摘要。
