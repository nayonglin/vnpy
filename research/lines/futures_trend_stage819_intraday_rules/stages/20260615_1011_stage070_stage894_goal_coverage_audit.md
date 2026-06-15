# Stage070 - Stage894 目标覆盖与剩余路线审计

- 时间：2026-06-15 10:11 CST
- 当前模式：day
- line_id：`futures_trend_stage819_intraday_rules`
- model_tag：`stage894_stage893_goal_coverage_audit_v1`
- 源候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 阶段性质：只读目标覆盖和路线收束审计；不新增交易规则、不跑回测、不接真实组合引擎、不改 Stage372 官方正式版、不改官方候选配置、不连接 CTP、不调用下单、不下载数据、不触发 A/B。
- 是否重要突破：否。它不是 alpha 突破，而是把当前研究目标的完成度、证据缺口和后续路线边界整理清楚。

## 外部调研和判断

- 参考资料：交易所/order type 资料继续支持日内规则必须能以 stop / stop-limit 等真实委托语义执行，而不是事后 K 线退出；历史趋势/技术规则研究也提示小参数技术规则容易样本化。
- 我的判断：当前不能继续用 `first60/OR/R/OI/volume/session` 小变体“挤规则”。Stage894 的正确动作不是再写一个入场/出场补丁，而是把已有证据做目标覆盖审计：哪些已经证明，哪些没有证明，哪些必须先补数据。

## 本次版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage894_stage893_goal_coverage_audit.py`
- 新增记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260615_1011_stage070_stage894_goal_coverage_audit.md`
- 新增只读输出：
  - 目标要求矩阵
  - 分支路线 disposition
  - 下一路线边界表
  - summary chart
  - report
  - decision JSON
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。
- 官方正式版 Stage372：未修改。
- 官方候选配置：未修改。

## 数据与输出

- 输入：Stage861 decision、Stage891 route matrix / scorecard / visual index / decision、Stage893 decision。
- 目标要求行数：`8`
- 未满足或仍开放要求：`3`
- 分支路线行数：`13`
- K 线视觉 PNG 页数：`95`
- Stage861 entry-day 覆盖率：`1.0`
- Stage893 combined local meets20 pct：`4.013377926421405%`
- summary chart 尺寸：`2340x900`
- 输出：
  - report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_report_stage894_stage893_goal_coverage_audit_v1.md`
  - requirements：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_requirements_stage894_stage893_goal_coverage_audit_v1.csv`
  - route disposition：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_route_disposition_stage894_stage893_goal_coverage_audit_v1.csv`
  - next routes：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_next_routes_stage894_stage893_goal_coverage_audit_v1.csv`
  - summary chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_summary_chart_stage894_stage893_goal_coverage_audit_v1.png`
  - decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage894_stage893_goal_coverage_audit_decision_stage894_stage893_goal_coverage_audit_v1.json`

## 新增回测/代理结果

本阶段不新增真实回测，也不新增交易代理。以下是目标覆盖审计结果：

- `R1_new_isolated_line`：`proven`。Stage819 官方候选独立研究线已建立，Stage372 和官方候选配置隔离。
- `R2_full_cycle_trade_data`：`proven`。Stage861 entry-day 覆盖 `341/341`，pressure key dates `19/19`。
- `R3_kline_visual_analysis`：`proven`。Stage891 统计 `10` 组 visual manifest、`95` 页 PNG。
- `R4_realtime_stop_and_retry`：`tested_not_promoted`。C9 已真实测试 `0.5R stop + reclaim retry once`，相对 C4 多赚 `4.6213m`，但 max broker10 `114.3987%`，不是可推广正式替代。
- `R5_rule_based_non_ai`：`proven`。Stage843-893 都是规则类路径，不拟合 ML/AI 模型。
- `R6_promotable_minute_improvement`：`not_proven`。没有新增分钟规则同时满足收益、回撤、Sharpe、broker10 和稳健性。
- `R7_external_market_breadth`：`data_missing`。Stage893 combined local symbols 达到 `20` 合约的 entry_date 只有 `12/299`。
- `R8_goal_completion`：`keep_active`。当前不能声明 goal 完成；已有完整法证，但没有可推广新规则，且市场广度仍需数据前置。

本阶段未跑真实回测，因此以下指标不适用：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率。

## 视觉检查

- summary chart 左图显示目标要求状态：`proven` 为 `4` 条，另有 `tested_not_promoted`、`not_proven`、`data_missing`、`keep_active`。
- 右图显示路线 disposition：`proxy_rejected` 最多，`true_engine_failed` 有 `3` 条，另有 `data_prerequisite_missing`、`branch_closed`、`knowledge_asset_not_promoted`。
- 图像正常，能直观看出“证据覆盖完整”和“无可推广规则”是两件不同的事。

## 决策

- decision：`stage894_goal_coverage_audit_no_promotable_minute_rule_keep_goal_active`
- goal_completion_claimed：`False`
- promotable_minute_rule_found：`False`
- market_panel_available：`False`
- 操作：不标记目标完成、不接真实引擎、不触发 A/B、不改官方正式版、不改官方候选配置。

## 反过拟合反思

- 运行前：否。Stage894 不新增规则、不扫参数，只用既有 evidence 做覆盖审计。
- 运行后：否。结论明确反对继续小变体救参；如果继续在 `first60/OR/R/OI/volume/session` 上微调，或者降低市场广度合约数要求，才是过拟合。

## 继续价值反思

- 运行前：有价值。目标已经推进很深，必须把“证据已覆盖”和“可推广规则未找到”拆清楚，避免继续无效搜索。
- 运行后：继续当前分钟 K 小变体没有价值；只有两条路线仍可能有价值：
  - 高对齐路线：先建全市场连续分钟面板，再研究市场广度。
  - 中等对齐路线：转账户级非交易层生存线，但这已经不是分钟 K 入场/出场 alpha。

## 后续规划和 TODO

- 不继续 `first60/OR/R/OI/volume/session` 小变体。
- 不降低市场广度 `20` 合约覆盖要求。
- 若继续市场广度，必须先解决数据：universe、主力/连续映射、夜盘归属、下载权限、entry_date 覆盖。
- 若不补数据，建议单独转账户级资金分层/出金锁盈/最大风险预算研究线，明确它不是本线分钟 K alpha。
- 本阶段不是正式候选、不是重要突破，不更新 `registry.md`、不追加根目录 `memory.md` / `back_log.md`。
