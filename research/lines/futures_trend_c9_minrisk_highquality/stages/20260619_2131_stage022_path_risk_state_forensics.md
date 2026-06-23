# Stage022 path_risk_state_forensics 路径风险状态只读归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 21:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读路径/组合状态归因，不是交易规则，不是撮合级真引擎
- 是否重要突破：否
- 是否触发A/B：否，本阶段 `candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API

## 外部调研与判断

- 参考资料：
  - Rob Carver `When endogenous risk management isn't enough: a simple risk overlay`：风险覆盖层应位于主系统外，处理组合 expected risk、相关冲击、跳跃波动等系统风险。链接：https://qoppac.blogspot.com/2020/05/when-endogenous-risk-management-isnt.html
  - Rob Carver `Vol Targeting and Trend Following`：趋势系统的仓位缩放应区分“按信号给定波动目标”与“全组合事后固定波动”，后者可能抛弃系统平均 conviction；没有免费午餐。链接：https://qoppac.blogspot.com/2018/07/vol-targeting-and-trend-following.html
  - `pysystemtrade` backtesting 文档：系统化组合要缓存和复用 risk overlay、correlation estimates、instrument weights 等跨品种计算，说明组合风险状态是独立于单笔 alpha 的研究层。链接：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - Sandberg & Ohman `Position sizing methods for a trend following CTA`：趋势 CTA 的 position sizing 中，Target Volatility 与 Max Drawdown Minimize 可改善部分风险收益特征，但最大回撤最小化通常偏向小仓位、牺牲绝对收益。链接：https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
- 我的判断：
  - Stage021 证明同向相关/拥挤不是当前 C9 主回撤解释变量；继续改相关阈值会过拟合。
  - 若存在普世风控源，它应先能解释路径：主回撤发生前是否已有可见的组合压力、波动、broker10 或权益分母状态。
  - 本阶段只做固定状态桶归因：前一交易日回撤 `-10/-20/-30%`、broker10 `50/90%`、20日年化波动 `50/100%`、active contracts `0/1/2/3+`。这些是诊断刻度，不是候选参数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage022_path_risk_state_forensics.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/`
- 新增参数/诊断刻度：
  - 前一日回撤桶：`dd_lt10/dd_10_20/dd_20_30/dd_ge30`
  - 前一日 broker10 桶：`broker_0/broker_0_50/broker_50_90/broker_ge90`
  - 前一日 20 日年化波动桶：`vol_lt50/vol_50_100/vol_ge100`
  - 前一日 active contracts 桶：`active_0/active_1/active_2/active_ge3`
  - `preentry_system_stress = prev_drawdown <= -20% OR prev_broker10 >= 90% OR prev_roll20_vol >= 100%`
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：
  - `.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage022_path_risk_state_forensics.py` 通过。
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage022_path_risk_state_forensics.py` 成功生成 CSV/JSON/Markdown/PNG。

## 回测/归因参数

- 输入：
  - Stage019 官方 A 日度曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_stage019_no_follow_light_shave_true_engine_v1.csv`
  - Stage016 closed-lot 特征：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage016_intersection_stability_audit/qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_stage016_intersection_stability_audit_v1.csv`
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 方法：
  - 从官方日度曲线计算 drawdown episodes、20 日/60 日年化波动、20 日收益、broker10、active contracts。
  - 对每笔 official closed lot 绑定“入场前一交易日”的组合状态，避免使用入场后或未来信息。
  - 按固定状态桶统计 closed-lot PnL、正负收益覆盖、跨年稳定性，并生成资金曲线/状态路径图。
- 口径限制：
  - 这是只读归因，不重算整数手，不生成订单，不得直接当成交易规则。
  - `preentry_system_stress` 是归因标签，不是候选信号。

## 结果

- 官方 C9/15w 基准仍沿用 Stage019：
  - 期末权益 `39,176,437.60`
  - 总收益 `26017.6251%`
  - 最大回撤 `-45.0827%`
  - Sharpe `1.6339`
  - 总滑点 `2,730,130`
  - 总交易次数 `787`
  - 胜率参考 `53.2560%`
- 最深 drawdown episode：
  - peak：`2022-03-09`
  - trough：`2022-06-29`
  - recovery：`2022-07-14`
  - 最大回撤：`-45.0827%`
  - drawdown days：`127`
  - peak-to-trough：`112` 天
- `preentry_system_stress` 归因：
  - stress 样本 `100` 笔、`26` 产品、`5` 年
  - 净 PnL `8,971,144.40`
  - 正收益覆盖 `24.2645%`
  - 负收益覆盖 `30.2896%`
  - `5` 个正收益年份、`0` 个负收益年份
  - 平均前一日回撤 `-26.2235%`，平均前一日 broker10 `20.7166%`，平均前一日 20 日年化波动 `59.8278%`
