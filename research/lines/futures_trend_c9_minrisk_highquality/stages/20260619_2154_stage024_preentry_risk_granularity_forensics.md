# Stage024 入场前风险颗粒度 / 风险距离只读归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 21:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读法证，不是交易规则，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段 `candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API

## 外部调研与判断

- 参考资料：
  - Rob Carver `Capital correction (pysystemtrade)`：风险资本会直接缩放仓位，实盘亏损后降风险是合理纪律；但复利/半复利会改变曲线形状，评估策略时不能只看最终复利结果。链接：https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html
  - `pysystemtrade` backtesting docs：趋势系统的仓位、buffer、账户曲线和 portfolio 层应作为系统级对象处理，不应把局部历史坏桶写成临时补丁。链接：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - Sandberg & Ohman `Position sizing methods for a trend following CTA`：仓位方法评估应固定入场/退出逻辑，比较风险收益关系；目标波动、动态止损等 sizing 方法可能改善风险收益，但必须避免参数过拟合。链接：https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
- 我的判断：
  - Stage023 已反证 `active_2/stress_loss` 分支，下一步必须回到入场前可见、与最终盈亏标签无关的字段。
  - 本阶段只审计 `selected_volume`、`contracts_by_risk`、`stop_distance`、`risk_to_target`、`margin_cap_binding` 等 sizing/risk ledger 字段是否存在单调风险源。
  - 如果大手数、窄止损或 cap binding 同时承载官方右尾，就不能按“看起来风险大”机械削仓；这会违背“高质量信号用最小风险搏最大收益”的本质，因为最小风险不是最小手数，而是单位风险换取最大右尾的不对称性。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage024_preentry_risk_granularity_forensics.py`
- 修改脚本：无正式策略脚本修改；只修正本阶段报告表格生成时整数年度列名的 Markdown 渲染问题。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/`
- 新增诊断分桶：
  - `selected_volume`：`vol_1/2_10/11_50/51_100/101_500/gt500`
  - `contracts_by_risk`：`riskctr_1/2_10/11_50/101_500/501_2000/gt2000`
  - `stop_distance`：`stop_le1pct/1_2pct/2_4pct/gt4pct`
  - `risk_to_target`：`rtt_le25/25_50/50_75/75_95/95_105/gt105`
  - `risk_cash`、`margin_to_risk_contract`、`margin_cap_binding`
- 新增参数：无交易参数；仅新增固定只读分桶边界。
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：
  - `.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage024_preentry_risk_granularity_forensics.py` 通过。
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage024_preentry_risk_granularity_forensics.py` 成功生成 CSV/JSON/Markdown/PNG。

## 回测/归因参数

- 输入：
  - Stage023/Stage022 entry state features 与官方 C9/15w closed-lot 账本。
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 账户规模：`15w` live profile；本阶段不改变账户规模。
- 成本口径：沿用官方 C9/15w closed-lot/curve 口径；不新增撮合、不新增滑点。
- 样本过滤：官方 closed lots 全样本 `399` 笔；分桶只使用入场前或下单时 risk ledger 可见字段。
- 策略/归因口径：
  - 不重跑策略、不改仓位，只做入场前 sizing/risk ledger 字段的 cohort 归因。
  - 所有 bucket 只用于解释，不产生交易条件。

## 结果

- 官方 C9/15w 基准参考：
  - 期末权益 `39,176,437.60`
  - 总收益 `26017.6251%`
  - 最大回撤 `-45.0827%`
  - Sharpe `1.6339`
  - 总滑点 `2,730,130`
  - 总交易次数 `787`
  - 胜率参考 `53.2560%`
- `all_lots`：
  - `399` 笔、`35` 产品、`9` 年
  - closed-lot realized PnL `43,054,612.60`
- 决策：`stage024_preentry_risk_granularity_no_candidate_nonmonotonic_right_tail_dominant`
- `margin_cap_binding`：
  - `37` 笔、`17` 产品、`9` 年
  - 净 PnL `13,724,545.00`
  - 正收益年份 `6`、负收益年份 `3`
  - 结论：保证金 cap binding 不是坏信号。
- `selected_volume_101_500`：
  - `125` 笔、`18` 产品、`6` 年
  - 净 PnL `30,912,270.60`
  - 正收益年份 `5`、负收益年份 `1`
  - 结论：大手数不是坏信号充分条件，反而是官方右尾核心区域。
- `risk_to_target_50_75`：
  - `49` 笔、`17` 产品、`8` 年
  - 净 PnL `-2,582,991.60`
  - 正收益年份 `3`、负收益年份 `5`
  - 但相邻桶 `rtt_le25` 净 PnL `23,748,050.00`、`rtt_75_95` 净 PnL `11,933,349.10`、`rtt_95_105` 净 PnL `6,405,706.30`，关系明显非单调。
- `riskcash_le2k`：
  - `41` 笔、`12` 产品、`3` 年
  - 净 PnL `-31,860.20`
  - 样本宽度不足，且更像低参与度而非可交易化风险源。
- `stop_le1pct`：
  - `130` 笔、`19` 产品、`9` 年
  - 净 PnL `17,216,006.00`
  - 正收益年份 `8`、负收益年份 `1`
  - 结论：窄止损不是坏信号，不能机械“止损窄/手数大就降风险”。

## 视觉输出

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_report_stage024_preentry_risk_granularity_forensics_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_decision_stage024_preentry_risk_granularity_forensics_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_stage024_preentry_risk_granularity_forensics_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_bucket_summary_stage024_preentry_risk_granularity_forensics_v1.csv`
- bucket-year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_bucket_year_matrix_stage024_preentry_risk_granularity_forensics_v1.csv`
- cohort summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_cohort_summary_stage024_preentry_risk_granularity_forensics_v1.csv`
- path contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_path_contribution_chart_stage024_preentry_risk_granularity_forensics_v1.png`
- bucket-year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_bucket_year_heatmap_stage024_preentry_risk_granularity_forensics_v1.png`
- risk scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_risk_granularity_scatter_stage024_preentry_risk_granularity_forensics_v1.png`
- volume-stop heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage024_preentry_risk_granularity_forensics/qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_volume_stop_heatmap_stage024_preentry_risk_granularity_forensics_v1.png`

