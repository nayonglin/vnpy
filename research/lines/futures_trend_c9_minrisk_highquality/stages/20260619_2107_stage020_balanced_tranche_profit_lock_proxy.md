# Stage020 balanced_tranche_v1 C9/15w 出金锁盈代理审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 21:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：账户层资金分层/出金锁盈 proxy boundary，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段预声明 `candidate_ready=0`，只做账户层边界审计

## 外部调研与判断

- 参考资料：
  - AQR `Demystifying Managed Futures`：趋势跟随/managed futures 的主要收益可由 time-series momentum 暴露解释，落地时必须重视风险管理、资产配置和成本。链接：https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures
  - Rob Carver `Capital correction (pysystemtrade)`：交易资本随账户盈亏变化会影响风险目标和仓位，是独立于 alpha 的账户层问题。链接：https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html
  - `pysystemtrade` GitHub backtesting 文档：若要看随资本变化的仓位，需要处理 capital correction，说明资本口径会影响回测路径。链接：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - AXA IM `Understanding Portfolio Insurance Management (CPPI/TIPP)`：CPPI/TIPP 的本质是在低风险/高风险资产间动态分配，以保护资本并保留部分增长。链接：https://core.axa-im.com/investment-strategies/multi-asset/insights/understanding-portfolio-insurance-management-cppitipp
  - 本仓库 `futures_trend_risk_overlay` Stage232/237：`balanced_tranche_v1` 已有固定部署口径，规则不是从 C9/15w 当前结果反推。
- 我的判断：
  - Stage019 已反证入场后 `no_follow_30m` 降仓比例路线；继续改 `70/75/85/90` 或窗口会过拟合。
  - 出金锁盈不改变 C9 单笔入场/出场路径，第一性问题是“高水位后是否把全部利润继续暴露为生产账户风险资本”。
  - 本阶段只复用既有 `balanced_tranche_v1` 单点规则，不扫 `300万/500万/700万`、`30/50/70%` 或锁盈拆分。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage020_balanced_tranche_profit_lock_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/`
- 新增参数：
  - `production_floor=150,000`
  - `sweep_start=5,000,000`
  - `sweep_ratio=0.50`
  - `lock_ratio=0.60`
  - `expansion_ratio=0.40`
- 修改参数：无。
- 删除参数：无。
- 验证：`.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage020_balanced_tranche_profit_lock_proxy.py` 通过。

## 回测/代理参数

- 输入：Stage019 输出中的官方 A 日度曲线：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_stage019_no_follow_light_shave_true_engine_v1.csv`
- A：当前官方 C9/15w 全复利路径 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- C：同一日收益序列做账户层代理：
  - 生产账户按官方日收益变化。
  - 月末若生产账户超过 `5,000,000`，提取超额部分 `50%`。
  - 提取资金中 `60%` 进锁盈账户，`40%` 进扩张/补仓储备。
  - 若月末生产账户低于初始 `150,000` 且扩张储备有余额，则补回生产账户。
- 口径限制：
  - 这是日收益缩放的账户账本代理，不是整数手重算。
  - `broker10` 同时报生产账户口径与总财富口径。
  - 胜率不重算，交易序列沿官方路径，C 只给交易次数参考。

## 结果

| 版本 | 期末总权益 | 总收益 | 收益保留 | 总财富最大回撤 | 回撤改善 | 生产账户最大回撤 | Sharpe | 总滑点/代理滑点 | 总交易次数参考 | 胜率参考 | broker10生产账户峰值 | broker10总财富峰值 | over100总财富天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 官方全复利 | `39,176,437.60` | `26017.6251%` | `100.0000%` | `-45.0827%` | `0.0000pp` | `-45.0827%` | `1.6339` | `2,730,130` | `787` | `53.2560%` | `111.7365%` | `111.7365%` | `5` |
| C balanced_tranche_v1 | `17,126,183.52` | `11317.4557%` | `43.4992%` | `-34.5078%` | `+10.5748pp` | `-55.2403%` | `1.5988` | `1,002,711.44` | `787` | `53.2560%` | `111.7365%` | `111.7365%` | `1` |

