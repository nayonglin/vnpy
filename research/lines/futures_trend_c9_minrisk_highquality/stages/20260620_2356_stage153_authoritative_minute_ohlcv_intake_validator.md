# Stage153 权威分钟 OHLCV 到货验收器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:56 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：到货验收 / 数据闸门 / 非规则候选
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Databento OHLCV schema：https://databento.com/docs/schemas-and-data-formats/ohlcv
  - Databento OHLCV resampling：https://databento.com/docs/examples/basics-historical/ohlcv-resampling
  - Apache Parquet file format：https://parquet.apache.org/docs/file-format/
  - IBKR historical bars：https://interactivebrokers.github.io/tws-api/historical_bars.html
- 我的判断：Stage153 不能把“分钟缺口”直接解释成行情或 alpha。Databento 说明 OHLCV 是成交聚合，且多数供应商只在有成交区间发布 bar；IBKR 也提示期货 session 可能跨自然日。因此到货验收必须依赖 proof JSON 里的 `no_trade_bar_policy`、`timezone`、`session_calendar`、`request_start/end`，并用 Parquet metadata/schema 先验收文件，不允许先把数据送进策略特征。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage153_authoritative_minute_ohlcv_intake_validator.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage152 的 `233` 个 request 与 `657` 个 required windows；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：不新增交易过滤；只扫描 Stage152 约定的 `incoming/stage152_authoritative_minute_ohlcv/...` 到货路径。
- 策略/归因口径：数据验收，不创建规则，不运行 true engine，不触发 A/B，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage153_authoritative_minute_ohlcv_intake_blocks_missing_real_data_no_rule`
  - next_best_action：`deliver_real_authoritative_minute_ohlcv_files_then_rerun_stage153`
  - stage152_contract_loaded：`1`
  - request_audit_ready：`1`
  - request_count：`233`
  - required_window_count：`657`
  - raw_file_present_count：`0`
  - proof_file_present_count：`0`
  - normalized_file_present_count：`0`
  - proof_json_valid_count：`0`
  - proof_raw_sha256_match_count：`0`
  - proof_identity_match_count：`0`
  - proof_no_trade_policy_declared_count：`0`
  - normalized_schema_pass_count：`0`
  - request_ready_count：`0`
  - window_coverage_pass_count：`0`
  - right_tail_required_window_count：`54`
  - bottom_loss_required_window_count：`54`
  - maxdd_required_window_count：`72`
  - low_resolution_required_window_count：`279`
  - forbidden_provenance_marker_count：`0`
  - stage154_feature_build_allowed：`0`
  - current_package_promotion_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - side_effect_count：`0`

## 视觉观察

- official path intake status 图显示资金/回撤/broker10 仍只是基准底图；下方状态条里 `requests=233`，但 raw/proof/parquet/window pass/release 全部为 `0`，下游特征构建被阻断。
- request role presence heatmap 显示四个交易所的 raw/proof/normalized/request_ready 均为 `0`，不是某个交易所或品种局部缺口。
- canonical schema readiness matrix 显示 proof/schema 合同已定义，但 accepted request observed 为 `0`，说明没有任何真实文件通过验收。
- window coverage heatmap 显示 right-tail、bottom-loss、maxDD、low-resolution 全部 `0/N`，因此不能用任何窗口做视觉/策略解释。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_report_stage153_authoritative_minute_ohlcv_intake_validator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_summary_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_request_file_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_proof_json_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_normalized_schema_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_window_coverage_audit_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_operator_failure_queue_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage153_authoritative_minute_ohlcv_intake_validator/qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator_gate_status_stage153_authoritative_minute_ohlcv_intake_validator_v1.csv`
  - 5 张视觉图：official path intake status、request role presence heatmap、canonical schema readiness matrix、window coverage heatmap、gate status matrix。

## 结论

- 本阶段结论：Stage153 验收器已可运行，但当前没有任何真实授权分钟数据到货。`233` 个 request 的 raw/proof/normalized 三件套均为 `0`，`657` 个 required windows 覆盖通过数为 `0`，因此 `stage154_feature_build_allowed=0`，继续禁止分钟规则、true engine、A/B 或正式候选。
- 是否进入下一步：否，除非真实数据到货。
- 下一步：交付真实授权 raw 文件、proof JSON、canonical normalized Parquet 后重跑 Stage153；只有全部 request 与 required windows 通过后，才允许进入 Stage154 只读特征构建预检。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验收文件、proof、schema 和覆盖，不使用收益标签做阈值，不筛年份/品种/方向，不产生任何交易信号。right-tail/bottom-loss/maxDD 只作为覆盖必验项。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage153 把“真实数据未到不能继续分钟策略研究”从原则变成了可复跑闸门，避免未来拿零量分钟条、synthetic fixture 或无 provenance 文件继续过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
