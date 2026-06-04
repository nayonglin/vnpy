# Stage296 低单笔风险扩池风险槽设计审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 02:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：整合既有冻结审计输出，定义扩池风险槽、产品分层、证据闸门；不做收益回测，不修改策略，不生成交易白名单。
- 是否重要突破：否，但它把“扩池降单笔风险”的下一步从泛泛想法收敛成可审计结构。
- 是否触发A/B：否。当前不形成可接正式版本的交易候选，也不启动 paper selector。

## 外部调研与判断

- 参考资料：
  - AQR Trend Following：趋势策略长期依赖跨市场、多资产、低相关暴露来提高稳定性。
  - Man Group Trend Following Market Mix：市场组合选择和多市场覆盖是趋势跟踪的重要问题，但必须考虑流动性与可交易性。
  - Riskfolio-Lib / skfolio：风险预算、风险贡献、聚类和组合优化常用于控制相关性与风险贡献，但不能代替策略本身的正期望和点时化数据。
- 我的判断：
  - 用户提出的方向是对的：减少单笔风险、扩大品种池、每年抓部分趋势，比继续调 079 或回撤窗口小数更低过拟合。
  - 但“扩池”不能理解成简单加更多历史有收益的品种。正确口径应是增加独立风险槽，而不是增加同族深度。
  - 当前真正瓶颈不是 P0 内部 pairwise corr，而是有效风险槽不足、point-in-time selector edge 不足、官方外生源未闭环、live TCA 未闭环。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage596_breadth_risk_slot_design.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MAX_PRODUCT_RISK_HARD_PCT=20.0`
  - `MAX_PRODUCT_RISK_PREFERRED_PCT=15.0`
  - `MAX_CORE_CORR_WATCH=0.10`
  - `MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED=7`
  - `MIN_FAMILIES_FOR_PREFERRED=6`
  - `MIN_SELECTOR_CAPTURE_PCT=92.58401999814832`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_VALID_TCA_SAMPLES=9`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做新回测；读取 Stage574/590/592/595 的冻结输出。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：只做产品风险槽与证据分层；不启动 TopN、risk、corr、family cap 扫描。
- 策略/归因口径：Stage526/低单笔风险扩池的结构审计，不生成交易候选。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`breadth_risk_slot_design_valid_direction_not_tradeable`
  - raw P0 products：`5`
  - P0 families：`4`
  - P1 new-family candidates：`2` 个产品，但只有 `1` 个新产品族
  - effective slots with current P1：`5`
  - preferred effective slots required：`7`
  - hard gates：`2/8`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`

## 风险槽结论

- P0 原始等权是 `5` 个产品，单产品风险 `20.0%`，只过硬线，不达 `15%` 偏好线。
- `y.DCE/c.DCE` 同属 `grains_oilseeds`，且必须同族同向 top1-only；因此从有效独立风险槽看，当前 P0 实际只有 `4` 个风险槽，单槽风险约 `25.0%`。
- 当前可接受的新产品族候选只有黑色系 `j.DCE/i.DCE`，它们能把有效槽从 `4` 推到 `5`，但离 `7` 个有效槽仍差 `2` 个。
- `al.SHFE/pg.DCE/bu.SHFE/TA.CZCE` 只能补已有产品族深度，不能显著降低独立风险槽风险。
- `br.SHFE` 虽有正收益机会，但核心相关 `0.2783` 明显超过观察线，不适合作为降低核心相关风险的扩池候选。

## 图表视觉复盘

- 左上机会-核心相关散点图显示：`lu.INE` 收益机会最高，但越过 `0.10` 核心相关观察线；`j/i` 靠左、相关性低，但收益机会明显小于 P0 主力产品，且同属一个新族。
- 右上风险槽图显示：P0 raw 为 `20.0%`，y/c top1 后有效槽为 `25.0%`，加入当前 P1 新族后仍为 `20.0%`，只有目标 `7` 槽才到 `14.3%`。这是本阶段最重要的视觉结论。
- 左下 P0 证据热力图显示：`y/c` route/event 已绿但 official monitor 全红；`v/ao/lu` 仍缺 event 或 route，`lu` 还卡核心相关观察。
- 右下结构闸门只有 `single_product_risk_hard`、`pairwise_corr_budget`、`random_breadth_not_enough` 通过；有效风险槽、selector edge、官方源、forward 样本深度、live TCA 均未过。

## 输出文件

- product tiers：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_product_tiers_stage596_breadth_risk_slot_design_v1.csv`
- risk slot plan：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_risk_slot_plan_stage596_breadth_risk_slot_design_v1.csv`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_gates_stage596_breadth_risk_slot_design_v1.csv`
- next actions：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_next_actions_stage596_breadth_risk_slot_design_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_decision_stage596_breadth_risk_slot_design_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_report_stage596_breadth_risk_slot_design_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage596_breadth_risk_slot_design_chart_stage596_breadth_risk_slot_design_v1.png`

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage596_breadth_risk_slot_design.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage596_breadth_risk_slot_design.py`：通过。
- `python -m json.tool ...decision_stage596_breadth_risk_slot_design_v1.json`：通过。
- 输出文件存在：通过。
- 图表视觉检查：通过，四个面板可读，且与表格结论一致。

## 结论

- 本阶段结论：低单笔风险扩池方向值得继续，但当前不能晋级为 paper 或交易。当前不是“相关性太高”导致失败，而是有效风险槽不足和 selector/TCA/数据源未闭环。
- 是否进入下一步：是。
- 下一步：
  - 定义 Stage597 新产品族候选补证清单，优先看是否能从 `black_ferrous/rubber/soft_agri/precious_metals/financial_index` 中找到至少 `2` 个新有效族。
  - 对候选新族只做 source/TCA/容量补证，不做收益回测白名单。
  - P0 继续补 `v/ao/lu` 官方源、事件/舆情、forward sample depth 和 live TCA。
  - 只有达到 `>=7` 有效风险槽、`>=6` 产品族、`20/20` forward 样本和 `9/9` live TCA 后，才允许讨论低风险扩池 paper selector。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不做新收益回测、不调 TopN/risk/corr/family cap 小数、不生成白名单，只把既有冻结审计输出转成结构闸门和下一步补证清单。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但下一步必须补证，不该直接回测。
- 原因：本阶段证明“有效风险槽”是比“产品数量”更本质的约束；如果能找到至少两个新的低相关、容量足够、可点时化监控的产品族，才可能真正改善 3/6 个月持有体验和单品种路径风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与下一步。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
