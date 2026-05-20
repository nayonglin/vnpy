# Stage004 放松下影线开仓要求对比

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：day
- 记录时间：2026-05-15 15:06 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：预先锁定参数的规则放松对比
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TrendSpider Marubozu：`https://trendspider.com/learning-center/marubozu-candlesticks-a-traders-guide/`
  - RoboForex Marubozu：`https://blog.roboforex.com/blog/2021/12/24/how-to-trade-marubozu-pattern/`
  - Strike Marubozu：`https://www.strike.money/technical-analysis/marubozu`
- 我的判断：
  - 外部资料普遍允许 Marubozu/近似无影线存在极小影线，因此“放松一点”在形态定义上合理。
  - 但放松必须预先锁定少数固定口径，不能看结果调参数。本阶段只比较 strict、1tick、2tick/body10 三档。
  - 核心验收不是交易次数增加，而是初始止损率、亏损尾部、跨年稳定性是否改善。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_relaxed_entry_compare.py`
- 修改脚本：`examples/portfolio_backtesting/run_qmt_no_lower_shadow_swing_backtest.py`
- 修改测试：`tests/test_qmt_no_lower_shadow_swing.py`
- 删除脚本：无
- 新增参数：
  - `signal_variant = strict`
  - `signal_variant = lower_shadow_1tick`
  - `signal_variant = lower_shadow_2tick_body10`
- 修改参数：无，默认仍为 `strict`。
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 到 2026-04-30。
- 账户规模：500,000。
- 成本口径：继承 Stage001，使用现有合约 `size/pricetick/slippage/margin_ratio`。
- 样本过滤：eligible 全市场 57 个品种，主力合约映射；信号到入场日换月仍跳过。
- 策略/归因口径：
  - `strict`：按 tick 取整后 `open == low` 且 `close > open`。
  - `lower_shadow_1tick`：下影线允许 `open - low <= 1 * pricetick`。
  - `lower_shadow_2tick_body10`：下影线允许 `open - low <= min(2 * pricetick, 10% * body)`。
  - 入场、止损、首日减半、移动止损、换月强平规则全部不变。

## 结果

| signal_variant | 单根信号 | 连续两日候选 | 实际开仓 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 胜率 | 总滑点 | 初始止损笔数 | 初始止损净亏 | 移动止损净盈亏 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| strict | 2,711 | 119 | 86 | 463,825 | -7.2350% | -13.5818% | -0.4146 | 23.2558% | 21,130 | 33 | -80,505 | 25,250 |
| lower_shadow_1tick | 3,811 | 213 | 155 | 438,035 | -12.3930% | -16.8245% | -0.5757 | 26.4516% | 38,070 | 58 | -135,900 | 33,000 |
| lower_shadow_2tick_body10 | 4,368 | 247 | 175 | 462,560 | -7.4880% | -14.3776% | -0.2915 | 30.8571% | 34,540 | 57 | -133,705 | 57,815 |

- 期末权益：最优仍低于初始资金，`lower_shadow_2tick_body10` 为 `462,560`。
- 总收益：三档均为负，`strict` `-7.2350%`，`1tick` `-12.3930%`，`2tick/body10` `-7.4880%`。
- 最大回撤：放松后均比 strict 更差。
- Sharpe：`2tick/body10` 的 Sharpe 较 strict 略好，但收益仍负、回撤更深，不能作为升级理由。
- 总滑点：放松后显著增加，交易数增加带来成本放大。
- 总交易次数：`207` / `380` / `435`。
- 胜率：放松后胜率上升，但风险收益没有改善，说明胜率上升被初始止损尾部吞掉。

## 输出文件

- compare_report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_relaxed_entry_compare_stage004_report.md`
- compare_summary_csv：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_relaxed_entry_compare_stage004_summary.csv`
- compare_summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_relaxed_entry_compare_stage004_summary.json`
- strict_report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage004_strict_attribution_report.md`
- lower_shadow_1tick_report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage004_lower_shadow_1tick_attribution_report.md`
- lower_shadow_2tick_body10_report：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_stage004_lower_shadow_2tick_body10_attribution_report.md`

## 结论

- 本阶段结论：
  - 放松下影线确实有效增加交易数，但没有改善策略质量。
  - `lower_shadow_1tick` 是明确反证：开仓数从 86 增到 155，收益从 `-7.2350%` 恶化到 `-12.3930%`。
  - `lower_shadow_2tick_body10` 看似胜率和 Sharpe 较好，但期末权益仍低于 strict，回撤更深，初始止损净亏扩大到 `-133,705`，不具备升级价值。
  - 新增样本主要增加了同类首日/初始止损失败，说明“严格无下影线”不是唯一问题，第三天开盘追多结构仍是核心矛盾。
- 是否进入下一步：不继续放松下影线；回到首日执行反事实。
- 下一步：
  - 做“信号不变，但第三天不开盘追入”的执行反事实。
  - 优先测试回踩信号2收盘/信号2中位/信号2低点附近才成交，记录未成交和成交后的初始止损变化。
  - 同时测试初始止损放宽到两日低点，但只作为风险结构解释，不作为参数搜索。

## 过拟合反思

- 运行前判断：存在过拟合风险，但可控。
- 运行后判断：没有过拟合升级，但结果反证了放松方向。
- 原因：
  - 本阶段三档规则在运行前已固定，没有根据收益结果追加或修改阈值。
  - 放松后的交易数增加并未被解释为好事，反而按风险收益和初始止损尾部做反证，避免了“为了更多交易而更多交易”的偏差。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但价值不在继续放松信号，而在验证执行结构。
- 原因：
  - 这次确认“严格信号太少”不是主要瓶颈；放宽信号只会把首日失败扩大。
  - 原始形态和放松形态都暴露同一个问题：第三天开盘追多容易吃回撤。
  - 如果执行反事实仍失败，就应该停止该线，不要再扩参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage004 反证。
- 是否更新 `research/registry.md`：是，更新最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是研究线内部反证，不是正式候选或跨线合并。
