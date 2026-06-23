# Stage114 - Stage929 手数归因补充与 rb 11手解释

- 时间：2026-06-22 20:14 CST。
- line_id：`futures_trend_stage819_intraday_rules`。
- 工作模式：day。
- 是否重要突破：否，属于实盘报告可解释性补强，不改变策略信号、参数、CTP连接或下单闸门。

## 背景

用户看到邮件中 rb 止损距离只有 6 点，但计划手数只有 11 手，询问是否命中了单品种最大保证金占用风控。

复核 Stage901 C9/15w live shadow 的 rb2610.SHFE entry_risk：

- 止损距离：6。
- 合约乘数：10。
- 单手风险：60。
- 目标风险金额：4,860。
- 风险上限手数：81。
- 策略保证金上限手数：43。
- 单笔资金上限手数：33。
- 最终手数：11。

进一步检查最终 live setting：

- `enable_risk_cluster_margin_cap=True`。
- `risk_cluster_margin_cap_ratio=0.25`。
- `risk_cluster_map` 中 `rb.SHFE=rb.SHFE`，因此 rb 自身就是一个 risk cluster。
- 15万权益下品种/集群 cap 金额为 37,500。
- rb 策略每手保证金为 3,127。
- `floor(37,500 / 3,127) = 11`，第 12 手约为 37,524，会超过 25% cap。

结论：rb 11 手不是由止损距离、总保证金 90% cap、单笔资金 70% cap、Stage830 broker10 cap、增量保证金闸门或相关性/AI/cooldown 缩手导致，而是命中了策略内 `risk_cluster_margin_cap`，在当前映射下等价于单品种/单风险集群 25% 保证金占用上限。

## 代码改动

- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - 在 entry_candidates 与 entry_risk 导出中新增 `risk_cluster_cap_enabled`、`risk_cluster_name`、`risk_cluster_cap_ratio`、`risk_cluster_cap_amount`、`risk_cluster_reserved_margin_before`、`risk_cluster_max_volume`、`risk_cluster_selected_volume_before`、`risk_cluster_selected_volume`。
  - 同时导出 risk_cluster heat gate 的基础诊断字段，便于后续区分 cluster cap 与 heat gate 缩手。
- `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - 邮件和本地报告的“风险与资金补充”新增品种/集群、品种/集群 cap、cap 金额、上限手数、cap 前手数、cap 后手数。
  - 邮件字段说明补充：品种/集群 cap 是策略内单品种/风险集群保证金上限；券商实际保证金仍以交易软件/CTP 为准。

## 验证

- `py_compile` 通过：
  - `qmt_roll_portfolio_strategy.py`
  - `run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- `git diff --check` 通过。
- 重跑 Stage901 只读 shadow：
  - 命令：`.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py --analysis-start 2026-06-16 --target-date 2026-06-22`
  - 订单 API：0。
  - pending order：`rb2610.SHFE Short Open 11 @ 3126.0`。
  - 新字段落盘：`risk_cluster_cap_enabled=1`，`risk_cluster_name=rb.SHFE`，`risk_cluster_cap_ratio=0.25`，`risk_cluster_cap_amount=37,500`，`risk_cluster_selected_volume_before=33`，`risk_cluster_selected_volume=11`。
- Stage929 dry-run 邮件通过：
  - 命令：`OFFICIAL_LIVE_EMAIL_DRY_RUN=1 .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase manual --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only`
  - 订单 API：0。
  - dry-run 邮件正文确认是普通文本，并包含：
    - `品种/集群：rb.SHFE`
    - `品种/集群cap：25%`
    - `品种/集群cap金额：37,500`
    - `品种/集群上限手数：11`
    - `品种/集群前手数：33`
    - `品种/集群后手数：11`

## 反过拟合判断

否。本阶段没有改信号、品种池、止损、风险倍率或任何交易参数，只补充已有风控链路的诊断字段和邮件展示，属于执行可解释性增强。

## 继续价值判断

是。实盘自动化必须让邮件直接解释“为什么是这个手数”，否则用户容易把止损距离、保证金口径和不同层级风控混在一起。下一步若继续，应把 Stage260/905 的阻断原因也做成同样的归因式普通文本。
