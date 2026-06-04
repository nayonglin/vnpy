# Stage360：Stage653 切换为官方实盘默认版本

- 时间：2026-06-04 20:36 CST
- 工作模式：day
- line_id：`futures_trend_drawdown30_preserve_return`
- 性质：正式口径切换 / 实盘默认配置切换
- 新官方实盘版本：`official_live_stage653_20w_force95_to80`
- 策略体：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`
- 初始资金：`200,000`
- order API：`0`

## 调研和判断结论

- 本地判断：用户明确要求把官方改成 Stage653/20万候选，因此当前实盘、虚拟盘、Phase B 草案、每日执行闸门的默认 signal source 应切到 Stage653；Stage78-1 50万只保留为历史/研究对照。
- 外部参考：vn.py/VeighNa 的实盘工程应通过 gateway、OrderRequest、账户/持仓查询和前置风控，不应让回测脚本直接发单。因此本次只切换官方实盘配置与输入源，不取消 fresh read-only、dry-run、人工确认、TCA/残余持仓检查。
- 反过拟合判断：否。此阶段是部署口径切换，不调收益参数，不根据结果扫阈值。
- 继续价值判断：是。否则后续“有没有信号”“跑虚拟盘”“实盘前检查”会继续误读 Stage78/50万。

## 代码与配置变更

- 新增 `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - 定义 `OFFICIAL_LIVE_VERSION=official_live_stage653_20w_force95_to80`
  - 定义 `OFFICIAL_LIVE_CAPITAL=200000`
  - 固定 Stage653 signal plan、current positions、report、AI eligibility 路径
  - 明确 `must_not_fallback_to_stage78_for_live=True`
- 修改 `examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py`
  - 新增标准 `signal_plan` 输出
  - 新增 `trade_usage` 输出
  - `target_signal_count` 写入 decision
- 修改 `examples/portfolio_backtesting/build_qmt_roll_stage242_phaseb_order_draft.py`
  - Phase B 委托草案默认读取 Stage653 official live summary/signal_plan
  - 空 signal_plan 正常生成空草案，不回落到 Stage78
  - 部署状态改为 Stage653 自身权益口径，不再引用 Stage238/Stage78 50万 tranche 状态
- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - 每日执行闸门默认读取 Stage653 official live signal_plan
  - 输出前缀切到 `qmt_roll_stage260_official_live_daily_execution_gate`
- 修改 `AGENTS.md` 与 `skills/futures-live-execution-sop/SKILL.md`
  - 当前实盘/虚拟盘默认口径从 Stage78-1 50万改为 Stage653 20万
  - Stage78-1 50万降为历史/研究对照
- 更新 `research/registry.md`、`research/lines/futures_trend/LINE.md`、`research/lines/futures_trend_drawdown30_preserve_return/LINE.md`

## 验证结果

- 语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_official_live_config.py examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py examples/portfolio_backtesting/build_qmt_roll_stage242_phaseb_order_draft.py examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - 结果：通过
- 重跑 Stage659：
  - 命令：`.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py --target-date 2026-06-04`
  - 期末权益：`201,140`
  - 总收益：`0.5700%`
  - 年化收益率：`1.3936%`
  - 最大回撤：`-14.5394%`
  - Sharpe：`0.1943`
  - 总滑点：`1,250`
  - 总交易次数：`18`
  - 胜率：`44.0000%`
  - broker10 保证金峰值：`55.1058%`
  - 强制减仓：`0次/0手`
  - 当前信号数：`0`
- Phase B 草案：
  - 命令：`.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage242_phaseb_order_draft.py --trade-date 2026-06-04`
  - 草案数：`0`
  - 行为：空信号正常生成空草案，不回落到 Stage78
- 每日执行闸门：
  - 命令：`.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py --max-snapshot-age-seconds 300`
  - official live version：`official_live_stage653_20w_force95_to80`
  - signal_count：`0`
  - executable_count：`0`
  - order API：`0`
  - readonly gate：旧快照过期且未通过，但因无信号，不进入提交流程

## 输出文件

- official live 配置：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
- Stage653 signal plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow_signal_plan_stage659_stage653_2026_ytd_latest_ai_shadow_v1.csv`
- Stage653 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow_decision_stage659_stage653_2026_ytd_latest_ai_shadow_v1.json`
- Phase B 空草案：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage242_phaseb_order_draft_draft_20260604_stage242_phaseb_order_draft_v1.csv`
- official live daily gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_official_live_daily_execution_gate_summary_20260604_stage260_official_live_daily_execution_gate_v1.json`

## 结论

- 当前官方实盘默认版本已经切到 Stage653/20万。
- 后续涉及实盘的默认设计、信号草案、每日执行闸门，不再读取 Stage78/50万信号。
- 真实 submit 仍必须 fail-closed 通过 fresh read-only、dry-run、人工确认、1手/实盘提交前闸门、TCA/残余持仓检查。

## 后续规划和 TODO

- 下一交易日收盘后先补数据和 AI 池状态，再跑 Stage659。
- 若 Stage653 `signal_plan` 非空，才进入 Phase B 草案和 fresh broker gate。
- 若券商前置可达，先跑 fresh read-only；如需测试单，仍只允许显式确认后的 1 手测试。
