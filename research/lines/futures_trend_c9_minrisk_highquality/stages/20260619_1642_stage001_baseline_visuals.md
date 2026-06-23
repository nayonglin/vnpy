# Stage001 C9正式版最小风险高质量信号线基线视觉审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 16:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新研究线立线、当前官方正式 C9/15w 基线视觉审计、分钟级延迟恢复风险代理审计
- 是否重要突破：否。只是建立研究线和第一条固定候选方向，不是策略通过。
- 是否触发A/B：否。当前没有真实组合引擎结果，只是闭式代理；不得接正式版或 A/B。

## 外部调研与判断

- 参考资料：
  - `pysystemtrade`：https://github.com/pst-group/pysystemtrade 。开源期货系统强调系统化框架、风险/仓位管理和多市场稳健性，适合作为“不要手工补丁化”的工程参照。
  - Robert Carver systematic trading 说明页：https://qoppac.blogspot.com/p/systematic-trading-start-here.html 。核心经验是长周期趋势跟随、分散和风险预算，不是单个入场形态优化。
  - Concretum trend-following position sizing/pyramiding 文章：https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/ 。仓位方法会显著改变趋势策略风险收益；pyramiding 必须服从总风险约束。
  - SSRN `Trend Following Strategies: A Practical Guide`：https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1 。趋势跟随可跨市场，但杠杆、相关性和回撤阶段是核心挑战。
  - QuantConnect opening range breakout research：https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/ 。分钟级 ORB/突破可作为执行确认参考，但其具体 `5/15min` 参数不应复制到商品期货 C9。
- 我的判断：
  - 可借鉴的是第一性原则：固定风险预算、先小风险试探、价格证明方向后再释放风险、失败时快速止损、多起点和 walk-forward 视觉验证。
  - 不可借鉴的是具体分钟数、R倍数、单市场 ORB 参数、按近期弱窗口救参。
  - 本线的核心候选应从“额外加仓”转为“延迟恢复原风险”：不增加总风险，只把原 C9 满风险暴露后移到分钟级确认之后。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage001_baseline_visuals.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SCOUT_INITIAL_FRACTION=0.50`：只作为第一条冻结代理候选，不允许扫 `0.25/0.33/0.67`。
  - `CONFIRM_PROGRESS_R=0.50`：复用 C9 已存在的 `0.5R` 风险单位，不新增小数扫参。
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - C9/15w 半年度独立冷启动：`2018-01-01` 至 `2026-06-15`，来自 Stage928 既有正式输出。
  - C9 月度冷启动：`2018-01` 至 `2026-05-29`，来自 Stage899 既有正式输出。
  - 分钟级代理：来自 Stage881 C9 closed-lot/minute features；该数据源是 C9 信号逻辑的分钟级代理，不是 15w 真实资金路径。
- 账户规模：正式基线为 `150,000`；代理只看 closed-lot PnL 保留比例。
- 成本口径：沿用既有 Stage928/Stage899/Stage881 输出；本阶段不重跑成本压力。
- 样本过滤：不按年份、月份、品种、方向过滤；所有现有窗口纳入视觉图。
- 策略/归因口径：
  - A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
  - 代理 C：`delayed_restore_50pct_after_0.5R_progress`，先用原 C9 风险的 `50%` 入场，入场日分钟 K 先触达有利 `+0.5R` 后才恢复剩余 `50%`；总风险不超过原 C9。

## 结果

- 基线 `2018-01 -> 2026-06-15` 半年度起点：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6331`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
  - broker10 峰值：`111.7365%`
- 成熟半年度窗口：
  - `16/16` 正收益
  - 中位收益 `976.9086%`
  - 最差回撤 `-59.7794%`
  - DD40 失败 `7` 个，DD50 失败 `2` 个，broker100 失败 `6` 个
- 月度起点：
  - 总窗口 `101`
  - 成熟 1 年以上窗口 `89`
  - 成熟窗口正收益 `89/89`
  - 月度起点最差回撤 `-58.0872%`
  - 月度起点中位收益 `562.7523%`
