# Stage047 volatility / participation joint-state 入场前联合状态只读审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 02:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - AQR / Hurst, Ooi, Pedersen `Demystifying Managed Futures`：`https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf`
  - Baltas/Kosowski `Improving Time-Series Momentum Strategies`：`https://www.cmegroup.com/education/files/improving-time-series-momentum-strategies.pdf`
  - CME `Managed Futures Research Digest`：`https://www.cmegroup.com/content/dam/cmegroup/education/files/research-digest.pdf`
  - Fidelity `Trend-following crisis alpha`：`https://institutional.fidelity.com/app/proxy/content?literatureURL=%2F9922231.PDF`
  - Man Group `The Optimal Market Mix for a Trend Follower`：`https://www.man.com/insights/trend-following-optimal-market-mix`
- 我的判断：
  - 趋势跟随的本质仍是中长期 time-series momentum 和右尾凸性，不应继续用入场日保本/硬退出去截断右尾。
  - 外部文献支持“波动、相关性、市场选择/参与度要联合看”，但也明确趋势跟随不是简单 long vol 或 short vol。
  - 因此本阶段只验证入场前 `20d` 组合波动、全市场趋势参与度、方向一致性、同向相关是否能形成普世风险状态；如果只能解释少数历史块，就不写规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage047_vol_participation_joint_state_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定复用既有粗桶：`prev_rolling20_ann_vol_pct <50 / 50-100 / >=100`
  - 固定复用既有粗桶：`trend_participation_pct <25 / 25-50 / >=50`
  - 固定复用既有同向相关桶：`<0.60 / 0.60-0.80 / >=0.80`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 曲线 `2018-01-02` 至 `2026-06-15`；market state 可用区间从 `2020-04-03` 起，缺失单独成桶。
- 账户规模：`150,000`
- 成本口径：官方 C9/15w 原始成本，未生成新交易。
- 样本过滤：不筛品种、年份、方向；`market_state_missing` 单独保留，不填补。
- 策略/归因口径：
  - A：当前官方正式版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - Stage047：只读绑定每笔 closed lot 入场前状态，输出 cohort 贡献曲线、年度热图、产品热图、状态散点和官方路径状态图。

## 结果

- 官方基准期末权益：`39,176,437.60`
- 官方基准总收益：`26017.6251%`
- 官方基准最大回撤：`-45.0827%`
- 官方基准 Sharpe：`1.6339`
- 官方基准总滑点：`2,730,130`
- 官方基准总交易次数：`787`
- 官方基准胜率：`53.2560%`
- 其他关键指标：
  - `joint_low_vol_low_participation`：`27` 笔、`15` 产品、`7` 年，净 PnL `-1,766,789.80`，正收益覆盖 `3.2077%`，负收益覆盖 `16.0586%`，正收益年份 `1`、负收益年份 `6`。
  - `joint_high_vol_low_participation`：`4` 笔、`4` 产品、`2` 年，净 PnL `+898,510.00`，不是坏状态。
  - `joint_high_vol_high_participation`：`8` 笔、`8` 产品、`1` 年，净 PnL `+2,128,341.40`，高波动不等于风险坏信号。
  - `joint_low_vol_high_participation`：`43` 笔、`22` 产品、`6` 年，净 PnL `+12,433,615.00`，是明显右尾贡献状态。
  - `joint_mixed_vol_participation`：`150` 笔、`30` 产品、`7` 年，净 PnL `+21,106,058.30`，承担主收益台阶也承担主负收益。
  - 同向相关联合状态里，`joint_low_vol_high_same_dir_corr` 虽 `14` 笔净亏 `-237,387.80` 且 `6/6` 年负，但正负覆盖都很小，解释力不足。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_report_stage047_vol_participation_joint_state_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_summary_stage047_vol_participation_joint_state_audit_v1.csv`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_features_stage047_vol_participation_joint_state_audit_v1.csv`
- cohort_curves：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_cohort_curves_stage047_vol_participation_joint_state_audit_v1.csv`
- path_chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_official_path_state_chart_stage047_vol_participation_joint_state_audit_v1.png`
- cohort_curve_chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_cohort_curve_chart_stage047_vol_participation_joint_state_audit_v1.png`
- year_heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_bucket_year_heatmap_stage047_vol_participation_joint_state_audit_v1.png`
- state_scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_state_scatter_stage047_vol_participation_joint_state_audit_v1.png`
- product_heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage047_vol_participation_joint_state_audit/qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_bucket_product_heatmap_stage047_vol_participation_joint_state_audit_v1.png`

## 视觉判断

- cohort curve 显示 `joint_low_vol_low_participation` 长期弱，但它不是 `2022` 主回撤的完整前置风险源；真正主收益来自 `joint_mixed_vol_participation` 与 `joint_low_vol_high_participation`。
- 官方路径状态图显示高波动 entry 点很少，且高波动 entry 多数不是坏信号；不能把 `vol_ge100` 或高波动 + 参与度弱直接当削仓条件。
- scatter 显示赢家和输家在 `prev 20d vol / trend participation` 空间高度重叠，不足以支持真引擎。
- 年度热图显示唯一弱负桶在 `2026` 下沉明显，需警惕把近端样本包装成普世规则。
- 产品热图显示弱负桶包含 `ru/fu/lh/FG/jm` 等产品块，但不是单一品种黑名单，也不足以证明可交易化。

## 结论

- 本阶段结论：`stage047_vol_participation_joint_state_no_candidate`
- 是否进入下一步：不直接进入正式候选或 A/B。
- 下一步：
  - 不把 `high_vol`、`low_participation`、同向相关或三者组合直接写成削仓规则。
  - 若继续该线索，只允许一次冻结前置审查：围绕 `low_vol_low_participation` 做“可执行真引擎前置检查”，先读 `skills/version-ab-experiment/SKILL.md`，并证明它不是 `2026` 近端样本或少数产品块；若要接真引擎，只能做一个固定版本，不扫阈值。
  - 更稳妥的方向仍是寻找覆盖更完整、点时化更强的外生源，或做 forward watch，而不是继续从 closed-lot 内部盈亏 cohort 反推。

## 过拟合反思

- 运行前判断：否。使用外部文献支持的粗联合状态，不按具体品种、年份、方向、月份或失败交易反推。
- 运行后判断：当前 Stage047 本身否；但如果直接把 `joint_low_vol_low_participation` 做成削仓规则并继续调阈值，就是过拟合。
- 原因：唯一弱负桶虽然跨 `7` 年，但负贡献不大，`2026` 近端影响明显，且主回撤和主收益路径并不由它单调解释。

## 继续价值反思

- 运行前判断：有。Stage046 证明入场日保本类规则会砍右尾，必须换成入场前可见的外生/系统状态审计。
- 运行后判断：有，但价值从“直接写规则”降为“谨慎 forward watch / 冻结前置审查”。`low_vol_low_participation` 是弱线索，不是候选。
- 原因：它的负收益覆盖有信息量，但不足以证明能降低 C9 主回撤并保留 `80%+` 收益；继续时必须严格限制自由度。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage047 结论和下一步边界。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重大突破或跨线结论。
