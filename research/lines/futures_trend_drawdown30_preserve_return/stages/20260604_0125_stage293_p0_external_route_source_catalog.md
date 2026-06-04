# Stage293 P0 外生 route/event 源目录与实盘账本合同审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 01:25 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据源与账本合同审计；不联网抓取、不生成事件样本、不做收益回测、不生成交易候选。
- 是否重要突破：否，但把 Stage292 的 `v/ao/lu` 外生 route/event 缺口推进为机器可审计 source catalog。
- 是否触发A/B：否。外生源仍未通过 parser、forward 样本和 selector 闸门。

## 外部调研与判断

- 参考资料：
  - 上海期货交易所首页显示 `仓单日报` 入口，可作为 `ao.SHFE` 仓单/库存替代 route 的官方入口：`https://www.shfe.com.cn/index.html`
  - 上海期货交易所氧化铝期货合约附件提供交割单位、质量规定、指定交割仓库/厂库等产品映射信息：`https://www.shfe.com.cn/products/futures/metal/nonferrousmetal/ao_f/appendix/202306/t20230616_800368.html`
  - 上海国际能源交易中心官网显示 `库存周报`、低硫燃料油产品和服务入口：`https://www.ine.cn/index.html`
  - 上海国际能源交易中心低硫燃料油期货合约：`https://www.ine.com.cn/eng/market/futures/energy/lu/contract/`
  - 上海国际能源交易中心交割细则含低硫燃料油交割、仓单和厂库标准仓单规则：`https://www.ine.cn/regulation/ineregulation/rules/202308/t20230811_814259.html`
  - 上海国际能源交易中心标准仓单管理系统指南：`https://www.ine.cn/services/delivery/standardwarrantms/202404/W020240517500690551744.pdf`
  - 大连商品交易所官网泛入口：`https://www.dce.com.cn/`
- 我的判断：
  - `ao/lu` 的官方合约、交割、仓单/库存入口和公告样例可作为 forward monitor 数据工程入口，但不是历史 selector alpha。
  - `v.DCE` 当前搜索只能确认 DCE 泛入口和第三方 PVC 仓单新闻线索，尚未冻结精确官方 PVC 事件/仓单 URL；第三方新闻不能计入 `event_ready`。
  - 所有事件/舆情源必须按 Stage572 账本合同写入 `received_at/source_url/published_at/raw_text_hash`，并保持 `usable_for_history_selector=0`，避免把 forward 采集反填成历史回测。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage593_p0_external_route_source_catalog.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增审计参数：
  - `MISSING_EVENT_PRODUCTS=v.DCE/ao.SHFE/lu.INE`
  - `MISSING_BASIS_SUBSTITUTE_PRODUCTS=ao.SHFE/lu.INE`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `LEDGER_REQUIRED_FIELDS=29`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不新增回测；读取 Stage592 product/next_actions、Stage571 source priority、Stage561 gates。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 缺口产品限定为 Stage292 明确的 `v/ao/lu`。
  - `y/c` 不新增 source catalog，因为当前缺口是同族同向 tie-break，不是 route/event 源缺口。
- 策略/归因口径：
  - 不生成收益曲线。
  - 不把 source catalog 当作 alpha。
  - 只冻结 source catalog、product route matrix、ledger contract 和 hard gates。

## 结果

