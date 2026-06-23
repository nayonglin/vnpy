# Stage082 最大回撤 episode 可见标签审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 10:41 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 maxDD episode attribution；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否；但属于重要防伪结论，剔除了一个未来亏损派生伪标签。
- 是否触发A/B：否。已读取 `skills/version-ab-experiment/SKILL.md`，本阶段最终没有可进入正式候选或 A/B 的策略版本。

## 外部调研与判断

- 参考资料：
  - AQR/SSRN `A Century of Evidence on Trend-Following Investing`：趋势跟随跨长期样本有效，但收益常来自少数趋势右尾，不能为了局部回撤随意砍掉右尾暴露。
  - SSRN `Trade Sizing Techniques for Drawdown and Tail Risk Control`：回撤控制应来自预先定义、可复验的 sizing/tail-risk 方法，而不是事后亏损 cohort 标签。
  - KTH/DiVA `Position sizing methods for a trend following CTA`：仓位方法可改善 CTA 风险体验，但必须保护趋势策略的盈利尾部。
- 我的判断：Stage081 已证明 stop/noise ratio 承载右尾；Stage082 只应检查已有 live-visible 标签是否能解释官方最大回撤段。任何由 `realized_pnl < 0` 派生的标签都不是入场当时可见信息，不能作为候选。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage082_maxdd_episode_label_audit.py`
- 修改脚本：同上；修正标签池，剔除未来盈亏派生标签，并消除 pandas `errors="ignore"` 弃用警告。
- 删除脚本：无
- 新增参数：审计闸门 `MIN_PREFLIGHT_LOTS=20`；未来盈亏派生剔除清单 `loss_flag/win_flag/active2_loss_flag/stress_loss_flag/active2_stress_loss_flag`
- 修改参数：无正式策略参数修改；仅修正 Stage082 preflight 审计口径。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w Stage010 official curve；本阶段无新增交易成本。
- 样本过滤：official closed lots `399` 笔；官方最大回撤 peak-to-trough 为 `2022-03-09 -> 2022-06-29`。
- 策略/归因口径：A 为当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；本阶段只把 maxDD episode 与 Stage024/Stage081 既有标签交叉，检查亏损捕获和右尾冲突。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage082_no_existing_visible_label_isolates_maxdd_without_righttail_damage`
  - maxDD peak date：`2022-03-09`
  - maxDD trough date：`2022-06-29`
  - maxDD recovery date：`2022-07-14`
  - peak equity：`9,506,358.50`
  - trough equity：`5,220,639.60`
  - maxDD overlap lots：`22`
  - maxDD overlap net PnL：`-257,098.90`
  - maxDD overlap loss lots：`17`
  - maxDD overlap loss abs：`3,188,608.90`
  - candidate label count：`124`
  - preflight pass label count：`0`
  - 最高亏损捕获标签 `preentry_system_stress_bool=1`：捕获 `100%` maxDD overlap loss，但全样本净 PnL `+8,971,144.40`、正贡献 `+16,390,640.00`、大赢家 `7` 笔，右尾/亏损捕获比 `5.1404`，不得规则化。
  - `no_follow_30m=1`：净 PnL `-6,100,118.10`、maxDD loss capture `55.5737%`、大赢家 `0`，但正贡献仍有 `+5,209,105.00`，右尾/亏损捕获比 `2.9396`，且 Stage008/019 已被真引擎反证，不得重启。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_report_stage082_maxdd_episode_label_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_summary_stage082_maxdd_episode_label_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_contribution_curve_stage082_maxdd_episode_label_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_label_scorecard_stage082_maxdd_episode_label_audit_v1.csv`
- visuals：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_maxdd_episode_path_chart_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_label_loss_capture_scatter_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_top_label_year_heatmap_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_atlas_page001_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_atlas_page002_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_atlas_page003_stage082_maxdd_episode_label_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage082_maxdd_episode_label_audit/qmt_roll_stage082_c9_minrisk_maxdd_episode_label_audit_atlas_page004_stage082_maxdd_episode_label_audit_v1.png`

## 视觉分析

- 资金曲线：maxDD peak-to-trough 集中在 `2022-03-09 -> 2022-06-29`，但后续权益大台阶主要来自 maxDD 段之外的右尾；广义 stress 标签若规则化，会切掉后续复利底座。
- scatter：能捕获 `20%+` maxDD loss 的标签多数全样本净 PnL 为正，且 positive PnL / captured maxDD loss 大幅高于 `1`；说明它们不是坏信号集合。
- 年度热图：`preentry_system_stress` 在 `2021/2022/2023` 都为正贡献，`under_noise_floor` 在 `2023/2025` 是核心右尾。标签不是“坏状态”，只是 2022 回撤段也出现过。
- 分钟 atlas：maxDD 亏损样本没有统一形态，有快速下探后修复、缓慢走弱、short 方向先不利后转有利等多种路径；右尾冲突样本 `OI309/jm2509/OI305/ru2501/jm2401` 证明 top loss-capture 标签会误伤趋势右尾。maxDD overlap 期间也有 `fu2205/SM205/au2206` 等赢家，不能把 episode 内的压力状态直接做过滤或降仓。

## 结论

- 本阶段结论：不进入真引擎。剔除未来亏损标签后，现有可见标签没有一个通过 preflight；最高亏损捕获标签同时承载大量右尾，`no_follow_30m` 虽为负净值但已被真实组合引擎反证，不能重启。
- 是否进入下一步：不沿“已有可见标签隔离 maxDD”方向继续。
- 下一步：停止组合 Stage022/023/024/081 近似标签来救 2022 maxDD。若继续目标，必须换真正点时化、入场前可见、非最终盈亏标签的新外生源，或做不改变 C9 单笔路径的账户层固定规则；不得用 maxDD episode、产品、年份、方向、月份或 near-miss label 组合补丁化。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但只有在保持本次“剔除未来盈亏标签、不组合 near-miss 标签、不扫桶”的约束下才成立。
- 原因：本阶段使用固定官方 maxDD 窗口和既有标签，只做归因；最初输出里 `active2_stress_loss_flag` 看似通过，但源码确认它由 `realized_pnl < 0` 派生，已经剔除。若把该标签或相邻组合当成规则，就是直接事后泄漏和过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：对现有标签继续做 maxDD reducers 没有价值；对全目标仍有价值。
- 原因：Stage082 明确封止了“已有标签解释 2022 maxDD”的捷径，避免后续把历史亏损集合包装成最小风险规则。继续推进应转向真正新信息源或账户层固定规则，而不是再从 closed-lot 内挖标签。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage082 结论和停止边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、路线废弃或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无回测候选、不触发 A/B；只记录在线内 stage 和 LINE。
