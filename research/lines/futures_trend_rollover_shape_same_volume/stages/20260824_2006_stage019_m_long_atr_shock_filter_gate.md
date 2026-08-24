# Stage019 M版多头信号日ATR冲击过滤全周期门禁

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：2026-08-24 20:06（Asia/Shanghai）
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：固定规则的单次全周期 A/C/M/O 实验前门禁
- 是否重要突破：否，结果未知
- 是否触发A/B：是；A=正式基线，C=换月续开，M=当前研究基线，O=M+本次过滤

## 外部调研与判断

- 参考资料：TA-Lib 官方 `TRANGE` 定义（https://ta-lib.org/functions/trange.html）；TA-Lib ATR 实现以首段 True Range 的简单平均初始化。
- 我的判断：过滤“开多当日出现异常大跌”有行为金融和执行质量上的直觉，但阈值来自同一历史样本上的连续迭代，先验过拟合风险高。只允许固定 `ATR5 × 2.0` 跑一次，不扫描周期、倍率、方向、品种或年份。

## 本次变更

- 新增脚本：`tools/stage019_m_long_atr_shock_filter_full_period_acmo.py`
- 修改脚本：策略新增只读关闭默认的多头ATR冲击过滤；回测引擎导出独立诊断帧。
- 删除脚本：无
- 新增参数：`enable_long_signal_atr_shock_filter=false`、`long_signal_atr_shock_period=5`、`long_signal_atr_shock_multiplier=2.0`、三类入口上下文。
- 修改参数：O臂显式开启过滤；M的三倍高量放大、半量低量缩减规则原样保留。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage017 全周期固定区间。
- 账户规模：沿用 A/C/M 的 C9/15万口径。
- 成本口径：沿用 Stage017，并使用固定成本门 `O滑点 <= 对照的105%`。
- 样本过滤：只跑 O 一次；A/C/M逐值复用 Stage017，不重跑。
- 策略/归因口径：信号日跌幅=`前收-信号日收`；ATR5=严格排除信号日、由此前5个完整交易日 True Range 简单平均；严格 `跌幅 > 2×ATR5` 才阻止开多，等于阈值允许。
- 生效范围：只含多头 `flat_entry/reverse_entry/rollover_reopen`；空头、所有加仓、C9止损重试均排除；历史不足或无效时保持M行为。

## 预声明门禁

1. 合同门：参数必须精确为5和2.0；诊断必须逐条符合严格大于；至少实际阻止1个信号；被阻止前手数必须大于0、过滤后必须为0；排除路径不得改变手数。
2. 晋级只看 `A_vs_O` 与 `C_vs_O`：收益不得低于对照；最大回撤恶化不超过1个百分点；Sharpe非劣0.01；滑点不超过105%；账户生存；broker100指标不恶化。
3. `M_vs_O` 仅做增量归因，不得替代正式A和换月C双门。
4. 任一晋级门失败即停止，不跑多周期，不救参；正式物料、master、生产配置、订单API和CTP均不触碰。

## 结果

- 唯一新运行：O `1` 次；冻结 commit `9b5beacbc808ca1376d1b13f2344e8ec10d1e1f6`。A/C/M 从 Stage017 结果 commit `89c042d9e82900580ae8046dd399267436a4c15e` 逐值复用。
- 期末权益：`14,293,257.00`
- 总收益：`9428.8380%`
- 最大回撤：`-54.2470%`
- Sharpe：`1.406198`
- 总滑点：`1,634,290`
- 总交易次数：`826`
- 胜率：`52.7496%`
- broker10峰值：`91.0591%`；超100% `0` 天；账户生存通过。
- 诊断共 `945` 条：多头 `482`（普通首次/反转入口归并为 `flat_entry` 465，换月重开17），空头旁路 `463`。所有482条有效多头候选均未超过门槛，实际拦截 `0`。
- 最接近门槛的是 `2024-03-14 lc2407.GFEX`：跌幅 `6700`、ATR5 `4060`，比值 `1.650246 < 2.0`；因此未拦截符合严格合同。
- O与M的2037日 `account_equity` 逐点完全一致，最大差 `0`；期末指标、滑点、交易数和826条trade也一致。
- O相对A/C仍复现M的优点：收益 `+814.6953/+636.5941pp`，回撤改善 `1.9599/2.7406pp`，Sharpe `+0.043967/+0.043529`；但滑点比 `107.1251%/107.7175%`，均超过105%门。
- 独立 reviewer 复算 `expected_block_count=0`、实际 `blocked_count=0`、O/M curve最大差0，并检查入口隔离、A/C/M复用、决策和生产边界；结论 `blocker=0/non-blocker=0`。

## 输出文件

- summary：`artifacts/stage019/stage019_acmo_summary.csv`
- comparison：`artifacts/stage019/stage019_acmo_comparison.csv`
- curve：`artifacts/stage019/stage019_acmo_curve.csv`
- 逐条过滤诊断：`artifacts/stage019/stage019_full_o_long_signal_atr_shock.csv`
- 合同：`artifacts/stage019/stage019_full_o_atr_filter_contract_summary.csv`
- 决策：`artifacts/stage019/stage019_decision.json`
- 资金曲线：`artifacts/stage019/stage019_full_period_equity_acmo.png`

## 结论

- 本阶段结论：`stop_m_long_atr_shock_filter_after_full_period`。实现和诊断合同正确，但全周期0命中，规则没有改变M；同时A/C成本门继续失败。
- 是否进入下一步：否。不跑多周期，不降低2倍阈值、不改变ATR周期、不扩展空头或加仓、不按年份/品种救参。
- 下一步：保留研究代码和负证据；若未来forward自然出现 `>2×ATR5` 的多头候选，可只读观察，不能用未来结果反向修改本次历史结论。

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：是，高风险，但本次未造成样本内收益选择。
- 原因：固定条件0命中，O与M完全一致；继续降低阈值寻找命中才会把本次从证伪变成明显的数据挖掘。

## 继续价值反思

- 运行前判断：是，但只值得完成一次固定全周期证伪。
- 运行后判断：否，当前历史数据上没有继续优化价值。
- 原因：规则与既有量价风险分配不是完全同一输入，因此完成一次固定证伪有价值；但0命中且A/C成本门失败，继续扫参不能增加可穿越周期的证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录Stage019负结论。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`；不更新根目录 `memory.md`。