- 延迟恢复风险代理：
  - closed-lot 数：`401`
  - 分钟确认候选数：`176`，占比 `43.8903%`
  - 原 closed-lot PnL：`53,950,264.60`
  - 代理 closed-lot PnL：`44,231,843.35`
  - PnL 保留：`81.9863%`
  - 重要限制：这不是资金曲线回测，不能证明最大回撤改善，也不能证明 broker10 改善。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_report_stage001_c9_minrisk_baseline_visuals_v1.md`
- summary：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_halfyear_summary_stage001_c9_minrisk_baseline_visuals_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_monthly_summary_stage001_c9_minrisk_baseline_visuals_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_delayed_restore_proxy_yearly_stage001_c9_minrisk_baseline_visuals_v1.csv`
- orders：无；本阶段不连接 CTP，不调用订单 API
- daily/curve：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_delayed_restore_proxy_features_stage001_c9_minrisk_baseline_visuals_v1.csv`
  - 视觉曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_visual_manifest_stage001_c9_minrisk_baseline_visuals_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage001_baseline_visuals/qmt_roll_stage001_c9_minrisk_baseline_visuals_decision_stage001_c9_minrisk_baseline_visuals_v1.json`
- 资金曲线/视觉图：
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_halfyear_nav_grid_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_halfyear_drawdown_grid_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_monthly_return_heatmap_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_monthly_drawdown_heatmap_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_monthly_wait_heatmap_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_delayed_restore_proxy_yearly_stage001_c9_minrisk_baseline_visuals_v1.png`
  - `qmt_roll_stage001_c9_minrisk_baseline_visuals_delayed_restore_proxy_closed_lot_curve_stage001_c9_minrisk_baseline_visuals_v1.png`

## 视觉分析

- 半年度回撤网格显示，`2020-01/2020-06` 起点的深回撤不是单日尖刺，而是 2022-2023 附近持续水下路径，且伴随 broker10 压力；这不支持按单日或单品种补丁。
- 月度回撤热力图显示，最差风险集中在 `2020-07` 至 `2021-02` 附近，但同一规则在后续多起点仍有强右尾；这说明应降低“初始未确认时的满风险暴露”，而不是否定 C9 alpha。
- 代理累计 PnL 曲线显示，延迟恢复风险会牺牲一部分右尾斜率，但没有把主右尾结构打断；整体 PnL 保留刚过 `80%`，值得写真实引擎验证。
- 年度代理图也提示风险：`2020/2022` 年代理收益保留偏弱。下一步真实引擎若只靠 2024/2025 变好而破坏 2020/2022，应直接否决，不救参。

## 结论

- 本阶段结论：`baseline_visuals_ready_next_true_engine_delayed_restore`
- 是否进入下一步：是，但只能进入冻结真实组合引擎验证，不能当作候选通过。
- 下一步：
  - 写 `delayed_restore_50pct_after_0.5R_progress` 真实引擎。
  - 生成 A/C 全路径资金曲线、回撤曲线、broker10 曲线、半年度/月度冷启动对比和分钟 K atlas。
  - 不扫初始比例、R 倍数、确认窗口、品种、方向、年份或月份。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但只有在下一步不扫参数的前提下成立。
- 原因：
  - 本阶段没有改正式策略，没有选择最优参数，只读取现有正式输出并生成视觉基线。
  - 代理规则来自普世执行原则：先小风险、方向确认后恢复风险、总风险不超过原版。
  - 风险点是 `0.50/0.5R` 仍然是固定数值；因此下一步必须只做一次冻结真实引擎，不能围绕它做参数搜索。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：
  - C9/15w 的收益右尾和多起点正收益证据很强，但 DD40/DD50 和 broker100 失败仍明显存在。
  - 代理 closed-lot PnL 保留 `81.9863%`，刚好跨过目标线，说明“延迟恢复风险”不是明显低价值想法。
  - 继续价值只在真实引擎验证和视觉复盘；如果真实引擎无法降低回撤或收益保留低于 `80%`，应停止该形状。

## 合入建议

- 是否更新本线 `LINE.md`：已新增。
- 是否更新 `research/registry.md`：暂不更新；本次是并行新线，按仓库规则由后续合入者统一更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；当前不是重要突破、正式候选或跨线合并。
