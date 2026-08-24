# Stage021 P版多空对称1倍ATR逆向冲击过滤全周期门禁

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：2026-08-24 20:33（Asia/Shanghai）
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：基于P扩展空头对称过滤的单次全周期 A/C/P/Q 实验
- 是否重要突破：否；空头新增7条sizing拦截但没有改变任何实际交易或资金路径
- 是否触发A/B：是；A=正式基线，C=换月续开，P=N+多头ATR过滤，Q=P+空头ATR过滤

## 外部调研与判断

- 参考资料：继续采用 TA-Lib 官方 `TRANGE` 标准定义（https://ta-lib.org/functions/trange.html）；不变更ATR口径。
- 我的判断：空头对称规则具有明确结构——多头避免大跌日追多，空头避免大涨日追空；但这是P之后的同样本扩展，仍有高过拟合风险，只固定跑一次。

## 本次变更

- 新增脚本：`tools/stage021_p_symmetric_atr_shock_filter_full_period_acpq.py`
- 修改策略：新增默认关闭的 `enable_short_signal_atr_shock_filter=false`；开启后空头以 `信号日收-前收` 作为逆向幅度。P及既有版本默认路径不变。
- 删除脚本：无。
- 新增参数：`enable_short_signal_atr_shock_filter=false`。
- 修改参数：Q显式开启多头与空头过滤；共用固定 `period=5/multiplier=1.0/contexts=flat,reverse,rollover`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-05-29`。
- 账户规模：C9/15万固定口径。
- 成本口径：沿用Stage020；固定滑点门 `Q <= 对照105%`。
- 样本过滤：A/C/P逐值复用Stage020，只新跑Q一次。
- 基础风险：继续完整保留N/P的多空成交量风险缩放。
- 多头：`前收-信号日收 > 前5完整日ATR5` 时禁开。
- 空头：`信号日收-前收 > 前5完整日ATR5` 时禁开。
- 严格边界：等于1倍ATR允许；ATR严格排除信号日。
- 生效上下文：普通、反转、换月重开；所有加仓和C9 retry排除；历史不足/无效保持P。

## 预声明门禁

1. 身份门：A/C/P与Stage020逐值一致；只允许Q一次新运行；N的多空风险缩放配置必须保持。
2. 合同门：long/short开关均开启；period=5、multiplier=1；多头用跌幅、空头用涨幅；严格大于；被阻止前手数>0且之后=0；至少各命中1条多头和空头候选。
3. 晋级只看 `A_vs_Q` 与 `C_vs_Q`：收益不低于、DD恶化<=1pp、Sharpe非劣0.01、滑点<=105%、生存通过、broker100不恶化。
4. `P_vs_Q` 只做空头增量归因，不得替代A/C双门。
5. 任一晋级门失败即停止，不跑多周期、不扫ATR倍数/周期/方向/品种/年份；正式物料、master、production、订单API与CTP不触碰。

## 结果

- 唯一新运行：Q `1` 次；冻结 commit `b907562db36d38ca5e07c9b1eba8e3e5dd9e88c5`。A/C/P从Stage020结果 commit `ab3bfb55f8dbc8e3d56d3211dc930b01ead2507f` 逐值复用。
- 期末权益：`15,135,800.10`
- 总收益：`9990.5334%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.495411`
- 总滑点：`1,571,580`
- 总交易次数：`821`
- 胜率：`52.8467%`
- broker10峰值：`99.6724%`；超100% `0` 天；账户生存通过。
- 过滤诊断946条：多头483、空头463。Q共拦截14条sizing候选，其中多头7（继承P）、空头新增7；普通入口13、换月重开1、反转0。配置、方向、严格边界和置零合同均通过。
- 空头7次触发为 `2019-04-01 MA`、`2019-10-09 au`、`2020-03-02 cu/ru`、`2021-02-04 jm`、`2022-11-01/11 MA`，上涨幅度/ATR为 `1.0309~1.6800`。
- 但上述7个空头sizing候选在P的原始trade中本来就没有形成对应实际空头OPEN；Q虽更早置零，最终仍和P同为821条trade，2037日权益曲线逐点最大差0，全部指标完全一致。
- A/C/P的summary与2037日curve均与Stage020逐值一致；Q只新跑一次。
- Q相对A：仍为收益 `+1376.3907pp`、回撤改善 `11.3036pp`、Sharpe `+0.133181`、滑点比 `103.0146%`，但broker峰值比A恶化 `8.1774pp`，失败。
- Q相对C全部门通过；P_vs_Q形式门全通过只是因为完全相等，不代表空头过滤产生增量收益或防守效果。
- 独立 reviewer 对P/N继承、多空对称计算、14条合同和交易链做键级复算；确认14/14均未进入entry_risk/OPEN/trade_events，P/Q全部产物一致，最终 `blocker=0/non-blocker=0`。

## 输出文件

- summary：`artifacts/stage021/stage021_acpq_summary.csv`
- comparison：`artifacts/stage021/stage021_acpq_comparison.csv`
- curve：`artifacts/stage021/stage021_acpq_curve.csv`
- 逐条过滤诊断：`artifacts/stage021/stage021_full_q_signal_atr_shock.csv`
- 合同：`artifacts/stage021/stage021_full_q_atr_filter_contract_summary.csv`
- 决策：`artifacts/stage021/stage021_decision.json`
- 资金曲线：`artifacts/stage021/stage021_full_period_equity_acpq.png`

## 结论

- 本阶段结论：`stop_p_symmetric_atr_shock_filter_after_full_period`。空头逻辑正确命中7条候选，但这些候选原本就未成为P实际交易，Q没有任何组合层增量；同时正式A的broker门继续失败。
- 是否进入下一步：否。不跑多周期，不把P_vs_Q的机器等价“通过”解释成改善，不扫ATR参数或后置门以制造实际命中。
- 下一步：保留Q作为对称规则实现与负证据；若未来forward出现原本可成交、被空头ATR实际阻止的自然样本，再做只读观察。

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：是，高风险，但本次没有产生结果选择收益。
- 原因：新增空头分支只有7条候选且没有进入实际交易；若继续修改后置门、阈值或上下文寻找可成交命中，将成为明显的样本内挖掘。

## 继续价值反思

- 运行前判断：是，但只值得一次固定全周期验证。
- 运行后判断：否，当前没有继续历史优化价值。
- 原因：一次固定验证确认了实现语义，却没有形成任何组合层差异；多周期只会重复P，不能提供新增证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录Stage021空头候选被既有后置门覆盖。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`，不改根目录 `memory.md`。
