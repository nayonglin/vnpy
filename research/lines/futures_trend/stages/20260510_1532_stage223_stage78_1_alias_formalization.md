# Stage223 固化Stage78-1正式别名

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 15:32
- 阶段性质：版本治理/入口固化
- 是否重要突破：是
- 是否触发A/B：否，本阶段不改变策略逻辑，只固化命名和入口

## 调研与判断

- 外部调研结论：可复现实验与生产策略应把配置、版本名、入口和产物路径显式绑定，避免依赖“最新版”口头约定。
- 我的判断：当前第78家族已有20万、30万、30万无封顶、50万无封顶等历史口径，如果继续只说“78版本”，新agent容易误读。因此需要把当前正式口径固化为短别名`78-1`。

## 版本定义

- 短别名：`78-1`
- 官方版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 策略家族：`official_stage78_defensive_v1`
- 口径：
  - 初始资金：`500,000`
  - sizing资金封顶：`0.0`
  - AI选品：开启
  - FU卫星规则：开启
  - 新开空门禁：只允许`short_case1a`

## 本次代码变更

- 修改：
  - `examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
  - `research/lines/futures_trend/LINE.md`
  - `memory.md`
- 新增：
  - `examples/portfolio_backtesting/run_qmt_roll_official_stage78_1.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage78_1_shadow_daily_runner.py`
  - `research/lines/futures_trend/STAGE78_1.md`
- 新增参数/常量：
  - `OFFICIAL_STAGE78_FAMILY_VERSION = "official_stage78_defensive_v1"`
  - `OFFICIAL_STAGE78_VERSION = "official_stage78_1_defensive_50w_no_sizing_cap"`
  - `OFFICIAL_STAGE78_SHORT_ALIAS = "78-1"`
- 修改参数：
  - `OFFICIAL_STAGE78_PROFILE_NAME` 改为带`stage78_1`与`50w_no_sizing_cap`语义的名称
- 删除参数：无

## 新Agent使用约定

- 用户说“回测78-1”：运行 `examples/portfolio_backtesting/run_qmt_roll_official_stage78_1.py`
- 用户说“用78-1做影子盘”：运行 `examples/portfolio_backtesting/build_qmt_roll_stage78_1_shadow_daily_runner.py`
- 用户说“最新第78正式基准”：默认等同于`78-1`
- 用户只说“78版本”且上下文不清：应追问是否指`78-1`

## 回测结果

- 本阶段不跑新回测。
- 沿用Stage220/Stage222写入的50万无封顶参考指标：
  - 全样本期末权益：`25,542,885`
  - 总收益：`5,008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`

## 过拟合反思

- 运行前判断：否。命名固化不改变策略参数和交易逻辑。
- 运行后判断：否。只是把当前正式口径变成可复现入口，降低误跑风险。

## 继续价值反思

- 运行前判断：有价值。版本别名能减少新agent因历史口径混乱导致的错误。
- 运行后判断：有价值。后续用户只需说`78-1`即可定位当前正式基准。

## TODO

- 用`78-1`入口重跑主回测，生成正式`qmt_roll_official_stage78_1_summary`产物。
- 用`78-1`口径重跑三件套和多周期曲线，替换Stage220临时反事实报告为正式报告。
