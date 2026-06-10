# Stage030 C50半风险关闭连败版本 OI+价格确认逐笔归因

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：2026-06-09 14:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因 / 逐笔法证
- 是否重要突破：否，属于候选特征在既有 C50 版本上的复核
- 是否触发A/B：否，本阶段不改策略规则，仅复盘 Stage748 C50 成交

## 外部调研与判断

- 参考资料：
  - Britannica Money: OI 与价格同向增加可作为期货趋势确认的一类证据。
  - NexusFi/Open Interest data: OI 需要和价格方向合读，单独 OI 上升并不等于多空方向。
  - GitHub/公开资料检索未找到可直接照搬到本策略的商品期货 OI+趋势跟随开源实现，更多是教学/指标层用法。
- 我的判断：`OI上升 + 价格沿交易方向` 比单纯 OI 上升更有结构含义，代表新仓资金沿当前信号方向进入；但是否能交易化仍要看跨版本、跨年份、剔除极端赢家后的稳定性。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage756_c50_no_streak_oi_confirm.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；脚本只读使用 Stage748 C50 版本
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage748 全周期，`2020-01` 至本地当前数据末端
- 账户规模：`500,000`
- 成本口径：沿用正式版手续费、滑点、合约乘数、保证金口径
- 样本过滤：
  - C50 closed lots：`347`
  - OI 可用：`301`
  - OI 缺失：`46`
- 策略/归因口径：
  - 版本：`stage526_500k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage748`
  - profile：`official_stage372_r040_no_streak_500k_stage748`
  - 全局 `risk_multiplier=0.40`，即正式版 `0.80` 的一半
  - `streak_risk_multipliers=1.0,1.0,1.0,1.0`
  - `enable_streak_entry_structure_risk_recovery=False`
  - `enable_recovery_sleeve=False`
  - 特征定义：`entry_oi_price_confirm = entry_oi_gt_prev1 AND entry_price_direction_aligned`
  - 多头价格沿方向：开仓日 close 大于前一交易日 close
  - 空头价格沿方向：开仓日 close 小于前一交易日 close

## 结果

- 期末权益：`5,565,350`
- 总收益：`1,013.0700%`
- 最大回撤：`-39.7082%`
- Sharpe：`1.3285`
- 总滑点：`470,250`
- 总交易次数：`686`
- 胜率：日级非零 PnL 胜率 `52.7165%`；逐笔 closed lot 胜率 `46.3977%`
- 其他关键指标：
  - OI 可用全体：`301` 笔，盈利 `143`、亏损 `158`，胜率 `47.5083%`，总 realized PnL `+5,910,090`，平均 R `+0.9319`
  - 命中 `OI上升+价格沿方向`：`120` 笔，盈利 `79`、亏损 `41`，胜率 `65.8333%`，总 realized PnL `+5,642,755`，平均 R `+1.9521`，中位 R `+0.6378`
  - OI 可用未命中：`181` 笔，盈利 `64`、亏损 `117`，胜率 `35.3591%`，总 realized PnL `+267,335`，平均 R `+0.2517`，中位 R `-0.4478`
  - OI 缺失：`46` 笔，盈利 `18`、亏损 `28`，胜率 `39.1304%`，总 realized PnL `-414,610`
  - 未命中或 OI 缺失合并：`227` 笔，盈利 `82`、亏损 `145`，胜率 `36.1233%`，总 realized PnL `-147,275`

## 稳健性复核

- 命中组剔除最大 `1` 笔赢家：`119` 笔，胜率 `65.5462%`，总 PnL `+4,870,555`，平均 R `+1.7877`
- 命中组剔除最大 `2` 笔赢家：`118` 笔，胜率 `65.2542%`，总 PnL `+4,336,645`，平均 R `+1.6802`
- 命中组剔除最大 `3` 笔赢家：`117` 笔，胜率 `64.9573%`，总 PnL `+3,969,685`，平均 R `+1.5941`
- 命中组剔除最大 `5` 笔赢家：`115` 笔，胜率 `64.3478%`，总 PnL `+3,358,405`，平均 R `+1.4707`
- 命中组剔除最大 `10` 笔赢家：`110` 笔，胜率 `62.7273%`，总 PnL `+2,195,245`，平均 R `+0.5071`
- 判断：剔除大赢家后胜率仍显著高于未命中组 `35.3591%`，说明这个特征在 C50 全周期上不是只靠单笔巨额右尾支撑；但 2024 年命中组胜率降到 `42.8571%`，仍有年份退化。

