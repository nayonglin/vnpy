# Stage061 - OI-confirmed 反向风险预算 proxy

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T22:29:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 审计，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- CME Open Interest: https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest
- pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade
- Rob Carver risk sizing note: https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html
- QuantConnect futures trend/carry risk regimes: https://www.quantconnect.com/research/15989/futures-trend-following-and-carry-in-different-risk-regimes/

- 我的判断：OI 可作为参与度/趋势确认背景，但不应直接当 alpha 或加仓条件；Stage061 只验证 Stage060 发现的 `oi_confirmed` 反向预算候选。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage061_oi_confirmed_reverse_budget_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；proxy 固定 `VARIANT=oi_confirmed_cap_to_one`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage061_oi_confirmed_reverse_budget_proxy_candidate_needs_daily_probe`。
- proxy gate 通过：`True`。
- 全样本 original PnL：`62843641.40`。
- 全样本 candidate PnL：`74077008.74`。
- 全样本收益保留：`117.8751%`。
- 压力样本 original PnL：`-474365.00`。
- 压力样本 candidate PnL：`-163175.00`。
- 压力样本 delta PnL：`311190.00`。
- 压力样本 loss reduction：`65.6014%`。
- late-adverse original PnL：`-235020.00`。
- late-adverse candidate PnL：`-53420.00`。
- late-adverse delta PnL：`181600.00`。
- late-adverse loss reduction：`77.2700%`。
- 全样本错杀正 PnL proxy：`36286847.63`。
- 全样本移除负 PnL proxy：`-47520214.97`。

## 回测指标说明

- 本阶段不是新增真引擎回测，不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 本阶段只读复用 Stage038/055/059 输出，检验一个 closed-lot 线性代理是否值得进入日级探针。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage061_oi_confirmed_reverse_budget_proxy/rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy_report_stage061_oi_confirmed_reverse_budget_proxy_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage061_oi_confirmed_reverse_budget_proxy/rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy_summary_stage061_oi_confirmed_reverse_budget_proxy_v1.csv`
- evaluation：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage061_oi_confirmed_reverse_budget_proxy/rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy_evaluation_stage061_oi_confirmed_reverse_budget_proxy_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage061_oi_confirmed_reverse_budget_proxy/rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy_chart_stage061_oi_confirmed_reverse_budget_proxy_v1.png`

## 过拟合反思

- 运行前判断：否。只冻结 Stage060 的 OI-confirmed 候选，不扫阈值/窗口/品种/方向。
- 运行后判断：否。本阶段只做单一冻结 proxy，未根据结果微调 OI 阈值、手数或样本窗口。

## 继续价值反思

- 运行前判断：有。需要验证 OI-confirmed 是否能在不伤全样本收益保留的前提下减少 pressure/late-adverse。
- 运行后判断：有。冻结 OI-confirmed 反向预算 proxy 同时满足全样本收益保留、压力样本减亏和 late-adverse 减亏，下一步必须做日级冷启动/真引擎探针，不能直接上线。
