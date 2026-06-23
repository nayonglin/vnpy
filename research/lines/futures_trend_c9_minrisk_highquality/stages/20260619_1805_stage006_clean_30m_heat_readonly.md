# Stage006 C9/15w 前30分钟低逆行热度只读审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 18:05`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读质量标签审计；不生成可执行候选，不触发 A/B。
- 是否重要突破：否，但形成一条有价值的归因线索。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - SSRN `Trend Following Strategies: A Practical Guide`：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633`
  - CAIA `Quantifying CTA Risk Management`：`https://caia.org/sites/default/files/AIAR_Q1_2016_04_Kaminsky_CTARiskManagement.pdf`
  - Rob Carver / qoppac risk overlay：`https://qoppac.blogspot.com/2020/05/`
  - GitHub `pysystemtrade`：`https://github.com/pst-group/pysystemtrade`
  - `Intraday Time Series Momentum: International Evidence`：`https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf`
  - `Market Intraday Momentum`：`https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf`
- 我的判断：趋势跟踪的本质是保留右尾和正偏，不是把所有短期回撤抹平。CTA 风险管理资料支持用风险分配和容量/相关性等共性因素审计风险，Carver 也提醒风险 overlay 会牺牲正偏，不能为了回撤随意砍仓。日内动量资料支持前半小时有信息消化和延续线索，但这只能作为普世质量标签审计，不足以直接变成交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage006_clean_30m_heat_readonly.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；只读标签固定为 `clean_continuation_30m = first_30m_directional_r > 0 and first_30m_mae_r <= 0.5R`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：官方 C9/15w 资金曲线 `2018-01-01` 至 `2026-06-15`。
- 账户规模：当前官方正式口径 `150000`。
- 成本口径：本阶段不重新定价、不改成本；官方指标沿用 Stage001/005 基线。
- 样本过滤：Stage005 导出的 Stage847/C9 core 30w closed_lots 形态参考样本 `373` 笔；不是 15w 官方资金指标来源。
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `stage847_c9_15w_stage819_05r_stop_retry_live`。
  - 标签分类：`clean_continuation_30m`、`adverse_heat_30m`、`no_follow_30m`、`missing_30m`。
  - 本阶段生成官方资金路径图，以及 closed-lot 累计实现盈亏贡献图；贡献图不是可执行逐日盯市回测。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：本阶段未重算，沿用 Stage001 官方基线 `1.6331`。
- 总滑点：本阶段未重算，沿用 Stage001 官方基线 `2,730,130`。
- 总交易次数：本阶段未重算，沿用 Stage001 官方基线 `787`。
- 胜率：本阶段未重算，沿用 Stage001 官方基线 `53.2560%`。
- 其他关键指标：
  - 官方 broker10 峰值：`111.7365%`
  - closed_lots 形态参考样本：`373`
  - 分钟缺失样本：`155`
  - `clean_continuation_30m`：`127` 笔、`17` 个品种、`7` 年，净实现盈亏 `32,245,296`，占参考总净 PnL `81.2118%`
  - clean 组正收益覆盖：`60.0280%`
  - clean 组负收益覆盖：`27.6380%`
  - `adverse_heat_30m`：仅 `6` 笔但净实现盈亏 `5,898,795`，包含 `OI309` 这种先逆行热度超过 `0.5R` 但最终 `153R` 的超大右尾
  - `no_follow_30m`：`85` 笔，净实现盈亏 `-4,045,508.60`，负收益覆盖 `34.9352%`
  - `missing_30m`：`155` 笔，净实现盈亏 `5,606,588.80`，正收益覆盖 `23.0891%`，包含 `rb2210/hc2210/OI605/ru2501` 等重要右尾

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_report_stage006_clean_30m_heat_readonly_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_summary_stage006_clean_30m_heat_readonly_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_decision_stage006_clean_30m_heat_readonly_v1.json`
- lot_features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_lot_features_stage006_clean_30m_heat_readonly_v1.csv`
- bucket_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_bucket_stats_stage006_clean_30m_heat_readonly_v1.csv`
- year_bucket_stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_year_bucket_stats_stage006_clean_30m_heat_readonly_v1.csv`
- contribution_curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_contribution_curve_stage006_clean_30m_heat_readonly_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_path_chart_stage006_clean_30m_heat_readonly_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_contribution_chart_stage006_clean_30m_heat_readonly_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage006_clean_30m_heat_readonly/qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_atlas_page001_stage006_clean_30m_heat_readonly_v1.png` 至 `page006`

## 视觉观察

- 官方资金路径图显示这些质量标签覆盖的事件跨多个年份，不能用单个弱窗口解释。
- closed-lot 累计实现盈亏贡献图显示 clean 组曲线较平滑，并贡献了约 `81%` 的净 PnL；这是有价值线索。
- 但 atlas 和样本清单显示非 clean 仍包含关键右尾：`OI309` 被标为 `adverse_heat_30m`，但最终 `153R`；`rb2210/hc2210/OI605/ru2501` 落在 `missing_30m`，合计贡献重要正收益。
- clean 组也有明显 false positive：`ru2409/OI205/AP505/rb2205` 等前 30 分钟低逆行且方向为正，最终仍亏损。因此“前 30 分钟 clean”不能单独定义高质量信号。

## 结论

- 本阶段结论：`stage006_readonly_quality_label_not_trade_rule`。
- 是否进入下一步：是，但不是进入真实交易候选，而是继续做只读归因或数据覆盖修复。
- 下一步：
  - 先解决分钟覆盖缺失对右尾归因的影响，尤其 `2022-07-07 rb/hc`、`2024-09 ru2501`、`2026 OI605` 等关键赢家。
  - 若继续规则方向，只能研究“no_follow_30m 是否可作为减风险/不恢复风险的反证标签”，不能用 clean 标签恢复满风险。
  - 暂不写真实 engine，不做 `15/30/60`、`0.25R/0.5R/1R`、品种/年份/方向救参。

## 过拟合反思

- 运行前判断：否。标签来自 Stage005 视觉假设和外部日内动量/MAE 风控概念，不按年份、品种、方向或最终盈亏调参。
- 运行后判断：否，但若继续扫标签阈值会很快过拟合。
- 原因：本阶段只冻结一个标签并做全样本分桶，结果同时暴露了正反证；没有把净贡献 `81%` 直接包装成候选。过拟合风险在于用 `OI309`、`rb2210` 等个案去补 missing/adverse 的特例。

## 继续价值反思

- 运行前判断：有。Stage005 已显示 progress-first 太浅，需要更接近“低逆行热度 + 顺势延续”的质量定义。
- 运行后判断：有，但方向要收窄。
- 原因：`no_follow_30m` 净贡献为负且覆盖 `34.9352%` 的负收益，说明早期不跟随可能是减风险线索；但 clean 标签漏掉的右尾太多，不能作为恢复满风险规则。继续价值在于做数据覆盖修复和 no-follow 反证标签，而不是直接接正式版。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是候选合入、路线废弃、正式候选、跨线合并或记录体系迁移，只是只读归因。
