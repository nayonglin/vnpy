# Stage232 部署资金分层账户层验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 23:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：账户部署层资金治理验证
- 是否重要突破：是，确认账户层资金分层比继续调策略覆盖层参数更有价值
- 是否触发A/B：是，`A=baseline_full_reinvest`，`C1=profit_tranche_v1`，`C2=balanced_tranche_v1`

## 外部调研与判断

- 参考资料：
  - CTA资料强调需要根据组合整体风险校准头寸，而不是把所有收益无限复利。
  - 资金管理资料强调交易资本、储备资本、长期资本要分层管理。
  - prop/funded账户资料里的提款与trailing drawdown机制，本质也是把部分利润锁住，避免回撤吞掉全部高水位收益。
- 我的判断：
  - Stage231后继续调策略参数已经开始接近过拟合。
  - 账户层分层不改`78-1` alpha、AI、信号和产品池，只改变收益如何进入生产账户/锁盈账户/扩张账户。
  - 这是更接近实盘的问题：赚到的钱是否全部继续加杠杆，还是部分锁定。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage232_deployment_capital_tranching.py`
- 修改脚本：无正式策略修改。
- 新增参数：无策略参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入路径：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_multiperiod_curves_stage225_stage78_1_ai_ablation_suite_v1.csv`
- 输入口径：
  - `78-1 AI ON`独立多周期日收益路径。
  - 以`rebased_balance`反推日收益，确保`since_2020`全复利路径对齐`25,542,885`。
- 账户层政策：
  - A `baseline_full_reinvest`：全部权益继续复利。
  - C1 `profit_tranche_v1`：月末超过`3,000,000`的生产资金，提取`70%`；其中`70%`进锁盈账户，`30%`进扩张/补仓储备。
  - C2 `balanced_tranche_v1`：月末超过`5,000,000`的生产资金，提取`50%`；其中`60%`进锁盈账户，`40%`进扩张/补仓储备。
- Monte Carlo：
  - daily-block bootstrap，`1000`次。
- 注意：
  - 这是账户部署层模拟，不是撮合级回测；它用于评估资金制度，不替代`78-1`正式回测。

## 结果

- A `baseline_full_reinvest` since_2020：
  - 期末总权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.4218`
  - 期末锁盈资金：`0`
- C1 `profit_tranche_v1` since_2020：
  - 期末总权益：`10,770,830`
  - 总收益：`2054.1661%`
  - 最大回撤：`-39.2765%`
  - Sharpe：`1.3450`
  - 期末锁盈资金：`5,480,758`
- C2 `balanced_tranche_v1` since_2020：
  - 期末总权益：`15,473,580`
  - 总收益：`2994.7161%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.3726`
  - 期末锁盈资金：`6,289,672`
- 多周期：
  - C2在`since_2021`总收益`2285.3814%`，锁盈`4,214,708`
  - C2在`since_2022`总收益`988.2330%`，略高于全复利基准`979.7190%`
  - C2对`2026`冷启动无改善，因为权益尚未触发分层提款
- Monte Carlo daily-block：
  - A亏损概率`0.0%`，回撤超过40%概率`89.9%`，中位收益`5354.1666%`
  - C1亏损概率`0.3%`，回撤超过40%概率`58.3%`，中位收益`2174.3852%`，中位锁盈`6,024,453`
  - C2亏损概率`0.2%`，回撤超过40%概率`66.6%`，中位收益`3063.0174%`，中位锁盈`6,553,148`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage232_deployment_capital_tranching_report_stage232_deployment_capital_tranching_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage232_deployment_capital_tranching_summary_stage232_deployment_capital_tranching_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage232_deployment_capital_tranching_curves_stage232_deployment_capital_tranching_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage232_deployment_capital_tranching_monte_carlo_summary_stage232_deployment_capital_tranching_v1.csv`

## 结论

- 本阶段结论：
  - `balanced_tranche_v1` 是当前更有价值的部署候选：它不改策略，却把`629万`利润锁出，并保留接近`3000%`的总收益。
  - `profit_tranche_v1`太保守，虽然锁盈明确，但收益降到`2054%`，不适合作为默认部署口径。
  - 账户层分层不能解决早期触发前的回撤，因此不能替代风控；它解决的是“高水位后不要把全部利润继续暴露”的问题。
- 是否进入下一步：是。
- 下一步：
  - 将`balanced_tranche_v1`整理成部署规则草案：何时提款、锁盈账户用途、扩张账户如何补生产账户。
  - 做一版“影子盘资金分层日报/账本”模板，便于未来真实执行。

## 过拟合反思

- 运行前判断：否。账户层现金流制度不依赖品种或信号微调。
- 运行后判断：否。C2并没有追求完美曲线，只是把高水位后部分利润转移到账户层。
- 风险提示：Stage232是日收益路径模拟，不是撮合级引擎；不能把它当作策略收益替代。

## 继续价值反思

- 运行前判断：有。策略内覆盖层参数优化已经触及停止条件，需要转向部署层治理。
- 运行后判断：有。C2给出了可执行、可解释的资金分层制度。
- 原因：它保留了主要复利能力，同时把真实可保全利润显性化，比继续调策略参数更贴近实盘。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，将下一步切换为部署规则草案与影子盘账本。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`补充Stage232结论。
