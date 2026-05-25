# Stage013 外生开仓质量因子评估器

- 记录时间：2026-05-25 17:43 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 是否重要突破：否，属于方向修正和评估脚手架；尚未形成策略候选
- 当前正式基准：`78-1` / `official_stage78_1_defensive_50w_no_sizing_cap`

## 用户修正

用户明确修正：外生数据的目标不是解释“公告附近导致亏损”，而是结合政府公告、交易所公告、产业新闻、舆情等数据，优化第78-1的开仓质量和开仓数量。

因此，本阶段撤回“事件日避险/公告附近归因”的理解，改为“开仓候选质量评分 + 建议手数倍率 + 可选禁止新增开仓”的点时化外生因子框架。

## 外部调研判断

- 商品期货新闻/情绪研究通常更适合作为过滤器、排序器或仓位调节因子，而不是独立交易信号。
- 官方报告、政府公告、交易所公告和固定发布时间的产业数据更适合点时化回放；泛舆情噪声和回填风险更高。
- 对第78-1而言，最自然的接入点不是事后归因窗口，而是已有的 `entry_candidate_snapshots`：每个候选已经包含产品、方向、入场上下文、计划手数、AI池评分、pairwise评分和风控状态。

## 本次变更

新增脚本：

- `examples/portfolio_backtesting/analyze_qmt_roll_stage312_external_quality_signal_evaluator.py`

新增输出：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_external_signal_template_stage312_external_quality_signal_evaluator_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_external_signal_schema_stage312_external_quality_signal_evaluator_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_joined_candidates_stage312_external_quality_signal_evaluator_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_coverage_stage312_external_quality_signal_evaluator_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_bucket_summary_stage312_external_quality_signal_evaluator_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_report_stage312_external_quality_signal_evaluator_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage312_external_quality_signal_evaluator_summary_stage312_external_quality_signal_evaluator_v1.json`

新增正式参数：无。

修改正式参数：无。

删除正式参数：无。

## 输入契约

外生信号表字段：

- `available_datetime`：信号在交易前实际可用时间。
- `product_vt_symbol`：产品级映射，例如 `SC.INE`、`FU.SHFE`，或 `ALL`。
- `direction`：`long`、`short` 或 `both`。
- `source_type`：`official_announcement`、`government_policy`、`inventory_report`、`industry_news`、`news_sentiment`、`manual_research` 等。
- `external_quality_score`：建议范围 `[-1, 1]`。
- `suggested_volume_multiplier`：建议手数倍率，研究期只评估，不执行。
- `veto_flag`：是否建议禁止新增开仓。
- `confidence`：来源和解析置信度。

点时化规则：

- `available_datetime <= candidate_datetime`。
- 同一候选最多使用最近 `45` 个自然日内的外生信号。
- 同一候选命中多条信号时，取最近一条；同时间取置信度更高者。

## 运行结果

本阶段没有运行收益回测，只运行外生因子评估器和候选 join。

覆盖情况：

- 候选样本数：`953`
- 实际开仓候选数：`315`
- 外生信号行数：`0`
- 候选命中外生信号数：`0`
- 实际开仓命中外生信号数：`0`
- 判定：`data_not_ready_create_point_in_time_external_signal_file`

由于当前还没有真实外生信号表，本阶段不产生收益、最大回撤、Sharpe、滑点、交易次数或胜率结论。

参考基准仍为 Stage012 最强内部风控线索：

- `C_pressure040`
- 期末权益：`25,429,055`
- 总收益：`4985.811%`
- 最大回撤：`-31.0767%`
- Sharpe：`1.2650`
- 总滑点：`2,047,490`
- 总交易次数：`862`
- 胜率：`45.0346%`

## 判定

当前不能说“外生数据有效”，也不能说“无效”。正确结论是：

- 技术接入点已确认。
- 点时化输入契约已建立。
- 评估器已能把外生信号映射到第78-1开仓候选。
- 下一步必须先填充真实外生信号，再看 valid/test 切分里高分桶是否稳定表现为更高20日R、更低20日不利波动R。

## 过拟合反思

- 运行前：不是过拟合。
- 原因：本阶段不调交易参数，不用历史亏损窗口倒推规则，只建立点时化外生信号契约和评估器。
- 运行后：仍不是过拟合。
- 原因：没有真实外生信号时，评估器明确输出数据未就绪，没有伪造效果。

## 继续价值反思

- 运行前：有价值。
- 原因：内生风控已接近边界，外生信息可能改善“该不该开/开多少”，这是和回撤后被动降风险不同的结构路径。
- 运行后：继续有价值，但必须先做数据层。
- 原因：框架已经验证能接入开仓候选；下一阶段价值取决于能否构造可信、点时化、低自由度的外生信号表。

## 下一步

1. 先接入低自由度外生源：交易所公告、政府/监管公告、EIA/USDA固定发布时间报告、产业库存/开工率。
2. 每条外生数据只生成少数字段：`external_quality_score`、`suggested_volume_multiplier`、`veto_flag`、`confidence`。
3. 先做只读分桶验证：高分桶是否在 valid/test 中拥有更高20日R、更低20日MAE。
4. 若通过，再进入 A/C 回测：
   - A：78-1正式基准。
   - C：78-1 + 冻结的外生质量手数倍率/禁止新增开仓规则。
5. 如果只在单一品种、单一年份、单一政策窗口有效，停止，不合入正式策略。
