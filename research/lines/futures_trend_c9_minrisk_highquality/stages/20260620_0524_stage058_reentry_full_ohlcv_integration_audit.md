# Stage058 reentry 全量 OHLCV 整合审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 05:24 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据整合与视觉归因；不是真实组合引擎
- 是否重要突破：否；这是数据覆盖里程碑，不是策略 alpha 突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 API 文档：`get_kline_serial()` 返回 open/high/low/close/volume/open_oi/close_oi 等 K 线字段，`get_tick_serial()` 返回 last_price、volume、open_interest 等 tick 字段；`is_serial_ready()` 用于判断序列是否已从服务器收到订阅数据。
  - TqSdk `TqBacktest` 文档：回测模式由 TqBacktest 推进历史行情并更新 K 线、tick。
  - vn.py GitHub `BarGenerator`：tick 合成分钟 bar 时使用 last_price 更新 close，用 tick volume 差值累加成交量，这与 Stage057 用 tick 重建目标分钟 OHLCV 的会计口径一致。
- 我的判断：
  - Stage057 tick rebuilt 可以作为历史 OHLCV 覆盖修复证据，但只能证明数据可用，不能证明 tick-ready、minute-not-ready 或 source 名称是可交易信号。
  - Stage058 必须只做预声明整合和四分位只读诊断，不允许把 FG601/OI/lh/sp 这些右尾产品块或 range/body/volume 分桶直接转成规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage058_reentry_full_ohlcv_integration_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读输出字段 `final_source/final_range_r/final_body_r/directional_close_position/directional_body_r/final_log_volume`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用当前官方 C9/15w 只读曲线，`2018-01-02` 至 `2026-06-15`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w Stage054 曲线成本口径；本阶段不重跑交易引擎
- 样本过滤：仅 `retry_reentered=1` 的 C9 reentry 事件，共 `54` 个 event key
- 策略/归因口径：合并 Stage055 best-source ready、Stage056 本地 deep-search ready、Stage057 tick rebuilt ready，形成 `54/54` 全量 reentry OHLCV ready 表；所有四分位分桶仅用于视觉归因

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6339`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- Stage058 integrated reentry events：`54`
- Stage058 full ready：`54/54`
- Stage058 unresolved：`0`
- 来源计数：Stage055 best-source `34`，Stage056 local deep-search `1`，Stage057 tick rebuilt `19`
- 来源 reentry PnL：Stage055 `+1,727,602.00`，Stage056 `-5,760.00`，Stage057 `+975,455.00`
- 全量 integrated reentry PnL：`+2,697,297.00`
- 最大正贡献事件：`FG601.CZCE 2025-11-05 09:07`，`+950,000.00`，来源 Stage057 tick rebuilt
- 最大负贡献事件：`jm2209.DCE 2022-05-25 10:46`，`-310,980.00`，来源 Stage055 best-source
- 特征相关：`max_abs_spearman_feature_pnl = 0.1835`，没有足够强的单变量单调关系
- 质量桶：`slow_or_deep_reclaim +1,361,035.60`，`fast_clean_reclaim -250,880.00`，与“慢/深回补是坏质量”的直觉相反

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_report_stage058_reentry_full_ohlcv_integration_audit_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_decision_stage058_reentry_full_ohlcv_integration_audit_v1.json`
- integrated events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_integrated_events_stage058_reentry_full_ohlcv_integration_audit_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_contribution_curve_stage058_reentry_full_ohlcv_integration_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_path_chart_stage058_reentry_full_ohlcv_integration_audit_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_ohlcv_scatter_stage058_reentry_full_ohlcv_integration_audit_v1.png`
- heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_product_year_heatmap_stage058_reentry_full_ohlcv_integration_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage058_reentry_full_ohlcv_integration_audit/qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_single_bar_atlas_stage058_reentry_full_ohlcv_integration_audit_v1.png`

## 结论

- 本阶段结论：`stage058_full_reentry_ohlcv_integrated_no_trade_rule`
- 是否进入下一步：本 stop/retry OHLCV 分支不进入 true engine、不进入 A/B、不改正式配置
- 下一步：
  - 暂时关闭 reentry OHLCV 直接交易化分支，不再围绕 `range_r/body_r/close_position/volume/source/year/product/direction` 做救参。
  - 若继续 stop/retry，只能引入真正重入当刻可见且非最终盈亏标签的信息源，例如盘口队列、买卖价差、订单簿不平衡或 forward watch；否则回到会员持仓、仓单、库存、基差等点时化外生数据覆盖。

## 过拟合反思

- 运行前判断：否。本阶段目标是补齐 Stage057 之后预声明的 `34+1+19=54/54` 数据表，不新增规则，不搜索参数。
- 运行后判断：否，但存在明显诱惑。FG601、OI、lh、sp 等右尾点非常显眼，若按产品/年份/来源切规则就是过拟合。
- 原因：全量图显示收益来自少数右尾台阶，四分位分桶没有稳定单调关系，最大 Spearman 绝对值只有 `0.1835`；所以只能记录数据资产，不能升级为交易规则。

## 继续价值反思

- 运行前判断：有价值。Stage057 已补齐 tick rebuilt，必须整合全量表才能判断 stop/retry OHLCV 分支是否还有研究价值。
- 运行后判断：作为数据资产有价值，作为 alpha 分支暂时没有继续价值。
- 原因：数据阻塞已解除，但视觉和统计都说明 OHLCV 当根结构不能稳定地区分高质量/低质量 reentry；继续在这些字段上切片只会放大历史右尾依赖。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage058 和关闭边界。
- 是否更新 `research/registry.md`：否，不是正式候选、路线合并或重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破或正式合入摘要。
