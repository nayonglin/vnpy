# Stage303 executable critical path board

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 03:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读关键路径审计；汇总 Stage561/583/587/588/591/595/601/602 输出，把 Stage526 实盘无偏差、P0 外生源、扩池风险槽三个方向放到同一张 gate board 中排序；不做收益回放、不改策略、不调用交易接口。
- 是否重要突破：否，但它把下一步优先级从“继续扩池/继续找品种”改为“先闭合执行无偏差证据”。
- 是否触发A/B：否。`promotion_allowed=false`、`paper_selector_allowed=false`、`trading_whitelist_allowed=false`、`zero_bias_claim_allowed=false`。

## 外部调研与判断

- 参考资料：
  - CFA Institute `Trading Costs and Electronic Markets`：TCA 应覆盖 VWAP、implementation shortfall 等执行质量度量。
  - pfolio look-ahead bias 资料：基本面/替代数据必须有 point-in-time 时间戳，不能用事后可得数据回填决策点。
  - Freqtrade lookahead-analysis：需要专门做时间泄漏检测，而不是只相信回测代码形态。
  - Man Group trend following market mix：趋势跟踪扩市场有效，但有效的是独立风险来源，不是重复相关暴露。
- 我的判断：
  - 当前目标的第一阻塞不是策略收益，也不是继续扩池，而是实盘执行证据。没有 `bridge_signal_id -> vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 闭环，就不能声明“真实交易不存在偏差”。
  - 基本面/舆情数据仍有研究价值，但必须先变成 forward-only ledger：`received_at/source_url/published_at/raw_hash/product_map`，否则会把历史可得性误读成实盘可执行。
  - 扩池方向仍成立，但 Stage302 已证明非DCE新槽当前为0；DCE `j/i` 即使解决 source 也只是从4槽到5槽，不能优先于执行无偏差。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage603_executable_critical_path_board.py`
