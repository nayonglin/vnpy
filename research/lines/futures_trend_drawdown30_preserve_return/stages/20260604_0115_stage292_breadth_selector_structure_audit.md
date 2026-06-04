# Stage292 低单笔风险扩池 selector 可交易结构审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 01:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读结构审计；不修改策略、不新增交易候选、不做收益回测化 selector。
- 是否重要突破：否，但属于“减少单笔风险、扩大品种池、避免高相关、选对品种”路线的关键结构闸门。
- 是否触发A/B：否。本阶段没有形成可接入正式版本的新策略候选；结论反而禁止启动 P0 交易白名单和 A/B。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen `Time Series Momentum`：跨多类流动期货的时间序列动量支持多市场分散趋势组合。
  - `pysystemtrade`：instrument weights、diversification multiplier、risk target 是系统化期货组合构造核心。
  - `Increasing Diversification of Commodities Trend-Following Strategies`：扩大商品 universe 有潜在价值，但需要异质性和可部署选择机制。
  - Concretum trend-following position sizing：仓位规模和风险预算会显著改变权益曲线、回撤和持有体验。
- 我的判断：
  - 用户提出的方向在第一性原理上成立：趋势收益稀疏，降低单笔风险并扩大低相关机会集合，理论上能提高每年抓到部分趋势的概率。
  - 但“扩池”和“选对品种”必须拆开：相关性预算只能降低拥挤风险，不能制造 alpha；真正瓶颈是 point-in-time selector 和真实成交证据。
  - 当前阶段只能把 P0 转成 forward collection 和结构闸门，不能转成交易白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage592_breadth_selector_structure_audit.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增审计参数：
  - `MIN_PIT_PRODUCTS=6`
  - `MIN_PIT_FAMILIES=5`
  - `MAX_PRODUCT_RISK_HARD_PCT=20`
  - `MAX_PRODUCT_RISK_PREFERRED_PCT=15`
  - `MAX_FAMILY_RISK_PCT=20`
  - `MAX_PAIRWISE_ABS_CORR=0.50`
  - `MAX_CORE_ABS_CORR_WATCH=0.10`
  - `MIN_ROUTE_READY_PRODUCTS=5`
  - `MIN_EVENT_READY_PRODUCTS=5`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_ACTUAL_SLEEVE_PNL=50000`
  - `MIN_SELECTOR_CAPTURE_PCT=92.5840`
  - `MIN_VALID_TCA_SAMPLES=9`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不新增回测；只读取 Stage570/574/588/590/561/571/583/591 既有输出。
- 账户规模：Stage526 核心 `50万` 口径；P0 扩池只作为低单笔风险 sleeve 结构审计。
- 成本口径：沿用既有 Stage574/570 正常成本结果；本阶段不新增成本压力回放。
- 样本过滤：
  - P0 来自 Stage574 `independent_material_capacity_ok=1`。
  - route/event readiness 来自 Stage588。
  - forward 样本深度来自 Stage561。
  - 真实TCA与 submit adapter 状态来自 Stage583/591。
- 策略/归因口径：
  - 不改 Stage526。
  - 不把 Stage256 hindsight upper 或 P0 历史赢家转为白名单。
  - 把风险壳、selector edge、持有体验和真实成交证据拆成独立硬闸门。

## 结果

- 期末权益：不适用；本阶段无新增收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`breadth_selector_structure_promising_not_tradeable_selector_and_tca_blocked`
  - `promotion_allowed=false`
  - `paper_selector_allowed=false`
  - `trading_whitelist_allowed=false`
  - P0 产品数 / 产品族数：`5 / 4`
  - hard gates：`3/13`
  - soft gates：`2/4`
  - 通过硬闸门：
    - 单产品等权风险 `20.00%`，刚好通过 `20%` 硬线，但未达 `15%` 偏好线。
    - 同族 top1 tie-break 后产品族风险可压到 `20%`。
    - P0 内部最大 pairwise abs corr `0.0508`，远低于 `0.50`。
  - 失败硬闸门：
    - P0 池深度 `5` 产品 / `4` 产品族，低于 `6/5`。
    - route ready `3/5`，`ao/lu` 缺 basis 或替代路线。
    - event ready `2/5`，`v/ao/lu` 缺真实事件/舆情覆盖。
    - forward runs/dates `2/20`、`2/20`。
    - P0 capture `52.79%`，低于约 `92.58%` 的材料性捕获门槛。
    - 可部署宽池壳 `0/3` 通过不劣化。
    - all noncore actual sleeve `9,395`，低于 `50,000` 材料性线。
    - best deployable 63/126日 p10 delta 为 `-0.0141pp/-0.1054pp`，没有改善任意启动后的3/6个月左尾。
    - live TCA 样本 `0/9`。
    - submit adapter 仍是 dry-run，真实 `vt_orderid` 为 `0`。

### 产品预算

| 产品 | 产品族 | 历史机会 | 正年份率 | abs核心相关 | route | event | 证据分 | 当前角色 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `y.DCE` | grains_oilseeds | `38,140` | `57.1429%` | `0.0072` | 1 | 1 | `95` | route/event ready，但需要同族 tie-break |
| `c.DCE` | grains_oilseeds | `21,100` | `85.7143%` | `0.0160` | 1 | 1 | `95` | route/event ready，但需要同族 tie-break |
| `v.DCE` | petrochem | `50,705` | `85.7143%` | `0.0647` | 1 | 0 | `75` | route ready，缺事件覆盖 |
| `lu.INE` | energy_oil | `87,510` | `42.8571%` | `0.1543` | 0 | 0 | `30` | 历史机会高，但缺 route/event 且越过核心相关观察线 |
| `ao.SHFE` | base_metals | `28,840` | `75.0000%` | `0.0159` | 0 | 0 | `35` | 缺 basis/替代 route 和事件覆盖 |

### 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_chart_stage592_breadth_selector_structure_audit_v1.png`
- 左上：`lu.INE` 的历史机会最高，但位于 `0.10` 核心相关观察线右侧；这说明不能把 `lu` 直接视为低相关 alpha，它更像高机会但需约束的观察品种。
- 左上同图中 `v.DCE` 的历史机会和正年份率更均匀，且核心相关低于 `0.10`，视觉上更像可持续 selector 的底座；但它缺真实事件覆盖。
- 上中：只有 Stage256 hindsight upper 的 63/126日 p10 delta 为正，三个可部署宽池壳都是负值；这直接说明现有宽池 selector 不能改善任意启动后的3/6个月体验。
- 右上：route readiness `60%`、event readiness `40%`、forward runs/dates `10%/10%`、valid TCA `0%`，阻塞点非常集中，不是图表噪声。
- 左下：随机 k3/k6 与 family-cap k3/k6 的 p95 全部远低于红色材料性机会代理线，确认“随机扩池 + 同族分散”不能自然抓趋势。
- 中下：`grains_oilseeds` 原始等权风险 `40%`，只有 top1 tie-break 后才能降到 `20%`；所以 y/c 不能同向同时吃满。
- 右下：hard fail `10` 个，hard pass 只有 `3` 个；这不是小修小补可以晋级的状态。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_report_stage592_breadth_selector_structure_audit_v1.md`
- product_budget：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_product_budget_stage592_breadth_selector_structure_audit_v1.csv`
- family_budget：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_family_budget_stage592_breadth_selector_structure_audit_v1.csv`
- structure_gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_structure_gates_stage592_breadth_selector_structure_audit_v1.csv`
- next_actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_next_actions_stage592_breadth_selector_structure_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_decision_stage592_breadth_selector_structure_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage592_breadth_selector_structure_audit_chart_stage592_breadth_selector_structure_audit_v1.png`

## 结论

- 本阶段结论：`breadth_selector_structure_promising_not_tradeable_selector_and_tca_blocked`
- 是否进入下一步：进入，但只进入 forward collection 与证据补齐，不进入收益回测、交易白名单或 A/B。
- 下一步：
  1. 补 `ao/lu` 的 basis 或可点时化替代 route。
  2. 补 `v/ao/lu` 的真实事件/舆情账本，必须有 `source_url/published_at/received_at/raw_hash`。
  3. 执行 `y/c` 同族同向 top1-only tie-break，排序只能来自 point-in-time 外生证据。
  4. 累计 Stage561 `20/20` forward runs/dates 后，才允许做固定 IC/bucket/paper-sleeve 审计。
  5. 执行侧继续补 Stage526 P0 的 `0/9 -> 9/9` live TCA 样本和真实 `vt_orderid` 映射。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只读取既有冻结输出，没有新增交易规则、历史赢家白名单或收益参数。
  - Stage256 被明确作为 hindsight upper，不作为可部署版本。
  - 对 P0 历史机会没有晋级，反而把 route/event/forward/TCA 缺口设为硬闸门。
  - 若后续为了通过闸门去删除 2020、调产品名单、调 family cap 或调相关阈值，则会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但路径更窄。
- 原因：
  - P0 内部相关性确实低，年度机会也存在，说明用户的结构性方向不应废弃。
  - 但当前证据证明随机扩池和现有可部署宽池都不够，继续价值只在 point-in-time selector 证据、同族风险预算和真实执行偏差闭环。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage592_breadth_selector_structure_audit.py`：通过。
- 图表已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，作为当前线最新边界阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或路线废弃，只是结构闸门收束。
