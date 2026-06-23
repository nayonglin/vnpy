# Stage108 OI 后路线重置与未解释风险地图

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 16:15 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：路线复审 / 风险地图 / 下一候选边界，不写真引擎
- 是否重要突破：否；这是防止 OI 路线和触价分钟规则过拟合的路线重置
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen 的百年趋势跟随证据：趋势跟随跨市场、跨宏观环境的长期价值来自趋势右尾和危机 alpha。
  - Moskowitz/Ooi/Pedersen 的 time-series momentum 研究：期货趋势收益来自较长期价格延续，而不是短期噪声阈值。
  - Baltas/Kosowski 等关于 time-series momentum 的风险管理讨论：风险管理和趋势强度缩放要服务于保住收益/降低换手，不应靠参数化止损制造 alpha。
  - stop-loss 相关研究：止损更常见的价值是降低投资风险，而不是稳定提高收益。
- 我的判断：
  - 本线目标不是做更激进的止损，而是保住 C9 趋势右尾，同时降低坏尾暴露。
  - Stage102/103/107 共同说明：近触价分钟 OHLC、OI rank/share、当前本地 tick proxy 都不能直接规则化；继续在这些方向救参会破坏“穿越周期”的原则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage108_post_oi_route_reset_risk_map.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage045 官方资金曲线、Stage102 `219` 笔 timestamp-ready resolution rows、Stage103 orderflow data contract、Stage107 OI patched-root features。
- 账户规模：沿用官方路径背景，`150,000` 初始账户口径。
- 成本口径：不新增回测，沿用官方背景指标；总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；只做 route/risk map。
- 策略/归因口径：路线复审；不创建交易规则、不跑 true engine、不触发 A/B。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `timestamp_ready_order_count=219`
  - `closed_or_blocked_route_count=6`
  - `true_engine_allowed_route_count=0`
  - Stage102 `low_resolution_order_count=93`
  - Stage102 `low_resolution_bottom_loss_count=5`
  - Stage103 `initial_entry_tick_ready_count=5`
  - Stage103 `initial_entry_tick_ready_rate_pct=2.2831%`
  - Stage107 `adjusted_panel_ready_count=218`
  - Stage107 `single_contract_panel_count=1`
  - `bottom_loss_order_count=18`
  - `bottom_loss_orderflow_required_count=6`
  - `bottom_loss_low_resolution_count=5`
  - `next_recommended_route=authorized_orderflow_or_one_frozen_far_from_touch_preflight`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage108_post_oi_route_reset_risk_map/qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_report_stage108_post_oi_route_reset_risk_map_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage108_post_oi_route_reset_risk_map/qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_summary_stage108_post_oi_route_reset_risk_map_v1.csv`
- route scorecard：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage108_post_oi_route_reset_risk_map/qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_route_scorecard_stage108_post_oi_route_reset_risk_map_v1.csv`
- risk event map：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage108_post_oi_route_reset_risk_map/qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_stage108_post_oi_route_reset_risk_map_v1.csv`
- bottom-loss route map：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage108_post_oi_route_reset_risk_map/qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_bottom_loss_route_map_stage108_post_oi_route_reset_risk_map_v1.csv`
- 视觉图：
  - official path unresolved risk：`qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_official_path_unresolved_risk_chart_stage108_post_oi_route_reset_risk_map_v1.png`
  - route scorecard heatmap：`qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_route_scorecard_heatmap_stage108_post_oi_route_reset_risk_map_v1.png`
  - bottom-loss route chart：`qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_bottom_loss_route_chart_stage108_post_oi_route_reset_risk_map_v1.png`
  - next route gate：`qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_next_route_gate_chart_stage108_post_oi_route_reset_risk_map_v1.png`

## 结论

- 本阶段结论：`stage108_post_oi_route_reset_no_rule_next_non_touch_or_data_procurement`。当前没有任何路线允许 true engine 或 A/B：OI rank/share 因 `SH607` single-contract bottom-loss 阻断，近触价分钟 OHLC 因 Stage102 低分辨率阻断，授权 orderflow/depth 信息增益最高但本地数据不存在。
- 是否进入下一步：是，但只能二选一：第一，采购/导入授权历史 quote/depth 或 broker execution replay；第二，在没有新数据时，只允许设计一个 frozen 的 `far_from_touch` 内部只读预检。
- 下一步：若继续内部分钟方向，Stage109 只能设计“远离 C9 stop/progress、不会 close 后下一根立刻成交、不依赖 first/second bar 触价顺序”的只读 preflight spec，fallback/no-proxy 保持官方路径。

## 过拟合反思

- 运行前判断：是，若继续 OI 或近触价分钟规则会过拟合。
- 运行后判断：是，继续救旧路线会过拟合；Stage108 自身不过拟合。
- 原因：Stage108 只是把固定历史证据合并成 route map，没有调参或筛收益。过拟合风险来自后续误用：排除 `SH607`、重开触价 close rule、用本地 tick proxy 替代授权 orderflow，都会把特定失败样本包装成规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但必须换方向。
- 原因：Stage108 把剩余空间压缩为两条真实方向：新信息源，或一个严格冻结的非触价敏感内部 preflight。它避免继续在已经证明不稳定的路线里扫参。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage108 路线重置和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不改正式候选，不触发跨线总账。