- 固定桶归因：
  - `dd_ge30`：`38` 笔，净 PnL `6,003,926.10`，`3/3` 年正收益；高回撤不是坏信号充分条件。
  - `broker_ge90`：`5` 笔，净 PnL `-7,873.50`，覆盖太小；不能作为主回撤治理规则。
  - `vol_ge100`：`19` 笔，净 PnL `2,015,901.40`；高波动状态不是稳定坏信号。
  - `active_2`：`64` 笔，净 PnL `-1,106,150.00`，但 `active_0/active_1/active_ge3` 均为正，关系不单调，不能直接写成规则。

## 视觉输出

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_report_stage022_path_risk_state_forensics_v1.md`
- daily state：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_stage022_path_risk_state_forensics_v1.csv`
- drawdown episodes：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_drawdown_episodes_stage022_path_risk_state_forensics_v1.csv`
- entry state features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_entry_state_features_stage022_path_risk_state_forensics_v1.csv`
- bucket attribution：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_state_bucket_attribution_stage022_path_risk_state_forensics_v1.csv`
- path state panel：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_path_state_panel_stage022_path_risk_state_forensics_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_entry_state_contribution_stage022_path_risk_state_forensics_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_entry_state_scatter_stage022_path_risk_state_forensics_v1.png`
- yearly heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_year_bucket_heatmap_stage022_path_risk_state_forensics_v1.png`
- drawdown episode bar：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage022_path_risk_state_forensics/qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_drawdown_episode_bar_stage022_path_risk_state_forensics_v1.png`

## 视觉结论

- path state panel 显示，最深回撤谷 `2022-06-29` 附近已经多日 active contracts 为 `0`、broker10 为 `0`；主回撤不是“持续高 broker10 扛仓到谷底”，而是前面交易损失造成权益分母塌陷后进入空仓低谷。
- 2022 主回撤窗口内，broker10 尖峰集中在更早的持仓期；到 trough 时已经无法通过“谷底退出”修复，只能研究入场或持仓早期的风险释放时机。
- contribution chart 显示 `preentry_stress` 红线最终明显为正，`prev DD <= -20` 橙线也长期为正；高回撤/高波动状态不是简单坏信号，统一降风险会砍掉右尾。
- yearly heatmap 显示 stress 桶在 `2021/2022/2023` 都为正，不是单年坏标签。
- scatter 和 bucket 表显示 `active_2` 桶为负，但非单调且集中有 `2025 AP/cu/lc` 与 `2022 AP/OI/fu` 大亏，不能直接变成 `active==2` 规则。

## 结论

- 本阶段结论：`stage022_preentry_system_state_forensics_no_candidate_keep_as_hypothesis_source`。
- 是否进入下一步：不进入真实引擎，不接正式版，不触发 A/B。
- 是否更新本线 `LINE.md`：是，追加 Stage022 结论和下一步边界。
- 是否更新 `research/registry.md`：否，并行研究线日常不更新 registry。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
- 不修改当前 official live config，不连接 CTP，不调用订单 API。

## 删除/修改的假设

- 删除假设：前一日高回撤、高波动、高 broker10 这种粗粒度系统压力可以直接作为 C9 降风险规则。
- 新增结果：高压力状态本身仍承载大量右尾；真正问题更可能是“压力状态下哪些新 entry 缺乏足够质量/流动性/路径确认”，而不是压力状态本身。

## 过拟合反思

- 运行前判断：否。固定状态桶来自组合风险常识，不按坏年份/品种/方向反推。
- 运行后判断：否，本阶段只读归因；但如果直接把 `active_2` 或 `2022` 几笔大亏写成规则，就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage021 后需要找更强的路径解释源。
- 运行后判断：有，但方向要更细。粗系统压力不能直接用；下一步应只读拆解 `active_2` 和压力期大亏是否存在入场前/入场刻共同结构，例如产品集中、同向已有仓、entry_open/first_bar 关系、risk distance、broker10 cap 后新开仓，而不是继续写交易规则。

## 后续规划和 TODO

- 停止把 `preentry_system_stress`、`dd_ge30`、`vol_ge100`、`broker_ge90` 直接写成削仓规则。
- 下一阶段如果继续，应做只读 `active_2 / stress_loss` 二级拆解：
  - 是否集中在少数产品/交易所/方向。
  - 是否与 Stage015 的 entry_open/first_bar/aligned 标签、same-direction correlation、broker10 cap、risk distance 同时出现。
  - 如果仍非单调、跨年不稳，则停止该分支。
