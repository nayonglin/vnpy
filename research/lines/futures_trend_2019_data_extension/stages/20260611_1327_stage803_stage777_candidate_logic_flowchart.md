# 2026-06-11 13:27 Stage803 / Stage777 官方候选版完整交易逻辑流程图

## 基本信息

- line_id：`futures_trend_2019_data_extension`
- 当前工作模式：`day`
- 阶段类型：候选版逻辑文档化，不新增回测，不修改策略代码
- 目标版本：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`
- 别名：`Stage777-50w-AM41-OI0.8-oldAI`
- 当前状态：官方候选，高收益高回撤；当前实盘默认仍是 `official_live_stage372_20w_recovery_sleeve`

## 本次产出

- 新增流程图：
  - `examples/portfolio_backtesting/backtest_outputs/stage803_stage777_candidate_full_logic_flowchart.png`
  - `examples/portfolio_backtesting/backtest_outputs/stage803_stage777_candidate_full_logic_flowchart_cropped.png`
  - `examples/portfolio_backtesting/backtest_outputs/stage803_stage777_candidate_full_logic_flowchart_compact_v2.png`

## 依据文件

- `examples/portfolio_backtesting/qmt_roll_official_candidate_stage777_config.py`
- `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage777_am41_oi08_monthly.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage772_am40_80_120_oi_monthly.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage748_half_risk_no_streak_500k.py`
- `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage324_true_combo_capital_margin.py`
- `examples/portfolio_backtesting/analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage.py`

## 核对后的候选口径

- 初始资金：`500,000`
- 产品池：`static18 + fu`，共 `19` 个品种
- AI：`ai_top8_plus_fu_satellite_post_signal_entry_filter`
- AM：`research_exact_array_manager_size=41`，`array_manager_size_floor=40`
- 最大持仓品种数：`4`
- 基础风险：`0.045 * 0.40 = 0.018`
- 连败缩放：`streak_risk_multipliers=1.0,1.0,1.0,1.0`，即关闭连败缩仓
- recovery sleeve：关闭
- OI price confirm：开启，`flat_entry,reverse_entry,rollover_reopen` 生效，`multiplier=2.0`
- 供需逆风过滤：开启，`external_quality_score <= -0.35` 时 `weight=0`
- 同方向相关性门控：开启，20日相关性，`0.60 -> 0.80`，权重下限 `0.35`
- pairwise v2：开启；catastrophic veto 关闭；long volume tilt `0.15`
- 风险簇上限：开启，identity map 口径，接近单品种保证金上限 `25%`
- 强制保证金减仓：开启，broker multiplier `1.65`，`95% -> 80%`，largest margin 优先

## 重要发现

代码真实逻辑里，`risk_ratio_open_interest_surge=0.06` 和 `risk_ratio_volume_open_interest_surge=0.06` 来自 `build_roll_setting` 默认值，没有随 Stage777 的 `0.40` 基础风险倍率缩放；如果同一笔交易还命中 `OI price confirm`，还会再乘 `2.0`。因此常规交易命中 OI confirm 是 `0.018 * 2 = 0.036`，等效正式风险 `0.80`；但 OI surge 类交易理论上会到 `0.06 * 2 = 0.12` 的 limited balance 风险预算。

这不一定是错误，但和我们口头简称“命中 OI 恢复到 0.8”不完全等价。后续如果要工程化候选版，建议单独做有效 setting 冻结清单、单笔风险上限审计、OI surge 实际触发样本复盘。

## 反思

- 是否过拟合：否。本阶段没有调参、没有回看收益改规则，只是把当前候选代码路径画成流程图。主要风险是文档误读，因此明确区分了生效模块与关闭模块。
- 是否值得继续：是。候选版已经包含 AI、OI、供需、相关性、pairwise、风险簇、强制保证金多个层级；先把完整流程固定下来，后续才能做可靠审计和工程化。

