# Stage215 Stage214保证金差异归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-01 19:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读口径复盘；解释 Stage213 代理保证金与 Stage214 精确持仓保证金的差异来源。
- 是否重要突破：是。确认 Stage213 proxy 不能作为部署裁决依据，后续候选必须使用 exact position margin。
- 是否触发A/B：否。没有新候选接入，不修改正式策略。

## 外部调研与判断

- 参考资料：
  - SHFE Clearing：`https://www.shfe.com.cn/eng/services/investor/Investor_clearing/`
  - SHFE settlement parameter fields：`https://tsite.shfe.com.cn/eng/reports/businessdata/settlement/index.html`
  - CFFEX contract rules：`https://www.cffex.com.cn/en_new/fzhygz/`
  - vn.py / VeighNa GitHub：`https://github.com/vnpy/vnpy`
- 我的判断：交易所保证金按持仓合约价值、保证金率和每日结算/风控规则重算，部署审计必须落到逐日持仓粒度。vn.py 回测也以合约乘数、价格、持仓为基础组织多合约回测；因此 Stage214 用 `build_positions_df(engine)` 重建保证金，比 Stage213 用旧路径保证金线性缩放更接近真实约束。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage515_stage214_margin_gap_postmortem.py`
- 修改脚本：无策略脚本修改。
- 删除脚本：无。
- 新增参数：无策略参数。新增审计分类：`exact_only`、`proxy_only`、`both_exact_gt_proxy`、`both_proxy_gt_exact`、`close_enough`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-05-25。
- 账户规模：沿用 Stage208/Stage214 账户权益路径。
- 成本口径：本阶段不重算成本压力，只复盘 1x 保证金差异。
- 样本过滤：无日期、品种、坏窗口过滤。
- 策略/归因口径：
  - exact：Stage214 逐日 C3 持仓保证金 + xsmom true margin。
  - proxy：Stage213 口径，即 Stage352 `start_2020` 旧 C3 保证金路径乘以 `risk060=0.60` 或 `risk070=0.70`，再加 xsmom true margin。
  - 差异：`(exact_broker10_margin - proxy_broker10_margin) / account_equity`。

## 结果

- `risk060 + true xsmom`：
  - 期末权益：沿用 Stage214 `20,682,740`
  - 总收益：沿用 Stage214 `3263.0472%`
  - 最大回撤：沿用 Stage214 `-36.2870%`
  - Sharpe：沿用 Stage214 `1.2291`
  - 总滑点：沿用 Stage214 `1,231,020`
  - 总交易次数：沿用 Stage214 `1,220`
  - 胜率：沿用 Stage214 非零日胜率 `52.8614%`
  - 其他关键指标：最大 exact-proxy 差异 `104.9598pp`，日期 `2021-09-27`；proxy 为正时 C3 exact/proxy 均值 `1.9784`、中位数 `1.3053`；`exact_only` 天数 `118`，exact 比 proxy 高 50pp 以上天数 `34`。
- `risk070 + true xsmom`：
  - 期末权益：沿用 Stage214 `21,210,535`
  - 总收益：沿用 Stage214 `3348.8675%`
  - 最大回撤：沿用 Stage214 `-38.5861%`
  - Sharpe：沿用 Stage214 `1.1674`
  - 总滑点：沿用 Stage214 `1,228,400`
  - 总交易次数：沿用 Stage214 `1,215`
  - 胜率：沿用 Stage214 非零日胜率 `52.4887%`
  - 其他关键指标：最大 exact-proxy 差异 `102.7679pp`，`exact_only` 天数 `113`，exact 比 proxy 高 50pp 以上天数 `34`。
- 差异类别：
  - risk060：`both_exact_gt_proxy=600` 天、`both_proxy_gt_exact=294` 天、`exact_only=118` 天、`proxy_only=84` 天、`close_enough=82` 天。
  - risk070：`both_exact_gt_proxy=523` 天、`both_proxy_gt_exact=371` 天、`exact_only=113` 天、`proxy_only=97` 天、`close_enough=69` 天。
- 最大差异例子：
  - `risk060` 在 `2021-09-27`：exact C3 保证金 `2,626,920`，proxy C3 保证金仅 `159,048`，exact broker10/equity `111.7242%`，proxy `6.7644%`，差异 `104.9598pp`。
  - `risk060` 在 `2024-08-21`：proxy C3 保证金为 `0`，但 exact C3 保证金 `5,039,820`，属于 `exact_only` 路径错位。

## 图表视觉复盘

- 左上/右上线图显示 exact 与 proxy 经常错位，尤其在 2021-09、2023-03、2024-08、2025-01 等阶段；这不是同一曲线的倍率差。
- 左下散点图大量点远离 `y=x`，还存在 proxy 接近 0 但 exact 很高的点，说明问题来自持仓路径变化，不是保证金率或乘数小误差。
- 右下分类柱图显示 `exact_only`、`proxy_only`、`both_exact_gt_proxy` 同时存在，证明两条路径的持仓日期和合约集合都不一致。
- 产品构成显示最大正差异由 C3 主体的高名义保证金合约驱动，例如 `ru/OI/FG/fu/AP`；不是 xsmom 小腿造成。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_report_stage515_stage214_margin_gap_postmortem_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_decision_stage515_stage214_margin_gap_postmortem_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_chart_stage515_stage214_margin_gap_postmortem_v1.png`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_daily_stage515_stage214_margin_gap_postmortem_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_summary_stage515_stage214_margin_gap_postmortem_v1.csv`
- top gap days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_top_gap_days_stage515_stage214_margin_gap_postmortem_v1.csv`
- top gap products：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage515_stage214_margin_gap_postmortem_top_gap_products_stage515_stage214_margin_gap_postmortem_v1.csv`

## 结论

- 本阶段结论：Stage213 proxy invalid。它将旧 Stage352/Stage079 C3 保证金乘以风险倍率，但下一真实窗口 `risk060/risk070` 的实际持仓路径已变化，不能作为部署裁决证据。
- 是否进入下一步：是。
- 下一步：以后候选必须先用 exact position margin 做硬闸门。策略方向转为低名义风险结构、保证金感知 sizing，或低相关且保证金轻的独立收益源；不得继续修 Stage213 proxy，也不得扫 `risk=0.61/0.62`。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有修改交易规则、信号、品种、日期或参数；只是解释两个固定阶段输出之间的口径差异。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：目标仍未完成，但 Stage215 明确了后续研究的硬约束：必须使用 exact position margin。继续在代理保证金上优化会制造虚假的可部署感。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段改变后续所有候选的保证金审计口径。
