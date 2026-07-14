# Stage137 四锚点 1x canary 失败

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`canary 1x`
- 记录时间：`2026-07-12 17:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：首次真实卫星绩效 canary
- 是否重要突破：否
- 是否触发A/B：否；未达到进入正式 A/B 的门槛

## 外部调研与判断

- 参考资料：前序 in-toto/Pandas/Python 证据合同调研；本次不新增收益导向资料或参数。
- 我的判断：冻结 conjunctive gate 已明确失败，必须先关闭 Stage137，不得调整 25%、锚点、margin gate 或 selector 来救结果。

## 本次变更

- 新增脚本：无
- 修改脚本：无；运行 attempt 5 独立批准版本
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01 / 2022-01 / 2022-07 / 2026-01`，统一终点 `2026-06-30`
- 账户规模：A 冻结 C9 `150,000`；B 独立卫星初始 `150,000`；C 为 A equity + B cumulative net PnL，收益分母仍 `150,000`
- 成本口径：`1x`；按 metadata slippage，metadata rate 当前显式为 0，不声称覆盖非零手续费
- 样本过滤：current-AI 固定 SHA、`504` 行、`55` eval_date；flat/base、AI allowed Top8、selected volume >1、25% floor
- 策略/归因口径：单向卫星，不反馈 A；真实 C9 trade 时间/价，FIFO close，broker10 open gate，逐日 MTM

## 结果

- 期末权益：C 分别 `7,107,237.40 / 335,987.10 / 496,594.90 / 150,862.00`
- 总收益：C 分别 `4,638.1583% / 123.9914% / 231.0633% / 0.5747%`
- 最大回撤：C 分别 `-53.7702% / -45.2253% / -57.8938% / -15.9232%`
- Sharpe：C 分别 `1.4492 / 0.6682 / 0.9366 / 0.1951`
- 总滑点：C 分别 `901,350 / 30,840 / 46,610 / 3,460`
- 总交易次数：C 分别 `1,018 / 439 / 433 / 56`
- 胜率：C 非零日胜率分别 `52.6316% / 49.1086% / 49.9069% / 53.4247%`
- 其他关键指标：收益保留 `118.9957% / 109.4628% / 110.7991% / 18.5313%`；B cumulative net PnL `1,110,606.40 / 16,078.10 / 33,781.20 / -3,789.60`；C 最长水下 `662 / 652 / 665 / 98` 日。

## A 基准对照

- A 期末权益：`5,996,631.00 / 319,909.00 / 462,813.70 / 154,651.60`
- A 总收益：`3,897.7540% / 113.2727% / 208.5425% / 3.1011%`
- A 最大回撤：`-55.3701% / -39.9820% / -55.1835% / -14.2479%`
- A Sharpe：`1.3963 / 0.6682 / 0.9400 / 0.3718`
- A 最长水下：`662 / 651 / 665 / 98` 日

## 运行与会计审计

- decision：`canary_pass=false`、`full_allowed=false`、`cost_stress_allowed=false`
- failed checks：`broker10_exceeded`、`return_retention_below_70`、`historical_drawdown_not_strictly_better`、`2022_drawdown_not_strictly_better`、`latest_drawdown_worse_over_1pp`、`2022_underwater_worse`、`2022_underwater_no_strict_improvement`
- bankrupt：四锚点均为 `0`
- reconciliation：max daily error `0`；terminal position/margin error `0`；terminal PnL error最大 `6.984919e-10`
- broker10：2020 最大 proposed `102.2194%`，触发 `1` 个 blocked lifecycle；其他起点 proposed 均低于 `100%`；所有 EOD broker10 均低于 `100%`

## 输出文件

- report：`outputs/stage137_current_c9_quality_one_way_satellite/report.md`
- summary：`summary.csv`
- orders：`candidate_orders.csv`、`replayed_orders.csv`
- daily：`satellite_daily.csv`
- quality：decision、input/AI/repeat/source/PIT/FIFO/margin/reconciliation/price evidence 与三张图

## 结论

- 本阶段结论：Stage137 1x canary 明确失败；按预声明关闭本路线，不运行 2x/3x 或 full，不救参。
- 是否进入下一步：否；独立 raw-data 复算和失败归因已经完成，Stage137 路线正式关闭。
- 下一步：只保留“同向风险叠加无法保护共同亏损路径”的机制证据，下一实验必须是未被证伪的结构性假设。

## 独立终审

- reviewer：`Leibniz`
- verdict：`APPROVE FAILURE AND CLOSE ROUTE`
- 严重度与置信度：`P0=0 / P1=0 / P2=4`，置信度 `99%`
- 独立复算：重哈希 `394` 个冻结源文件、合计 `460,713,937` bytes，漂移/软链接/缺失为 `0`；A/B/C 指标、`651` 笔 FIFO、margin、terminal 和 7 个失败 gate 均与产物一致。
- 失败机制：B 与 A 是同向加风险，不是对冲；四锚点主回撤窗日权益变化相关性分别 `0.9746 / 0.8090 / 0.8995 / 0.5102`，历史锚点最大回撤峰谷均为 `2022-07-15 -> 2023-07-05`。
- 终审文件：`.superpowers/sdd/task-4-canary-1x-review-1.md`

## 过拟合反思

- 运行前判断：中等但受控；selector 来自历史质量归因，但规则、25% 和 gate 在结果可见前冻结。
- 运行后判断：没有新增过拟合行为。
- 原因：结果失败后不改变参数或筛选条件，不继续搜索使其过关的变体。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：该具体 Stage137 路线无继续优化价值；失败归因仍有研究价值。
- 原因：三个历史起点虽增收，但两个 2022 起点回撤更差且水下不改善，最新起点收益保留仅 `18.53%`，核心目标没有成立。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为路线关闭
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不重复追加 `memory.md`
