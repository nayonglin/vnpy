# Stage055 C3 部署层外部现金边界决策表

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：`2026-05-26 15:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：部署层资金边界复验；候选边界澄清。
- 是否重要突破：是，明确当前目标在“正常成本”下可由部署层资金结构实现，但高滑点下不可称为最终解。
- 是否触发A/B：否；不修改78-1/C3策略逻辑，不进入正式策略A/B。

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen 的趋势跟随长期证据显示，趋势策略的长期价值来自跨市场分散与风险承受，而不是事后弱窗口补丁。
  - Kim/Tse/Wald 对时间序列动量与波动缩放的讨论提示，风险预算/波动缩放会显著影响趋势策略表现。
  - CTA/managed futures 实务资料通常把资金分配、风险预算和现金准备看作独立于信号逻辑的治理层。
- 我的判断：
  - 本线大量内部风控已经反证，继续往 C3 内部加阈值容易切掉趋势复利腿。
  - 当前最低过拟合的可执行方案是承认 C3 自然回撤边界约 `-31%`，然后在账户部署层增加现金分母，而不是改交易信号。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage355_c3_deployment_cash_boundary_decision.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 目标最大回撤：`-30%`
  - 收益保留闸门：`80%`
  - 滑点倍率：`1x/2x/3x/5x`
  - 外部现金向上取整单位：`5,000`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage336 多起点 C3 日权益路径。
- 账户规模：C3策略资金 `500,000`，外部现金只作为账户权益分母，不参与下单。
- 成本口径：正常成本、2x、3x、5x 滑点压力。
- 样本过滤：`start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026/weak_2021_full/phase_2024_2025`。
- 策略/归因口径：不修改 C3 的信号、AI池、品种池、出场、手数和成交路径。

## 结果

- 正常成本 `1x`：
  - 需要外部现金：`115,000`
  - 账户总资金：`615,000`
  - 机械收益保留：`81.3008%`
  - 窗口通过：`9/9`
  - 正收益窗口通过：`8/8`
  - 最差窗口最大回撤：`-29.9039%`
  - 最低正收益窗口收益保留：`81.3008%`
- `2x` 滑点：
  - 需要外部现金：`320,000`
  - 账户总资金：`820,000`
  - 机械收益保留：`60.9756%`
  - 正收益窗口通过：`0/8`
  - 最差窗口最大回撤：`-29.9930%`
- `3x` 滑点：
  - 需要外部现金：`600,000`
  - 账户总资金：`1,100,000`
  - 机械收益保留：`45.4545%`
  - 正收益窗口通过：`0/8`
  - 最差窗口最大回撤：`-29.9458%`
- `5x` 滑点：
  - 需要外部现金：`3,345,000`
  - 账户总资金：`3,845,000`
  - 机械收益保留：`13.0039%`
  - 正收益窗口通过：`0/8`
  - 最差窗口最大回撤：`-29.9900%`
- 关键窗口：
  - 正常成本最严窗口是 `start_2022`，所需现金 `112,433.33`，向上取整为 `115,000`。
  - `2x` 滑点最严窗口是 `start_2020`，所需现金 `318,850`，向上取整为 `320,000`。
  - `3x` 滑点最严窗口是 `start_2024`，所需现金 `595,231.67`，向上取整为 `600,000`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage355_c3_deployment_cash_boundary_decision_report_stage355_c3_deployment_cash_boundary_decision_v1.md`
- boundary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage355_c3_deployment_cash_boundary_decision_boundary_stage355_c3_deployment_cash_boundary_decision_v1.csv`
- requirements：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage355_c3_deployment_cash_boundary_decision_requirements_stage355_c3_deployment_cash_boundary_decision_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage355_c3_deployment_cash_boundary_decision_decision_stage355_c3_deployment_cash_boundary_decision_v1.json`

## 结论

- 本阶段结论：`normal_cost_deployment_boundary_passes_but_slippage_stress_fails_retention`。
- 是否进入下一步：正常成本部署边界可以作为当前最清晰候选；高滑点目标仍未完成。
- 下一步：
  - 若目标定义为“正常低频成本口径”：`50万C3 + 11.5万外部现金` 已满足多周期最大回撤30以内和收益保留80%以上。
  - 若目标要求 `2x/3x` 滑点压力也保收益：该部署层现金路线失败，必须继续寻找真正低相关收益源或更低成本执行方式。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段不修改策略，只计算账户资金边界。
- 运行后判断：不是过拟合，但不能把 `112,433.33` 这类精确值当成实盘神奇参数。
- 原因：采用多起点、弱窗口、滑点压力和 `5,000` 元向上取整，目的是得到部署边界，而不是拟合某一天。

## 继续价值反思

- 运行前判断：有价值。前序内部风险控制和旧卫星大多失败，需要确定是否已有可执行边界。
- 运行后判断：有价值。它给出一个清晰分叉：正常成本下可部署；高滑点下仍需新收益源。
- 原因：这不是提高 alpha，而是把策略自然回撤通过账户总资金承载下来，适合实盘前资金纪律讨论。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录正常成本部署边界。
- 是否更新 `research/registry.md`：是，更新当前关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要部署边界摘要追加。
