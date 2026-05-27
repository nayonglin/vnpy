# Stage066 xsmom真实承载失败归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 21:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：xsmom 净值层候选到真实期货承载的失败归因；路线边界固化
- 是否重要突破：否，重要反证和研究边界更新
- 是否触发A/B：否。本阶段不提出新候选，只审计既有 Stage045/046/048/049/052 证据，防止重复围绕已失败承载形状救援。

## 外部调研与判断

- 参考资料：
  - 商品横截面动量和时间序列动量在外部研究中有长期理论基础，常见实现是按过去收益排序、跨商品分散持有，并显式扣除换手成本。
  - 但真实期货账户不是连续净值仓位：合约乘数、保证金、最小1手、品种流动性、滑点和再平衡频率都会让小权重卫星与净值层结果不等价。
- 我的判断：
  - Stage045 的 xsmom 净值层结果有信息含量，但不能直接当作可交易版本。
  - 现有期货承载形状已经验证了三类失败：`3.75万`卫星资金太小、`35/15`真实拆分多起点收益保留不足、滑点压力下回撤重新超过30。
  - 继续调 `7.5%`、`35/15`、篮子数量、低保证金优先顺序或小额现金 overlay，会把有效因子研究变成历史救援。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage366_xsmom_carrying_failure_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无。本阶段只设置诊断闸门：
  - 最大回撤目标：`30%`
  - 收益保留目标：`80%`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/046/048/049/052 的既有输出。
- 账户规模：
  - 净值层：`92.5% C3 + 7.5% xsmom`
  - 小资金期货腿：`3.75万`卫星腿
  - 真实拆分：`35万 C3 + 15万 xsmom`
- 成本口径：沿用既有 xsmom 20bp 成本、真实引擎默认成本，并做 `1x/2x/3x/5x` 滑点压力引用。
- 样本过滤：不新增样本过滤。
- 策略/归因口径：只审计承载可行性，不改第78-1/C3入场、AI池、品种池、xsmom排序窗口或供需/热度规则。

## 结果

- 期末权益：无。本阶段不是新回测。
- 总收益：无。本阶段不是新回测。
- 最大回撤：无。本阶段不是新回测。
- Sharpe：无。本阶段不是新回测。
- 总滑点：无。本阶段不是新回测。
- 总交易次数：无。本阶段不是新回测。
- 胜率：无。本阶段不是新回测。
- 其他关键指标：
  - Stage045 净值层 `92.5%C3 + 7.5%xsmom`：总收益 `4880.7988%`，收益保留 `80.2086%`，最大回撤 `-29.5427%`，Sharpe `1.6317`，全样本通过，但未证明可交易。
  - Stage046 `3.75万`卫星腿：按保证金向下取整最大回撤 `-31.4478%`；低保证金1手优先最大回撤 `-31.2509%`；全部信号至少1手最高需保证金 `191,288.6`，合成回撤仍 `-30.3389%`。
  - Stage048/049 `35万C3 + 15万xsmom`：全样本总收益 `5129.5990%`，最大回撤 `-27.9488%`，收益保留 `84.2973%`，但多起点和滑点压力失败。
  - 失败窗口：`start_2021/start_2022/start_2023/ytd_2026/weak_2021_full`。
  - `start_2021/start_2022/start_2023` 收益保留分别为 `40.6752%/47.8951%/51.9342%`。
  - `ytd_2026` 组合最大回撤 `-50.5798%`。
  - 滑点压力：`1x/2x` 通过，`3x` 回撤 `-30.4983%` 失败，`5x` 回撤 `-36.5074%` 失败。
  - `15万`卫星资金相对 min1 全篮子最高需保证金覆盖率仅 `78.4155%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_xsmom_carrying_failure_diagnostic_report_stage366_xsmom_carrying_failure_diagnostic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_xsmom_carrying_failure_diagnostic_summary_stage366_xsmom_carrying_failure_diagnostic_v1.csv`
- window_attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_xsmom_carrying_failure_diagnostic_window_attribution_stage366_xsmom_carrying_failure_diagnostic_v1.csv`
- stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_xsmom_carrying_failure_diagnostic_stress_stage366_xsmom_carrying_failure_diagnostic_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_xsmom_carrying_failure_diagnostic_decision_stage366_xsmom_carrying_failure_diagnostic_v1.json`

## 结论

- 本阶段结论：xsmom 理论和净值层价值仍成立，但当前期货卫星承载方式失败；不能晋级为真实候选。
- 决策：`xsmom_theory_valid_but_current_futures_carrier_fail`
- 是否进入下一步：当前期货卫星形状不进入下一步。
- 下一步：
  - 停止围绕 `7.5%`、`35/15`、`3万现金+xsmom overlay`、`min1_cheapest`、篮子数量和保证金优先顺序微调。
  - 若继续 xsmom，只允许三种方向：换承载工具、显著提高卫星资金口径、或作为监控/解释层。
  - 若目标仍是“回撤30以内且收益不显著降低”，优先寻找新的独立收益源，或把 Stage055 作为正常成本部署边界。

## 过拟合反思

- 运行前判断：不是过拟合。当前动作是承载失败归因，不新增参数、不调权重。
- 运行后判断：不是过拟合。结论来自多阶段已冻结结果的交叉审计。
- 原因：本阶段没有因为失败结果去调窗口、权重、阈值或资金拆分；反而把容易过拟合的救援空间关掉。

## 继续价值反思

- 运行前判断：有价值。Stage065 把 xsmom 标为下一步，但如果不先做承载归因，会重复走已失败路径。
- 运行后判断：当前期货卫星形状继续价值低，总研究目标仍有价值。
- 原因：C3 相比78-1已显著更平滑，但离30%硬目标只差约 `1.08pp`；继续有价值，但需要真正低相关收益源或部署边界，而不是已反证的 xsmom 微调。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段改变后续研究禁区和下一步优先级。
