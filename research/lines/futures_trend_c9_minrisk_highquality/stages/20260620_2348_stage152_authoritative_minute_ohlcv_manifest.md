# Stage152 权威分钟 OHLCV 清单和覆盖闸门

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据合同 / 授权分钟K清单 / 非规则候选
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Databento OHLCV schema：https://databento.com/docs/schemas-and-data-formats/ohlcv
  - Databento Historical API：https://databento.com/docs/api-reference-historical/client/historical
  - CME DataMine：https://www.cmegroup.com/datamine.html
  - IBKR historical bars：https://interactivebrokers.github.io/tws-api/historical_bars.html
  - FirstRateData：https://firstratedata.com/
- 我的判断：权威分钟 OHLCV + real volume/OI 是当前最贴近本线目标的数据路线，因为它能服务分钟级进出场并避开 Stage102/150 internal replay 的事后标签。但供应商可能只返回有成交的分钟 bar，所以必须把 no-trade interval、sequence gap、timestamp convention 和 raw/proof/hash 固化进清单；在真实授权数据到货前，不能创建任何交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage152_authoritative_minute_ohlcv_manifest.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/102/151 输出；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：不新增交易过滤；只把 Stage102 的 `219` 笔上下文展开成固定数据覆盖窗口。
- 策略/归因口径：数据合同，不创建规则，不运行 true engine，不触发 A/B，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage152_authoritative_minute_ohlcv_manifest_ready_no_data_no_rule`
  - next_best_action：`stage153_authoritative_minute_ohlcv_intake_validator_after_real_data`
  - manifest_contract_ready：`1`
  - stage102_context_order_count：`219`
  - required_window_count：`657`
  - request_template_count：`233`
  - field_schema_count：`28`
  - hard_field_count：`26`
  - unique_vt_symbol_count：`146`
  - unique_product_count：`26`
  - unique_exchange_count：`4`
  - right_tail_required_window_count：`54`
  - bottom_loss_required_window_count：`54`
  - maxdd_required_window_count：`72`
  - low_resolution_required_window_count：`279`
  - event_time_missing_context_order_count：`18`
  - estimated_required_1m_bar_count：`108,477`
  - max_window_duration_minutes：`1,358`
  - data_file_present_count：`0`
  - normalized_file_present_count：`0`
  - proof_file_present_count：`0`
  - coverage_ready_window_count：`0`
  - coverage_gate_pass_count：`7/17`
  - stage153_intake_allowed：`0`
  - current_package_promotion_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - side_effect_count：`0`

## 视觉观察

- official path manifest status 图显示资金/回撤/broker10 曲线仍只是基准底图；下方状态条里 `windows=657`、`requests=233` 已生成，但 `raw_ready=0`、`coverage=0`、`rule=0`、`engine=0`，说明研究尚停在数据合同层。
- required window heatmap 显示三类窗口对每笔上下文一视同仁展开，没有按收益结果挑样本；right-tail、bottom-loss、maxDD 和 low-resolution 只是覆盖优先级，不是交易条件。
- field schema matrix 显示字段合同已定义，但 `current_ready=0`；这符合本阶段定位，即先固定验收标准，等真实数据到货再做 Stage153 intake。
- request template product chart 用 priority score 排出 vendor 请求顺序，作用是采购/验收排序，不是产品筛选规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_report_stage152_authoritative_minute_ohlcv_manifest_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_summary_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_field_schema_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_required_window_contract_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_request_manifest_template_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_coverage_gate_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_operator_intake_checklist_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage152_authoritative_minute_ohlcv_manifest/qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest_gate_status_stage152_authoritative_minute_ohlcv_manifest_v1.csv`
  - 5 张视觉图：official path manifest status、field schema matrix、required window heatmap、request template product chart、gate status matrix。

## 结论

- 本阶段结论：Stage152 已把 Stage151 选出的 `authoritative_minute_ohlcv_volume` 路线落成可执行的数据合同。`657` 个必需窗口和 `233` 个请求模板说明下一步需要真实授权数据，而不是继续在本地 replay 标签里挖规则。当前 `stage153_intake_allowed=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。
- 是否进入下一步：有条件进入。
- 下一步：只有真实 raw/proof/normalized 文件到货后，才运行 Stage153 intake validator；否则继续禁止分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益优化、阈值扫描、品种/年份/方向筛选、true engine 或交易规则；right-tail/bottom-loss/maxDD 只用于数据覆盖优先级，不能作为规则输入。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：这一步把“要什么真实分钟数据、如何验收、缺什么就不能研究”固定下来，能防止后续拿不可靠的本地 replay/零量分钟条继续过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