- C 期末生产账户：`4,617,867.08`
- C 期末锁盈账户：`7,504,989.87`
- C 期末扩张储备：`5,003,326.58`
- 总提款：`12,508,316.45`
- 总补回：`0.00`
- 提款次数：`39`
- 首次提款日期：`2021-10-29`

## 视觉输出

- ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_ledger_stage020_balanced_tranche_profit_lock_proxy_v1.csv`
- transfers：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_transfers_stage020_balanced_tranche_profit_lock_proxy_v1.csv`
- metrics：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_metrics_stage020_balanced_tranche_profit_lock_proxy_v1.csv`
- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_report_stage020_balanced_tranche_profit_lock_proxy_v1.md`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_path_drawdown_chart_stage020_balanced_tranche_profit_lock_proxy_v1.png`
- account layers：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_account_layers_chart_stage020_balanced_tranche_profit_lock_proxy_v1.png`
- transfer ladder：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_transfer_ladder_chart_stage020_balanced_tranche_profit_lock_proxy_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_return_drawdown_scatter_stage020_balanced_tranche_profit_lock_proxy_v1.png`
- yearly heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage020_balanced_tranche_profit_lock_proxy/qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_year_return_heatmap_stage020_balanced_tranche_profit_lock_proxy_v1.png`

## 视觉结论

- path chart 显示 C 的总财富绿线在 `2022` 后比官方蓝线平滑，最大回撤确实浅了约 `10.57pp`。
- 同一张图也显示 C 从 `2021` 后系统性跑不赢官方蓝线，收益保留只有 `43.4992%`，低于目标 `80%`。
- 橙色生产账户线在提款后长期贴近 `500万` 附近，2022 后生产账户最大回撤达到 `-55.2403%`，比官方更深；这说明提款改善的是总财富保全，不是策略本体或生产账户风险。
- account layers 图显示 risk scale 从 `2021` 后逐步降到约 `0.12`，后续右尾复利被大量转移到锁盈/扩张储备，导致收益保留失败。
- transfer ladder 显示 `39` 次提款，累计锁盈 `750.50万`，但这些资金不再参与生产账户复利，因此不能满足“收益保留 80%+”。

## 结论

- 本阶段结论：`stage020_balanced_tranche_proxy_failed_return_retention`。
- 是否进入下一步：不作为 C9/15w 低回撤候选，不接正式版。
- 是否更新本线 `LINE.md`：是，追加 Stage020 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：`balanced_tranche_v1` 可直接复用到 C9/15w 并同时满足总财富回撤下降与收益保留 `80%+`。
- 新增结果：在 C9/15w 上，该固定账户层规则能锁出利润、降低总财富回撤，但对生产账户复利压制过强，收益保留仅 `43.4992%`。

## 过拟合反思

- 运行前判断：否。规则来自既有 Stage232/237 的账户治理口径，不按 C9/15w 的坏窗口、品种、方向、月份或指标曲线反推。
- 运行后判断：否，本次没有调参；失败后若继续改提款阈值、比例、锁盈拆分或只看某个起点，就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage019 后继续分钟内降仓会变成参数救援；不改变单笔路径的资金分层是更低自由度方向。
- 运行后判断：该固定账户层形状对 C9/15w 没有候选价值；整条目标仍有价值，但下一步要换真正外生风险源，或只做更严格的多起点账户审计而不是调提款参数。

## 后续规划和 TODO

- 停止把 Stage232 `balanced_tranche_v1` 直接当作 C9/15w 候选，不扫 `sweep_start/sweep_ratio/lock_ratio/expansion_ratio`。
- 账户层若继续，只能做多起点“固定规则是否稳定失败/稳定保全”的审计，不能把多起点结果用于调参数。
- 若继续追求目标，应优先找真正外生风险源或可交易状态，而不是继续在 C9 单笔路径里用入场后分钟标签削右尾。
