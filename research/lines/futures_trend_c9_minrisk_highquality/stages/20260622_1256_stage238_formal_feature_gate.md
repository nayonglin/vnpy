# Stage238 - formal feature gate

- 时间：2026-06-22 12:56 CST
- 工作模式：day
- 研究线：futures_trend_c9_minrisk_highquality
- 本次性质：从 Stage181 只读 audit 进入 formal feature gate，但继续锁定策略使用
- 是否重要突破版本：否，属于特征准入地基，不是策略效果突破

## 开始前反思

- 是否可能过拟合：有潜在风险，但本阶段采取了规避。风险来自把 `219/219` 横截面分布直接转成交易尺度；因此 Stage238 只做固定准入和自然单位入表，不允许全样本拟合尺度用于策略，不读取收益标签。
- 是否仍有价值继续做：是。覆盖已经补完，如果没有 formal feature gate，后续任何分钟信号审计都会把数据质量字段、尺度依赖字段和候选信号混在一起，容易走向过拟合。

## 外部调研与判断

- pandas rank/表处理 API 适合做固定、无标签的数据准入审计，但横截面 rank 只能作为诊断，不能直接当作未来可用的线上尺度：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rank.html
- scikit-learn `RobustScaler` 说明中位数/IQR 是常见鲁棒尺度，但 Stage238 不把全样本中位数/IQR 作为生产尺度，只用于 heatmap 视觉诊断，避免未来分布泄漏：https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.RobustScaler.html
- TqSdk 官方对象文档继续作为 tick/K 线字段来源参考，字段可得性不等于特征可交易：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
- vn.py `BarGenerator` 继续作为确定性分钟聚合语义参考，Stage238 不重新聚合行情，只继承 Stage180/181 的 cutoff 和 lineage：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 判断结论：应写 formal feature table，但必须把“可入表”和“可被策略使用”分开；本阶段只完成准入，不做信号打分或交易规则。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage238_formal_feature_gate.py`
- 新增产物：
  - formal feature table：CSV + parquet
  - feature gate audit
  - row gate audit
  - normalization contract
  - feature distribution audit
  - gate status
  - report 与 5 张视觉图
- 新增参数：无外部可调参数，候选/诊断划分在脚本中固定声明
- 修改参数：无
- 删除参数：无
- 新增回测结果：无，本阶段没有运行 true engine 或策略回测
- 修改回测结果：无
- 删除回测结果：无
- 代码边界：不创建策略规则，不运行 true engine，不触发 A/B，不改变 official config，不连接 CTP，不调用 order API

## Stage238 结果

- decision：`stage238_formal_feature_gate_written_strategy_locked_no_rule`
- formal_feature_table_row_written_count：219
- formal_row_ready_count：219
- formal_row_ready_ratio：1.0
- input_feature_count：10
- formal_feature_admitted_count：10
- strategy_candidate_feature_count：7
- diagnostic_only_feature_count：3
- normalization_contract_row_count：10
- distribution_audit_row_count：10
- feature_table_file_written：1
- feature_table_file_count：2
- strategy_feature_usable：0
- strategy_rule_created：0
- true_engine_run：0
- ab_triggered：0
- order_api_called：0
- official_config_changed：0

## 候选与诊断划分

进入 strategy-candidate 候选但仍未允许策略使用的 7 个无量纲特征：

- `bar_return_1m`
- `range_ratio_1m`
- `directional_efficiency_30m`
- `realized_volatility_30m`
- `volume_participation_30m`
- `volume_zscore_60m`
- `turnover_vwap_gap_30m`

进入 formal table 但只允许诊断、不得直接作为策略信号的 3 个字段：

- `true_range_median_30m`：价格尺度依赖，需先做比例化或 tick/价格基准归一
- `open_interest_delta_60m`：合约尺度依赖，需先有 OI 基准归一
- `closed_bar_count_coverage`：数据质量字段，不是 alpha 或风险信号

## 当前路径指标

本阶段没有改动策略路径，以下指标保持为当前线只读参照：

- 期末权益：39,176,437.60
- 总收益：26,017.625067%
- 最大回撤：-45.082656%
- Sharpe：1.633096
- 总滑点：2,730,130
- 总交易次数：787
- 胜率：36.090226%
- 最大 broker10 保证金/权益：111.736478%

## 视觉核验

- official path formal gate status：资金曲线、回撤和 broker10 路径未改变，底部显示 formal rows、ready rows、candidate features、rules。
- feature gate matrix：10 个特征全部 formal admitted；7 个 strategy candidate；3 个 diagnostic only；no_future_data/no_final_pnl_label/no_product_or_year_patch 全部通过。
- feature role counts：formal admitted 10、strategy candidates 7、diagnostic only 3、strategy usable now 0。
- formal row gate matrix：219 行 cutoff/lineage/all_feature/formal_row_ready 全绿；`strategy_feature_usable=0` 列为红色，表示刻意锁住策略使用。
- candidate feature audit heatmap：只用于鲁棒视觉诊断，不能作为生产尺度或交易规则。
- PNG 非空检查：Stage238 共 5 张 PNG 全部非空。

## 结论

- Stage238 完成了从 `219/219` audit 数据到 formal feature table 的准入转换。
- 这一步让后续 Stage239 可以在固定候选集合上做只读信号质量审计，但还没有产生任何交易规则或收益结果。
- 当前阶段仍不证明最大回撤已降低，也不证明收益保留 80%；它只是让下一步可以在不混入数据质量和尺度依赖字段的前提下研究信号质量。

## 后续规划与 TODO

- Stage239 做只读 universal signal quality audit：只用 7 个候选特征，先审计它们与“低风险/高质量入场上下文”的普世关系，不跑 true engine。
- Stage239 必须避免收益标签调参：不按产品、年份、方向、月份做特例；不调阈值救局部样本；只允许预声明、单调、可穿越周期的信号质量检验。
- 若 Stage239 发现候选特征没有稳定普世结构，应回到特征定义本身，而不是进入策略参数扫描。

## 结束反思

- 是否过拟合：否。本阶段没有使用最终 PnL、最大回撤归因标签或产品年份补丁；全样本鲁棒尺度只用于 heatmap，不写入 production transform。
- 是否仍有价值继续做：是。覆盖工程已结束，formal gate 已完成；下一步有价值的是只读验证 7 个候选特征是否真的对应高质量、低风险的分钟入场环境。
