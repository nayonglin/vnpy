# Stage166 C9 合成成交时间与历史 base 边界修复

- line_id：`futures_trend_stage819_intraday_rules`
- 时间：2026-07-01 01:29
- 工作模式：day
- 阶段性质：当前重建版逻辑审计与工程修复；不调参、不连接 CTP、不调用下单 API。
- 外部调研：本阶段按用户约束不继续外部搜索；仅基于本地 `memory.md/back_log.md` 历史脉络、Stage160 健康检查、Stage847/Stage901 代码与输出做审计。

## 本次发现

1. `Stage847StopRetryEngine._fill_synthetic_intraday_close` 之前会把 C9 close/open/close 合成成交的 `TradeData.datetime` 写成日线引擎 `self.datetime`，虽然 `trade_usage_rows.proxy_first_time/proxy_last_time` 保存了分钟触发时间。这对日级 PnL 不是 P0，但对 TCA、实盘对齐和排错是语义风险。
2. 当前 live profile 已切到 `stage847_c9_15w_stage819_05r_stop_retry_live` 后，独立运行 Stage847 历史回测会沿 Stage746/660 调用链读取当前 live profile，导致 `official spec/base profile not found`。这是执行边界 bug，不是策略参数问题。
3. 初版时间修复把事件时间统一转成 naive datetime，完整 Stage847 暴露出和 vn.py 原始成交的 timezone-aware datetime 混用排序错误；最终改为继承引擎 fallback 时区。

## 代码变更

- 新增测试：`tests/test_qmt_entry_context_diagnostics.py`
  - C9 合成成交必须使用事件时间，并保持 fallback 时区一致。
  - Stage847 profile 必须显式固定 legacy Stage372/Stage819 base。
  - Stage901 不再直接 patch Stage660 live 全局。
- 修改 `analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py`
  - 增加 `_stage847_synthetic_trade_datetime()`：优先使用 `synthetic_trades[].time`，并与 `self.datetime` 保持相同时区类型。
  - C9 合成成交的 `TradeData.datetime` 与 `fill_date` 改为使用 `trade_datetime`。
  - 增加 `_stage847_stage372_legacy_official_context()`，让 Stage847 自己固定历史 Stage372 base profile，避免被当前 live config 污染。
- 修改 `analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
  - 移除 `_run_live_c9()` 内对 Stage660 `OFFICIAL_LIVE_*` 全局变量的直接 patch/restore。
- 修改 `analyze_qmt_roll_stage160_current_live_logic_healthcheck.py`
  - `c9_synthetic_trade_datetime_semantics` 变为 PASS。
  - `stage901_global_state_restore` 改为验证 Stage901 不直接 patch Stage660，且 Stage847 固定 legacy base。

## 验证结果

- `.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics tests.test_official_live_config_import`
  - 7 tests OK。
- `.py311/bin/python -m py_compile ...`
  - 通过。
- 完整 Stage847：
  - 成功跑完。
  - C9 结果与修复前记录一致：期末权益 `18,707,245.1`，总收益 `6,135.748%`，最大回撤 `-64.5503%`，Sharpe `1.245105`，总滑点 `2,567,940`，总交易次数 `793`，胜率 `52.8109%`。
  - stop/retry 事件 `60`，其中 no_reentry `37`、open_after_reentry `11`、retry_failed `12`。
  - 结论仍是 `stage847_c9_not_promoted_stop_retry_fullpath_failed`；本次修复没有把 C9 回测调好，只修执行语义与入口边界。
- Stage162 预影子门：
  - `11 PASS / 0 WARN`，gate_status=`pass`。
- Stage901 当前只读影子：
  - analysis_end=`2026-06-30`
  - latest_available_data_date=`2026-06-30`
  - target_signal_count=`0`
  - pending_order_count=`0`
  - current_position_count=`1`
  - order_api_called=`false`
  - send_order_api_called_count=`0`
  - cancel_order_api_called_count=`0`

## 过拟合反思

否。本阶段没有新增 alpha 参数、没有筛选品种、没有扫 R 倍数/窗口/年份；只修复合成成交日志时间语义和历史 profile 构造边界。

## 继续价值反思

是。Stage160 已无 P0/P1/P2 WARN，说明当前版本更适合作为继续审计和后续多周期回测的稳定基线。下一步更有价值的是继续沿历史有效版本链做归因和局部 bug 审计，而不是继续试图 1:1 找回已删除中间产物。

## TODO

- 若继续优化，不要在 C9 上扫参数；历史完整回测已经显示 C9 单独恶化 C4。
- 继续 review AI 池 fail-open 语义、分钟数据缺失覆盖率、以及实盘止损 ledger 与 shadow position alignment 的可审计性。
