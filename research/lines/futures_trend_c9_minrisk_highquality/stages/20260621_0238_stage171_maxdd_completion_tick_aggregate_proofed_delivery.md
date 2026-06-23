# Stage171 maxDD 补完 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 02:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。它补满关键最大回撤窗口，但仍只是数据地基。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqBacktest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
  - CFM 趋势右尾凸性资料：`https://www.cfm.com/wp-content/uploads/2022/12/188-2018-Making-fat-right-tails-fatter-with-trend-following-most-of-the-time.pdf`
- 我的判断：趋势系统的最大回撤通常来自震荡、反复止损、跨品种同向失效和波动切换，但收益底座又来自少数不可预知右尾。Stage169/170 已补满 right-tail 与 bottom-loss，本阶段补满 maxDD，是为了在同一权威分钟源上观察“右尾、左尾、最大回撤段”三者的共同结构。maxDD 只作为覆盖义务和视觉审计索引，不能直接转成削仓/过滤规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage171_maxdd_completion_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE171_MAX_REQUESTS`，默认 `15`
  - `STAGE171_WRITE_INCOMING`，默认 `1`
  - `STAGE171_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE171_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE171_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE171_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 maxDD 覆盖缺口；本批 `2022-08-25` 至 `2023-03-08`，覆盖 CZCE/DCE/SHFE。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：仅选择 Stage153 尚未 ready 且 `maxdd_window_count > 0` 的 request；这是 manifest 覆盖义务，不是交易筛选条件。
- 策略/归因口径：不创建交易规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130.0`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage171：`decision=stage171_maxdd_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=48`
  - `remaining_before_count=185`
  - `selected_request_count=15`
  - `selected_maxdd_window_count=42`
  - `selected_low_resolution_window_count=9`
  - `selected_bottom_loss_window_count=0`
  - `selected_right_tail_window_count=0`
  - `fetch_attempted_count=15`
  - `fetch_extracted_count=15`
  - `delivery_success_count=15`
  - `delivered_maxdd_window_count=42`
  - `delivered_low_resolution_window_count=9`
  - `expected_files_written=45`
  - `raw_written_count=15`
  - `normalized_written_count=15`
  - `proof_written_count=15`
  - `raw_tick_row_count=249748`
  - `normalized_row_count=2387`
  - `positive_volume_row_count=2385`
  - `window_precheck_count=42`
  - `window_precheck_pass_count=42`
  - `window_precheck_fail_for_written_count=0`
  - Stage160 复验：`present_expected_file_count=189/699`，`request_complete_triplet_count=63/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`
  - Stage153 复验：`request_ready_count=63/233`，`window_coverage_pass_count=174/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=72/72`，`low_resolution_window_coverage_pass_count=69/279`
  - Stage153 质量：`proof_json_valid_count=63`，`proof_raw_sha256_match_count=63`，`proof_identity_match_count=63`，`proof_no_trade_policy_declared_count=63`，`normalized_schema_pass_count=63`，`forbidden_provenance_marker_count=0`
  - Stage153 仍然：`stage154_feature_build_allowed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_report_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_summary_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_selected_requests_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_request_run_status_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_delivery_audit_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage171_maxdd_completion_tick_aggregate_proofed_delivery/qmt_roll_stage171_c9_minrisk_maxdd_completion_tick_aggregate_proofed_delivery_window_precheck_stage171_maxdd_completion_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage171 5 张 PNG 均非空：
  - delivery matrix：`std_sum=302.422168`
  - gate status：`std_sum=281.669026`
  - official path：`std_sum=105.990917`
  - selected maxDD priority：`std_sum=185.274853`
  - window precheck：`std_sum=263.076094`
- Stage160 5 张 PNG 均非空。
- Stage153 5 张 PNG 均非空。
- 视觉判断：
  - 官方资金曲线、回撤和 broker10 曲线未改变，说明本阶段没有引入策略收益变化。
  - selected maxDD priority 图显示本批只补 maxDD，顺带覆盖 9 个 low-resolution 窗口，未混入 right-tail/bottom-loss。
  - delivery matrix 显示 15 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
  - window precheck matrix 显示 42 个 maxDD 窗口全部正量通过；其中包含 `FG305`、`MA305`、`rb2305` 夜盘延伸窗口和 `cu2303` 跨日窗口。

## 结论

- 本阶段结论：Stage171 成功把 maxDD 覆盖补满到 `72/72`。当前线关键尾部覆盖已经达到 right-tail `54/54`、bottom-loss `54/54`、maxDD `72/72`，权威分钟数据地基推进到 `63` 个 request / `174` 个窗口。
- 是否进入下一步：进入下一步数据覆盖，不进入策略规则。
- 下一步：继续补低分辨率与其他非尾部窗口，当前全包仍是 `174/657`，低分辨率 `69/279`；Stage153 全包通过前，继续禁止 Stage154 feature builder、分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage171 只按 Stage153 剩余 maxDD 覆盖缺口补数据，不调阈值、不跑交易引擎、不把最大回撤年份或品种变成规则。
- 运行后判断：否。结果只是 maxDD 覆盖从 `30/72` 推进到 `72/72`，没有任何收益指标优化动作。
- 原因：maxDD 是审计索引，不是交易条件。尤其本批集中在 `2022-2023`，如果直接写年份/品种/交易所补丁，就会明显过拟合。

## 继续价值反思

- 运行前判断：有。没有 maxDD 分钟样本，后续无法用视觉 atlas 判断最大回撤段是否存在入场前/入场当刻可见的普世结构。
- 运行后判断：有。三类关键尾部样本已满，后续可以更稳地做只读 atlas，但全包覆盖仍不足，不能急着写规则。
- 原因：目标要求最大回撤下降且收益保留 `80%` 以上，必须先确认任何未来候选不会系统性切断 right-tail，也不能只是贴合 bottom-loss 或 maxDD 历史 cohort。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage171 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
