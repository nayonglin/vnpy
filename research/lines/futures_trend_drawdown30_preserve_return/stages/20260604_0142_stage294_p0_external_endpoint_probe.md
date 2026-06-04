# Stage294 P0 外生 endpoint probe 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 01:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：联网 endpoint probe；不做收益回测，不修改交易策略，不新增交易候选。
- 是否重要突破：否，但把“低单笔风险扩池 + 选对品种”的外生源瓶颈进一步落到可执行 endpoint 层。
- 是否触发A/B：否。`paper_selector_allowed=false`、`trading_whitelist_allowed=false`。

## 外部调研与判断

- 参考资料：
  - `pysystemtrade` 文档强调 instrument weights、diversification multiplier 和 risk target，是扩池趋势组合的基础结构。
  - `Optimal Allocation of Trend Following Strategies` 认为多资产趋势配置需要显式处理资产间相关性，而不是把相关性当成自然消失的噪声。
  - Bloomberg/Barclays diversified trend-following 资料强调更广 universe、分层风险预算、leverage cap，并把 time underwater 作为长期持有体验指标。
  - SHFE 官方页面公开 `仓单日报`、`库存周报`、`氧化铝` 等数据/产品入口。
  - INE 官方页面公开 `低硫燃料油`、`仓单日报`、`库存周报` 等入口。
  - 本地 AKShare `1.18.55` 暴露 `futures_inventory_em`、`futures_spot_price`、`futures_warehouse_receipt_dce`、`futures_shfe_warehouse_receipt`、`futures_stock_shfe_js` 等函数。
- 我的判断：
  - 用户提出“减少单笔风险、扩大品种池、避免高相关、选对品种”的方向仍然成立。
  - 但 Stage294 证明，当前能稳定返回的是第三方 forward 数据，不是官方可审计 endpoint 闭环。
  - 第三方库存/基差可以进入 forward monitor 账本，帮助积累经验，但不能直接晋级为历史 selector 或交易白名单。
  - 选品的真正瓶颈仍是 `v/ao/lu` 的官方事件/仓单/库存 endpoint、发布时间和 raw hash。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage594_p0_external_endpoint_probe.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `P0_PRODUCTS=["y.DCE","c.DCE","v.DCE","ao.SHFE","lu.INE"]`
  - `GAP_PRODUCTS=["v.DCE","ao.SHFE","lu.INE"]`
  - `MISSING_BASIS_SUBSTITUTE_PRODUCTS=["ao.SHFE","lu.INE"]`
  - `MISSING_EVENT_PRODUCTS=["v.DCE","ao.SHFE","lu.INE"]`
  - `SOURCE_TIMEOUT_SECONDS=8`
  - `LOOKBACK_DAYS=6`
  - `MAX_AGE_DAYS_FORWARD=5`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：无新增收益回测；只做 `2026-06-04 01:41 CST` 附近 received_at 的外生源联网探测。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只检查 Stage593 P0 产品：`y.DCE`、`c.DCE`、`v.DCE`、`ao.SHFE`、`lu.INE`。
  - 只把 `received_at` 当下可抓取的 endpoint 记为 forward evidence。
  - 所有 `usable_for_history_selector` 强制保持 `0`。
- 策略/归因口径：
  - 不修改 Stage526、Stage079、78-1 的任何交易逻辑。
  - 不用探测结果回填历史收益。
  - 第三方源只作为 forward monitor 辅助证据，不作为 alpha 闭环。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p0_endpoint_probe_partial_third_party_forward_ready_official_event_blocked`
  - `promotion_allowed=false`
  - `paper_selector_allowed=false`
  - `trading_whitelist_allowed=false`
  - endpoint rows：`20`
  - P0 产品数：`5`
  - hard gates：`5/9`
  - 第三方 forward 产品覆盖：`5/5`
  - 官方 forward 产品覆盖：`0/5`
  - 事件自动 monitor 覆盖：`0/3`
  - history selector ready routes：`0`
  - `v/ao/lu` 东方财富库存均返回 `2026-06-03` 记录：
    - `v.DCE`：库存 `103719`，增减 `-140`
    - `ao.SHFE`：库存 `403425`，增减 `-16810`
    - `lu.INE`：库存 `2000`，增减 `-3000`
  - 生意社基差返回 `v/y/c`，未返回 `ao/lu`。
  - DCE 仓单函数当前返回 `JSONDecodeError`，不能计为 `v/y/c` 官方 endpoint ready。
  - SHFE 仓单函数当前日期返回 `JSONDecodeError`；历史默认函数可返回旧数据但不含 `氧化铝/低硫燃料油`，不能计为 `ao/lu` 官方 endpoint ready。
  - `futures_stock_shfe_js` 当前探测为空，不能作为 `ao/lu` 周库存 monitor。

### Product Readiness

| 产品 | 第三方 forward routes | 官方 forward routes | event monitor | history selector | 角色 |
| --- | ---: | ---: | ---: | ---: | --- |
| `ao.SHFE` | 1 | 0 | 0 | 0 | third-party 库存可看，但官方/事件阻塞 |
| `c.DCE` | 2 | 0 | 0 | 0 | forward monitor 支持；仍需同族 top1-only |
| `lu.INE` | 1 | 0 | 0 | 0 | third-party 库存可看，但官方/事件阻塞 |
| `v.DCE` | 2 | 0 | 0 | 0 | basis+库存可看，但事件阻塞 |
| `y.DCE` | 2 | 0 | 0 | 0 | forward monitor 支持；仍需同族 top1-only |

### Hard Gates

| gate | passed | value | threshold | 说明 |
| --- | ---: | ---: | --- | --- |
| `akshare_required_functions_available` | 1 | 5 | `5/5` | 本地依赖暴露必要函数 |
| `all_p0_have_any_forward_probe` | 1 | 5 | `5/5` | 每个 P0 至少有一个第三方 forward 源 |
| `gap_products_have_any_forward_probe` | 1 | 3 | `3/3` | `v/ao/lu` 均有第三方 forward 源 |
| `ao_lu_have_official_substitute_endpoint` | 0 | 0 | `2/2` | `ao/lu` 官方替代 route 未闭合 |
| `missing_event_products_have_auto_monitor` | 0 | 0 | `3/3` | `v/ao/lu` 事件源仍 catalog-only |
| `all_forward_rows_have_hash` | 1 | 8 | all forward rows | forward 行已写 raw hash |
| `history_selector_disabled` | 1 | 0 | `0` | 禁止回填历史 selector |
| `paper_selector_allowed` | 0 | 0 | true only after official/event/forward-depth gates | 不允许 |
| `trading_whitelist_allowed` | 0 | 0 | true only after paper selector and TCA gates | 不允许 |

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_chart_stage594_p0_external_endpoint_probe_v1.png`
- 左上热力图：
  - `inventory_3p` 对 5 个 P0 全绿，说明第三方库存 forward monitor 有现实可执行性。
  - `basis_3p` 只覆盖 `y/c/v`，`ao/lu` 为红色，说明基差路线不能自然扩展到所有缺口品种。
  - `warehouse_official` 全红，是本阶段最关键阻塞：官方仓单/库存 endpoint 没有实际闭环。
  - `event_official` 对 `v/ao/lu` 是黄色 catalog，不是绿色 forward-ready，说明只是找到了入口或例子，没有自动 monitor。
