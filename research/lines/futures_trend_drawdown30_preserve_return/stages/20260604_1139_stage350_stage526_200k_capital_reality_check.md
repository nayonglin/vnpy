# Stage350 Stage526 20万资金现实可行性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 11:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署资金层 A/C 审计；不改 Stage526 alpha，不接 CTP，不调用下单。
- 是否重要突破：否，但属于实盘资金边界的重要约束。
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 归类为部署层 A/C。A 为原 Stage526 权威口径，C 为 20万真实整数手资金口径。

## 外部调研与判断

- 参考资料：
  - NexusFi：期货 sizing 的核心约束是账户权益、单笔风险、合约价值与止损距离，不能只看保证金。
  - vn.py PortfolioStrategy 文档：多合约组合策略可以实盘承载，但资金小于原始设计口径时必须重新做真实整数手与保证金验证。
- 我的判断：20万商品期货账户不是把 61.5万 Stage526 线性缩小。整数手、保证金和最小风险单位会改变交易集合，因此必须真实重放。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `ACCOUNT_200K=200000`
  - `stage526_200k_allin_r080_pc25_maxpos4`
  - `stage526_200k_ratio_cash_r080_pc25_maxpos4`
  - `stage526_200k_defensive_r050_pc25_maxpos2`
- 修改参数：仅资金口径、风险倍率和最大同时持仓探针；Stage526 入场/出场/alpha 不改。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本、`2x`、`3x`
- 样本过滤：无
- 策略/归因口径：
  - 原版 Stage526 20万 all-in：`risk_multiplier=0.8`、`product_cap=25%`、`maxpos=4`
  - 比例留现金：C3 核心资金 `162,601.626`，其余现金，`risk_multiplier=0.8`、`product_cap=25%`、`maxpos=4`
  - 防守探针：`risk_multiplier=0.5`、`product_cap=25%`、`maxpos=2`
  - 原 Stage526 `61.5万` 口径的 xsmom/现金腿关闭。

## 结果

### 原版 Stage526 20万 all-in

- 期末权益：`11,554,320`
- 总收益：`5677.16%`
- 年化收益：`89.9139%`
- 最大回撤：`-38.0459%`
- Sharpe：`1.6639`
- 总滑点：`683,440`
- 总交易次数：`656`
- 胜率：`52.4871%`
- 最大 broker10 保证金/权益：`120.0983%`
- 超过100%保证金天数：`2`
- 结论：收益和回撤表面过线，但保证金硬闸门失败，不能直接实盘。

### 20万按原资金比例留现金

- 期末权益：`8,358,445`
- 总收益：`4079.2225%`
- 年化收益：`80.4357%`
- 最大回撤：`-35.7830%`
- Sharpe：`1.6107`
- 总滑点：`501,020`
- 总交易次数：`651`
- 胜率：`52.1441%`
- 最大 broker10 保证金/权益：`110.8667%`
- 超过100%保证金天数：`1`
- 结论：比 all-in 更稳，但仍有保证金穿线，不能直接实盘。

### 20万防守探针

- 期末权益：`1,434,940`
- 总收益：`617.47%`
- 年化收益：`36.5580%`
- 最大回撤：`-24.2399%`
- Sharpe：`1.2639`
- 总滑点：`101,430`
- 总交易次数：`442`
- 胜率：`51.3389%`
- 最大 broker10 保证金/权益：`65.6421%`
- 超过100%保证金天数：`0`
- 结论：基本资金/保证金闸门通过，但它改变了风险倍率和最大同时持仓，不是 Stage526 原版。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_report_stage650_stage526_200k_capital_reality_check_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_summary_stage650_stage526_200k_capital_reality_check_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_daily_stage650_stage526_200k_capital_reality_check_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_positions_stage650_stage526_200k_capital_reality_check_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_cost_stress_stage650_stage526_200k_capital_reality_check_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage650_stage526_200k_capital_reality_check_chart_stage650_stage526_200k_capital_reality_check_v1.png`

## 结论

- 本阶段结论：`stage526_200k_not_deployable`
- 是否进入下一步：可以，但不是原版 Stage526 直接实盘。
- 下一步：
  - 若坚持 20万资金，优先把 `r050_pc25_maxpos2` 作为“小资金防守候选”重新立成独立部署版本，补 start-year、季度冷启动、2x/3x成本、实盘保证金和 TCA 闭环。
  - 原版 `r080_pc25_maxpos4` 在 20万下不得直接实盘，除非另加保证金缓冲或进一步降风险。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做真实资金约束重放，并主动拒绝高收益但保证金失败的原版 20万路径；没有按坏窗口、品种或小数阈值救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向变化。
- 原因：20万资金实盘需求真实存在；结果说明原版 Stage526 不能直接上，继续价值在于小资金防守版本和执行验收，而不是继续追求原版高收益。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待用户确认是否正式开启 20万小资金部署线。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；`memory.md` 仅在用户确认采用 20万小资金路径后再写长期政策。
