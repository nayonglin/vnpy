# Stage093 点时化外生状态 schema 绑定

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 13:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage090-092 raw provenance 的 point-in-time state schema 只读绑定；不是策略回测
- 是否重要突破：否。只是完成状态 schema，不是数值特征或策略候选
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - 官方 raw 状态字段可以先形成点时化 schema，但 AKShare/GitHub wrapper 只能作接口参考，不能作权威数据证据。
  - Stage093 只允许输出 `source_ready/raw_parse_ready/product_present_state/symbol_hit/first_present_date` 这类状态字段。
  - 仓单量、会员排名、TopN、净持仓、flow 等数值字段尚未解析与审计，必须显式固定为不可用，防止误入策略层。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage093_point_in_time_feature_schema_binding.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - `FEATURE_SCHEMA_VERSION=external_raw_state_schema_v1`
  - state fields：`source_ready`、`raw_hash_ready`、`raw_parse_ready`、`state_feature_ready`、`product_present_state`、`symbol_hit`、`first_present_date`、`target_minus_first_present_calendar_days`
  - hard gates：`quantity_feature_ready=0`、`member_rank_numeric_feature_ready=0`、`warehouse_numeric_feature_ready=0`、`strategy_rule_allowed=0`、`true_engine_allowed=0`
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage090 入场前 `7` 交易日 lot-window links；Stage091 full raw backfill；Stage092 product-date status
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：绑定全部 Stage090 links，不按盈亏、回撤、右尾或产品表现筛选
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - 只定义点时化状态 schema 和只读覆盖审计
  - PnL rank 只用于右尾覆盖安全审计，不作为字段筛选或阈值

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage093_state_schema_bound_all_state_ready_no_numeric_no_rule`
  - feature_schema_version：`external_raw_state_schema_v1`
  - feature_row_count：`2,590`
  - linked_lot_count：`188`
  - source_count：`3`
  - state_feature_ready_count：`2,590/2,590`
  - quantity_feature_ready_count：`0`
  - product_present_row_count：`2,576`
  - absent_before_first_row_count：`14`
  - raw_parse_gap_row_count：`0`
  - after_prior_presence_gap_row_count：`0`
  - lot_all_state_ready_count：`188/188`
  - right_tail_lot_count：`19`
  - right_tail_all_state_ready_count：`19/19`
  - schema_design_complete：`1`
  - feature_binding_read_only：`1`
  - numeric_feature_extraction_done：`0`
  - feature_binding_strategy_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage093_point_in_time_feature_schema_binding/qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_report_stage093_point_in_time_feature_schema_binding_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage093_point_in_time_feature_schema_binding/qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_summary_stage093_point_in_time_feature_schema_binding_v1.csv`
- orders：无
- daily：无新交易日线，仅复用官方路径
- quality：
  - `qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_feature_rows_stage093_point_in_time_feature_schema_binding_v1.csv`
  - `qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_lot_source_summary_stage093_point_in_time_feature_schema_binding_v1.csv`
  - `qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_lot_summary_stage093_point_in_time_feature_schema_binding_v1.csv`
  - `qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_source_state_summary_stage093_point_in_time_feature_schema_binding_v1.csv`
  - `qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_schema_fields_stage093_point_in_time_feature_schema_binding_v1.csv`
  - official feature path chart：`qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_official_feature_path_chart_stage093_point_in_time_feature_schema_binding_v1.png`
  - source state heatmap：`qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_source_state_heatmap_stage093_point_in_time_feature_schema_binding_v1.png`
  - lot coverage chart：`qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_lot_coverage_chart_stage093_point_in_time_feature_schema_binding_v1.png`
  - schema field chart：`qmt_roll_stage093_c9_minrisk_point_in_time_feature_schema_binding_schema_field_chart_stage093_point_in_time_feature_schema_binding_v1.png`

## 视觉观察

- official feature path chart：全阶段 `188/188` 个 lot 都 all-state-ready；红点只显示 `2018` 与 `2023` 的 absent-before-first 行，不改变权益/回撤/broker10 背景路径。
- source state heatmap：所有 planned source-year 的 state feature ready ratio 为 `100%`；GFEX 只在 `2023-2025` 出现，符合 Stage090-092 的边界。
- lot coverage chart：lot-level state ready ratio 全部为 `1.0`；right-tail `19/19` 全部 product-present 且 state-ready。PnL rank 图仅作覆盖安全审计，不是规则图。
- schema field chart：`18` 个字段均为 point-in-time safe，`0` 个字段允许交易规则；这符合 Stage093 的只读边界。

## 结论

- 本阶段结论：
  - 点时化状态 schema 已完成，可作为后续数值字段解析的绑定骨架。
  - 当前 artifact 仍不是策略可用特征，因为 `quantity_feature_ready=0` 且 `feature_binding_strategy_usable=0`。
  - 不允许把 `product_present_state`、`symbol_hit`、`first_present_date`、source ready 或 gap 状态直接接入 true engine、A/B 或正式候选。
- 是否进入下一步：可以进入 Stage094 数值字段解析 smoke 与 schema audit；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - 固定解析字段，不做阈值：CZCE/GFEX warehouse 的产品级仓单合计、当日变化；CZCE member_rank 的产品级成交量/持买仓/持卖仓排名字段只做 schema smoke。
  - 先做少量跨年份样本的 numeric parse smoke 和字段稳定性图，再决定是否能全量解析。

## 过拟合反思

- 运行前判断：否。绑定全部 Stage090 links，不按最终盈亏挑样本。
- 运行后判断：否，但要防止“状态字段先入为主”。
- 原因：本阶段没有计算收益阈值、没有跑 true engine、没有交易规则；风险在于把状态覆盖当作 alpha，所以 hard gate 全部设为不允许策略。

## 继续价值反思

- 运行前判断：有价值。没有 point-in-time schema，后续数值解析会变成临时拼接，很容易泄漏或混入不可交易状态。
- 运行后判断：有价值。schema 骨架完成，且右尾全覆盖，下一步可以更安全地做数值字段解析 smoke。
- 原因：这一步把 raw provenance、产品状态、lot-window 统一到一张可审计表；继续前进比从 closed-lot 直接猜信号更接近普世化数据源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage093 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
