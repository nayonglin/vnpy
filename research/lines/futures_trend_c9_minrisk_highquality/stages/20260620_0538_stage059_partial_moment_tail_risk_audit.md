# Stage059 partial-moment tail risk audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-20 05:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读外生风险状态审计 + 诊断上界曲线；不是真实组合引擎
- 是否重要突破：否
- 是否触发A/B：否；本阶段结论为反证，不是可接入正式版候选

## 外部调研与判断

- 参考资料：
  - Liu, Lu, Wang《Asymmetry, Tail Risk and Time Series Momentum》：用上/下 partial moments 描述商品期货时间序列动量的尾部不对称，并报告在中国商品期货中可改善 Sharpe/Sortino 的规则化尝试。
  - Quantpedia `Time Series Momentum Effect`：TSMOM 的长期证据支持趋势跟随跨资产有效，但也强调波动调整、信号质量和风险管理是关键。
  - GitHub `alipbcs/TSMOM`：开源实现侧重期货 TSMOM 的收益、波动、回撤、滚动 Sharpe 等图形评估，说明视觉曲线与风险图不能省略。
- 我的判断：
  - partial moments 有第一性价值：它不是用最终盈亏反推，而是用入场前产品日收益分布刻画顺/逆方向尾部。
  - 但本线目标不是证明文献成立，而是验证当前 C9/15w 的低回撤可交易状态。Stage059 的自然 adverse-tail 桶在本地恰好承载大额右尾，不能为了贴合文献而硬改成削风险规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage059_partial_moment_tail_risk_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `WINDOW=126`
  - `MIN_PERIODS=63`
  - `MAX_SIGNAL_AGE_DAYS=7`
  - `TARGET_BUCKET=adverse_tail_dominant`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage052 / 官方 C9/15w 曲线，覆盖 2018-2026，最新曲线到 2026-06。
- 账户规模：`150,000`
- 成本口径：沿用官方 C9/15w 曲线成本，官方总滑点 `2,730,130`
- 样本过滤：official closed lots `399`；partial moment ready `299`；缺失 `100` 笔保持 `tail_moment_missing`
- 策略/归因口径：
  - 用 Stage496 synthetic close 生成产品日收益。
  - 计算 126 日 rolling 上/下二阶 partial moments，最少 63 日启用。
  - 多头用下行 partial moment 作为方向逆尾，空头方向反转。
  - 若 `directional_lpm2_126 > directional_upm2_126`，标为 `adverse_tail_dominant`。
  - 诊断上界只做“乐观跳过 adverse-tail-dominant”的资金曲线，不代表可交易引擎。

## 结果

- 官方基准：
  - 期末权益：`39,176,437.60`
  - 总收益：`26,017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- 诊断上界：跳过 `adverse_tail_dominant`
  - 期末权益：`19,930,164.50`
  - 总收益：`13,186.7763%`
  - 最大回撤：`-46.7092%`
  - Sharpe：`1.3190`
  - 收益保留：`50.6840%`
- 其他关键指标：
  - `adverse_tail_dominant`：`131` 笔、`18` 产品、`7` 年，净 PnL `+19,246,273.10`
  - `favorable_tail_not_worse`：`168` 笔、`18` 产品、`7` 年，净 PnL `+23,257,117.10`
  - `tail_moment_missing`：`100` 笔、`15` 产品、`5` 年，净 PnL `+551,222.40`
  - tail score 四分位全部为正贡献，最高为 q3 `+13,982,176.60`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_report_stage059_partial_moment_tail_risk_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_summary_stage059_partial_moment_tail_risk_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_decision_stage059_partial_moment_tail_risk_audit_v1.json`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_partial_moment_daily_stage059_partial_moment_tail_risk_audit_v1.csv`
- quality/features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_features_stage059_partial_moment_tail_risk_audit_v1.csv`
- 资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_upper_bound_path_chart_stage059_partial_moment_tail_risk_audit_v1.png`
- 贡献图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_bucket_contribution_chart_stage059_partial_moment_tail_risk_audit_v1.png`
- 年度热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_bucket_year_heatmap_stage059_partial_moment_tail_risk_audit_v1.png`
- 产品热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_product_bucket_heatmap_stage059_partial_moment_tail_risk_audit_v1.png`
- 散点图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage059_partial_moment_tail_risk_audit/qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit_tail_score_scatter_stage059_partial_moment_tail_risk_audit_v1.png`

## 视觉分析

- 资金曲线：跳过 `adverse_tail_dominant` 的红线不是更稳的 80% 收益版本，2023 年之后长期低于官方蓝线，最大回撤也从 `-45.0827%` 恶化到 `-46.7092%`。
- 贡献图：红色 `adverse_tail_dominant` 曲线最终累计接近 `+1,924.6万`，不是需要过滤的坏桶；绿色 `favorable_tail_not_worse` 也为正，二者都在官方右尾中起作用。
- 散点图：tail score 与 realized PnL、前 30 分钟 directional R、Stage052 trend t-stat、全程 MAE R 均没有干净单调边界；高 adverse score 中既有超大赢家，也有亏损点。
- 年度/产品热图：adverse 桶在 `2021/2022/2026` 为负，但 `2023/2025` 大幅为正；产品上 `jm.DCE/OI.CZCE/lh.DCE` 的 adverse 桶是大额右尾，不能按年份或产品补丁化。

## 结论

- 本阶段结论：`stage059_partial_moment_tail_risk_no_candidate_right_tail_dominant`
- 是否进入下一步：不进入 true engine，不触发 A/B。
- 下一步：
  - 关闭 partial-moment adverse-tail 直接削仓/跳过分支。
  - 不扫 `63/126/252`、min periods、ratio/score 阈值、四分位、产品、方向、年份或月份。
  - partial moments 只保留为诊断/forward-watch 特征；若未来复用，必须与真正独立、点时化、可实盘取得的信息源交叉预声明，不能单独交易化。

## 过拟合反思

- 运行前判断：否。使用文献支持的 partial moments，固定 126/63 口径，没有用最终盈亏选择窗口或阈值。
- 运行后判断：直接交易化会过拟合。因为本地数据已经显示 natural adverse 桶是大右尾来源，若继续改阈值、分位、年份或产品让它看起来负贡献，就是事后救参。
- 原因：一个普世风险状态应在跨年、跨产品、资金曲线上有稳定不伤右尾的单调性；Stage059 没有。

## 继续价值反思

- 运行前判断：有。partial moments 是外生于最终盈亏的入场前尾部结构，值得检验。
- 运行后判断：作为直接规则没有继续价值；作为诊断特征有有限价值。
- 原因：它解释了 C9 的一部分尾部环境，但不能把“尾部不对称”简化为坏信号。当前目标要求低回撤且保留 80% 收益，Stage059 上界只保留 `50.6840%` 收益并恶化回撤。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage059 反证和边界。
- 是否更新 `research/registry.md`：否，非重要突破、非候选、非路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。
