# Stage060 relative-basis shock audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-20 05:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读相对基差外生信息源审计 + 诊断上界曲线；不是真实组合引擎
- 是否重要突破：否
- 是否触发A/B：否；本阶段结论为反证，不是可接入正式版候选

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档/GitHub：`futures_spot_price`、`get_futures_daily`、`get_receipt` 等接口可提供国内商品期货基差、日行情和仓单类基础数据，适合做外生供需/期限结构审计。
  - AEA 2025 / LSE paper《Relative Basis and the Expected Returns of Commodity Futures》：相对基差被定义为近端 basis 与远端 basis 的差，核心直觉是剔除持久仓储/融资特征后捕捉期限结构曲率和便利收益变化。
  - AKShare GitHub issue #5952：国内期货长区间/DCE 等接口存在稳定性与口径风险，必须把覆盖率、点时化和缺失桶作为硬约束。
- 我的判断：
  - 相对基差有第一性价值：它不是最终盈亏标签，而是入场前可见的期限结构/供需状态。
  - 但 C9/15w 的目标不是验证文献因子单独有效，而是判断它能不能作为低回撤过滤器。Stage060 的自然“方向性 YoY 相对基差逆风”桶在本地承担大额右尾，所以不能交易化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage060_relative_basis_shock_audit.py`
- 修改脚本：无；运行中仅在新增脚本内修正 pandas warning 口径
- 删除脚本：无
- 新增参数：
  - `YOY_DELTA_PERIODS=252`
  - `MAX_SIGNAL_AGE_DAYS=7`
  - `TARGET_BUCKET=relative_basis_yoy_headwind`
  - `relative_basis_rate = near_basis_rate - dom_basis_rate`
  - `directional_yoy_delta = direction_sign * relative_basis_yoy_delta_252`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用官方 C9/15w 曲线，覆盖 2018-2026；相对基差缓存覆盖 `2020-01-02 -> 2026-04-17`
- 账户规模：`150,000`
- 成本口径：沿用官方 C9/15w 曲线成本，官方总滑点 `2,730,130`
- 样本过滤：official closed lots `399`；relative-basis ready `204`；missing `195` 保持 `relative_basis_missing`
- 策略/归因口径：
  - 读取现有 AKShare 基差缓存，计算近端基差率与主力基差率的差。
  - 每个产品按 `252` 行计算相对基差 YoY delta。
  - 多头要求方向性 YoY delta 为正，空头要求为负；方向相反标为 `relative_basis_yoy_headwind`。
  - 信号最大陈旧期 `7` 天；缺失不硬补，不把 missing 当信号。
  - 诊断上界只做“乐观跳过 headwind 桶”的资金曲线，不代表可交易引擎。

## 结果

- 官方基准：
  - 期末权益：`39,176,437.60`
  - 总收益：`26,017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- 诊断上界：跳过 `relative_basis_yoy_headwind`
  - 期末权益：`14,068,087.90`
  - 总收益：`9,278.7253%`
  - 最大回撤：`-95.2645%`
  - Sharpe：`1.1820`
  - 收益保留：`35.6632%`
- 其他关键指标：
  - relative-basis ready：`204/399 = 51.1278%`
  - 基差日表：`24,482` 行、`18` 个 symbol
  - `relative_basis_yoy_headwind`：`101` 笔、`25` 产品、`6` 年，净 PnL `+25,108,349.70`
  - `relative_basis_yoy_supportive`：`103` 笔、`27` 产品、`6` 年，净 PnL `+16,853,643.30`
  - `relative_basis_missing`：`195` 笔、`34` 产品、`9` 年，净 PnL `+1,092,619.60`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_report_stage060_relative_basis_shock_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_summary_stage060_relative_basis_shock_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_decision_stage060_relative_basis_shock_audit_v1.json`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_relative_basis_daily_stage060_relative_basis_shock_audit_v1.csv`
- quality/features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_features_stage060_relative_basis_shock_audit_v1.csv`
- 资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_upper_bound_path_chart_stage060_relative_basis_shock_audit_v1.png`
- 贡献图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_bucket_contribution_chart_stage060_relative_basis_shock_audit_v1.png`
- 覆盖图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_coverage_chart_stage060_relative_basis_shock_audit_v1.png`
- 年度热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_bucket_year_heatmap_stage060_relative_basis_shock_audit_v1.png`
- 产品热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_product_bucket_heatmap_stage060_relative_basis_shock_audit_v1.png`
- 散点图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage060_relative_basis_shock_audit/qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_relative_basis_scatter_stage060_relative_basis_shock_audit_v1.png`

## 视觉分析

- 资金曲线：跳过 `relative_basis_yoy_headwind` 的红线在 `2021` 后多次断崖式回撤，底部回撤线多次接近 `-90%` 到 `-95%`，不是低回撤路径。
- 贡献图：headwind 红线最终累计 `+2,510.8万`，且自 `2021` 起持续贡献右尾；supportive 也为正，说明相对基差方向性并不是简单的好坏二分。
- 覆盖图：`2018/2019/2020` ready 为 `0`，`2021-2026` 才达到约 `82%-94%`；这本身已经不满足全周期正式过滤器的覆盖要求。
- 散点图：directional YoY delta 与 realized PnL、前 30 分钟 R、趋势 t-stat、全程 MAE R 均无干净单调边界；headwind 与 supportive 都混有大赢家和大亏损。
- 年度/产品热图：headwind 桶在 `2021/2022/2023/2024` 连续正贡献，其中 `2023` 达 `+1,247.3万`；产品上 `OI.CZCE/jm.DCE/ru.SHFE/rb.SHFE/SM.CZCE/FG.CZCE` 等均有正贡献，不能按产品或年份补丁化。

## 结论

- 本阶段结论：`stage060_relative_basis_headwind_no_candidate_right_tail_dominant`
- 是否进入下一步：不进入 true engine，不触发 A/B。
- 下一步：
  - 关闭 relative-basis YoY headwind 直接削仓/跳过分支。
  - 不扫 `252/126/63`、near/dom 组合、zscore、正负阈值、信号年龄、产品、方向、年份、月份或交易所。
  - 相对基差只保留为经济解释/forward-watch 特征；若未来复用，必须先补独立点时化数据覆盖，并证明不会切断 C9 右尾。

## 过拟合反思

- 运行前判断：否。相对基差来自外部文献和供需期限结构直觉，本阶段固定 `252` 行 YoY delta 与 `7` 天信号年龄，没有用最终盈亏选择阈值。
- 运行后判断：直接交易化会过拟合。因为自然 headwind 桶是 C9 右尾来源，继续改窗口、阈值、产品、年份或交易所让它变负，就是历史切片救参。
- 原因：一个普世低风险状态应在资金曲线和跨年跨品种贡献上稳定降低左尾且不砍右尾；Stage060 证据完全相反。

## 继续价值反思

- 运行前判断：有。相对基差是入场前可见、非最终盈亏标签的外生信息源，值得验证。
- 运行后判断：作为直接规则没有继续价值；作为经济监控有有限价值。
- 原因：它解释了 C9 在某些供需/期限结构环境下的右尾参与，但不能提供“高质量信号才承担风险”的筛选边界。当前目标要求收益保留 `80%+` 且降低最大回撤，Stage060 上界只保留 `35.6632%` 收益并把最大回撤恶化到 `-95.2645%`。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage060 反证和边界。
- 是否更新 `research/registry.md`：否，非重要突破、非候选、非路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。
