# Stage162 TqSdk 单请求 proofed conversion smoke

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:10`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 授权分钟包单请求交付验证
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk 历史/行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html`
  - Nasdaq Data Link Chinese Futures Data：`https://data.nasdaq.com/databases/DY8`
- 我的判断：TqSdk 技术上可以作为分钟 K、volume、open_interest 的潜在来源，但当前线能否使用取决于 Stage152 raw/normalized/proof 三件套和 Stage153 proof/schema/hash/window coverage。本阶段没有重复确认正式版身份，而是顺着 Stage161 的结论，直接做一个最小交付验证：如果 TqSdk 能提供真实有量的 1m 数据，就写入 expected incoming 路径；如果成交量或 proof 条件不满足，必须硬停，不能把外部可取到的 K 线当成可交易数据。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage162_tqsdk_single_request_proofed_conversion_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增执行环境开关 `STAGE162_REQUEST_ID` 与 `STAGE162_WRITE_INCOMING`，用于指定单个 Stage152 request 和是否允许在三件套合格时写入 `incoming/`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：单请求 `stage152_req_0011_jm2509_DCE_20250709`，`2025-07-09 08:30:00` 至 `2025-07-09 14:03:00`，查询扩展为 `2025-07-09 07:30:00` 至 `2025-07-09 15:03:00`。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160/161 官方路径总滑点口径；本阶段不运行新回测。
- 样本过滤：只选 1 个 Stage152 request 做交付 smoke；显式指定 `STAGE162_REQUEST_ID=stage152_req_0011_jm2509_DCE_20250709`，选择依据是数据交付优先级与可验证性，不按收益、品种表现或回撤贡献筛选。
- 策略/归因口径：TqSdk `TqBacktest + get_kline_serial(duration_seconds=60)` 单请求拉取、字段标准化、成交量闸门、expected raw/normalized/proof 写入审计；不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage162_tqsdk_single_request_delivery_not_ready_no_rule`
  - `next_best_action=repair_tqsdk_source_or_wait_authorized_stage152_package`
  - `request_id=stage152_req_0011_jm2509_DCE_20250709`
  - `vt_symbol=jm2509.DCE`
  - `exchange=DCE`
  - `selected_request_count=1`
  - `credential_present=1`
  - `tqsdk_import_ok=1`
  - `fetch_status=extracted`
  - `tqsdk_fetch_succeeded=1`
  - `raw_row_count=225`
  - `normalized_row_count=169`
  - `positive_volume_row_count=0`
  - `write_incoming_enabled=1`
  - `expected_files_written=0`
  - `raw_written=0`
  - `normalized_written=0`
  - `proof_written=0`
  - `stage153_full_package_ready=0`
  - `current_package_promotion_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `objective_completion_proven=0`
  - `side_effect_count=0`
  - `visual_output_count=5`
  - `max_broker10_margin_to_equity_pct=111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_report_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_summary_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- selected request：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_selected_request_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- fetch status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_fetch_status_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- raw sample：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_raw_bars_sample_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- normalized sample：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_normalized_bars_sample_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- delivery audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_delivery_audit_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_gate_status_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage162_tqsdk_single_request_proofed_conversion_smoke/qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_decision_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：5 张 PNG 视觉产物均非空：
  - `qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_official_path_conversion_status_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.png`
  - `qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_selected_request_kline_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.png`
  - `qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_selected_request_volume_oi_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.png`
  - `qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_delivery_matrix_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.png`
  - `qmt_roll_stage162_c9_minrisk_tqsdk_single_request_proofed_conversion_smoke_gate_status_matrix_stage162_tqsdk_single_request_proofed_conversion_smoke_v1.png`

## 视觉分析

- 官方路径 conversion status 只用于资金曲线/基线视觉跟踪；Stage162 没有改变交易路径，目标仍未完成。
- selected request kline 图显示价格序列可抽取，说明这不是完全无行情的问题。
- selected request volume/OI 图显示 OI 有数，但成交量全部为 0；这在分钟级进出场研究里是硬伤，因为量能、真实 bar 活跃度和 proofed delivery 不能成立。
- delivery matrix 显示 `credential_present=1`、`tqsdk_import_ok=1`、`normalized_row_count=169` 都通过，但 `positive_volume_row_count=0`、`expected_files_written=0` 失败，因此 `incoming/` 没有写入任何 raw/normalized/proof 文件。
- gate matrix 显示安全闸门通过：`strategy_rule_created=0`、`true_engine_run=0`、`order_api_called=0`；数据闸门失败，不能进入 Stage153 或策略实验。

## 结论

- 本阶段结论：TqSdk 当前 backtest 拉取路径能拿到 `jm2509.DCE` 的分钟价格和 OI，但本次交付样本 `positive_volume_row_count=0`，不满足 Stage152/153 对真实分钟 OHLCV 的要求。脚本按设计没有写入 `incoming/`，也没有生成策略规则。
- 是否进入下一步：可以继续，但下一步仍是数据源修复，不是策略规则。
- 下一步：优先修复 TqSdk/source 路径，确认是否能取到真实成交量/成交额；如果不能，应等待授权 Stage152 package。只有当至少一个 request 写齐 raw/normalized/proof 且 Stage153 通过后，才允许进入 feature builder 或分钟级信号候选。

## 过拟合反思

- 运行前判断：否。Stage162 是单请求数据交付 smoke，不用收益结果选择规则；指定 request 是为了验证 Stage152 三件套路径，不是按 PnL 或回撤挑样本。
- 运行后判断：否。没有扫参数、没有按品种/年份/盈亏反推阈值、没有 true engine、没有候选规则；成交量为 0 直接硬停，避免把不可交易数据包装成 alpha。
- 原因：本阶段所有判断来自数据可用性和 lineage/proof 闸门，而非收益曲线拟合。

## 继续价值反思

- 运行前判断：有。Stage161 判断 TqSdk 可能可用但必须 proofed conversion，因此需要一个最小真实拉取来区分“可取价格”和“可作为权威 OHLCV 交付”。
- 运行后判断：仍有价值，但价值集中在数据工程修复或等待授权包；继续直接做策略没有价值。
- 原因：本次已经证明当前 TqSdk backtest 路径的数据质量不足以支撑分钟量能特征或 Stage153 入库。继续强行研究规则会把数据缺陷和历史标签选择误当成信号。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage162 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃。
