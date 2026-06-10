# Stage774 AM41 2018 起点冻结法证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-10 01:04 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage773 AM41 2018 起点结果复核/异常样本法证
- 是否重要突破：否，但修正 Stage773 中 AM41 2018 口径解读
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮补充检索 vn.py GitHub `ArrayManager` 源码，确认 `update_bar` 达到 `size` 后 `inited=True`，AM size 是指标可计算前置门槛。
- 我的判断：AM41 是研究专用最小窗口，不是原策略自然口径；策略内部正常 AM 公式为 `max(ma_extra_long + donchian_entry_period + 20, floor)`，即至少 `80`，正式 floor 为 `120`。因此 AM41 出现异常时不能当成正式候选表现。

## 本次变更

- 新增脚本：无，使用临时复跑脚本复核 `no_oi_am40` 与 `oi_restore_am40` 的 2018 起点
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`
- 账户规模：Stage773 AM41 口径，`500,000`
- 成本口径：基础回测成本
- 样本过滤：2018 年度起点
- 策略/归因口径：`no_oi_am40` 与 `oi_restore_am40`，其中 `am40` 实际为研究专用 `AM=41`

## 结果

- 期末权益：
  - `no_oi_am40`：`434,170`
  - `oi_restore_am40`：`439,850`
- 总收益：
  - `no_oi_am40`：`-13.166%`
  - `oi_restore_am40`：`-12.030%`
- 最大回撤：
  - `no_oi_am40`：`-15.0743%`
  - `oi_restore_am40`：`-17.8817%`
- Sharpe：
  - `no_oi_am40`：`-0.4139`
  - `oi_restore_am40`：`-0.2223`
- 总滑点：
  - `no_oi_am40`：`5,440`
  - `oi_restore_am40`：`7,170`
- 总交易次数：
  - `no_oi_am40`：`66` 个成交事件；2018 年 `46` 个，2019 年 `20` 个，2019-04-04 后无成交
  - `oi_restore_am40`：`66` 个成交事件；2018 年 `46` 个，2019 年 `20` 个，2019-04-04 后无成交
- 胜率：未重新统计逐笔胜率
- 其他关键指标：
  - `no_oi_am40` 最后非零 PnL 日为 `2019-04-11`，此后到 `2026-05-29` 权益固定为 `434,170`
  - `oi_restore_am40` 最后非零 PnL 日为 `2019-04-11`，此后到 `2026-05-29` 权益固定为 `439,850`
  - `no_oi_am40` 最终残留仓位轧差：`AP905.CZCE +2`、`SM809.CZCE +8`、`hc1905.SHFE +8`、`jm1901.DCE +5`
  - `oi_restore_am40` 最终残留仓位轧差：`AP905.CZCE +2`、`SM809.CZCE +15`、`hc1905.SHFE +8`、`jm1901.DCE +5`

## 输出文件

- report：无新增
- summary：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage773_am40_80_120_oi_yearly_summary_stage773_am40_80_120_oi_yearly_v1.csv`
- orders：无新增
- daily：沿用 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage773_am40_80_120_oi_yearly_curves_stage773_am40_80_120_oi_yearly_v1.csv`
- quality：无新增

## 结论

- 本阶段结论：用户质疑是正确的。AM41 2018 起点的低回撤不是有效的全周期低回撤，而是因为 2019-04 后权益、PnL 和交易全部冻结，且仍有老合约残留仓位。该样本应标为异常冻结样本，不能用于证明 AM41 稳健。
- 是否进入下一步：不推广 AM41；Stage773 中 AM41 只保留为反证。
- 下一步：如果继续研究降低预热门槛，优先看不破坏策略历史长度假设的 AM80；更合理的方向是研究“连续产品序列算信号、真实主力合约执行”，而不是把真实合约 AM 强行压到 41。

## 过拟合反思

- 运行前判断：有过拟合风险，尤其容易把 AM41 2018 亏损低回撤误读为稳定。
- 运行后判断：该样本不是过拟合收益，而是异常冻结；更不能用于推广。
- 原因：2019-04 后没有交易和 PnL，回撤低只是权益冻结后的数学结果，不是策略风险控制有效。

## 继续价值反思

- 运行前判断：有价值，因为用户指出的疑点确实需要复核。
- 运行后判断：有价值，但只限于纠偏；继续围绕 AM41 做收益比较价值很低。
- 原因：AM41 已经偏离原策略的历史窗口结构，并出现老合约残留冻结，不是正式策略候选。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
