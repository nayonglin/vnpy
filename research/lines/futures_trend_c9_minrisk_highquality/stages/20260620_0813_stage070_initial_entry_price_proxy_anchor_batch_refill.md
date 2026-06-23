# Stage070 初始开仓 price_proxy_anchor 批次补数审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 08:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据覆盖/成交价锚点复验，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档：`TqBacktest + get_tick_serial` 可在历史回放中取得 tick 序列；tick 与 K 线生成 quote 的语义不同。
  - vn.py GitHub README：`data_recorder` 明确把 Tick 与 K 线作为不同数据资产记录，tick 可用于更细粒度回放和初始化。
  - HftBacktest 文档/GitHub：短周期成交审计需要 tick、盘口、延迟和队列/深度信息，不能只看 bar close。
  - QuantStart / Quantpedia 连续合约方法论：连续合约适合研究和信号归一，但执行价格必须回到具体合约、具体时间和具体价格口径。
- 我的判断：
  - Stage069 的 `5/5 proxy exact` 只是 smoke 证据，不能直接外推到全周期。
  - 本阶段必须按固定时间顺序补数，不按盈亏、品种、方向或年份挑样本。
  - 若 price proxy 批次不能稳定 exact，下一步应先做价格口径根因审计，而不是提前提取 spread/depth/imbalance 规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage070_initial_entry_price_proxy_anchor_batch_refill.py`
- 修改脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage069_initial_entry_dual_anchor_price_basis_audit.py`
  - 修改内容仅为图标题使用 `STAGE` 变量，便于 Stage070 wrapper 复用可视化函数。
- 删除脚本：无
- 新增参数：
  - `STAGE070_ENABLE_TQSDK=1`
  - `STAGE070_MAX_EVENTS=60`
  - `STAGE070_DOWNLOAD_ROLES=price_proxy_anchor`
  - `STAGE070_MAX_SECONDS_PER_EVENT=45`
  - `STAGE070_TICK_DATA_LENGTH=12000`
  - `STAGE070_DOWNLOAD_WINDOW_MINUTES=3`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage068/069 初始开仓计划中按时间顺序前 `60/219` 笔，覆盖 `2020-01-09` 至 `2021-01-06`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定时间顺序前 `60` 笔 initial-entry，不按收益、亏损、产品、方向或年份筛选。
  - 复用 Stage069 已有 `5` 个 price proxy tick。
  - 新增下载 `55` 个 `price_proxy_anchor` tick。
  - `event_scan_anchor` 本阶段保持 Stage068 的 `5` 个 ready；未下载其他 scan anchor，因为它只服务事件语义，不服务成交价解释。
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
  - decision：`stage070_price_proxy_anchor_batch_mixed_partial_coverage_no_rule`
  - base trade count：`60`
  - anchor plan rows：`120`
  - price proxy ready：`60/60`
  - price proxy exact：`46/60`
  - price proxy exact ratio：`76.6667%`
  - price proxy mismatch：`14/60`
  - mismatch near `<=0.05R`：`7`
  - mismatch far `>0.05R`：`7`
  - mismatch inside any spread：`1`
  - exact group net PnL：`250,404.50`
  - mismatch group net PnL：`28,619.00`
  - download status：`extracted=55`，`cached_stage069=5`，`cached_stage068=5`，`planned_not_downloaded_role_disabled=55`
  - event scan ready：`5/60`
  - event scan price exact：`1/5`

## 视觉观察

- 资金曲线价格基准图显示：Stage070 只覆盖到 `2021-01` 前 `60` 笔，仍只是官方长期资金曲线最早段；绿色 exact 组和灰色 mismatch 组都出现在早期低权益区间，不能代表全周期。
- 贡献曲线显示：exact 组累计 PnL `+250,404.50`，mismatch 组累计 PnL `+28,619.00`，二者都不是稳定亏损标签；mismatch 不能当作过滤或最小风险触发条件。
- anchor 状态图显示：`price_proxy_anchor` 已达到 `60/60` ready，但 exact 只有 `46/60`；`event_scan_anchor` 仍只有 Stage068 的 `5` 个 ready，符合本阶段只补成交价 proxy 的边界。
- tick atlas 显示：前 5 个 Stage069 样本继续支持 scan/proxy 双锚点拆分；新增的 `BACKTESTING.178 jm2005.DCE` 则显示即使 proxy anchor 已对到 `2020-02-11 09:00`，official open price `1230` 仍在当分钟 tick 盘口下方，最近 last 为 `1233.5`，偏差约 `0.3684R`。这说明 Stage070 的新 mismatch 不是简单 scan/proxy 混用，可能涉及价格源、连续/复权/主力映射、bar/tick 时间截取或 `_resolve_trade_price` fallback 口径。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_report_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_summary_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_decision_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.json`
- dual anchor plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_dual_anchor_plan_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- download status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_download_status_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- anchor features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_anchor_price_features_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- trade comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_trade_anchor_comparison_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- coverage summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_coverage_summary_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_official_path_price_basis_chart_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.png`
- status chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_anchor_status_chart_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage070_initial_entry_price_proxy_anchor_batch_refill/qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_dual_anchor_tick_atlas_stage070_initial_entry_price_proxy_anchor_batch_refill_v1.png`

## 结论

- 本阶段结论：`stage070_price_proxy_anchor_batch_mixed_partial_coverage_no_rule`
- 是否进入下一步：是，但下一步不是继续直接抽 TCA 特征，而是先做 mismatch 根因审计。
- 下一步：
  - 固定 Stage070 的 `14` 个 proxy mismatch 做 Stage071 根因审计。
  - 对比 `_resolve_trade_price` raw proxy、Stage861 分钟、TqBacktest tick、交易所 tick size、主力映射/连续合约口径、candidate date/official date 时间口径。
  - 将 mismatch 分成可接受近似误差、tick size/价差内误差、价格源不可解释、合约/复权/主力映射疑点几类。
  - 只有当 mismatch 口径被解释或剔除为数据口径问题后，才允许继续补 `60->219` 或提取 spread/depth/TCA 特征；否则继续补数只会扩大错误。

## 过拟合反思

- 运行前判断：否。本阶段按时间顺序固定前 `60` 笔补数，不按盈亏或弱窗口挑样本。
- 运行后判断：否，但如果把 `46/60 exact` 或 `14/60 mismatch` 当作信号质量标签，就会过拟合。
- 原因：
  - exact/mismatch 两组都为净正 PnL，不存在可直接交易化的单调坏信号。
  - mismatch 分布跨 SHFE/CZCE/DCE、09:00 和 21:00，不是单一产品或单一时段补丁。
  - 本阶段只处理价格基准，不触发策略规则。

## 继续价值反思

- 运行前判断：有价值。Stage069 的 `5/5 exact` 需要更大样本检验。
- 运行后判断：有价值，但路线应先转向 root-cause，而不是继续盲目批量下载。
- 原因：
  - `60/60` proxy ready 证明批量补数链路可行。
  - `46/60 exact` 证明 price_proxy anchor 大体有效。
  - `14/60 mismatch` 暴露了新的价格口径阻塞，如果不先解释，会污染后续所有盘口/TCA 规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage070 状态和 Stage071 根因审计边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据资产与价格基准推进。
