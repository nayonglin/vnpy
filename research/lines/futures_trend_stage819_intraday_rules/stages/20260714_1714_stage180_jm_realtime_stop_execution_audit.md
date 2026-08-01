# Stage180 JM 实时止损执行审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：只读执行证据审计；不连接 CTP、不加载实盘 env、不运行报撤单
- 记录时间：`2026-07-14 17:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：对 2026-07-14 JM 实时止损是否触发、报单、成交及重进场状态做事实核验
- 是否重要突破：否；这是已发生实盘事件的审计记录，不是新策略版本
- 是否触发A/B：否；不修改 alpha、阈值、手数、资金或正式配置

## 外部调研与判断

- 参考资料：
  - VeighNa `vnpy_ctp` 官方网关：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>
  - VeighNa `EventEngine`：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>
- 我的判断：vn.py/CTP 的行情、订单和成交均由异步事件推进，不能把单个 summary 或“价格碰线”当成已止损。本次必须同时看到 Stage904 动作来源、Stage931 API 调用、phase-d ledger 成交和后续 broker 持仓四层证据。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增记录：本 Stage180 审计文件。

## 回测/归因参数

- 数据区间：日历时间 `2026-07-14 14:40-15:11 CST`；策略 `target_date=2026-07-13`。
- 账户规模：输出声明为 `Stage847-C9-15w`；本次不读取或披露账户资产。
- 成本口径：不适用；本次核对真实委托与成交回报。
- 样本过滤：`jm2609.DCE`、Stage904/905/930/931、phase-d ledger、Stage174/608 trades/positions。
- 策略/归因口径：原空单 `2手 @ 1245.5`；原始止损 `1258.0`；风险距离 `12.5`；C9 入场日 `0.5R` 止损阈值 `1251.75`。

## 结果

- 期末权益：不适用；未跑回测。
- 总收益：不适用；未跑回测。
- 最大回撤：不适用；未跑回测。
- Sharpe：不适用；未跑回测。
- 总滑点：不适用；未跑回测。
- 总交易次数：本次事件真实平仓成交 `1` 笔、`2` 手；本次审计自身报单/撤单 API `0/0`。
- 胜率：不适用。
- 其他关键指标：
  - Stage930 的 `14:41:21-14:43:37` controller cycle 产出 `stage904_monitor_status=intraday_monitor_close_dry_run`、`close_dry_run_count=1`。
  - 意图来源为 `stage904_c9_intraday_close`，原因为 `stage847_initial_05r_stop_triggered`；不是 Stage901 日线平仓。
  - Stage931 于 `14:43:56` 调用 CTP 买平 `2` 手：计划保护价 `1255.0`，最终依据新 tick 重定价为限价 `1256.5`。
  - `14:43:57` 全部成交于 `1254.0`，`residual_volume=0`，订单标识 `CTP.17_-626460948_1`。
  - phase-d ledger、Stage174 trades、Stage608 trades 三方均记录该成交；后续 Stage174/608 position 显示 `jm2609` 空头 `0` 手。
  - `14:48:59-15:00:58` 始终为 `retry_watch=1、retry_open=0、order_api=0`；没有重进场。15:03 后 fresh tick 不足而 fail-close，15:11 离开盘中监控时段。
  - 16:38 的 Stage905 日线 pending close 因 broker 已 flat 而 blocked，未重复平仓。
  - 时间标签：文件 `target_date=2026-07-13` 是策略信号/入场日；实际止损发生在日历 `2026-07-14 14:43:57`。原开仓回报中的 `2026-07-14 21:02:08` 是 CTP TradingDay 日期拼接，实际对应用户 7 月 13 日夜盘手动开仓。

## 输出文件

- report：`research/lines/futures_trend_stage819_intraday_rules/stages/20260714_1714_stage180_jm_realtime_stop_execution_audit.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260714_085517_stage930_official_live_c9_session_daemon_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_phase_d_execution_ledger.ndjson`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage905_official_live_executor_dry_run_summary_20260714_stage905_official_live_executor_dry_run_v1.json`
- quality：Stage930 event snapshot、command log、ledger、Stage174/608 trades/positions 交叉验证，并由独立 agent 做只读复核；结论一致。

## 结论

- 本阶段结论：`2026-07-14` 确实触发并完成了 JM 的 C9 入场日实时止损。它已越过“价格碰线”和“生成意图”两个层级，真实调用一次下单 API，并以 `1254.0` 买平 `2` 手；之后 broker flat，未重进场。
- 是否进入下一步：是，继续做只读对账和下一交易时段状态检查；不因单次成功直接宣称整条执行链长期稳定。
- 下一步：核对当晚 Stage905/Stage931 是否继续因 broker flat 阻断重复 close；若讨论部署新版可靠性加固，需另行解决 `AGENTS.md` 的 Stage372 20万与当前运行 Stage847-C9 15万口径冲突。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只审计固定阈值下已经发生的执行事件，没有依据结果调整阈值、样本、品种或参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：完整证据链能区分价格碰线、意图、报单、成交和重进场，直接避免对自动风控状态的误判；下一步价值在持续对账，而不是继续静态扩规则。

## 合入建议

- 是否更新本线 `LINE.md`：否；本次只写唯一 Stage 文件，避免同线并行冲突。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；这是单次运行审计，不属于正式候选或跨线突破。
