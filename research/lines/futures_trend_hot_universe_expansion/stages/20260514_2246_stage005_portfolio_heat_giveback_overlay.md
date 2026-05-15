# Stage005 / Stage270：组合层 Heat/Giveback 风险倍率最小回放

## 基本信息

- 时间：2026-05-14 22:46 CST
- 研究线：`futures_trend_hot_universe_expansion`
- 当前模式：day
- 是否触发 A/B：是，风险覆盖层可能与 Stage78-1 结合；本轮做最小 A vs C。
- 是否重要突破版本：否。结论为失败，不进入撮合级/引擎级回测。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage270_portfolio_heat_giveback_overlay.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage270_portfolio_heat_giveback_overlay_report_stage270_portfolio_heat_giveback_overlay_v1.md`
- Summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage270_portfolio_heat_giveback_overlay_summary_stage270_portfolio_heat_giveback_overlay_v1.json`

## 外部调研与判断

- 外部参考：趋势跟踪组合风险管理、commodity futures stress testing、portfolio heat 风险预算实践、vn.py/VeighNa CTA组合框架。
- 判断：组合级风险倍率有第一性原理价值，但必须避免复活 Stage128 已经反证过的持仓利润保护；本轮只做前一日组合权益状态驱动的日级资本倍率回放，不改 alpha 和交易信号。

## 候选假设

当组合在过去60日已经快速上涨，且相对20日高点出现明显回吐时，下一交易日整体风险倍率降到 `0.75` 或 `0.50`。如果这个规则是真正结构性的，它应该不只改善全周期最大回撤，还要在 Stage269 暴露的弱窗口独立回放中不明显伤害收益/Sharpe。

## A/C 预声明

- A：Stage78-1 `static18+fu` 原始日收益路径。
- C：A + `portfolio_heat_giveback_v1` 日级资本倍率。
- B：无。该模块是部署/风险覆盖层，单独交易没有意义。

## 预注册规则

```json
{
  "name": "portfolio_heat_giveback_v1",
  "heat_return_60_soft": 0.20,
  "heat_return_60_hard": 0.25,
  "giveback_20_soft": -0.03,
  "giveback_20_hard": -0.06,
  "soft_scale": 0.75,
  "hard_scale": 0.50
}
```

## 通过标准

- 全周期最大回撤改善，Sharpe 不明显下降。
- 2026独立回放不更差。
- Stage269 三个弱窗口中至少两个回撤改善，且收益不能明显恶化。
- 5x滑点下仍保持正权益。
- 若只改善全周期、但弱窗口独立回放失败，则不进入引擎级回测。

## 新增结果

### A基准路径

- 全周期：C 期末权益 `25,371,181.25` vs A `26,353,935`，少 `982,753.75`；收益差 `-196.5507pct`；最大回撤改善 `+4.3203pct`；Sharpe 提高 `+0.0799`；风险降档 `397`天，平均风险倍率 `0.8918`。
- 5x滑点：C 期末权益 `17,819,451.25` vs A `18,124,415`；仍为正，但收益低于A；最大回撤由 A `-67.2151%` 改为 C `-54.6536%`。
- 2026独立回放：C 期末权益 `2,775,412.5` vs A `1,969,895`，多 `805,517.5`；最大回撤改善 `+18.7654pct`，但 Sharpe 低 `-0.1016`。

### Stage269 弱窗口独立回放

- `stage269_full_aug_nov_2025`：C 期末权益 `531,495` vs A `2,641,290`，少 `2,109,795`；收益差 `-421.9590pct`；回撤不改善，Sharpe 差 `-0.1066`。
- `stage269_ag_peak_to_trough`：C 与 A 完全相同，无触发，无改善。
- `stage269_y_worst_63d`：C 期末权益 `2,304,350` vs A `4,002,310`，少 `1,697,960`；收益差 `-339.5920pct`；回撤不改善。
- `stage269_post_trough_recovery`：C 与 A 完全相同，无触发，无改善。
- `stage131_q2022_4_252d`：C 期末权益 `2,315,617.5` vs A `2,705,890`，少 `390,272.5`；收益差 `-78.0545pct`；回撤不改善。

### 判定

```json
{
  "promotion_decision": "fail_do_not_promote",
  "full_period_pass": true,
  "latest_2026_pass": true,
  "weak_window_dd_improved_count": 0,
  "weak_window_return_not_worse_count": 1,
  "slippage_5x_positive_equity_pass": true,
  "pass_minimal_gate": false,
  "next_step": "stop_this_overlay_shape"
}
```

修改回测结果：无。删除回测结果：无。

历史旧第78参考字段：期末权益 `1,610,900`、总收益 `705.45%`、最大回撤 `-54.93%`、Sharpe `0.661`、总滑点 `100`、总交易次数 `1000`。本轮为当前第78-1/50万口径的日级回放，不是旧口径复跑。

## 结论

- `portfolio_heat_giveback_v1` 不晋级，不做引擎级回测。
- 它在全周期看起来改善回撤/Sharpe，但在 Stage269 真实关注的弱窗口独立回放中明显牺牲恢复收益，尤其 `2025-08` 至 `2025-11` 少 `2,109,795`。
- 该失败说明：用短期组合权益热度/回吐来降风险，容易在趋势恢复段“没子弹”，与 Stage128 利润回吐失败的本质类似。

## 运行前过拟合反思

- 判断：不是过拟合。
- 原因：规则在运行前预声明，未按结果调阈值；且只是最小日级回放。

## 运行后过拟合反思

- 判断：继续优化这个形状会变成过拟合。
- 原因：全周期漂亮但目标弱窗口失败，若继续调 `20/25%`、`3/6%`、`0.75/0.50` 这类阈值，就是围绕失败窗口找舒适点。

## 运行前继续价值反思

- 判断：是。
- 原因：能快速验证 Stage269 后续方向是否值得进入更昂贵的引擎级回测。

## 运行后继续价值反思

- 判断：这个 overlay 形状不值得继续；组合层风险研究仍有价值。
- 原因：失败不是执行误差，而是机制问题：权益回吐后降风险会切掉恢复段。后续若继续组合层风险，应转向账户层资金分层/实盘额度制度，或已有 `balanced_tranche_v1` 日更链路，而不是继续调日内风险倍率。

## TODO

1. 停止 `portfolio_heat_giveback_v1`。
2. 不用该规则去拯救 `y.DCE` 或 `ag.SHFE`。
3. 热门扩池线暂时收束：正式池不变，`y/ag`保留研究结论但不再推进。
4. 若继续风险治理，应回到 `futures_trend_risk_overlay` 的账户层 `balanced_tranche_v1`，而不是在本线继续调风险倍率。