## 分层结果

- 年份：
  - `2020` 命中 `23` 笔，胜率 `82.6087%`；未命中 `29` 笔，胜率 `31.0345%`
  - `2021` 命中 `30` 笔，胜率 `76.6667%`；未命中 `43` 笔，胜率 `32.5581%`
  - `2022` 命中 `15` 笔，胜率 `66.6667%`；未命中 `41` 笔，胜率 `26.8293%`
  - `2023` 命中 `21` 笔，胜率 `57.1429%`；未命中 `17` 笔，胜率 `29.4118%`
  - `2024` 命中 `21` 笔，胜率 `42.8571%`；未命中 `20` 笔，胜率 `50.0000%`
  - `2025` 命中 `10` 笔，胜率 `60.0000%`；未命中 `28` 笔，胜率 `50.0000%`
  - `2026` 命中 `0` 笔；未命中 `3` 笔
- 方向：
  - 多头命中 `96` 笔，胜率 `68.7500%`，总 PnL `+4,299,955`；多头未命中 `145` 笔，胜率 `35.1724%`，总 PnL `-362,605`
  - 空头命中 `24` 笔，胜率 `54.1667%`，总 PnL `+1,342,800`；空头未命中 `36` 笔，胜率 `36.1111%`，总 PnL `+629,940`
- 信号：
  - `long_case1a` 命中 `27` 笔胜率 `62.96%`，未命中 `39` 笔胜率 `25.64%`
  - `long_case2` 命中 `39` 笔胜率 `76.92%`，未命中 `77` 笔胜率 `38.96%`
  - `long_case3` 命中 `16` 笔胜率 `62.50%`，未命中 `20` 笔胜率 `35.00%`
  - `short_case1a` 命中 `20` 笔胜率 `55.00%`，未命中 `32` 笔胜率 `34.38%`

## 输出文件

- report：无图表，本阶段为 CSV/终端归因
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_summary_stage756_c50_no_streak_oi_confirm_v1.csv`
- orders：无单独 orders 输出
- daily：无单独 daily 输出
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_closed_lots_stage756_c50_no_streak_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_group_stats_stage756_c50_no_streak_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_year_stats_stage756_c50_no_streak_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_direction_stats_stage756_c50_no_streak_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_hit_lots_stage756_c50_no_streak_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage756_c50_no_streak_oi_confirm_miss_lots_stage756_c50_no_streak_oi_confirm_v1.csv`

## 结论

- 本阶段结论：`OI上升+价格沿交易方向` 在 C50 半风险关闭连败版本的全周期逐笔上是更强、更稳定的质量标签。命中 `120` 笔，不是 Stage029 的 `10` 笔小样本；命中胜率 `65.8333%`，未命中仅 `35.3591%`；剔除前 `10` 笔最大赢家后仍有 `62.7273%` 胜率。
- 是否进入下一步：可以继续做预声明验证，但不能直接接正式版。
- 下一步：把该特征作为候选质量评分，而不是单独开关；下一轮应做 A50正式版全体交易、A50低风险档、C50全体交易三者统一口径对比，并专门检查 2024-2025 退化原因。

## 过拟合反思

- 运行前判断：有过拟合风险，但比 0.1 风控样本更值得验证，因为 C50 全体交易样本更大。
- 运行后判断：过拟合风险下降，但没有消失。
- 原因：样本扩大到 `120` 个命中 lot，剔除极端赢家后胜率仍明显领先；但年份稳定性不是完美，`2024` 命中表现弱于未命中，说明这个特征不是普世开仓条件，更适合作为多特征评分中的一个维度。

## 继续价值反思

- 运行前判断：有价值继续。OI+价格方向是期货市场结构特征，不是纯内部回测字段。
- 运行后判断：有价值继续。
- 原因：该特征在全体 C50 交易里同时改善胜率、中位 R、平均理论收益和合并非命中表现，且多头、空头、主要 signal case 均有提升。但下一步必须做跨版本和弱年份归因，而不是马上放大风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage030 摘要
- 是否更新 `research/registry.md`：否，本阶段不是正式候选合入
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段仍是只读归因
