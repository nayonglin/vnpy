# Stage373 Stage372 20万受限恢复仓正式锁版

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-05 02:36 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式实盘版本锁定 / 执行配置切换
- 是否重要突破：是
- 是否触发A/B：是，Stage372 从候选审计切换为当前官方实盘默认版本；Stage653 原版保留为历史对照

## 外部调研与判断

- 参考资料：本阶段未新增联网调研；沿用 Stage370/371/372 多周期审计、Stage359 最新 AI 池影子盘、Stage366-369 真实 CTP 只读与 1 手开平仓闭环证据。
- 我的判断：这不是严格成本闸门突然通过，而是用户基于高收益偏好、since2021/since2022 修复和最新 YTD 改善，明确接受 Stage372 的 2x 成本尾部风险后做出的正式锁版。工程上必须把研究脚本补丁固化为策略 native 参数，并让官方配置成为唯一默认入口。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage660_stage653_multiperiod_live_audit.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage662_stage653_recovery_sleeve_multiperiod.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - `AGENTS.md`
  - `skills/futures-live-execution-sop/SKILL.md`
  - `research/registry.md`
  - `research/lines/futures_trend_drawdown30_preserve_return/LINE.md`
- 删除脚本：无。
- 新增参数：
  - `enable_recovery_sleeve`
  - `recovery_sleeve_base_multiplier_max`
  - `recovery_sleeve_broker_margin_multiplier`
  - `recovery_sleeve_max_single_contract_broker_margin_to_equity`
  - `recovery_sleeve_cooldown_days`
  - `recovery_sleeve_volume`
- 修改参数：
  - 官方版本：`official_live_stage653_20w_force95_to80` -> `official_live_stage372_20w_recovery_sleeve`
  - 官方策略体：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4` -> `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - Stage659 输出前缀：`qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow` -> `qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow`
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage372 固定审计结果；本阶段已重跑 Stage659 最新 AI 池 YTD 至 `2026-06-04`。
- 账户规模：`200,000`
- 成本口径：Stage372 正常成本、2x、3x 成本压力均保留。
- 样本过滤：固定 Stage526/Stage653 基础策略，恢复仓 sleeve 仅允许结构恢复信号 `long_case1a,short_case1a`。
- 策略/归因口径：只在 `risk_multiplier` 触底 `0.1`、组合空仓、同向相关不拥挤、单手 broker10 估算保证金不超过权益 `20%`、20 自然日冷却后允许 `1` 手恢复仓。

## 结果

- 期末权益：`8,728,285`
- 总收益：`4264.1425%`
- 最大回撤：`-38.6713%`
- Sharpe：`1.6279`
- 总滑点：`506,220`
- 总交易次数：`633`
- 胜率：`52.2586%`
- 其他关键指标：
  - broker10 保证金峰值：`79.6015%`
  - 强制减仓：`6` 次 / `299` 手
  - 2x 成本最大回撤：`-40.6555%`
  - 3x 成本最大回撤：`-42.7649%`
  - `since_2021`：`4,642,610 / 2221.3050% / -38.1656%`
  - `since_2022`：`467,710 / 133.8550% / -28.0550%`
  - 最新 AI 池 YTD 至 `2026-06-04`：`222,440 / 11.2200% / -16.3027% / Sharpe 1.0240`
  - Stage659 smoke 目标日信号：`0`
  - Stage659 smoke 影子盘理论持仓：`OI609.CZCE` 多 `3` 手、`jm2609.DCE` 多 `2` 手；实盘执行不得追历史影子仓，必须以真实账户 fresh read-only 持仓为准。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_summary_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_signal_plan_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_daily_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- quality：`py_compile` 通过；Stage659 smoke 输出 `target_signal_count=0`、`order API=0`。

## 结论

- 本阶段结论：Stage372 已锁定为当前官方实盘默认版本 `official_live_stage372_20w_recovery_sleeve`。Stage653 原版只保留为历史/研究对照，不得作为实盘默认 signal source。
- 是否进入下一步：是。
- 下一步：夜盘/每日执行只按 current official live config 生成信号和执行闸门；目标日 `2026-06-04` 当前无理论信号。

## 过拟合反思

- 运行前判断：否，但存在明确尾部成本风险。
- 运行后判断：否。
- 原因：本阶段没有新增 alpha、没有继续调保证金/冷却/恢复倍率小数，而是把已审计规则固化为默认入口。Stage659 smoke 只复验配置路径和最新 AI 池 YTD，不参与调参。风险在于用户选择接受严格成本闸门失败的尾部成本，而不是过拟合收益。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前阶段把“聊天确认”转成可复验的代码、配置和 SOP 状态，且 Stage659 smoke 已确认官方路径可生成 Stage372 YTD 结果和空信号计划；后续价值在真实 TCA、保证金口径和每日影子盘，不在继续调参。

## 合入建议

- 是否更新本线 `LINE.md`：是，已更新。
- 是否更新 `research/registry.md`：是，已更新。
- 是否追加根目录 `memory.md/back_log.md`：是，追加最终摘要。
