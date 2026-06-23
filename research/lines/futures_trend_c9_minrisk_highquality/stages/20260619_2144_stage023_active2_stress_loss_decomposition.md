# Stage023 active_2 / stress_loss 二级只读拆解

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 21:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读法证，不是交易规则，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段 `candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API

## 外部调研与判断

- 参考资料：
  - `pysystemtrade` GitHub：Rob Carver 的系统化期货交易/回测工程，强调组合层 risk overlay、correlation、instrument weights 等应作为系统层资产，而不是事后补丁。链接：https://github.com/pst-group/pysystemtrade
  - Rob Carver `The three kinds of (over) fitting`：策略复杂度/自由度越高，越容易把样本内曲线拟合好但失去样本外能力；应限制自由度并遵守 no-time-machine。链接：https://qoppac.blogspot.com/2015/11/the-three-kinds-of-overfitting.html
  - Rob Carver `When endogenous risk management isn't enough`：风险覆盖层可以降低尾部，但会牺牲收益和趋势正偏；校准不应按历史表现微调。链接：https://qoppac.blogspot.com/2020/05/when-endogenous-risk-management-isnt.html
  - Rob Carver `Simulating my futures system`：为避免过拟合，应跨品种池化证据，不能轻易认为某类品种需要不同规则。链接：https://qoppac.blogspot.com/2015/03/simulating-my-futures-system.html
- 我的判断：
  - Stage022 已证明粗压力状态本身承载大量右尾，不能直接削仓。
  - 本阶段只允许拆解 `active_2` 与 `stress_loss` 的结构稳定性；其中 `loss` 使用未来结果标签，只能用于解释，不具备实时可交易性。
  - 如果亏损主要来自少数年份/产品块，按第一性原则应拒绝交易化，避免把默会经验误写成产品/年份黑名单。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage023_active2_stress_loss_decomposition.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/`
- 新增诊断 cohort：
  - `active_2_all`
  - `active_2_loss_future_label`
  - `active_2_win`
  - `stress_all`
  - `stress_loss_future_label`
  - `stress_win`
  - `active2_stress_loss_future_label`
  - `non_active2_nonstress`
- 新增派生标签：
  - `margin_cap_binding_flag = contracts_by_margin < contracts_by_risk`
  - `same_dir_corr_high_flag = same_direction_active_count >= 1 且 max_corr > 0.60`
  - `entry_or_first_aligned`、`ai4_6_entry_or_first_aligned`、交易所、产品-年份矩阵
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：
  - `.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage023_active2_stress_loss_decomposition.py` 通过。
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage023_active2_stress_loss_decomposition.py` 成功生成 CSV/JSON/Markdown/PNG。

## 回测/归因参数

- 输入：
  - Stage022 entry state features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_entry_state_features_stage022_path_risk_state_forensics_v1.csv`
  - Stage022 daily state：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_stage022_path_risk_state_forensics_v1.csv`
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 方法：
  - 不重跑策略、不改仓位，只读取官方 closed lots 与入场前一日组合状态。
  - 按 cohort 统计 closed-lot PnL、正负覆盖、正负年份、产品/年份亏损集中度、入场结构率。
  - 生成官方权益曲线 + cohort 累计贡献曲线、结构率热图、产品-年份热图、pre-entry state scatter。
- 口径限制：
  - `active_2_loss_future_label` 与 `stress_loss_future_label` 使用未来 realized PnL，只能作为失败结构说明，不能作为任何实时条件。
  - 本阶段不是候选，不进入真引擎，不触发 A/B。

## 结果

- 官方 C9/15w 基准沿用 Stage022/019：
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
  - `8` 个正收益年份、`1` 个负收益年份
- `active_2_all`：
  - `64` 笔、`22` 产品、`8` 年
  - 净 PnL `-1,106,150.00`
  - 正收益覆盖 `4.0328%`
  - 负收益覆盖 `15.6371%`
  - 正收益年份 `4`、负收益年份 `4`
  - `entry_or_first_aligned_rate=39.0625%`
  - `ai4_6_entry_or_first_aligned_rate=9.3750%`
  - `margin_cap_binding_rate=6.2500%`
  - `same_dir_corr_high_rate=14.0625%`
- `active_2_loss_future_label`：
  - `38` 笔、`19` 产品、`8` 年
  - 净 PnL `-3,830,330.00`
  - top3 产品亏损占该 cohort 亏损 `57.5495%`
  - top1 年亏损占该 cohort 亏损 `42.9107%`
  - 最差产品-年份包括 `AP.CZCE 2022 -775,880`、`AP.CZCE 2025 -500,000`、`OI.CZCE 2022 -468,160`、`fu.SHFE 2022 -379,440`、`cu.SHFE 2025 -372,000`
- `stress_all`：
  - `100` 笔、`26` 产品、`5` 年
  - 净 PnL `8,971,144.40`
  - 正收益覆盖 `24.2645%`
  - 负收益覆盖 `30.2896%`
  - 正收益年份 `5`、负收益年份 `0`
  - 结论：系统压力整体不是坏信号。
