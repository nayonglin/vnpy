# Stage203 第78连续复权指标正式样本反证

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 03:07
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读反证、归因验证
- 是否重要突破：否，但是否定了一个看似合理的修复方向
- 是否触发A/B：否，continuous_diff_back_adjust未通过正式样本，不进入A/B

## 外部调研与判断

- 参考资料：
  - TradeStation Help: Continuous Futures Contracts。连续期货用于期货回测，因为单个合约生命周期有限；换月点需要拼接并调整以保持连续。
  - TradingView Help: Back-adjustment for continuous futures。复权通过换月时的新旧合约价差系数消除换月跳空。
  - vn.py PortfolioStrategy文档。PortfolioStrategy用于多合约组合策略实盘生命周期管理。
- 我的判断：
  - 连续/复权合约适合做多年指标研究，但不是现实可成交价格。
  - 对第78更稳妥的方式只能是“指标层可尝试连续复权，执行层仍用真实合约”。
  - 该方向必须先过2020-2026正式样本反证；如果正式样本显著恶化，就不能为了修复2015-2019早期无信号而合入。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage203_stage78_continuous_diff_formal_oos.py`
- 修改脚本：
  - 无正式策略修改；脚本内补充了适用于2020-2026的动态年度汇总函数，避免复用Stage199固定2015-2019的汇总逻辑。
- 删除脚本：无
- 新增参数：
  - `continuous_indicator=True`
  - `adjust_mode=diff_back_adjust`
- 修改参数：无第78正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 预加载：2019-06-01
- 账户规模：200,000
- 成本口径：沿用第78正式回测元数据滑点；手续费为当前框架默认0
- 样本过滤：第78正式`official_stage78_defensive_v1`配置
- 策略/归因口径：
  - baseline_contract_am：正式合约级ArrayManager
  - continuous_diff_back_adjust：差值后复权连续主力指标，真实合约执行

## 结果

### baseline_contract_am

- 期末权益：4,637,530
- 总收益：2,218.7650%
- 最大回撤：-36.9907%
- Sharpe：1.2922
- 总滑点：261,740
- 总交易次数：782
- 胜率：42.1053%
- raw_signal_count：1,194
- candidate_count：1,078
- opened_candidate_count：362

### continuous_diff_back_adjust

- 期末权益：808,795
- 总收益：304.3975%
- 最大回撤：-50.1180%
- Sharpe：0.4878
- 总滑点：159,610
- 总交易次数：668
- 胜率：47.8134%
- raw_signal_count：1,217
- candidate_count：1,032
- opened_candidate_count：314
- 换月复权事件：475

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage203_stage78_continuous_diff_formal_oos_report_stage203_stage78_continuous_diff_formal_oos_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage203_stage78_continuous_diff_formal_oos_stats_stage203_stage78_continuous_diff_formal_oos_v1.csv`
- orders/trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage203_stage78_continuous_diff_formal_oos_trades_stage203_stage78_continuous_diff_formal_oos_v1.csv`
- daily：本阶段未单独导出daily曲线
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage203_stage78_continuous_diff_formal_oos_yearly_summary_stage203_stage78_continuous_diff_formal_oos_v1.csv`

## 结论

- 本阶段结论：
  - continuous_diff_back_adjust能解释2015-2019早期合约级AM断裂，但不能作为第78升级。
  - 正式样本表现显著劣化：收益大幅下降、最大回撤突破用户40%可承受回撤，Sharpe降至0.4878。
  - 不继续对该连续复权指标做T+1延迟成交验证，因为同日成交正式样本已经未通过。
- 是否进入下一步：是，但方向切回第78正式基准。
- 下一步：
  - 2015-2019早期样本在报告中标注为“合约级AM历史断裂导致的低交易期”，不为修复早期样本修改第78。
  - 继续推进第78正式基准的T+1成交审计、影子盘SOP和每日信号对账。

## 过拟合反思

- 运行前判断：否。本阶段是拿正式样本反证连续复权指标，不按收益调参。
- 运行后判断：否，但阻止了一个潜在过拟合方向。
- 原因：
  - 如果只看2015-2019，continuous_diff_back_adjust会显得有吸引力；但2020-2026正式样本明确劣化。
  - 因此不能为了让2015年更“有交易”而改第78指标口径。

## 继续价值反思

- 运行前判断：有价值。它能判断2015-2019早期无信号到底是数据缺口、AI池问题，还是合约级指标初始化问题。
- 运行后判断：有价值，但该分支应收束。
- 原因：
  - 价值在于解释机制和排除错误修复，而不是产出新策略。
  - 第78仍应以正式合约级AM基准为主，后续价值在实盘可交易性和影子盘，不在继续优化连续复权。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待本轮2015多周期审计汇总后统一整理。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
