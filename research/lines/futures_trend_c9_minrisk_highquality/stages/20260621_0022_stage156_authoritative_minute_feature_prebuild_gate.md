# Stage156 权威分钟特征构建前置闸门

- 时间：2026-06-21 00:22 CST
- line_id：`futures_trend_c9_minrisk_highquality`
- 脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage156_authoritative_minute_feature_prebuild_gate.py`
- 输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage156_authoritative_minute_feature_prebuild_gate/`
- 决策：`stage156_authoritative_minute_feature_prebuild_gate_blocked_no_real_data_no_rule`
- 是否重要突破版本：否。本阶段是数据/特征构建闸门，不是收益候选。

## 本次调研和判断结论

外部参考：

- Apache Arrow Parquet 文档：Parquet 可先检查 metadata、row group、schema、row count，再决定是否读取数据。
- Apache Parquet concepts：Parquet 的 row group / column chunk / page 结构适合列式验收和分层审计。
- pandas `Resampler.ohlc` 官方文档：OHLC 聚合要明确 open/high/low/close 的时间桶语义。
- vn.py `BarGenerator` / `BarData` GitHub 源码：1m bar 和多分钟 bar 的生成必须固定聚合语义，`volume/turnover/open_interest` 是真实交易信息字段。

判断：Stage156 不应该发明交易规则，也不应该在没有真实分钟数据时生成 feature table。正确动作是先固定“可进入特征层”的硬合同：真实授权 1m OHLCV + real volume/OI、Stage153 全窗口覆盖、闭合 bar 聚合语义、无未来泄漏、无 product/year 补丁、无最终盈亏标签。这个动作不是过拟合，因为它没有用当前样本调阈值，也没有根据 right-tail/bottom-loss 结果反推规则；它是在阻断不可信数据和未来泄漏。

## 本次版本改动

新增：

- `stage156_authoritative_minute_feature_prebuild_gate.py`
- `feature_contract`：10 个通用分钟特征合同，覆盖 price_path、volatility、participation、positioning、data_quality 五类。
- `aggregation_contract`：1m 到 5m/15m/30m 的闭合 bar 聚合规则，open 取首、high 取 max、low 取 min、close 取末、volume/turnover 求和、open_interest 取末。
- `leakage_overfit_guard`：9 条泄漏/过拟合硬禁令，包括最终盈亏、未来 MFE/MAE、post-event 标签、product/year 例外、right-tail/bottom-loss 标签、fixture/synthetic、数据 ready/missing 交易化、当前样本阈值搜索。
- `window_feature_readiness`：657 个 Stage152 required windows 的特征 readiness 审计。
- 5 张视觉图：官方资金路径 + gate 状态、feature family readiness、window readiness、leakage guard、gate matrix。

修改：

- 无正式配置修改。
- 无策略参数修改。
- 无交易规则修改。
- 无 true engine 修改。

删除：

- 无。

## 新增参数

- `feature_contract_count=10`
- `feature_family_count=5`
- `aggregation_contract_count=9`
- `leakage_guard_count=9`

这些不是交易参数，只是特征构建合同和审计字段。

## 修改参数

无。

## 删除参数

无。

## 回测和指标

本阶段没有运行新回测、没有创建候选、没有进入 true engine。以下为沿用 Stage153 官方路径资金曲线的审计指标，用于满足每阶段视觉跟踪，不代表 Stage156 产生了收益改进：

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- max broker10 margin/equity：`111.7365%`

新增结果：

- `stage153_request_count=233`
- `stage153_request_ready_count=0`
- `stage153_required_window_count=657`
- `stage153_window_coverage_pass_count=0`
- `stage155_case_expectation_pass_count=6/6`
- `stage155_unexpected_ready_count=0`
- `stage155_strategy_rule_allowed_count=0`
- `leakage_guard_pass_count=9/9`
- `feature_ready_window_count=0`
- `positioning_feature_ready_window_count=0`
- `feature_table_write_allowed=0`
- `strategy_rule_created=0`
- `true_engine_run=0`
- `ab_triggered=0`
- `current_package_promotion_allowed=0`
- `strategy_feature_usable=0`

修改结果：

- 无。

删除结果：

- 无。

## 视觉分析

已生成并检查 5 张图均非空：

- `qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate_official_path_feature_gate_status_stage156_authoritative_minute_feature_prebuild_gate_v1.png`
- `qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate_feature_family_readiness_matrix_stage156_authoritative_minute_feature_prebuild_gate_v1.png`
- `qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate_window_feature_readiness_heatmap_stage156_authoritative_minute_feature_prebuild_gate_v1.png`
- `qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate_leakage_guard_matrix_stage156_authoritative_minute_feature_prebuild_gate_v1.png`
- `qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate_gate_status_matrix_stage156_authoritative_minute_feature_prebuild_gate_v1.png`

视觉结论：

- 官方路径资金曲线仍只是基线审计；Stage156 没有改变权益、回撤或交易。
- feature family 图显示合同存在，但所有 ready window 仍为 0，说明没有真实数据时不会误生成特征。
- window readiness 图显示 entry/event/session guard 三类窗口均未覆盖，正确阻断。
- leakage guard 图显示 9 类泄漏/过拟合输入均未进入 feature contract。
- gate matrix 显示输入/合同/泄漏 guard 通过，data/coverage/feature hard gate 全部阻断。

## 过拟合反思

开始前判断：不是过拟合。原因是本轮不做收益优化、不扫参数、不按赢家/输家标签调阈值，只沿当前线补真实分钟数据进入特征层之前的闸门。

完成后判断：仍不是过拟合。10 个特征只是跨品种通用的 OHLCV/OI 原语合同，且全部被 `feature_table_write_allowed=0` 锁住；没有任何阈值、品种、年份、right-tail/bottom-loss 标签被交易化。

## 是否还有价值继续

开始前判断：有价值。Stage155 已证明负例无法绕过数据 gate，下一步需要定义通过 gate 以后才能安全生成什么特征，否则真实数据一到就容易把未来泄漏或局部补丁混进去。

完成后判断：仍有价值，但下一步不能继续在空数据上发明规则。价值在于 Stage156 固定了后续真实数据到达后的特征层边界；继续推进应是导入真实授权 1m OHLCV+OI，重跑 Stage153/156，或做 Stage157 的到货后 feature table 只读生成器框架，但仍必须保持 no-data 时硬阻断。

## TODO

1. 等真实授权 `incoming/stage152_authoritative_minute_ohlcv/...` raw/proof/normalized 到货后，先重跑 Stage153。
2. Stage153 全部 request/window 通过后，重跑 Stage156；只有 `feature_ready_window_count=657` 且 OI ready 后，才允许写只读 feature table。
3. 写 Stage157 时只允许做 feature table builder dry-run/empty-run 合同，不允许阈值搜索、true engine、A/B 或正式候选。
4. 特别禁止把数据 ready/missing、产品、年份、right-tail、bottom-loss、post-event 结果写成交易条件。
