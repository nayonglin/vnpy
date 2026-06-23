# Stage170 bottom-loss 补完 tick 聚合 proofed delivery

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 02:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：权威分钟 OHLCV 数据补齐与验收；不是策略版本
- 是否重要突破：否。它是必要数据地基推进，但还不是降回撤候选。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqBacktest 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
  - CFM trend following 右尾凸性资料：`https://www.cfm.com/wp-content/uploads/2022/12/188-2018-Making-fat-right-tails-fatter-with-trend-following-most-of-the-time.pdf`
- 我的判断：趋势系统的长期价值往往来自右尾凸性，降低回撤不能靠历史亏损标签直接削仓，也不能砍掉 right-tail 复利来源。Stage169 已把 right-tail 覆盖补满，本阶段再补满 bottom-loss，是为了让后续视觉 atlas 同时看见右尾和左尾，而不是从单侧亏损样本反推规则。TqSdk tick 聚合继续可用，但必须保留 raw/proof/schema/hash provenance；W3C PROV-DM 支持这种可追溯链路。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE170_MAX_REQUESTS`，默认 `12`
  - `STAGE170_WRITE_INCOMING`，默认 `1`
  - `STAGE170_OVERWRITE_EXISTING`，默认 `0`
  - `STAGE170_MAX_SECONDS_TICK`，默认 `90`
  - `STAGE170_TICK_DATA_LENGTH`，默认 `120000`
  - `STAGE170_MIN_NORMALIZED_ROWS`，默认 `10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage152 manifest 中剩余 bottom-loss 覆盖缺口；本批 `2021-12-17` 至 `2026-04-30`，覆盖 CZCE/DCE/SHFE。
- 账户规模：沿用官方 C9 路径统计，不改变资金口径。
- 成本口径：沿用官方 C9 路径统计，`total_slippage=2730130.0`。
- 样本过滤：仅选择 Stage153 尚未 ready 且 `bottom_loss_window_count > 0` 的 request；这是 manifest 覆盖义务，不是交易筛选条件。
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
  - Stage170：`decision=stage170_bottom_loss_completion_tick_aggregate_delivery_written_run_stage160_153_no_rule`
  - `ready_before_count=36`
  - `remaining_before_count=197`
  - `selected_request_count=12`
  - `selected_bottom_loss_window_count=30`
  - `selected_maxdd_window_count=0`
  - `selected_right_tail_window_count=0`
  - `fetch_attempted_count=12`
  - `fetch_extracted_count=12`
  - `delivery_success_count=12`
  - `delivered_bottom_loss_window_count=30`
  - `expected_files_written=36`
  - `raw_written_count=12`
  - `normalized_written_count=12`
  - `proof_written_count=12`
  - `raw_tick_row_count=188197`
  - `normalized_row_count=1947`
  - `positive_volume_row_count=1938`
  - `window_precheck_count=30`
  - `window_precheck_pass_count=30`
  - `window_precheck_fail_for_written_count=0`
  - Stage160 复验：`present_expected_file_count=144/699`，`request_complete_triplet_count=48/233`，`request_partial_triplet_count=0`，`unexpected_file_count=0`
  - Stage153 复验：`request_ready_count=48/233`，`window_coverage_pass_count=132/657`，`right_tail_window_coverage_pass_count=54/54`，`bottom_loss_window_coverage_pass_count=54/54`，`maxdd_window_coverage_pass_count=30/72`，`low_resolution_window_coverage_pass_count=60/279`
  - Stage153 质量：`proof_json_valid_count=48`，`proof_raw_sha256_match_count=48`，`proof_identity_match_count=48`，`proof_no_trade_policy_declared_count=48`，`normalized_schema_pass_count=48`，`forbidden_provenance_marker_count=0`
  - Stage153 仍然：`stage154_feature_build_allowed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_report_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_summary_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.csv`
- selected requests：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_selected_requests_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.csv`
- request run status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_request_run_status_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_delivery_audit_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.csv`
- window precheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage170_bottom_loss_completion_tick_aggregate_proofed_delivery/qmt_roll_stage170_c9_minrisk_bottom_loss_completion_tick_aggregate_proofed_delivery_window_precheck_stage170_bottom_loss_completion_tick_aggregate_proofed_delivery_v1.csv`
- quality：Stage160/Stage153 已重跑并覆盖更新同名 summary/audit/visual 输出。

## 视觉检查

- Stage170 5 张 PNG 均非空：
  - delivery matrix：`std_sum=304.370238`
  - gate status：`std_sum=281.664871`
  - official path：`std_sum=106.169747`
  - selected bottom-loss priority：`std_sum=208.918204`
  - window precheck：`std_sum=263.541528`
- Stage160 5 张 PNG 均非空。
- Stage153 5 张 PNG 均非空。
- 视觉判断：
  - 官方资金曲线、回撤和 broker10 曲线未改变，说明本阶段没有引入策略收益变化。
  - selected bottom-loss priority 图显示本批只补 bottom-loss，未混入 maxDD/right-tail。
  - delivery matrix 显示 12 个 request 的 raw、normalized、proof 全部写入，没有 partial triplet。
  - window precheck matrix 显示 30 个 bottom-loss 窗口全部正量通过；其中包含 CZCE 白糖/锰硅、DCE 焦煤/生猪、SHFE 螺纹/橡胶/铜，覆盖 2021、2022、2023、2024、2025、2026 多个年份。

## 结论

- 本阶段结论：Stage170 成功把 bottom-loss 覆盖补满到 `54/54`。当前线已经拥有完整 right-tail 与 bottom-loss 两侧尾部样本，权威分钟数据地基推进到 `48` 个 request / `132` 个窗口。
- 是否进入下一步：进入下一步数据覆盖，不进入策略规则。
- 下一步：优先补 maxDD 缺口，当前 `maxdd_window_coverage_pass_count=30/72`，剩余 `42` 个 maxDD 窗口；然后继续补低分辨率窗口。Stage153 全包通过前，继续禁止 Stage154 feature builder、分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage170 只补 Stage153 剩余 bottom-loss 覆盖缺口，不调阈值、不跑交易引擎、不把亏损标签变成交易条件。
- 运行后判断：否。结果只是数据覆盖从 `36/233` request 推进到 `48/233` request，bottom-loss 从 `24/54` 推进到 `54/54`；没有任何收益指标优化动作。
- 原因：bottom-loss 是覆盖标签，不是交易规则。后续必须用它做视觉对照和反证，不能从亏损 cohort 中直接提取过滤器。

## 继续价值反思

- 运行前判断：有。right-tail 已补满后，如果不补 bottom-loss，后续视觉 atlas 会偏右尾，不能解释回撤来源。
- 运行后判断：有。两侧尾部样本现在都满覆盖，下一步补 maxDD 后，才有资格更完整地比较“高质量信号时用最小风险搏最大收益”的分钟结构是否普世。
- 原因：目标要求既降低最大回撤又保留 `80%` 以上收益，必须同时看右尾、底部亏损和最大回撤段；单看一侧必然容易过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage170 摘要。
- 是否更新 `research/registry.md`：否，非正式候选、非路线合并、非重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非重大突破。
