# Stage254 Stage78-1资金口径去30万化与入口隔离

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-12 20:02
- 阶段性质：部署口径治理/入口隔离
- 是否重要突破：是
- 是否触发A/B：否，本阶段不改策略、不改参数、不跑新收益比较

## 外部调研与判断

- 本阶段不是策略研究，而是工程口径治理。
- 参考 Python `warnings`/弃用机制的工程原则：旧接口如果继续可运行，容易被调用方误用；仅在日志里说明不够，需要在入口层明确提示或阻断。
- 本仓库场景更接近部署安全闸门，不适合只给 `DeprecationWarning`，因为 Python 对部分弃用警告默认会隐藏；因此旧`30w`入口采用 `SystemExit` 明确阻断。

## 本次代码变更

- 新增 canonical 入口：
  - `examples/portfolio_backtesting/build_qmt_roll_stage168_stage78_1_shadow_startup_pack.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage169_stage78_1_shadow_daily_runner.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage186_stage78_1_2026_cold_start.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_1_2026_cold_start_latest_ai_pool.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage217_stage78_1_execution_slippage_mc_suite.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage218_stage78_1_multiperiod_equity_curves.py`
- 修改兼容入口：
  - `build_qmt_roll_stage168_50w_qmt_shadow_startup_pack.py` 改为导入 canonical Stage78-1 启动包
  - `build_qmt_roll_stage169_50w_qmt_shadow_daily_runner.py` 改为导入 canonical Stage78-1 日报 runner
  - `build_qmt_roll_stage78_1_shadow_daily_runner.py` 直接导入 canonical Stage78-1 日报 runner
  - `run_qmt_roll_stage186_stage78_2026_50w_cold_start.py` 改为导入 canonical Stage78-1 冷启动
  - `run_qmt_roll_stage188_stage78_2026_50w_cold_start_latest_ai_pool.py` 改为导入 canonical Stage78-1 最新AI池冷启动
- 禁用旧`30w`可运行入口：
  - `build_qmt_roll_stage168_30w_qmt_shadow_startup_pack.py`
  - `build_qmt_roll_stage169_30w_qmt_shadow_daily_runner.py`
  - `run_qmt_roll_stage186_stage78_2026_30w_cold_start.py`
  - `run_qmt_roll_stage188_stage78_2026_30w_cold_start_latest_ai_pool.py`
  - `run_qmt_roll_stage217_stage78_30w_execution_slippage_mc_suite.py`
  - `run_qmt_roll_stage218_stage78_30w_multiperiod_equity_curves.py`
- 修改数据缺口检查：
  - `build_qmt_roll_stage170_forward_data_gap_check.py` 从旧`30w`产物路径切到`50w`产物路径。
- 修改正式配置：
  - `qmt_roll_official_stage78_config.py` 新增 `OFFICIAL_STAGE78_CAPITAL_LABEL="50w"` 和 `OFFICIAL_STAGE78_CAPITAL_POLICY`。
- 修改记录入口：
  - `research/lines/futures_trend/STAGE78_1.md`
  - `research/lines/futures_trend/LINE.md`
  - `research/registry.md`

## 参数变化

- 新增参数：无交易参数新增；仅新增部署说明常量 `OFFICIAL_STAGE78_CAPITAL_POLICY`。
- 修改参数：无交易参数修改；`OFFICIAL_STAGE78_CAPITAL` 仍为 `500,000`。
- 删除参数：无。

## 回测/复验结果

- 本阶段未跑新回测。
- 原因：本阶段只治理入口命名和执行防误读，不改变 Stage78-1 策略、资金、AI池、风控或成交假设。
- 静态复验：
  - 活跃代码中不再 import 旧`30w` Stage78入口。
  - canonical Stage78-1入口已通过 `py_compile`。
  - 旧 `build_qmt_roll_stage168_30w_qmt_shadow_startup_pack.py` 直接运行时已明确阻断，并提示改用Stage78-1/50万入口。
- 现有 Stage78-1 参考指标保持：
  - 期末权益：`25,542,885`
  - 总收益：`5,008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：待专项复跑确认

## 过拟合反思

- 运行前判断：否。去掉30万可运行入口不是为了优化历史收益，而是消除部署口径误读。
- 运行后判断：否。没有按收益结果选择资金参数；当前仍固定为已确认的78-1/50万口径。

## 继续价值反思

- 运行前判断：有价值。资金口径混乱会直接污染影子盘、SimNow和实盘手数。
- 运行后判断：有价值。后续 agent 即使搜到旧`30w`文件，运行时也会被明确阻断，并被引导到 Stage78-1 canonical 入口。

## TODO

- 后续若真实账户不是50万，必须新增独立部署变体，不得临时修改78-1。