- 修改脚本：无策略脚本修改；仅本审计脚本内修正图表 heatmap 语义和引用链接。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage603_executable_critical_path_board_v1`
  - gate board 按 `candidate_return_risk / execution_no_bias / external_selector / official_monitor / new_risk_slots` 五类归因
  - task priority 按 impact/effort/直接目标相关性排序
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做新回测；读取冻结输出。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：只读 Stage561/583/587/588/591/595/601/602 的决策表、闸门表、P0证据表、TCA缺口表。
- 策略/归因口径：可执行关键路径，不生成收益候选、不做 selector IC、不做 paper sleeve。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`execution_no_bias_first_source_selector_second_no_promotion`
  - blocked gates：`10`
  - critical blockers：`3`
  - Stage526 candidate boundary：`100%`
  - OrderRequest dry-run contract：`100%`
  - fresh live context：`0/45`
  - real vt_orderid mappings：`0`
  - P0 TCA valid samples：`0/9`
  - P0 products with >=2 routes：`3/5`
  - P0 products with event coverage：`2/5`
  - forward dates：`2/20`
  - official auto monitor for v/ao/lu：`0/3`
  - deployable non-DCE new slots：`0`

## 关键路径排序

1. `close_execution_no_bias_loop`
   - 证据：`vt_orderid missing 3`、live context missing fields `45`、P0 TCA remaining `9`。
   - 原因：这是目标“真实交易不存在偏差”的直接证明链。没有它，任何回测收益/扩池结论都不能最终关账。
   - 允许下一步：只做 dry-run/live-context plumbing 和 mapped evidence collection，不做交易白名单。
2. `freeze_yc_tiebreak_and_p0_event_ledgers`
   - 证据：event missing products `3`、route missing products `2`、forward dates `2/20`。
   - 原因：把 P0 从 hindsight 产品证据转成 forward-auditable selector 证据。
   - 允许下一步：只写 `received_at/source_url/raw_hash` ledger，不做历史 selector replay。
3. `official_monitor_for_v_ao_lu`
   - 证据：官方入口已定位，但 auto monitor ready `0/3`，仍有 WAF/412。
   - 原因：基本面数据只有能自动抓取并精确匹配产品，才可能进入实盘研究。
4. `authorized_dce_or_alternative_source_for_ji`
   - 证据：`j/i` 即使解决也只让有效槽 `4 -> 5`，仍低于目标 `7`。
   - 原因：有价值但不足以单独解决低单槽风险。
5. `non_dce_forward_monitor_only`
   - 证据：Stage302 全57 scout 显示 deployable non-DCE new slots `0`。
   - 原因：只能监控，暂不值得收益回放或扫参。

## 图表视觉复盘

- 图表路径：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_chart_stage603_executable_critical_path_board_v1.png`
- 第一版视觉检查发现 heatmap 中 `tiebreak needed` 和 `corr watch` 用绿色显示，语义容易误读；已改为 `tiebreak ok` / `corr ok` 并缩短 gate 标签。
- 最终图表显示：
  - 左上：策略候选和 OrderRequest contract 为绿；执行无偏差三项 `fresh live context / real vt_orderid map / P0 TCA samples` 全红。
  - 右上：`y/c` 只有 tiebreak 未通过；`v` 缺 event；`ao/lu` 同时缺 route、event、basis，其中 `lu` 还触发 corr watch。
  - 左下：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 三个 P0 hard close-window/roll 事件均为 `0/3` TCA 样本。
  - 右下：impact/effort 图把 `close_execution_no_bias_loop` 排第一，P0外生源排第二，DCE源排第四。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_report_stage603_executable_critical_path_board_v1.md`
- gate board：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_gate_board_stage603_executable_critical_path_board_v1.csv`
- product gaps：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_product_gap_priority_stage603_executable_critical_path_board_v1.csv`
- execution gaps：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_execution_gap_priority_stage603_executable_critical_path_board_v1.csv`
- task priority：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_task_priority_stage603_executable_critical_path_board_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_decision_stage603_executable_critical_path_board_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage603_executable_critical_path_board_chart_stage603_executable_critical_path_board_v1.png`

## 结论

- 本阶段结论：Stage526 仍是正常成本主候选，但当前不应继续把主要精力放在扩池或策略调参；第一优先级是执行无偏差闭环。
- 是否进入下一步：是，但下一步应进入 submit-capable live context / vt_orderid / TCA mapping，而不是 P0/P1 收益回测。
- 下一步：
  - 把 Stage591 submit plan 接入 fresh live context contract，至少补齐 contract/account/position/limit/margin/operator_confirmed 字段。
  - 真实或测试 submit 返回后立即持久化 `vt_orderid`，并用 Stage587 reducer 归并 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK`。
  - 对 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 各补 `3` 个真实可比 live fills 或独立全日分钟证据。
  - P0 外生源只做 forward ledger；`y/c` tie-break 可先冻结，但不得回放 selector 收益。

## 过拟合反思

- 运行前判断：否。关键路径审计不接触策略参数，不用收益结果筛选新候选。
- 运行后判断：否。没有新回测、没有 selector IC、没有交易白名单；只是汇总已有闸门证据。
- 原因：本阶段把“该不该继续做什么”显式绑定到可执行证据，而不是根据历史收益调方向。

## 继续价值反思

- 运行前判断：有价值。上一阶段已经证明扩池暂时无新增槽，需要决定下一步最能推动主目标的工作。
- 运行后判断：有价值且方向更清楚。执行无偏差闭环是主目标的直接 blocker；继续在扩池收益上浅尝会偏离目标。
- 原因：Stage526 的正常成本收益/回撤边界已有，但没有真实订单映射和TCA样本无法证明实盘可复现。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage303 当前状态。
- 是否更新 `research/registry.md`：是，更新本研究线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是关键路径排序，不是正式候选、重大突破或跨线合并。
