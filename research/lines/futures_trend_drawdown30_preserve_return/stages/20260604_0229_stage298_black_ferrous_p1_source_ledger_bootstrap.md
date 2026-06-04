# Stage298 黑色族 P1 source ledger bootstrap

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 02:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读采集/审计；不做收益回测，不修改策略，不生成交易白名单。
- 是否重要突破：否。它启动了 `j/i` 点时化 source 账本，但不是策略晋级。
- 是否触发A/B：否。`promotion_allowed=false`、`paper_selector_allowed=false`、`trading_whitelist_allowed=false`。

## 外部调研与判断

- 参考资料：
  - AKShare 文档列出 `get_dce_rank_table`、`futures_dce_position_rank`、`futures_warehouse_receipt_dce` 等 DCE 会员持仓/仓单路线。
  - 大连商品交易所官网 `http://www.dce.com.cn` 是 `j/i` 会员持仓、仓单、公告和交割规则的官方源入口。
  - Man Group 趋势跟踪 market mix 研究强调市场选择需要同时考虑收益、相关性、流动性和执行约束。
- 我的判断：
  - `j/i` 可以作为黑色新产品族继续补证，但当前 source 只启动了第三方 forward monitor，不足以作为 alpha。
  - 官方 DCE member/warehouse 路线本次仍未闭合，不能把 `j/i` 当作完整基本面闭环。
  - 本阶段用外部网络重跑成功；沙箱内 DNS 失败只说明沙箱无外网，不作为源不可用结论。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `P1_PRODUCTS=["j.DCE","i.DCE"]`
  - `MIN_FORWARD_DATES=20`
  - `MIN_TCA_PER_PRODUCT=3`
  - `MIN_FORWARD_READY_ROUTES_PER_PRODUCT=2`
  - `MAX_SOURCE_AGE_DAYS=7`
  - 同日去重键：`received_date + product_vt_symbol + route`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-06-04 02:28 CST` 当前 source snapshot；basis/inventory source_date 为 `2026-06-03`。
- 账户规模：N/A
- 成本口径：N/A
- 样本过滤：仅 `j.DCE/i.DCE`；只检查 `basis/inventory/member_detail/warehouse/event_catalog`。
- 策略/归因口径：point-in-time forward source ledger；所有行 `usable_for_history_selector=0`。

## 结果

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 其他关键指标：
  - 决策：`black_ferrous_p1_source_ledger_started_no_paper`
  - snapshot rows：`10`
  - scoped master rows：`10`
  - 每品种当前 forward-ready routes 最小值：`2`
  - 每品种 scoped received dates 最小值：`1/20`
  - hard gates：`4/8`
  - `basis`：`2/2 ok`，第三方 forward-ready，source_date `2026-06-03`
  - `inventory`：`2/2 ok`，第三方 forward-ready，source_date `2026-06-03`
  - `member_detail`：`0/2 ok`，`futures_dce_position_rank` 返回 `BadZipFile`
  - `warehouse`：`0/2 ok`，`futures_warehouse_receipt_dce` 返回 `JSONDecodeError`
  - `event_catalog`：`0/2 forward-ready`，仅 catalog-only，不计 event_ready
  - forward hash：`4/4`
  - history selector ready：`0`
  - new family live TCA：`0/6`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_report_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.md`
- snapshot：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_snapshot_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.csv`
- scoped master ledger：`examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger/black_ferrous_p1_source_forward_ledger.csv`
- route summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_route_summary_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.csv`
- product summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_product_summary_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_gates_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.csv`
- next actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_next_actions_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_decision_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap_chart_stage598_black_ferrous_p1_source_ledger_bootstrap_v1.png`

## 图表复盘

- 左上热力图显示 `j/i` 只有 `basis` 和 `inventory` 为绿，`member_detail/warehouse/event_catalog` 全红；说明当前只启动了弱 source 账本，没有官方闭环。
- 右上 route status 显示 ok 行全部来自第三方，official ready 为 `0`；这防止把 DCE 官方入口或 AKShare 函数名误读为官方 monitor ready。
- 左下样本深度显示每个品种 ready routes 为 `2`，received dates 为 `1`，距离 `20` 日期门槛很远。
- 右下 gate 图显示通过项集中在 scope、当前 snapshot、hash 和 history disabled；失败项集中在样本深度、TCA 和 paper allowed。

## 结论

- 本阶段结论：
  - `j/i` 黑色族 P1 source ledger 已启动，当前 basis/inventory 两条 third-party forward route 可抓并可 hash。
  - 但 DCE member/warehouse 官方路线未闭合，事件路线仍是 catalog-only，不能作为完整基本面 alpha。
  - 该阶段不支持收益回测、paper sleeve、A/B 或交易白名单。
- 是否进入下一步：进入日更采集和官方路线修复，不进入策略回测。
- 下一步：
  1. 每日复跑 Stage598，按同日去重累计 `20` 个 scoped received dates。
  2. 修 DCE member/warehouse parser：解决 `BadZipFile` 与 `JSONDecodeError`，并冻结 exact source_url/raw payload。
  3. 补 `j/i` DCE 公告/交割规则事件 monitor，catalog-only 不计 event_ready。
  4. 每品种补 `3` 个真实或独立分钟 TCA 样本；未达 `6/6` 前不允许 paper。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有收益回测、没有调参、没有用 source 结果改变交易规则；所有历史 selector 标志保持 `0`，且同日重复运行不会增加样本日期。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只限补证方向。
- 原因：`j/i` 已经有可落账的 third-party basis/inventory forward route，说明不是空想；但官方 DCE 与 TCA 缺口仍大，继续价值在于数据工程和执行证据，不是立刻做收益曲线。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新阶段与下一步。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合并。
