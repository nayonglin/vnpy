# Stage018 多空对称三倍放大与半量缩减风险全周期反证

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：研究分支全周期 A/C/M/N 对照；A/C/M 复用 Stage017，N 仅新跑一次
- 记录时间：2026-08-24 19:42（Asia/Shanghai）
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：用户确认后的固定规则反证
- 是否重要突破：否；N 路径改善明显，但正式 A/C 双基线成本门失败
- 是否触发A/B：是；运行前合同、身份、正式门和停止条件已冻结
- 候选冻结提交：`f1ac2ef6b95a8e69a6d45c59a4186403079bafaf`

## 外部调研与判断

- 参考资料：CME 对成交量的定义强调参与度和流动性，不把成交量本身解释为方向；pysystemtrade 将预测信号与风险/仓位缩放分层。
- 我的判断：N 的多空对称实现消除了 M 的方向旁路，但依旧是用同一历史样本继续改风险覆盖面，并未增加外生信息源。收益、回撤和 Sharpe 的显著改善只能视为历史路径证据，不能覆盖预先声明的成本失败。

## 本次变更

- 新增脚本：`tools/stage018_symmetric_triple_volume_with_low_volume_discount_full_period_acmn.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`，允许 `long_only=False` 时空头进入低量折减分支。
- 新增测试：Stage018 runner 合同测试；空头低量、空头高量和严格边界测试。
- 新增参数：无。
- 修改参数：N 固定 `directional_30d_risk_adjust_long_only=False`；高量阈值/倍率 `3.0/1.5`，低量阈值/倍率 `0.5/0.5`。
- 删除参数：无。
- 修改/删除历史回测结果：无；A/C/M 摘要和各 `2037` 点资金曲线与 Stage017 逐值一致。

## 回测参数

- 数据区间：`2018-01-01 -> 2026-05-29`
- 账户规模：`150,000`
- 成本口径：沿用正式 A/C/M 相同真引擎、合约乘数、滑点与手续费口径
- 样本过滤：不扫描年份、品种或起点；全周期一次运行
- 策略口径：
  - 多头 30 日上涨或空头 30 日下跌，且最近 10 日量严格大于前 10 日量的 `3.0` 倍时风险 `×1.5`。
  - 两方向最近 10 日量严格小于前 10 日量的 `0.5` 倍时风险 `×0.5`，不要求 30 日方向一致。
  - 其他为 `×1.0`；等号不命中；无效或不足历史 fail closed 为 `×1.0`。

## 结果

| 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 | 超100%天数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A 正式 | 13,071,214.10 | 8614.1427% | -56.2069% | 1.362230 | 1,525,590 | 808 | 52.5841% | 91.4950% | 0 |
| C 换月续接 | 13,338,365.80 | 8792.2439% | -56.9876% | 1.362669 | 1,517,200 | 825 | 52.6812% | 100.4112% | 1 |
| M 仅多头 | 14,293,257.00 | 9428.8380% | -54.2470% | 1.406198 | 1,634,290 | 826 | 52.7496% | 91.0591% | 0 |
| N 多空对称 | 15,573,747.90 | 10282.4986% | -46.5442% | 1.468868 | 1,671,490 | 827 | 52.4673% | 87.3320% | 0 |

- N 相对 A：收益 `+1668.3559pp`、回撤改善 `9.6628pp`、Sharpe `+0.106637`，但滑点为 A 的 `109.5635%`，超过固定 `105%` 上限。
- N 相对 C：收益 `+1490.2547pp`、回撤改善 `10.4435pp`、Sharpe `+0.106198`，但滑点为 C 的 `110.1694%`，超过固定上限。
- N 相对 M：收益 `+853.6606pp`、回撤改善 `7.7029pp`、Sharpe `+0.062670`、滑点比 `102.2762%`；该诊断对照全门通过，但不替代 A/C 正式双基线。
- `377` 条风险诊断：多头高量/低量/基准 `17/4/281`，空头高量/低量/基准 `4/2/69`。严格阈值、应用标记、倍率和目标风险金额逐行合同通过。
- 空头实际改变风险的 6 条均为普通开仓：4 条高量 `×1.5`、2 条低量 `×0.5`；本次两条空头低量自然样本恰好也都 30 日同向，非同向可用性由底层代码和单测证明。

## 输出文件

- summary：`artifacts/stage018/stage018_acmn_summary.csv`
- comparison：`artifacts/stage018/stage018_acmn_comparison.csv`
- daily curve：`artifacts/stage018/stage018_acmn_curve.csv`
- N risk diagnostics：`artifacts/stage018/stage018_full_n_entry_risk.csv`
- N trades/events：`artifacts/stage018/stage018_full_n_trades.csv`、`stage018_full_n_trade_events.csv`
- quality：`artifacts/stage018/stage018_full_n_risk_split_contract_summary.csv`
- decision：`artifacts/stage018/stage018_decision.json`
- report image：`artifacts/stage018/stage018_full_period_equity_acmn.png`

## 验证与独立评审

- `68` 个相关单测通过；策略与 Stage018 runner `py_compile` 通过，`git diff --check` 通过。
- curve 独立复算期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率和 broker 指标，与 summary 最大数值误差 `1.82e-12`。
- A/C/M 摘要九项核心指标及各 `2037` 点资金曲线与 Stage017 逐值一致；decision provenance 记录 N 独立运行次数为 `1`。
- 独立 reviewer 确认规则、风险合同、比较表、停止决策、无未来数据和无生产副作用正确；首轮唯一 blocker 为缺中文结果记录，本文件用于关闭该记录阻断。

## 结论

- 决策：`stop_symmetric_triple_volume_with_low_volume_discount_after_full_period`。
- `A_vs_N` 与 `C_vs_N` 均仅成本门失败，但预声明门不能因其他指标表现好而事后放宽。
- 不进入多周期，不扫描成交量阈值、风险倍率、方向、品种、年份或起点，不晋升，不发布正式物料，不修改 `master`、production、CTP 或订单提交链路；订单/撤单 API `0/0`。

## 过拟合反思

- 运行前判断：是，风险高；这是同一历史样本上的连续风险倍率迭代。
- 运行后判断：仍是高风险；空头仅 `4` 次高量和 `2` 次低量改变风险，复利路径可放大极少数事件，不能把全周期改善当成稳定 alpha。
- 原因：规则没有新增独立信息源，而且固定 A/C 成本门已失败；若继续围绕 `3.0/0.5/1.5/0.5` 扫描就是明确的后验救参。

## 继续价值反思

- 运行前判断：有，但仅限一次性对称实现验证。
- 运行后判断：该规则无继续历史优化或自动多周期价值；保留代码、产物和负证据有价值，等待未参与设计的 forward 样本才可能重开审计。
- 下一步：继续固定换月 C 的 forward shadow；N 只作为研究归因版本保存，不进入正式策略。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：否，line_id 和归属未变化。
- 追加根目录 `back_log.md`：是；不追加根目录 `memory.md`，因为不是重要突破或正式候选。
