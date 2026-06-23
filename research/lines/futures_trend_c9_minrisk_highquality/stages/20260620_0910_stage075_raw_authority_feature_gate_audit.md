# Stage075 raw authority 特征门控审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：raw authority 下的可交易特征门控审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 Time Series Momentum 研究：`https://elmwealth.com/wp-content/uploads/2017/06/timeseriesmomentum.pdf`，趋势跟随的长期有效性来自跨资产、跨时期的时间序列动量，而不是少数样本微观阈值。
  - Hurst/Ooi/Pedersen 的 A Century of Evidence on Trend-Following Investing：`https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2993026_code277060.pdf?abstractid=2993026`，趋势跟随穿越周期的关键在长期、分散和风险管理。
  - 趋势跟随仓位管理/波动目标资料：`https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf`，相关研究通常从 target volatility、drawdown/tail-risk sizing 等普世风险预算入手。
  - TqSdk DataDownloader 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`，tick 与 K 线是不同数据层，`dur_sec=0` 为 tick。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`，`TickData` 与 `BarData` 分别表示盘口快照/成交统计与 OHLCV 周期条。
- 我的判断：
  - 趋势跟随要降低回撤且保留右尾，原则上应从风险预算、同源执行质量或真正外生状态出发；不能用历史亏损样本和异源盘口差异拼阈值。
  - Stage074 已把权威执行源限定为 raw proxy bar authority，但该源是 zero-volume/OHLC-flat price proxy，不是可用的分钟 K 信号。
  - Stage075 的任务不是写候选，而是证明当前源下哪些字段可以继续审计，哪些必须禁止；这能避免为了推进目标而制造伪分钟规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage075_raw_authority_feature_gate_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage074 全量 `324` 个 initial opens，覆盖 `2018-2026`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定审计 Stage074 全部 `324` 个 initial opens。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
  - 本地 same-source tick/orderbook 只扫描 Stage074 raw authority roots：`tqsdk_stage452_true_path_fallback_1455` 与 `tqsdk_stage448_minute_session_rebuild_batch`。
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
  - decision：`stage075_raw_authority_price_only_no_valid_minute_rule_without_same_source_data`
  - initial opens：`324`
  - same-source price authority ready：`219`
  - Stage449 same-source price authority：`202`
  - Stage452 raw fallback price authority：`17`
  - same-source OHLCV non-degenerate ready：`0`
  - same-source tick/orderbook local files：`0`
  - heterologous Tq tick batch/exact：`60/46`
  - fallback no proxy：`105`
  - strategy_rule_created：`False`
  - true_engine_run：`False`
  - ab_triggered：`False`
  - broker10 峰值：`111.7365%`

## 特征门控分类

- `raw_stage449_price_only_no_ohlcv`：`202` 笔，same-source price authority `202`，same-source OHLCV ready `0`，same-source tick/orderbook `0`，Tq tick ready/exact `58/44`，净 PnL `+35,425,025.70`。
- `raw_stage452_fallback_price_only_no_ohlcv`：`17` 笔，same-source price authority `17`，same-source OHLCV ready `0`，same-source tick/orderbook `0`，Tq tick ready/exact `2/2`，净 PnL `-3,034,368.20`。
- `fallback_no_proxy_official_path_only`：`105` 笔，same-source price authority `0`，只能保持官方路径或先补 raw proxy。

## 视觉观察

