# Stage001 当前正式版连败阈值全周期扫描

- line_id：`futures_trend_loss_streak_threshold_sweep`
- 当前模式：`day`
- 记录时间：`2026-06-08 17:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：参数敏感性全周期回测
- 是否重要突破：否，关键负结论
- 是否触发A/B：否，本阶段只做全周期曲线，不做正式晋级

## 外部调研与判断

- 参考资料：
  - trend following / systematic trading position sizing 资料普遍支持用风险预算和账户状态控制仓位，但也强调连败序列是常见统计现象，不能仅按历史最佳阈值调参。
  - Rob Carver 系统化交易相关资料强调仓位规则会显著改变右尾和回撤分布，必须多起点验证。
- 我的判断：用户提出“3 笔后降到 0.1 是否过早”是合理问题；但阈值 `3~12` 属于路径敏感参数扫描，全周期最优不能直接正式化，必须先作为机制理解。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage717_official_loss_streak_threshold_sweep.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `THRESHOLDS=3,4,5,6,7,8,9,10,11,12`
  - `FLOOR_MULTIPLIER=0.1`
  - `ANALYSIS_START=2020-01-01`
  - `ANALYSIS_END=2026-04-30`
- 修改参数：仅运行期把 `streak_risk_multipliers` 改为不同阈值；阈值 N 对应 `1.0` 重复 N 次后接 `0.1`。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本；本阶段未做 2x/3x 成本压力
- 样本过滤：无，完整当前正式版全周期回测
- 策略/归因口径：当前 Stage372/20万正式版，其余配置不变，包括 AI 池、品种池、`recovery_sleeve`、`maxpos4`、强制减仓规则；不连接 CTP，不调用下单。

## 结果

| 连亏阈值 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 | 强制减仓 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% | 79.6015% | 6 / 299手 |
| 4 | 3,976,010 | 1888.0050% | -41.6430% | 1.3586 | 301,560 | 642 | 52.2007% | 75.7834% | 6 / 288手 |
| 5 | 3,427,445 | 1613.7225% | -43.7796% | 1.2932 | 272,520 | 653 | 51.4938% | 78.5207% | 7 / 281手 |
| 6 | 3,758,300 | 1779.1500% | -44.8384% | 1.2723 | 303,520 | 673 | 51.7241% | 77.2845% | 9 / 363手 |
| 7 | 3,535,665 | 1667.8325% | -44.8384% | 1.2491 | 328,740 | 673 | 51.7749% | 77.2845% | 9 / 366手 |
| 8 | 3,338,515 | 1569.2575% | -46.1478% | 1.2204 | 319,690 | 677 | 51.5962% | 77.2845% | 9 / 342手 |
| 9 | 3,203,395 | 1501.6975% | -46.1478% | 1.2047 | 326,070 | 677 | 51.5962% | 77.2845% | 9 / 342手 |
| 10 | 3,203,395 | 1501.6975% | -46.1478% | 1.2047 | 326,070 | 677 | 51.5962% | 77.2845% | 9 / 342手 |
| 11 | 3,203,395 | 1501.6975% | -46.1478% | 1.2047 | 326,070 | 677 | 51.5962% | 77.2845% | 9 / 342手 |
| 12 | 3,203,395 | 1501.6975% | -46.1478% | 1.2047 | 326,070 | 677 | 51.5962% | 77.2845% | 9 / 342手 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage717_official_loss_streak_threshold_sweep_report_stage717_official_loss_streak_threshold_sweep_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage717_official_loss_streak_threshold_sweep_summary_stage717_official_loss_streak_threshold_sweep_v1.csv`
- orders：不适用
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage717_official_loss_streak_threshold_sweep_curves_stage717_official_loss_streak_threshold_sweep_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage717_official_loss_streak_threshold_sweep_equity_curves_stage717_official_loss_streak_threshold_sweep_v1.png`

## 结论

- 本阶段结论：`loss_streak_threshold_sweep_full_period_only_no_promotion`。
- 是否进入下一步：不自动进入正式候选。
- 下一步：若继续，只能把阈值 `3/4/6` 做多起点、季度冷启动、弱窗口、成本压力和交易归因反证；但当前全周期结果已强烈支持“3 笔后降到 0.1 不是明显过早”。

## 过拟合反思

- 运行前判断：否，但风险高。只改一个结构参数，范围预声明，没有按结果动态调参。
- 运行后判断：若据全周期最高值继续调阈值会过拟合；但当前结果反而支持保持原阈值。
- 原因：阈值后移并没有释放可持续右尾，反而破坏 2020-2022 权益底座，使 2023-2026 的复利空间整体降低。

## 继续价值反思

- 运行前判断：有价值。它直接回答“连续亏 3 笔就降到 0.1 是否太早”。
- 运行后判断：单纯后移阈值继续价值低。
- 原因：阈值 4 到 12 全部在全周期收益、回撤和 Sharpe 上弱于阈值 3；后续价值只在归因为什么阈值 3 保护了底座，而不是继续扫阈值。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是，本线为用户明确要求新建研究线
- 是否追加根目录 `memory.md/back_log.md`：是，作为正式连败风控边界结论
