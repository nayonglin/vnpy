# Stage779 Stage777 2022 连续亏损逐笔复盘

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-10 10:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读逐笔归因
- 是否重要突破：否，但解释 Stage777 2022 回撤的直接机制
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Open Interest：OI 上升可用于趋势参与度确认，但不是独立低风险信号。
  - Man Group / 趋势跟随 whipsaw 资料：趋势策略在反复反转和宽幅震荡中容易遭遇连续小亏和止损簇。
- 我的判断：本阶段要区分“连败机制导致”和“真实交易结果连续亏损”。Stage777 关闭了连败缩放，所以不能把回撤归因给连败风控机制；但实际交易结果确实存在高度集中的连续亏损段。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage779_stage777_2022_loss_streak_review.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`FOCUS_PROFILE=oi_restore_am40`、`FOCUS_START=2021-09`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取 Stage778 `2022-03-09 -> 2022-06-29` 峰谷窗口闭合 lot
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 / Stage778 闭合 lot
- 样本过滤：仅统计出场日在峰值日至谷值日之间的闭合 lot
- 策略/归因口径：`AM41 + OI0.8` 对照 `no_oi/am41`

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：引用 Stage777 最差 `-50.1325%`
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：焦点起点 `oi_restore/am41 2021-09` 峰谷窗口闭合 lot `19` 个
- 胜率：焦点起点峰谷窗口 `5/19=26.3158%`
- 其他关键指标：
  - `oi_restore/am41 2021-09`：`19` 个闭合 lot，`14` 亏损、`5` 盈利，窗口 realized PnL `-198,350`。
  - 最大连续亏损段：`13` 笔，合计 `-271,030`。
  - 最大连续亏损段中 OI 放大：`8` 笔，合计 `-208,390`。
  - `no_oi/am41 2021-09` 同窗口也有 `13` 笔连续亏损，合计 `-201,730`，说明连亏来自行情环境和趋势本体。
  - 所有代表起点中，OI 版本最大连续亏损段均为 `13` 笔；不开 OI 版本除 `2022-01` 为 `12` 笔外，其余也为 `13` 笔。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage779_stage777_2022_loss_streak_review_report_stage779_stage777_2022_loss_streak_review_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage779_stage777_2022_loss_streak_review_summary_stage779_stage777_2022_loss_streak_review_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage779_stage777_2022_loss_streak_review_worst_sequence_stage779_stage777_2022_loss_streak_review_v1.csv`
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage779_stage777_2022_loss_streak_review_oi_group_stage779_stage777_2022_loss_streak_review_v1.csv`

## 结论

- 本阶段结论：如果问题是“是不是连续失败导致净值下行”，答案是是；如果问题是“是不是连败缩仓机制导致”，答案是否。
- 是否进入下一步：不进入连败参数扫描；可进入“连亏簇识别/暂停开仓”的只读特征研究。
- 下一步：若继续，研究方向应是识别反转/震荡期的连续亏损簇，例如近 N 笔同方向/跨品种止损密度、同向相关性、价格路径顺畅度和波动扩张，而不是恢复或放大仓位。

## 过拟合反思

- 运行前判断：低过拟合，原因是只读重排既有闭合 lot，不调参。
- 运行后判断：低过拟合，结论来自代表起点和 OI/不开 OI 对照共同序列。
- 原因：没有改变交易规则，只解释 2022 峰谷窗口内部发生了什么。

## 继续价值反思

- 运行前判断：有价值，因为用户明确追问是否由连续失败造成。
- 运行后判断：有价值，但方向不是扫连败倍率，而是识别连续亏损簇。
- 原因：连亏是真实风险结构，但 Stage777 没有启用连败缩放；问题在于 OI 放大没有避开连亏簇。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
