# Stage021 P版多空对称1倍ATR逆向冲击过滤全周期门禁

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：2026-08-24 20:33（Asia/Shanghai）
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：基于P扩展空头对称过滤的单次全周期 A/C/P/Q 实验
- 是否重要突破：否，结果未知
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

## 结果（运行后填写）

- 期末权益：待回测
- 总收益：待回测
- 最大回撤：待回测
- Sharpe：待回测
- 总滑点：待回测
- 总交易次数：待回测
- 胜率：待回测

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：待填写。
- 原因：P只有7次多头触发，本次再增加空头小样本分支；少量事件可能经复利放大，不能把单次全周期改善直接视为稳定alpha。

## 继续价值反思

- 运行前判断：是，但只值得一次固定全周期验证。
- 运行后判断：待填写。
- 原因：对称规则可以检验空头逆向冲击是否具有独立防守价值；若A/C双门失败就停止。

## 合入建议

- 是否更新本线 `LINE.md`：结果后更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：结果后只追加 `back_log.md`，不改根目录 `memory.md`。