- `stress_loss_future_label`：
  - `64` 笔、`24` 产品、`5` 年
  - 净 PnL `-7,419,495.60`
  - top3 产品亏损占该 cohort 亏损 `47.4582%`
  - top1 年亏损占该 cohort 亏损 `74.0184%`
  - 年度亏损：`2019 -5,384.50`、`2020 -23,543.00`、`2021 -434,928.60`、`2022 -5,491,794.50`、`2023 -1,463,845.00`
  - 最差产品-年份包括 `AP.CZCE 2022 -1,067,820`、`fu.SHFE 2022 -1,065,165.60`、`jm.DCE 2022 -931,544.10`、`lh.DCE 2022 -581,184.00`
- `active2_stress_loss_future_label`：
  - `6` 笔、`5` 产品、`4` 年
  - 净 PnL `-1,248,788.50`
  - top3 产品亏损占 `98.6392%`
  - 样本太小且集中，不可交易化。

## 视觉输出

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_report_stage023_active2_stress_loss_decomposition_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_decision_stage023_active2_stress_loss_decomposition_v1.json`
- cohort summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_cohort_summary_stage023_active2_stress_loss_decomposition_v1.csv`
- bucket attribution：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_bucket_attribution_stage023_active2_stress_loss_decomposition_v1.csv`
- year product matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_year_product_matrix_stage023_active2_stress_loss_decomposition_v1.csv`
- path contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_path_contribution_chart_stage023_active2_stress_loss_decomposition_v1.png`
- structure heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_structure_rate_heatmap_stage023_active2_stress_loss_decomposition_v1.png`
- active2 product-year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_active2_product_year_heatmap_stage023_active2_stress_loss_decomposition_v1.png`
- stress loss product-year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_stress_loss_product_year_heatmap_stage023_active2_stress_loss_decomposition_v1.png`
- pre-entry scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage023_active2_stress_loss_decomposition/qmt_roll_stage023_c9_minrisk_active2_stress_loss_decomposition_preentry_state_scatter_stage023_active2_stress_loss_decomposition_v1.png`

## 视觉结论

- path contribution chart 显示 `stress_all` 累计最终是正的，不能作为全局降风险条件；`active_2_loss` 和 `stress_loss` 的下沉主要是阶段性台阶，不是稳定提前预警线。
- structure heatmap 显示 `active_2_win` 的 `entry_or_first_aligned_rate` 为 `52.0000%`，高于 `active_2_loss` 的 `28.9474%`，aligned 更像右尾保护标签，而不是坏信号。
- active2 product-year heatmap 显示净亏主要集中在 `2022` 和 `2025` 少数产品块；同一 `active_2` 在 `2022` 也有 `SM/au/MA` 正贡献，不能写成 active=2 规则。
- stress loss product-year heatmap 几乎是 `2022` 压力年产品簇；这最容易诱导产品/年份黑名单，必须按过拟合拒绝。
- pre-entry scatter 显示亏损点与其他样本在前一日 drawdown/broker10 空间混杂；没有干净可见边界。

## 结论

- 本阶段结论：`stage023_active2_stress_loss_no_candidate_concentrated_nonmonotonic_future_label`。
- 是否进入下一步：不进入真实引擎，不接正式版，不触发 A/B。
- 是否更新本线 `LINE.md`：是，追加 Stage023 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：`active_2` 可以作为普世削仓条件。
- 删除假设：`stress_loss` 背后存在一个简单、入场前可见、跨年份稳定的共同结构。
- 新增结果：当前损失更像少数压力年份/产品簇与官方趋势右尾共用状态空间，而不是能被一个低自由度分钟/组合状态规则提前分离。

## 过拟合反思

- 运行前判断：否。Stage023 只做固定 cohort 拆解，且明确 `loss` 是未来标签，不能当交易规则。
- 运行后判断：否，本阶段没有产生候选；但如果继续沿 `2022`、`2025`、`AP/fu/jm/lh`、`active_2_loss` 或 `stress_loss` 写规则，就是明显过拟合。

## 继续价值反思

- 运行前判断：有。Stage022 留下的 `active_2` 异常需要拆清，否则容易误把它当规则。
- 运行后判断：有，但不是沿本分支继续。`active_2/stress_loss` 已不足以形成普世规则；后续若继续目标，应转向真正外生、入场前可见、与最终盈亏无关的风险源，或者做 forward watch，而不是从历史亏损 cohort 反推。

## 后续规划和 TODO

- 停止 `active_2`、`stress_loss`、产品-年份簇、方向、交易所、具体品种的交易化。
- 停止在该分支上扫 active contracts、stress 阈值、corr 阈值、margin cap 状态或 aligned 组合。
- 下一阶段如果继续，应换第一性原则：
  - 找独立于最终盈亏标签的外生风险状态；
  - 或做仅观察 forward watch；
  - 或回到分钟级入场前可见、跨年跨品种稳定、不会切断右尾的全新结构。