- 期末权益：不适用；本阶段无新增收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p0_external_route_catalog_ready_parser_and_forward_depth_blocked`
  - `promotion_allowed=false`
  - `paper_selector_allowed=false`
  - `trading_whitelist_allowed=false`
  - source catalog rows：`10`
  - P0 products with catalog rows：`3`，对应本轮缺口产品 `v/ao/lu`
  - missing event products catalogued：`3/3`
  - missing event products auto monitor ready：`0/3`
  - missing basis products catalogued：`2/2`
  - missing basis products auto monitor ready：`0/2`
  - hard gates：`5/10`
  - 失败硬闸门：
    - `event_auto_monitor_ready`
    - `basis_substitute_auto_monitor_ready`
    - `exact_official_source_depth`
    - `forward_sample_depth`
    - `paper_selector_allowed`

### 产品 route 状态

| 产品 | 当前缺口 | catalog rows | exact official rows | auto monitor ready | Stage293 判断 |
| --- | --- | ---: | ---: | ---: | --- |
| `y.DCE` | same_family_tiebreak | `0` | `0` | `0` | 不是本轮源缺口；继续执行 y/c 同族同向 top1-only |
| `c.DCE` | same_family_tiebreak | `0` | `0` | `0` | 不是本轮源缺口；继续执行 y/c 同族同向 top1-only |
| `v.DCE` | sentiment/news/manual event | `2` | `0` | `1` | inventory route 已有，但事件精确官方 URL 未冻结 |
| `ao.SHFE` | basis substitute + event | `3` | `1` | `0` | 有官方产品/仓单入口，但 daily/event monitor 未接 |
| `lu.INE` | basis substitute + event + core corr watch | `5` | `4` | `0` | 官方上下文最完整，但仍缺自动采集和核心相关约束 |

### 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_chart_stage593_p0_external_route_source_catalog_v1.png`
- 左上：`y/c` 证据分 `95/95` 且为绿色，确认它们不是 source 缺口；`v/lu/ao` 为红色，说明本轮应集中在这三个产品。
- 上中：`lu` catalog 最多且 exact official rows 最多，说明数据源入口不是空白；但 auto monitor ready 为 `0`，不能算 selector-ready。
- 上右：`inventory` route 只有 `v` 一条已自动 ready，`sentiment_news_manual_event` 有 rows 但无 auto monitor，视觉上明确区分了“有线索”和“可运行”。
- 左下：Stage571 显示 basis/inventory forward-ready 产品多，但 history-ready 全为 `0`；这再次确认不能做历史 selector 回测。
- 中下：hard pass/fail 为 `5/5`，阶段处于“源目录已建立，但还没过工程化闸门”的中间状态。
- 右下：`manual_reference_ready_not_alpha` 最多，说明大量官方页面只能用于产品映射和交割语义，不能直接作为信号。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_report_stage593_p0_external_route_source_catalog_v1.md`
- source_catalog：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_source_catalog_stage593_p0_external_route_source_catalog_v1.csv`
- product_route_matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_product_route_matrix_stage593_p0_external_route_source_catalog_v1.csv`
- ledger_contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_ledger_contract_stage593_p0_external_route_source_catalog_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_gates_stage593_p0_external_route_source_catalog_v1.csv`
- next_actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_next_actions_stage593_p0_external_route_source_catalog_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_decision_stage593_p0_external_route_source_catalog_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage593_p0_external_route_source_catalog_chart_stage593_p0_external_route_source_catalog_v1.png`

## 结论

- 本阶段结论：`p0_external_route_catalog_ready_parser_and_forward_depth_blocked`
- 是否进入下一步：进入，但只进入 parser/monitor 工程化，不进入收益回测。
- 下一步：
  1. `v.DCE`：冻结 DCE 精确 PVC 官方公告/仓单 URL，不能用第三方新闻替代。
  2. `ao.SHFE`：接入 SHFE 仓单日报或可复验库存/仓单 endpoint，写 raw hash 和 `received_at`。
  3. `lu.INE`：接入 INE 库存周报/仓单 endpoint，继续保留 core corr watch。
  4. 所有新增源先写 forward ledger，`usable_for_history_selector=0`。
  5. 达到 Stage561 `20/20` 后，才允许做固定 IC/bucket/paper-sleeve 审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有使用未来收益、没有修改交易规则、没有把源目录转成交易信号。
  - 对第三方新闻和泛入口保持降级处理，没有为了补绿灯而把不可复验来源计入 `event_ready`。
  - 历史 selector 仍显式禁用，避免 forward 采集反填历史。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值从“策略研究”转为“数据工程前置”。
- 原因：
  - Stage292 卡住的是 route/event/forward 样本；Stage293 已把源目录和账本合同落成机器可审计文件。
  - 下一步如果能接入精确 endpoint，就可以真正累计 forward 样本；如果接不通，则应停止相应产品的外生 selector 路线。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage593_p0_external_route_source_catalog.py`：通过。
- 图表已视觉检查并修正 parser status 标签重叠。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，作为当前线最新证据阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或路线废弃。
