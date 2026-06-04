# Stage353 Stage526 20万强制保证金减仓

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 15:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署资金层 A/C；不改 Stage526 alpha，不连接 CTP，不调用下单。
- 是否重要突破：否。正常成本下解决保证金穿线并保留高收益，但完整硬闸门仍未通过。
- 是否触发A/B：是。按 `skills/version-ab-experiment/SKILL.md`，资金/保证金治理为部署层，只做 A vs C。

## 外部调研与判断

- 参考资料：vn.py PortfolioStrategy 官方文档；vn.py RiskManager 官方文档。
- 我的判断：PortfolioStrategy 支持多合约组合目标持仓，RiskManager 是委托前风控；持仓后保证金超限必须在组合策略或账户层做主动减仓。实盘应使用券商账户保证金字段，本回测因策略内部保证金峰值 `81.2805%` 低于 exact broker10 审计峰值 `120.0983%`，使用 `1.65` 的回测触发校准倍数对齐 exact broker10 口径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无。
- 新增参数：
  - `enable_forced_margin_deleverage=False`
  - `forced_margin_deleverage_trigger_ratio=0.95`
  - `forced_margin_deleverage_target_ratio=0.80`
  - `forced_margin_deleverage_broker_multiplier=1.10`
  - `forced_margin_deleverage_priority="largest_margin"`
  - `forced_margin_deleverage_max_reductions_per_day=100`
- 修改参数：Stage653 显式测试 `100%->85%`、`95%->80%`、`90%->75%` 三个粗档，优先平最大保证金占用品种。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526/Stage650 真实整数手日线重放区间。
- 账户规模：`200,000`。
- 成本口径：`1x/2x/3x` 滑点压力。
- 样本过滤：无日期、品种或坏窗口过滤。
- 策略/归因口径：
  - A：`stage526_200k_allin_r080_pc25_maxpos4`
  - C1：`stage526_200k_force100_to85_largest_margin_r080_pc25_maxpos4`
  - C2：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`
  - C3：`stage526_200k_force90_to75_largest_margin_r080_pc25_maxpos4`

## 结果

- 正常成本最优候选：`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`
- 期末权益：`10,415,070`
- 总收益：`5107.5350%`
- 年化收益率：`86.8222%`
- 最大回撤：`-38.8730%`
- Sharpe：`1.6384`
- 总滑点：`597,710`
- 总交易次数：`655`
- 胜率：`52.3156%`
- 其他关键指标：
  - 收益保留相对20万 all-in：`89.9664%`
  - broker10 最大保证金/权益：`83.3212%`
  - 超100%保证金天数：`0`
  - 强制减仓次数：`6`
  - 强制减仓手数：`317`
  - 2x成本最大回撤：`-41.3142%`
  - 3x成本最大回撤：`-43.9072%`
  - hard_pass：`0`

## 全部候选摘要

| 候选 | 期末权益 | 总收益 | 收益保留 | 最大回撤 | broker10峰值 | 2x成本回撤 | 3x成本回撤 | 减仓次数/手数 | hard_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all-in原版 | `11,554,320` | `5677.1600%` | `100.0000%` | `-38.0459%` | `120.0983%` | `-40.5836%` | `-43.2876%` | `0/0` | `0` |
| 强制100->85 | `8,666,350` | `4233.1750%` | `74.5650%` | `-38.2866%` | `82.1437%` | `-40.8390%` | `-43.5672%` | `5/195` | `0` |
| 强制95->80 | `10,415,070` | `5107.5350%` | `89.9664%` | `-38.8730%` | `83.3212%` | `-41.3142%` | `-43.9072%` | `6/317` | `0` |
| 强制90->75 | `3,971,980` | `1885.9900%` | `33.2207%` | `-37.5691%` | `76.9053%` | `-40.1166%` | `-42.8463%` | `6/278` | `0` |

## 强制减仓事件摘要

- `95->80` 首次触发日期：`2020-08-21`
- `95->80` 最大触发前比率：`119.9221%`
- `95->80` 最大触发后比率：`81.3287%`
- `95->80` 主要减仓品种：`fu.SHFE:170, lc.GFEX:113, lh.DCE:13, SA.CZCE:11, CF.CZCE:10`
- 2022-02-16 对 `lh2205.DCE` 强制减 `13` 手至 `0` 手，使触发后比率降至 `81.3287%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage653_stage526_200k_forced_margin_deleverage_report_stage653_stage526_200k_forced_margin_deleverage_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage653_stage526_200k_forced_margin_deleverage_summary_stage653_stage526_200k_forced_margin_deleverage_v1.csv`
- orders：无订单输出；本阶段不连接交易接口。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage653_stage526_200k_forced_margin_deleverage_daily_stage653_stage526_200k_forced_margin_deleverage_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage653_stage526_200k_forced_margin_deleverage_decision_stage653_stage526_200k_forced_margin_deleverage_v1.json`

## 结论

- 本阶段结论：决策 `stage526_200k_forced_margin_deleverage_not_ready`。强制减仓可以把 all-in 的正常成本保证金穿线清零，`95->80` 还能保留约 `90%` 的 all-in 收益；但 2x/3x 成本回撤仍打穿 `-40%`，所以不能直接作为完整实盘通过版。
- 是否进入下一步：是，但方向应明确分层。
- 下一步：若用户接受正常成本口径风险，可把 `95->80` 作为高收益进攻候选继续做真实账户保证金/TCA；若要求完整硬闸门，则应回到 Stage352 `profit50_cap500k`，不要继续围绕强制减仓阈值小数救援。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续扫阈值会过拟合。
- 原因：本阶段测试的是账户生存风控，粗档为 `100/95/90` 触发与 `85/80/75` 目标，不按日期、品种或信号修补。结果说明机制有效解决保证金穿线，但不能解决成本压力回撤；若继续调 `97/82`、`93/78` 等小数就是为了救结果。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：有条件有价值。
- 原因：对用户偏好的 all-in 高收益，`95->80` 是目前最接近的风险治理形状；但它只适合高风险进攻候选，不适合直接替代 Stage352 的20万稳健候选。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，避免并行冲突；合入时统一整理。
- 是否更新 `research/registry.md`：暂不更新。
- 是否追加根目录 `memory.md/back_log.md`：是，追加重要摘要。
