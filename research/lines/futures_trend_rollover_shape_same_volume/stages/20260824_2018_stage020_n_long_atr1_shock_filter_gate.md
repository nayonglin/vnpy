# Stage020 N版多头信号日1倍ATR冲击过滤全周期门禁

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：2026-08-24 20:18（Asia/Shanghai）
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：纠正基线与阈值后的固定规则单次全周期 A/C/N/P 实验
- 是否重要突破：否；P相对C通过但相对正式A的broker峰值门失败
- 是否触发A/B：是；A=正式基线，C=换月续开，N=多空对称成交量风险缩放，P=N+多头ATR过滤

## 外部调研与判断

- 参考资料：继续采用 TA-Lib 官方 `TRANGE` 标准定义（https://ta-lib.org/functions/trange.html），ATR5为此前5个完整交易日TR的简单平均。
- 我的判断：P纠正了上一阶段误用M和2倍门槛的问题；但1倍ATR会比2倍更频繁命中，且仍是同一历史样本上的连续条件迭代，过拟合风险高。只允许固定参数跑一次，不扫倍数、周期、方向、品种或年份。

## 本次变更

- 新增脚本：`tools/stage020_n_long_atr_shock_filter_full_period_acnp.py`
- 修改策略：无；复用Stage019已参数化、默认关闭的ATR过滤能力。
- 删除脚本：无；O作为历史误解实验保留，不覆盖。
- 新增参数：无生产参数；P实验显式设置 `ATR period=5`、`multiplier=1.0`。
- 修改参数：研究基线由M纠正为N；ATR门槛由2倍纠正为1倍。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-05-29`。
- 账户规模：C9/15万固定口径。
- 成本口径：沿用Stage018/019；固定成本门 `P滑点 <= 对照105%`。
- 样本过滤：A/C/N逐值复用Stage018，只新跑P一次。
- N风险缩放：多头和空头均参与；方向同向且最近10日量严格大于前10日3倍时风险 `×1.5`；最近10日量严格小于前10日0.5倍时风险 `×0.5`；其余 `×1.0`。
- P新增过滤：只对多头 `flat_entry/reverse_entry/rollover_reopen`；信号日跌幅=`前收-信号日收`；ATR5严格排除信号日；严格 `跌幅 > 1×ATR5` 阻止开仓，等于允许。
- 排除：空头不做跌幅过滤；所有加仓、C9 retry不变；历史不足/无效时保持N。

## 预声明门禁

1. 身份门：A/C/N必须与Stage018逐值一致；只允许P一次新真引擎运行；P运行配置必须保持 `directional_30d_risk_adjust_long_only=false`。
2. 合同门：period=5、multiplier=1.0；严格大于；被阻止前手数>0、之后=0；等于门槛、空头和排除上下文不得被阻止；至少实际阻止1笔。
3. 晋级只看 `A_vs_P` 与 `C_vs_P`：收益不得低于对照；最大回撤恶化不超过1个百分点；Sharpe非劣0.01；滑点不超过105%；账户生存；broker100不恶化。
4. `N_vs_P` 仅做增量归因，不得替代A/C正式门。
5. 任一晋级门失败即停止，不跑多周期、不救参；正式物料、master、production、订单API与CTP均不触碰。

## 结果

- 唯一新运行：P `1` 次；冻结 commit `b9578feb30545566b7c5caacc164c981dabaf027`。A/C/N从Stage018结果 commit `f1255875ee2a56024e241f4850ab9dc2be26425f` 逐值复用。
- 期末权益：`15,135,800.10`
- 总收益：`9990.5334%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.495411`
- 总滑点：`1,571,580`
- 总交易次数：`821`
- 胜率：`52.8467%`
- broker10峰值：`99.6724%`；超100% `0` 天；账户生存通过。
- 过滤诊断 `946` 条：多头候选483、空头旁路463；7条多头sizing候选被置0，其中普通入口6、换月重开1、反转0。严格阈值与手数合同全部通过。
- 7次触发：`2020-04-17 au`、`2021-05-26 AP`、`2022-01-04 OI`、`2022-03-08 rb`、`2024-03-14 lc`、`2025-02-13 fu`换月、`2026-02-02 OI`；跌幅/ATR为 `1.0451~1.6502`。
- A/C/N的summary与2037日curve均和Stage018逐值一致，最大差0；P只新跑一次。
- P相对A：收益 `+1376.3907pp`、回撤改善 `11.3036pp`、Sharpe `+0.133181`、滑点比 `103.0146%`；但broker10峰值从 `91.4950%` 升至 `99.6724%`，恶化 `8.1774pp`，正式A的broker不恶化门失败。
- P相对C：收益 `+1198.2895pp`、回撤改善 `12.0843pp`、Sharpe `+0.132742`、滑点比 `103.5842%`、broker峰值改善 `0.7388pp`，全部门通过。
- P相对N：收益减少 `291.9652pp`，回撤改善 `1.6408pp`、Sharpe提高 `0.026543`、滑点降至约 `94.02%`，但broker峰值恶化 `12.3404pp`；收益门与broker不恶化门失败。
- 独立 reviewer 复算N配置、ATR合同、7次触发、A/C/N复用、P指标和三组门禁；修复一处结果页头文案后最终 `blocker=0/non-blocker=0`。

## 输出文件

- summary：`artifacts/stage020/stage020_acnp_summary.csv`
- comparison：`artifacts/stage020/stage020_acnp_comparison.csv`
- curve：`artifacts/stage020/stage020_acnp_curve.csv`
- 逐条过滤诊断：`artifacts/stage020/stage020_full_p_long_signal_atr_shock.csv`
- 合同：`artifacts/stage020/stage020_full_p_atr_filter_contract_summary.csv`
- 决策：`artifacts/stage020/stage020_decision.json`
- 资金曲线：`artifacts/stage020/stage020_full_period_equity_acnp.png`

## 结论

- 本阶段结论：`stop_n_long_atr_shock_filter_after_full_period`。P相对C完整通过，但相对正式A的broker峰值风险恶化；A/C双门未同时通过，不能晋级。
- 是否进入下一步：否。不自动跑多周期，不因相对C通过而覆盖正式A失败，不扫ATR倍数/周期/方向/品种/年份救参。
- 下一步：保留P及7次触发为研究证据；只有用户明确要求额外诊断时再做固定多周期，但不得据此改变本次正式晋级失败结论。

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：是，高风险。
- 原因：只有7次触发，却通过复利路径显著改变最终指标和broker峰值；小样本结果对路径依赖很强，不能证明跨周期稳定性。继续扫参数会进一步放大选择偏差。

## 继续价值反思

- 运行前判断：是，但只值得一次固定全周期验证。
- 运行后判断：否，当前没有继续历史优化价值。
- 原因：一次固定证伪回答了P相对C有改善、但仍不能穿越正式A的broker边界；继续历史调参没有第一性原理上的新增信息。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录Stage020结论。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`；不改根目录 `memory.md`。
