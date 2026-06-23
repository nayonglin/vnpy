# Stage064 候选碰撞闸门审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 06:43 CST` 初次生成，`06:45 CST` 复跑校验
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：预提交候选闸门、反过拟合审计、只读复用历史产物；不是真实组合引擎
- 是否重要突破：否；这是路线收束和边界更新，不是收益/回撤突破
- 是否触发A/B：否；`should_run_true_engine_now_count=0`

## 外部调研与判断

- 参考资料：
  - MDPI `Analysis of a Global Futures Trend-Following Strategy`：趋势跟随是路径依赖系统，应在多市场状态下看鲁棒性。
  - Clare/Seaton/Smith/Thomas `Trend Following, Stop Losses, and the Frequency of Trading`：简单趋势规则和止损/交易频率之间存在 whipsaw 与成本风险，止损不是天然增益。
  - Optimus Futures stop-loss 文章：止损应定义交易想法失效点，而不是情绪化或任意距离。
  - GitHub `TradersPost/pinescript` 示例：移动止损、方向翻转退出是常见实现模式，但只能证明“常见”，不能证明适配本线 C9 右尾分布。
- 我的判断：时间止损、保本、移动止损、reentry candle 质量过滤都具备表面第一性理由，但它们和本线已失败的 `no-follow` 降仓、opening-range 硬退出、默认最小风险恢复、确认后保本、stop/retry OHLCV 分支高度同构。当前没有新增独立信息源时继续写真引擎，主要是在旧失败形态上换名字，过拟合风险高。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage064_candidate_collision_gate_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `target_return_retention_pct=80.0`
  - `target_dd_improvement_pp=5.0`
  - 候选闸门维度：`structural_collision`、`cuts_right_tail`、`threshold_variant_risk`、`data_coverage_blocked`、`no_new_information`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage008/009/013/019/046 全周期曲线 `2018-01-02` 至 `2026-06-15`；复用 Stage051/053/054/058/062/063 只读产物。
- 账户规模：官方正式 C9/15w，`150,000`。
- 成本口径：复用既有 true-engine / upper-bound 产物原始成本口径；本阶段不新增成交、不改成本。
- 样本过滤：无新增交易样本过滤；候选只做预提交闸门。
- 策略/归因口径：
  - 官方基准：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
  - 候选审计：`entry_day_time_stop_no_progress`、`confirmed_breakeven_or_tight_trail`、`stop_retry_reentry_candle_quality_filter`、`member_rank_dce_rebind`、`entry_time_orderbook_liquidity_state`

## 结果

- 期末权益：官方基准 `39,176,437.60`；本阶段无新 C 版本期末权益。
- 总收益：官方基准 `26017.6251%`；本阶段无新 C 版本总收益。
- 最大回撤：官方基准 `-45.0827%`；目标闸门要求至少改善 `5pp` 且收益保留 `80%+`。
- Sharpe：官方基准 `1.6331`。
- 总滑点：官方基准 `2,730,130`。
- 总交易次数：官方基准 `787`。
- 胜率：官方基准日胜率 `53.2560%`，closed-lot 胜率参考 `36.0902%`。
- 其他关键指标：
  - `candidate_count=5`
  - `should_run_true_engine_now_count=0`
  - `reject_before_true_engine_count=3`
  - `data_blocked_or_data_first_count=2`
  - `prior_strict_candidate_pass_count=0`
  - Stage009 opening-range 硬退出回撤改善 `6.8986pp`，但收益保留仅 `40.2072%`。
  - Stage008 no-follow 半仓收益保留 `77.6488%`，最大回撤恶化 `1.1288pp`，broker10 恶化 `7.4484pp`。
  - Stage019 no-follow 80% 轻削收益保留 `78.8296%`，最大回撤恶化 `2.1625pp`。
  - Stage046 确认后保本收益保留 `77.7088%`，最大回撤恶化 `17.7228pp`，broker10 恶化 `22.5269pp`。
  - Stage054 slow/deep reentry 乐观跳过目标后收益保留 `96.5125%`，但最大回撤恶化 `7.9091pp`，目标 reentry lot PnL 为 `+1,361,035.60`。
  - Stage058 reentry OHLCV 已全量 ready `54/54`，但最大单变量绝对 Spearman 仅 `0.1835`，integrated reentry PnL `+2,697,297.00`，不是可交易坏质量信号。
  - Stage063 DCE HTTP direct `data_ready_count=0`，DCE member missing 净 PnL `+14,851,026.20`，公共 HTTP 数据修复不 ready。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_report_stage064_candidate_collision_gate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_summary_stage064_candidate_collision_gate_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_decision_stage064_candidate_collision_gate_audit_v1.json`
- candidate matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_candidate_collision_matrix_stage064_candidate_collision_gate_audit_v1.csv`
- supplemental evidence：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_supplemental_evidence_stage064_candidate_collision_gate_audit_v1.csv`
- equity/drawdown/broker10 chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_path_drawdown_broker_overlay_stage064_candidate_collision_gate_audit_v1.png`
- frontier chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_frontier_gate_chart_stage064_candidate_collision_gate_audit_v1.png`
- collision heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_collision_heatmap_stage064_candidate_collision_gate_audit_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage064_candidate_collision_gate_audit/qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit_prior_minute_atlas_montage_stage064_candidate_collision_gate_audit_v1.png`

## 结论

- 本阶段结论：`stage064_reject_colliding_minute_stop_variants_require_new_information`。不再把时间止损、确认后保本/紧 trailing、stop/retry reentry candle quality 这三类旧形态包装成新真引擎；会员持仓和 orderbook/liquidity 方向只允许数据先行。
- 是否进入下一步：进入，但不是进入旧形态参数救援；下一步只允许点时化 orderbook/spread/queue/trade-flow 或授权/vendor member-rank 数据的固定 spec 只读审计。
- 下一步：优先寻找或构建入场/重入当刻可见的盘口流动性数据源；若无数据源，暂停新增分钟规则真引擎，避免从 historical closed-lot 亏损 cohort 继续反推规则。

## 过拟合反思

- 运行前判断：否，本阶段目的就是预声明候选闸门，先用既有失败证据阻止重复试错，而不是按结果补参数。
- 运行后判断：否。
- 原因：没有新增阈值扫描、没有产品/年份/方向切片、没有用历史亏损样本反推新规则；相反，5 个候选中 `0` 个允许立即进入 true engine。

## 继续价值反思

- 运行前判断：有价值，因为 Stage063 关闭 DCE 公共 HTTP 后，需要判断是否回到 Stage045 replay 子集还是转数据源。
- 运行后判断：仍有价值，但价值已集中到“新增独立点时化信息源”，不是旧价格路径风控形态。
- 原因：资金曲线显示旧分钟风控形态普遍砍掉 `2024-2025` 右尾或恶化 `2022-2023` 回撤；frontier 图显示没有旧碰撞路线同时满足收益保留 `80%+` 与回撤改善 `5pp+`。继续做同形态真引擎大概率是过拟合，继续做数据源则仍可能接近目标。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage064 结论和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段不是跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无新候选回测、无正式候选、无重要突破。
