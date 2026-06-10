# Stage034 Stage757 OI恢复交易K线图册

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-09 18:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读视觉复盘
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Open Interest：`https://www.cmegroup.com/education/lessons/open-interest`
  - Britannica Volume & Open Interest：`https://www.britannica.com/money/futures-volume-open-interest`
  - NexusFi Open Interest Analysis：`https://nexusfi.com/a/concepts/open-interest-analysis`
- 我的判断：公开资料继续支持把价格同向与 OI 上升放在同一张图上观察趋势参与度；但这只是视觉法证，不构成新交易规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage760_stage757_oi_restore_kline_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`PRE_BARS=50`、`POST_BARS=50`、`PER_PAGE=4`
- 修改参数：相对 Stage752/753 图册，开平仓前后窗口从 `40` 根扩展到 `50` 根
- 删除参数：无

## 回测/归因参数

- 数据区间：跟随 Stage757 closed lots，`2020-01` 至 `2026-03`
- 账户规模：读取 Stage757 已生成结果，不重跑账户回测
- 成本口径：读取 Stage757 closed lot 已实现盈亏，不重新计算成本
- 样本过滤：仅 `oi_price_confirm_risk_restore_applied=1` 的 Stage757 closed lots
- 策略/归因口径：只读画图；每笔图包含价格K线、MA5/10/20、入场线、出场线、持仓区间、成交量柱和持仓量曲线

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：图册样本 `125` 笔 closed lots
- 胜率：`60/125=48.0000%`
- 其他关键指标：
  - 总实现盈亏：`+3,950,340`
  - 亏损笔数：`65`
  - 平盘笔数：`0`
  - 中位 R：`-0.1153`
  - 中位理论方向收益率：`-0.2300%`
  - 图册页数：`32`
  - 每页：`4` 笔
  - 本地合约CSV缺失：`15` 笔，对应图格标注 `missing bars`

## 输出文件

- report：无
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage760_stage757_oi_restore_kline_atlas_summary_stage760_stage757_oi_restore_kline_atlas_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage760_stage757_oi_restore_kline_atlas_manifest_stage760_stage757_oi_restore_kline_atlas_v1.csv`
- chart pages：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage760_stage757_oi_restore_kline_atlas_page01_stage760_stage757_oi_restore_kline_atlas_v1.png` 至 `page32`

## 结论

- 本阶段结论：Stage757 OI 恢复实际应用的 `125` 笔交易已全部按之前图册格式生成，窗口扩展为开仓前后各 `50` 根K线，并保留成交量与持仓量副图。
- 是否进入下一步：可以进入只读视觉归因，不进入策略改参
- 下一步：先人工看图归纳盈利与亏损的共性，再把候选形态转为低自由度、事前可见的统计特征；不得从少数图片直接反推阈值。

## 过拟合反思

- 运行前判断：画图本身不过拟合，但看图后容易事后挑模式。
- 运行后判断：仍是只读材料，不形成可交易规则。
- 原因：样本中盈利 `60`、亏损 `65`，中位 R 为负，说明“命中 OI”本身不是高胜率规则；图片只能帮助找第二层结构。

## 继续价值反思

- 运行前判断：有价值，因为可以直观看到 OI 恢复交易的成功/失败形态。
- 运行后判断：有继续价值，但只限法证分析。
- 原因：图册覆盖全部应用交易，能帮助区分右尾放大和左尾失败的 K 线结构。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破或正式候选变更
