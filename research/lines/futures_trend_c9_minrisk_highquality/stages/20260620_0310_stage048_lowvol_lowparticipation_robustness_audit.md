# Stage048 low-vol low-participation 冻结鲁棒性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 03:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；closed-lot cashflow 乐观上限；冻结前置鲁棒性审计
- 是否重要突破：否
- 是否触发A/B：否。本阶段不是可接正式版的候选，也没有 true engine。

## 外部调研与判断

- 参考资料：
  - AQR《Demystifying Managed Futures》：https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures
  - AQR《A Century of Evidence on Trend-Following Investing》：https://www.ecapital.ch/downloads/AQR_A%20Century_of_Evidence_on_Trend-Following.pdf
  - CME / Baltas & Kosowski《Improving Time-Series Momentum Strategies》：https://www.cmegroup.com/education/files/improving-time-series-momentum-strategies.pdf
  - Rob Carver / qoppac `Vol attenuation` 与 `pysystemtrade`：https://qoppac.blogspot.com/2021/12/my-trading-system.html ，https://github.com/pst-group/pysystemtrade
- 我的判断：
  - 趋势跟随的长期本质仍是跨市场时间序列趋势、波动调整和右尾凸性，不是单纯“低波动坏 / 高波动坏”。
  - CME 论文提到趋势信号质量、波动估计、无显著趋势合约数量会影响 TSMOM 表现，因此 Stage047 的 `low_vol_low_participation` 可以做一次冻结审查。
  - 但资料不支持把 `low_vol <50`、`participation <25` 这种历史 closed-lot 弱桶直接交易化；必须先确认不是 `2026` 近端、少数产品块或最终盈亏反推。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage048_lowvol_lowparticipation_robustness_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；仅固定审计目标 `TARGET_STATE=joint_low_vol_low_participation`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方曲线 `2018-01-02 -> 2026-06-15`；目标 closed-lot exit `2020-08-17 -> 2026-03-04`
- 账户规模：`150,000`
- 成本口径：沿用 Stage046 官方 A 曲线；Stage048 上限曲线只按目标 closed-lot realized PnL 做 cashflow add-back，不重算真实成交、滑点和持仓路径
- 样本过滤：只读 Stage047 固定桶 `joint_low_vol_low_participation`；不扫阈值、产品、方向、年份、月份
- 策略/归因口径：
  - 读取 Stage047 features 与 Stage046 官方 A 曲线。
  - 目标桶按 `vt_symbol` 规范化产品，避免 `fu` / `fu.SHFE`、`lh` / `lh.DCE` 这类字段混合造成假分散。
  - 做 leave-one-year、leave-one-product、产品-年份热图、目标贡献曲线。
  - 生成“完美跳过目标桶 closed-lot cashflow”的乐观上限资金曲线：`upper_bound_equity = official_equity - cumulative(target_realized_pnl)`。

## 结果

- 官方 A 期末权益：`39,176,437.60`
- 官方 A 总收益：`26017.6251%`
- 官方 A 最大回撤：`-45.0827%`
- 官方 A Sharpe：`1.6339`
- 官方 A 总滑点：`2,730,130`
- 官方 A 总交易次数：`787`
- 官方 A 胜率：`53.2560%`
- 目标桶：
  - lots：`27`
  - 规范化产品数：`11`
  - 年份数：`7`
  - 净 PnL：`-1,766,789.80`
  - 正收益覆盖：`3.2077%`
  - 负收益覆盖：`16.0586%`
- 乐观上限曲线：
  - 期末权益：`40,943,227.40`
  - 总收益：`27195.4849%`
  - 最大回撤：`-44.9196%`
  - Sharpe：`1.6500`
  - 最大回撤改善：`0.1631pp`
  - 收益保留：`104.5272%`
- 鲁棒性：
  - 排除 `2026` 后剩余 PnL：`-224,960.40`，仍为负但幅度很小，说明主要损伤集中在近端。
  - 排除最大负产品 `ru.SHFE` 后剩余 PnL：`-629,889.80`，仍为负但解释力显著下降。
  - 年度贡献：`2026=-1,541,829.40`，`2025=+350,000.00`，`2020-2024` 多数年份只是小负。
  - 产品贡献：`ru.SHFE=-1,136,900.00`、`fu.SHFE=-601,750.00`、`sp.SHFE=-374,106.40`、`FG.CZCE=+754,400.00`、`lh.DCE=+306,896.00`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage048_lowvol_lowparticipation_robustness_audit/qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_report_stage048_lowvol_lowparticipation_robustness_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage048_lowvol_lowparticipation_robustness_audit/qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_summary_stage048_lowvol_lowparticipation_robustness_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage048_lowvol_lowparticipation_robustness_audit/qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_decision_stage048_lowvol_lowparticipation_robustness_audit_v1.json`
- upper_bound_curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage048_lowvol_lowparticipation_robustness_audit/qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_upper_bound_curve_stage048_lowvol_lowparticipation_robustness_audit_v1.csv`
- target_lots：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage048_lowvol_lowparticipation_robustness_audit/qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_target_lots_stage048_lowvol_lowparticipation_robustness_audit_v1.csv`
- charts：
  - `qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_upper_bound_path_chart_stage048_lowvol_lowparticipation_robustness_audit_v1.png`
  - `qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_target_contribution_chart_stage048_lowvol_lowparticipation_robustness_audit_v1.png`
  - `qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_leave_one_robustness_chart_stage048_lowvol_lowparticipation_robustness_audit_v1.png`
  - `qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_product_year_heatmap_stage048_lowvol_lowparticipation_robustness_audit_v1.png`
  - `qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_state_scatter_highlight_stage048_lowvol_lowparticipation_robustness_audit_v1.png`

## 结论

- 本阶段结论：`stage048_lowvol_lowparticipation_fails_robustness_no_engine`。
- 是否进入下一步：不进入 true engine，不触发 A/B。
- 下一步：
  - 关闭 `low_vol_low_participation` 直接交易化路线。
  - 不扫 `vol 50/100`、`participation 25/50`、同向相关阈值、产品、年份、方向或月份。
  - 若继续该状态，只能作为 forward-watch 标签；策略研究应转向更强的外生、入场前可见、覆盖完整且非 closed-lot 反推的信息源，或暂时回到账户层非交易路径的固定规则审计。

## 过拟合反思

- 运行前判断：直接交易化会有过拟合风险；本阶段只做冻结审查，风险可控。
- 运行后判断：审计本身没有新增过拟合，但该线索若继续进 true engine 就会明显过拟合。
- 原因：
  - 固定桶来自 Stage047 预先限定，没有扫阈值。
  - 上限路径对最大回撤只改善 `0.1631pp`，证明它不是主回撤解释变量。
  - 弱贡献明显受 `2026` 和少数产品块影响，且 `FG.CZCE/lh.DCE` 等同状态仍给出正贡献，不具备普世单调性。

## 继续价值反思

- 运行前判断：有价值。它能判断 Stage047 唯一弱线索是否值得写真实引擎。
- 运行后判断：该具体线索没有继续写引擎的价值；总目标仍有价值。
- 原因：
  - 即使使用完美跳过的乐观 closed-lot 上限，也几乎没有修复官方主回撤。
  - 视觉上资金曲线橙线几乎贴着官方蓝线，差异主要集中在 `2026` 后段；`2022-06-29` 主回撤谷没有被修复。
  - 后续继续在该桶周边找阈值、产品或年份只会把一个近端弱样本做成历史补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage048 并收紧 Stage047 后边界。
- 是否更新 `research/registry.md`：否，非合入级别。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或跨线结论。