- 右上产品 readiness：
  - 只有蓝色第三方柱，没有橙色官方柱和绿色事件柱。
  - 视觉上直接说明“能抓到一些数据”和“选品证据可实盘”不是一回事。
- 左下 route status：
  - `inventory_3p` 全部 ok。
  - `warehouse_official` 主要是 error / missing_function。
  - `weekly_stock_3p` 为空，不能作为 `ao/lu` 的周库存替代。
- 右下 hard gates：
  - 通过的只是函数可用、第三方 forward、hash 和 history 禁用。
  - 失败集中在官方替代 endpoint、事件 monitor、paper/trading 晋级。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_report_stage594_p0_external_endpoint_probe_v1.md`
- endpoint matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_endpoint_matrix_stage594_p0_external_endpoint_probe_v1.csv`
- product readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_product_readiness_stage594_p0_external_endpoint_probe_v1.csv`
- function signatures：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_function_signatures_stage594_p0_external_endpoint_probe_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_gates_stage594_p0_external_endpoint_probe_v1.csv`
- next actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_next_actions_stage594_p0_external_endpoint_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_decision_stage594_p0_external_endpoint_probe_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage594_p0_external_endpoint_probe_chart_stage594_p0_external_endpoint_probe_v1.png`

## 结论

- 本阶段结论：`p0_endpoint_probe_partial_third_party_forward_ready_official_event_blocked`
- 是否进入下一步：进入，但只能进入官方 endpoint 冻结和 forward collection，不能进入收益回测、paper selector、P0 交易白名单或 A/B。
- 下一步：
  1. `v.DCE`：冻结 DCE/PVC 精确官方公告/仓单/事件 URL，替代当前 generic homepage。
  2. `ao.SHFE`：绕开当前 AKShare 仓单函数缺口，直接定位 SHFE 氧化铝仓单日报或库存周报的真实数据 endpoint。
  3. `lu.INE`：直接定位 INE 低硫燃料油仓单日报/库存周报 endpoint，不再依赖 SHFE 仓单函数覆盖。
  4. `v/ao/lu`：事件源必须输出 `source_url/published_at/received_at/raw_hash/headline/relevance` 后才算 event-ready。
  5. 累计至少 `20` 个 forward received_at 日期后，才允许做 IC、bucket 或 paper sleeve 审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有使用 realized PnL、没有调产品名单、没有调仓位、没有调整收益目标。
  - 探测失败没有被“解释成通过”，反而继续阻止 paper/trading 晋级。
  - 所有 forward 行保留 `received_at` 和 hash，且 `usable_for_history_selector=0`。
  - 如果后续为了让 `v/ao/lu` 通过而手工挑历史表现更好的日期、产品或事件关键词，才会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但路径更明确。
- 原因：
  - 第三方库存源证明 `v/ao/lu` 并非完全不可监控，forward collection 可以启动。
  - 官方 endpoint 和事件 monitor 缺口被清晰定位，下一步不是继续扫收益，而是补实盘证据链。
  - 只有把这条证据链补齐，低单笔风险扩池才可能从“结构上合理”变成“可实盘验证”。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage594_p0_external_endpoint_probe.py`：通过，使用联网权限。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage594_p0_external_endpoint_probe.py`：通过。
- 图表已视觉检查，修正 hard gate 标签后重新生成并复看。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或路线废弃；只更新本线边界。
