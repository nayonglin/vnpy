# Stage222 第78正式基准与影子盘口径切换为50万

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 15:03
- 阶段性质：正式基准资金口径与影子盘启动口径变更
- 是否重要突破：是
- 是否触发A/B：是，部署层 `A vs C`

## 外部调研与判断

- 资金规模变更是部署层变更，不改变信号本身，但会通过手数取整、保证金占用、并发仓位和收益率分母改变策略路径。
- 对趋势策略而言，资金越大不必然越好；若仓位可随权益扩张，绝对回撤、滑点和容量压力也会同步放大。
- 本轮用户明确要求把第78正式初始资金与既有影子盘口径统一为50万，因此执行固化，但后续仍需用三件套验证执行压力。

## A/C定义

- A：Stage221，第78正式基准，30万本金，关闭100万sizing封顶
- C：Stage222，第78正式基准，50万本金，关闭100万sizing封顶，并同步影子盘启动/日报默认口径
- B：不适用，本次不是独立策略模块

## 本次代码变更

- 修改：
  - `examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage168_30w_qmt_shadow_startup_pack.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage169_30w_qmt_shadow_daily_runner.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage172_stage78_forward_shadow_report.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage186_stage78_2026_30w_cold_start.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_2026_30w_cold_start_latest_ai_pool.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage218_stage78_30w_multiperiod_equity_curves.py`
  - `research/lines/futures_trend/LINE.md`
- 新增50万wrapper入口：
  - `examples/portfolio_backtesting/build_qmt_roll_stage168_50w_qmt_shadow_startup_pack.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage169_50w_qmt_shadow_daily_runner.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage186_stage78_2026_50w_cold_start.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_2026_50w_cold_start_latest_ai_pool.py`
- 新增参数：无
- 修改参数：
  - `OFFICIAL_STAGE78_CAPITAL`：`300,000` -> `500,000`
  - `run_qmt_roll_backtest.py` 默认 `capital/capital_base`：`300,000` -> `500,000`
  - Stage168影子盘 `SHADOW_CAPITAL` 改为跟随 `OFFICIAL_STAGE78_CAPITAL`
  - Stage186/188冷启动默认本金改为 `OFFICIAL_STAGE78_CAPITAL`
- 删除参数：无
- 输出命名：
  - Stage168/169/186/188/217/218后续默认产物名从 `30w` 调整为 `50w`

## 回测/复验结果

- 本轮没有新跑完整主回测；参考指标来自前序Stage220的50万无封顶多周期结果，并已写入第78官方参考指标。
- 50万无封顶全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5,008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：待后续正式三件套复跑确认
- 50万无封顶2026冷启动：
  - 期末权益：`450,540`
  - 总收益：`-9.8920%`
  - 最大回撤：`-28.5861%`
  - Sharpe：`-0.6975`
  - 总滑点：`4,660`
  - 总交易次数：`27`
  - 胜率：待后续正式三件套复跑确认

## 影子盘产物

- 已重新生成50万Stage168启动包：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_50w_qmt_shadow_startup_config_stage168_50w_qmt_shadow_startup_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_50w_qmt_shadow_startup_report_stage168_50w_qmt_shadow_startup_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage168_50w_qmt_shadow_startup_runbook_stage168_50w_qmt_shadow_startup_v1.md`
- 已重新生成50万Stage169影子日报：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_50w_qmt_shadow_daily_runner_summary_20260415_stage169_50w_qmt_shadow_daily_runner_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage169_50w_qmt_shadow_daily_runner_daily_report_20260415_stage169_50w_qmt_shadow_daily_runner_v1.md`
- Stage168关键边界：
  - 影子资金：`500,000`
  - 最大容忍回撤：`40%`
  - 最大容忍亏损现金：`200,000`
  - 下一模式：`50w_qmt_shadow_read_only`

## 过拟合反思

- 运行前判断：有一定风险。50万优于30万的部分来自历史路径和容量效应，不能把资金规模当作收益参数反复调。
- 运行后判断：可接受。此处是用户实际资金/影子盘边界统一，不是按某个弱窗口修补信号。

## 继续价值反思

- 运行前判断：有价值。正式基准与影子盘资金口径一致，能减少新agent和后续实盘准备误解。
- 运行后判断：有价值。Stage168/169已可生成50万启动与日报包，后续可以直接进入50万准实盘流程。

## TODO

- 用50万无封顶正式口径重跑三件套：T+1、滑点压力、Monte Carlo。
- 用50万无封顶正式口径重跑多周期资金曲线，替换Stage220临时反事实报告为正式报告。
- 审计50万下的绝对回撤、总滑点和保证金使用峰值。
