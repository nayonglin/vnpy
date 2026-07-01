# Stage160 当前 live 逻辑 healthcheck

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读源码/输出审计；不重跑策略、不连接 CTP、不调用订单 API
- 是否重要突破：否；但完成了当前重建版 C9 live 关键路径的结构化 bug review
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：按用户约束不再搜索外部资料；只使用本地源码、Stage157/Stage901 输出和当前 live config。
- 我的判断：Stage159 已反证简单日级账户层代理，继续优化不能靠扫阈值。当前更重要的是确认重建后的正式 C9 是否存在执行语义 bug。Stage160 结果显示未发现 P0/P1 策略逻辑 bug，但有 3 个 P2 工程脆弱点需要纳入后续 healthcheck gate。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage160_current_live_logic_healthcheck.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增回测；读取已有 Stage157 stop/retry events、Stage830/847/901 entry candidates 与 trade events、Stage901 decision
- 账户规模：当前 live config `150,000`
- 成本口径：不适用
- 样本过滤：只读当前 live C9 关键路径
- 策略/归因口径：
  - live config/override 一致性
  - AI PIT 源码语义
  - Stage830 broker10 cap 覆盖范围
  - Stage847 C9 stop/retry 事件状态机
  - Stage901 global state restore 与 order API 声明

## 结果

- 期末权益：不新增回测
- 总收益：不新增回测
- 最大回撤：不新增回测
- Sharpe：不新增回测
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - healthcheck 总数：`11`
  - PASS：`8`
  - WARN：`3`
  - FAIL：`0`
  - 决策：`stage160_no_p0_p1_logic_bug_found_with_p2_warnings`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage160_current_live_logic_healthcheck_report_stage160_current_live_logic_healthcheck_v1.md`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage160_current_live_logic_healthcheck_checks_stage160_current_live_logic_healthcheck_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage160_current_live_logic_healthcheck_decision_stage160_current_live_logic_healthcheck_v1.json`

## 结论

- 本阶段结论：
  - 未发现 P0/P1 逻辑 bug：当前 live config 指向 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，不是 Stage372/Stage78/30w；override 资金为 `150000/150000`；C9 核心开关、`0.5R`、重试一次、AI 过滤均开启。
  - AI 池文件存在，当前策略名 `ai_top8_plus_fu_satellite_post_signal_entry_filter` 有 `477` 行，`52` 个 eval_date，区间 `2019-12-31` 至 `2026-05-29`；PIT 源码使用 `searchsorted(..., side="left") - 1`，eval_date 当天仍用上一期快照，防止同日泄漏。
  - Stage157 stop/retry 事件状态字段一致：`171` 个事件，`max_retries=1`，`flat_no_reentry=77`、`open_after_reentry=58`、`flat_retry_failed=36`，状态机无异常。
  - Stage901 最新 decision 声明 `order_api_called=false`、`send/cancel=0`、`target_signal_count=0`、`pending_order_count=0`；仍需保留“pending_orders 也要看”的纪律，不能只看 signal_plan。
- P2 工程警告：
  - `broker10_cap_flat_entry_scope`：Stage830 broker10 cap 只处理 `flat_entry`。现有 Stage830/847/901 输出没有 `reverse_entry` 或 reverse trade event，所以不是已复现 bug；但如果未来 reverse entry 触发，可能绕过 broker10 cap。
  - `c9_synthetic_trade_datetime_semantics`：C9 合成成交使用 `datetime=self.datetime`，同时记录 `proxy_*` 分钟触发时间。对日级 PnL 不是 P0，但对 TCA/实盘对齐是语义风险。
  - `stage901_global_state_restore`：Stage901 有 finally 恢复 Stage660 全局状态保护；不是当前 bug，但依赖临时修改全局状态，工程边界脆弱。
- 是否进入下一步：是
- 下一步：
  - 不继续扫参数。
  - 应把 Stage160 healthcheck 接成固定只读 gate，至少在每日 shadow 或临时信号检查前跑一次，防止 live profile、AI 池、order API、pending_orders、entry_context 覆盖范围漂移。
  - 若要修代码，优先补 `reverse_entry` broker10 cap 覆盖的 targeted test/guard，以及 C9 合成成交分钟时间语义的 TCA 输出，不动 alpha。

## 过拟合反思

- 运行前判断：否。该阶段检查代码语义和执行输出，不改策略参数。
- 运行后判断：否。输出是 bug/warn 清单，不产生 alpha 参数或过滤规则。
- 原因：这类 review 是工程正确性约束，不基于收益曲线拟合。

## 继续价值反思

- 运行前判断：是。Stage159 已反证简单权益代理，继续价值在找真实执行差错风险。
- 运行后判断：是。当前没有 P0/P1 逻辑 bug，但 P2 工程脆弱点值得转化为固定 healthcheck gate。
- 原因：当前重建版不应靠回看调参继续优化；更高价值是把正式路径的执行语义固定住，避免后续实盘因为 profile、AI 池、pending_orders、reverse path 或全局状态漂移出错。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等待 healthcheck gate 是否接入后整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；若接入固定 gate 或修复 P2 风险，再追加重要摘要
