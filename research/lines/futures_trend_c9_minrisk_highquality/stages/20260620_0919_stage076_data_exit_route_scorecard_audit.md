# Stage076 数据出口路线 scorecard 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage075 后的数据出口路线审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`，`dur_sec=0` 支持下载历史 tick；但 Stage073-075 已证明当前 Tq tick 与 official open 不是同源。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`，`TickData` 包含 last trade、orderbook snapshot 和 intraday statistics，`BarData` 为 OHLCV 周期条；这说明盘口/量能规则必须有 tick 或非退化 K 线支撑。
  - LSEG Tick History：`https://www.lseg.com/en/data-analytics/market-data/data-feeds/tick-history`，历史 tick/quote/depth 通常是专门授权数据产品，不是 CTP/vn.py 实时连接自动能补齐的历史资产。
  - TqSdk 基础示例：`https://doc.shinnytech.com/tqsdk/latest/demo/base.html`，行情、K线/Tick、下单/撤单是不同使用层；历史回测和实时行情不能混作同源执行证据。
- 我的判断：
  - 当前目标要继续，不能再从 zero-volume/OHLC-flat 价格代理里硬挤出分钟信号。
  - 可行出口必须二选一：第一，拿到能解释 Stage449/raw zero-volume open 的同源 tick/orderbook；第二，换真正外生、入场前可见、覆盖完整且点时化的数据源。
  - CTP/vn.py live tick 可以做 forward watch，但不能补历史回测；Tq tick 可以做 TCA 观察，但 Stage073/074 已经禁止它直接进入规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage076_data_exit_route_scorecard_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage074/075 全量 `324` 个 initial opens，覆盖 `2018-2026`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定读取 Stage074 source audit、Stage075 permission matrix、Stage033 tick feasibility 与 Stage045 official curve。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
  - 对 route 只做数据可用性/同源性/可交易性条件审计，不做策略参数。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓、减仓、恢复风险或退出规则。
  - 不跑 true engine。
  - 不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage076_no_rule_ready_route_get_same_source_or_external_preentry_data`
  - route_count：`6`
  - rule_candidate_allowed_route_count：`0`
  - same-source price authority events：`219`
  - raw authority tick/orderbook files：`0`
  - line tick-like files：`144`
  - fallback no-proxy gap：`105`
  - strategy_rule_created：`False`
  - true_engine_run：`False`
  - ab_triggered：`False`
  - broker10 峰值：`111.7365%`

## route scorecard

- `R1_raw_authority_price_boundary`：本地证据 `219`，历史覆盖与 same-source execution 为 `1`，但 nondegenerate OHLCV/tick/orderbook 为 `0`，决策 `audit_only_not_strategy_rule`。
- `R2_same_source_tick_orderbook_backfill`：本地证据 `0`，当前不可写规则，但它是第一优先数据工程出口；需要获取能解释 Stage449/raw zero-volume open 的同源 tick/orderbook 后复验 exact。
- `R3_existing_tq_tick`：本地证据 `60`，有 tick/orderbook，但 same-source execution 为 `0`，决策 `blocked_heterologous_tca_only`。
- `R4_fallback_no_proxy_refill`：覆盖缺口 `105`，是 raw proxy 覆盖治理，不是 alpha。
- `R5_ctp_live_forward_tick_recorder`：本地 live/smoke tick-like 文件 `22`，可做未来样本记录，但不能回填 `2018-2026` 历史回测。
- `R6_authorized_external_preentry_source`：当前本地证据 `0`，只有拿到完整、点时化、非最终盈亏标签的数据后才允许重启只读审计。

## 视觉观察

- route scorecard chart 左侧显示：R1 有 `219` 个本地 evidence，但全是 price-boundary；R3 有 `60` 个 Tq tick evidence，R5 有 `22` 个 live/smoke evidence，R2/R4/R6 当前本地 evidence 为 `0`。
- route scorecard chart 右侧和 readiness atlas 显示：所有 route 的 `rule_candidate_allowed` 均为 `0`；R1 只满足 historical 与 same-source execution，不满足 nondegenerate OHLCV/tick/orderbook；R3/R5 有 tick/orderbook 但不同源或不覆盖历史；R6 是外生源方向但当前没有历史点时化证据。
- official path route-boundary chart 显示：绿色 Stage449 raw price boundary 与官方右尾高度同步，但这只是 source route 分布，不是 alpha；蓝色 Stage452 fallback 贡献偏负，也不能当作跳过/削仓信号；灰色 no-proxy 主要是覆盖缺口。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_report_stage076_data_exit_route_scorecard_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_summary_stage076_data_exit_route_scorecard_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_decision_stage076_data_exit_route_scorecard_audit_v1.json`
- route scorecard：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_route_scorecard_stage076_data_exit_route_scorecard_audit_v1.csv`
- local source catalog：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_local_source_catalog_stage076_data_exit_route_scorecard_audit_v1.csv`
- route scorecard chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_route_scorecard_chart_stage076_data_exit_route_scorecard_audit_v1.png`
- route readiness atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_route_readiness_atlas_stage076_data_exit_route_scorecard_audit_v1.png`
- official path route-boundary chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage076_data_exit_route_scorecard_audit/qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit_official_path_route_boundary_chart_stage076_data_exit_route_scorecard_audit_v1.png`

## 结论

- 本阶段结论：`stage076_no_rule_ready_route_get_same_source_or_external_preentry_data`
- 是否进入下一步：是，但下一步不能写交易规则。
- 下一步：
  - 第一优先：R2，获取同源 tick/orderbook 或能解释 Stage449/raw zero-volume open 的授权/vendor 源，先做 `same_source_exact` 复验。
  - 第二优先：R4，补 `105` 笔 no-proxy raw authority 覆盖，但只作为覆盖治理，不得写 no-proxy 规则。
  - 第三优先：R6，若暂时无法拿同源盘口，换真正外生、入场前可见、覆盖完整的数据源，并先做点时化覆盖审计。
  - 明确禁止：不得继续用 R1/R3/R5 写开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段是 route 可行性审计，不是候选回测。
- 运行后判断：否，并且进一步降低过拟合风险。
- 原因：
  - route 条件来自数据语义：同源、历史覆盖、可交易微观结构、外生性、非最终盈亏标签，而不是收益指标优化。
  - 所有路线最后一列 `rule_candidate_allowed=0`，没有因为某个 source class 右尾好看就强行放行。
  - 视觉图明确显示 source route 与年份/覆盖演化绑定，不能交易化。

## 继续价值反思

- 运行前判断：有价值。Stage075 证明当前 raw authority 不能写分钟 K 规则，但还需要明确下一步到底怎么继续。
- 运行后判断：有价值。现在下一步路线被压缩到可执行数据工程，而不是继续历史切片。
- 原因：
  - R2 是最贴近原目标“分钟级高质量信号”的出口，但必须先有同源盘口/量能数据。
  - R6 保留了不依赖执行源的外生路线，但必须先满足点时化和覆盖完整。
  - 这比继续在 R1/R3/R5 上写伪规则更符合“能穿越周期”的要求。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage076 状态、视觉结论和下一步 route 边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据出口路线审计。
