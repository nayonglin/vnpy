# Stage014 Stage013 失败归因：最小风险观察为何破坏右尾

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 19:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / 失败机制复盘 / 视觉审计
- 是否重要突破：否。它不是新候选，也不改变正式版本；但明确否决 Stage013 主形状继续救参。
- 是否触发A/B：否。没有新策略版本、没有接入正式版本、没有修改正式配置。

## 外部调研与判断

- 参考资料：
  - SSRN `Trend Following Strategies: A Practical Guide`：https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1
  - SSRN `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4438260_code412374.pdf?abstractid=4438260&mirid=1
  - GitHub `PyTrendFollow`：https://github.com/chrism2671/PyTrendFollow
  - GitHub `awesome-systematic-trading`：https://github.com/paperswithbacktest/awesome-systematic-trading
- 我的判断：
  - 趋势跟随的长期收益高度依赖右尾和仓位路径，position sizing 本身会重塑收益、回撤和正偏结构。
  - Stage013 不是“确认窗口还要微调”的问题，而是默认 1 手观察让系统在真正右尾开始时暴露不足；这会直接破坏 C9 的复利台阶。
  - 因此本阶段只做失败归因，不设计新交易规则；若用本阶段结果反推 `15/30/60`、`1/2/3` 手或 `0.25/0.5/1R`，就是过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage014_stage013_failure_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读匹配口径 `vt_symbol + direction + entry_day`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage013 A/C 曲线与 closed lots，官方路径为 C9/15w。
- 账户规模：`150000`，官方版本 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 成本口径：沿用 Stage013/官方 C9 口径；本阶段不新增成本压力回测。
- 样本过滤：Stage013 `quality_restore_events` 共 `170` 个事件。
- 策略/归因口径：
  - A：当前官方正式 C9/15w。
  - C：Stage013 `minrisk_1lot_clean30_restore` 候选。
  - 事件匹配：用 `vt_symbol + direction + entry_day` 精确匹配 official/candidate closed lots；避免使用 plan-day offset 作为主键。
  - 输出：事件账本、bucket/year 归因、top negative delta、资金路径归因图、delta contribution chart、分钟 atlas。

## 结果

- Stage013 A 官方期末权益：`39,176,437.60`
- Stage013 A 官方总收益：`26017.6251%`
- Stage013 A 官方最大回撤：`-45.0827%`
- Stage013 A 官方 Sharpe：`1.6331`
- Stage013 A 官方总滑点：`2,730,130`
- Stage013 A 官方总交易次数：`787`
- Stage013 A 官方胜率：`53.2560%`
- Stage013 C 候选期末权益：`6,170,215.30`
- Stage013 C 候选总收益：`4013.4769%`
- Stage013 C 候选收益保留：`15.4260%`
- Stage013 C 候选最大回撤：`-55.4688%`
- Stage013 C 候选 Sharpe：`1.1071`
- Stage013 C 候选总滑点：`534,810`
- Stage013 C 候选总交易次数：`864`
- Stage013 C 候选胜率：`48.8073%`
- Stage014 事件级结果：
  - Stage013 事件数：`170`
  - 精确匹配事件：`168`
  - 未匹配事件：`2`
  - 事件级 A 官方 PnL：`29,474,664.50`
  - 事件级 C 候选 PnL：`4,971,627.50`
  - 事件级 C-A delta：`-24,503,037.00`
- Bucket 归因：
  - `clean_restore_open`：`41` 事件，官方 PnL `24,752,030.00`，候选 PnL `5,662,990.00`，delta `-19,089,040.00`，占总负差约 `77.9048%`。
  - `no_restore_not_clean_30m`：`27` 事件，官方 PnL `3,106,213.70`，候选 PnL `53,480.40`，delta `-3,052,733.30`。
  - `c9_stop_retry_before_quality_restore`：`45` 事件，匹配 `44`，官方 PnL `2,412,730.30`，候选 PnL `2,151.20`，delta `-2,410,579.10`。
  - `clean_restore_stopped`：`56` 事件，匹配 `55`，官方 PnL `-768,809.50`，候选 PnL `-746,994.10`，delta `+21,815.40`。
  - `official_path_missing_stage861_observation`：`1` 事件，官方 PnL `-27,500.00`，候选 PnL `0.00`，delta `+27,500.00`。
- 关键反例：
  - `OI309.CZCE` long `2023-06-28`：C9 stop 先于 30m quality，A `6,083,280`，C `12,240`，delta `-6,071,040`。
  - `jm2509.DCE` long `2025-07-09`：clean restore open，A `8,970,000`，C `3,060,030`，delta `-5,909,970`。
  - `SH405.CZCE` short `2024-03-26`：no restore not clean，A `2,265,000`，C `4,530`，delta `-2,260,470`。
  - `au2412.SHFE` long `2024-10-17`：no restore not clean，A `1,248,180`，C `17,580`，delta `-1,230,600`。

## 视觉分析

- `delta_contribution_chart`：
  - 黑色总 delta 最终约 `-2450万`。
  - 蓝色 `clean_restore_open` 是最大负贡献，最终约 `-1909万`，说明主要损失不是“没有恢复”，而是“恢复太晚、恢复前暴露太小”。
  - 下方官方 PnL 贡献图显示这些事件恰好承载了 C9 的主要右尾收益。
- `path_attribution_chart`：
  - A 从 `2023` 后出现多次权益台阶，C 的 1 手观察路径没有同步放大，长期压低权益分母。
  - top negative delta 标记集中在 A 与 C 拉开的位置，broker10 恶化不是单日噪声，而是复利底座被压低后的结果。
- 分钟 atlas：
  - `OI309` 显示 C9 entry-day stop/retry 在 09:00 先触发，后续仍走出大右尾；固定先等 30m 会错过这种趋势启动。
  - `jm2509/jm2401/OI305` 显示即使 30m clean 后恢复，C 仍只保留官方收益的一小部分，因为前 30m 的 1 手 scout 已经切断大量仓位暴露。
  - `SH405/au2412` 显示 no-clean 并非坏信号充分条件，前 30m 不顺仍可能走成官方大赢家。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_report_stage014_stage013_failure_attribution_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_summary_stage014_stage013_failure_attribution_v1.csv`
- ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_event_match_ledger_stage014_stage013_failure_attribution_v1.csv`
- bucket：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_bucket_attribution_stage014_stage013_failure_attribution_v1.csv`
- year：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_year_attribution_stage014_stage013_failure_attribution_v1.csv`
- top negative delta：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_top_negative_delta_stage014_stage013_failure_attribution_v1.csv`
- 资金路径图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_path_attribution_chart_stage014_stage013_failure_attribution_v1.png`
- delta 贡献图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_delta_contribution_chart_stage014_stage013_failure_attribution_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage014_stage013_failure_attribution/qmt_roll_stage014_c9_minrisk_stage013_failure_attribution_atlas_page001_stage014_stage013_failure_attribution_v1.png` 至 `page005`

## 结论

- 本阶段结论：`stage014_stage013_failure_attribution_no_trade_rule`
- Stage013 失败机制已经明确：默认最小风险观察不是高质量信号执行，而是对趋势跟随右尾暴露的系统性削弱。`clean_restore_open` 已经是最大损失来源，说明不能用“更精细恢复规则”救 Stage013。
- 是否进入下一步：是，但不沿 Stage013 形状继续。
- 下一步：
  - 停止全体默认最小风险、30m clean 后恢复官方风险的主形状。
  - 不扫 scout 手数、确认窗口、R 阈值、品种、方向、年份、月份。
  - 若继续信号质量方向，只能先做只读入场前/入场当刻结构归因，要求特征在开仓前或开仓瞬间可见，并且不能切断官方右尾仓位。
  - 若找不到稳健结构，转向不改变单笔交易路径的账户层外部资金分层、出金锁盈或独立 sleeve。

## 过拟合反思

- 运行前判断：否。本阶段只做 Stage013 失败归因，不生成新交易分支、不挑参数。
- 运行后判断：否。本阶段没有选择品种、方向、年份、月份、窗口或 R 倍数规则；但如果用本阶段 top delta 样本反推新规则，会立刻进入过拟合。
- 原因：归因口径是事件级精确匹配和视觉审计，目标是找失败机制，不是从失败样本中挑补丁。

## 继续价值反思

- 运行前判断：有价值。Stage013 失败严重，必须先解释失败机制，否则下一步容易继续在 `1手/30m/0.5R` 附近救参。
- 运行后判断：本阶段归因有价值；Stage013 形状继续推进没有价值。
- 原因：结果显示主要损失来自错过右尾暴露，而不是恢复止损的小噪声。继续沿 Stage013 微调只会越来越贴合历史右尾路径，不能穿越周期。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage014 结论和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是重要突破、正式候选、路线废弃、跨线合并或记录体系迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是失败归因，不改变正式候选和正式执行路径。