- official path feature gate chart 显示：绿色 `raw_stage449_price_only_no_ohlcv` 覆盖 `2020` 后主要 timestamp-ready 事件和右尾台阶，但图中第二栏也显示这只是 source gate class 的贡献曲线，不是交易规则；蓝色 Stage452 fallback 贡献偏负，属于缺口源差异，不可被当作跳过/削仓信号。
- feature permission chart 显示：`same_source_price_authority_exact=219` 和 `stage449_same_source_price_authority=202` 足够做成交边界审计；但 `same_source_ohlcv_non_degenerate=0`、`same_source_tick_orderbook_local_files=0`，说明当前源不支持 volume/range/body/spread/depth/imbalance 规则。
- 同一图右侧年度堆叠显示：`2018-2019` 主要是 no-proxy 灰色缺口，`2020` 后转入 raw/Stage449 price-only class；这是数据覆盖演化，不是市场状态。
- feature gate atlas 显示：fallback/no-proxy 样本全部字段为 `0`；raw/Stage449 样本只有 `same_source_price_authority_ready` 与部分 `stage449_anchor_exact_official` 为 `1`；`same_source_nonzero_volume_ready`、`same_source_non_degenerate_ohlc_ready`、`same_source_tick_orderbook_ready` 全部为 `0`。这直接反证当前 raw authority 能写真实分钟 K 信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_report_stage075_raw_authority_feature_gate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_summary_stage075_raw_authority_feature_gate_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_decision_stage075_raw_authority_feature_gate_audit_v1.json`
- feature gate audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_gate_audit_stage075_raw_authority_feature_gate_audit_v1.csv`
- permission matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_permission_matrix_stage075_raw_authority_feature_gate_audit_v1.csv`
- class summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_gate_class_summary_stage075_raw_authority_feature_gate_audit_v1.csv`
- year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_year_feature_gate_matrix_stage075_raw_authority_feature_gate_audit_v1.csv`
- official path feature gate chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_official_path_feature_gate_chart_stage075_raw_authority_feature_gate_audit_v1.png`
- feature permission chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_permission_chart_stage075_raw_authority_feature_gate_audit_v1.png`
- feature gate atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage075_raw_authority_feature_gate_audit/qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_gate_atlas_stage075_raw_authority_feature_gate_audit_v1.png`

## 结论

- 本阶段结论：`stage075_raw_authority_price_only_no_valid_minute_rule_without_same_source_data`
- 是否进入下一步：是，但不能在当前 raw authority 上写真正分钟 K 候选。
- 下一步：
  - 路线 A：补同源 tick/orderbook 或能解释 Stage449/raw zero-volume open 的授权/vendor 数据，先复验 same-source exact，再进入盘口/量能稳定性审计。
  - 路线 B：换真正外生、入场前可见、覆盖完整的数据源，例如更可靠的会员持仓/仓单/库存/基差/产品参与度结构，并先做点时化覆盖审计。
  - 路线 C：如果只继续 raw authority，只允许做 bar-level 账本/执行边界审计，不得写开仓过滤、最小风险、恢复风险或退出规则。
  - 明确禁止：不得把 source class、Stage452 fallback、no-proxy、zero-volume、degenerate OHLC、Tq tick ready/exact、spread/depth/imbalance、volume/range/body 写成规则。

## 过拟合反思

- 运行前判断：否。本阶段不是候选回测，而是全量特征许可审计。
- 运行后判断：否，并且本阶段主动阻止过拟合。
- 原因：
  - 审计覆盖全部 `324` 个 initial opens，不按盈亏或年份切样本。
  - 结论来自数据语义和同源性，不来自指标优化。
  - 视觉图显示 source class 与年份覆盖高度相关，不能当作市场状态；用它写规则会是明显过拟合/数据泄漏。

## 继续价值反思

- 运行前判断：有价值。Stage074 已选权威源，但还没回答“这个源能不能支持下一条分钟规则”。
- 运行后判断：有价值，但价值是剪掉伪候选空间，而不是产生新 alpha。
- 原因：
  - Stage075 证明当前 raw authority 只能支持价格边界审计，不能支持真正的分钟 K 高质量信号。
  - 这让下一步决策更清晰：要么补同源 tick/orderbook，要么换真正外生源；继续用当前 zero-volume 价格代理写规则没有穿越周期的基础。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage075 状态、视觉结论和下一步数据源边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线特征门控推进。