## 视觉结论

- path contribution chart 显示 `margin_cap_binding`、`selected_volume_101_500`、`risk_to_target_le25` 都随官方权益右尾台阶上行，不是应削风险的坏状态。
- bucket-year heatmap 显示负贡献不是沿风险粒度逐级扩大；`risk_to_target_50_75` 只是局部中间桶偏弱，不能推广为单调利用率规则。
- risk scatter 显示盈利点与亏损点在 `actual risk / target risk` 和 `entry risk distance pct` 空间高度混杂，没有干净的可见分界。
- volume-stop heatmap 显示 `vol_101_500 × stop_le1pct/stop_1_2pct/stop_2_4pct` 均为主要正贡献区域；窄止损和大手数是右尾发动区之一。
- 默会经验判断：C9 的“最小风险”不能被简化为小手数、低 utilization 或宽止损。真正有价值的是在趋势赔率明显偏斜时承担经过 sizing 计算后的集中风险；机械削掉这些区域会损害右尾。

## 结论

- 本阶段结论：`stage024_preentry_risk_granularity_no_candidate_nonmonotonic_right_tail_dominant`。
- 是否进入下一步：不进入真实引擎，不接正式版，不触发 A/B。
- 是否更新本线 `LINE.md`：是，追加 Stage024 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：`selected_volume` 大、`contracts_by_risk` 大或 `margin_cap_binding` 可以作为普世坏信号。
- 删除假设：`stop_distance` 窄或 `risk_to_target` 高可以机械降风险。
- 保留观察：`risk_to_target_50_75` 和 `riskcash_le2k` 有局部弱性，但非单调、样本窄或解释不稳，只能做 forward watch，不可交易化。

## 过拟合反思

- 运行前判断：否。分桶边界来自风险会计和数量级刻度，不按年份、产品、方向或最终盈亏反推。
- 运行后判断：否，本阶段没有产生候选，也没有把局部坏桶写成规则；但若继续拿 `rtt_50_75`、`riskcash_le2k`、某个 volume-stop 交叉格做交易条件，就是隐性过拟合。
- 原因：所有有效风险源都必须满足跨年、跨品种、单调或可解释的普世结构；Stage024 的负桶不满足这些条件。

## 继续价值反思

- 运行前判断：有。Stage023 后必须检查是否存在入场前可见的 risk ledger 风险源，否则容易继续从未来亏损 cohort 反推。
- 运行后判断：有，但不应继续本分支。Stage024 排除了资金颗粒度/风险距离的简单普世削仓路线，减少了后续错误搜索空间。
- 原因：当前目标仍未达成；但继续价值应转向真正外生、入场前可见、与最终盈亏标签无关的信息，或只做 forward watch，而不是继续扫 sizing/risk ledger 阈值。

## 后续规划和 TODO

- 停止把 `selected_volume`、`contracts_by_risk`、`stop_distance`、`risk_to_target`、`risk_cash`、`margin_to_risk_contract`、`margin_cap_binding` 单桶或交叉格写成交易规则。
- 不扫 `risk_to_target`、止损距离、手数、风险金额、保证金金额等阈值；不按产品、年份、方向、交易所救参。
- 下一步若继续目标，应换信息源：
  - 外生且入场前可见的市场状态；
  - 或预声明 forward watch；
  - 或寻找不改变官方单笔右尾路径的独立 sleeve / 外层资金纪律。
