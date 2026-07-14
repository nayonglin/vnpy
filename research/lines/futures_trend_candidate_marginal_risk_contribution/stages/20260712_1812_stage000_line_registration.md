# Stage000 候选边际风险贡献研究线立项

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：`day`
- 记录时间：`2026-07-12 18:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：研究线注册与边界冻结
- 是否重要突破：否
- 是否触发A/B：是；若数据和实现可行，Stage001 仅做 A/C 风险 sizing canary

## 当前判断

- 过拟合：否。假设来自旧协方差线的语义缺口，不是按 Stage137 某个品种或日期修补。
- 继续价值：有，但只限一次真正日期对齐、同日批量感知、候选 leave-one-out 边际风险贡献验证。
- 停止边界：不得回到绝对 inflation，不得扫描窗口、阈值、floor/ceil、minimum lot 或 2022 品种黑名单。

## 外部调研后的口径修正

- 初始登记的 `Var(full)-Var(without i)` 属于 raw incremental variance，多个候选下不严格可加，已在任何回测结果可见前否决。
- 正式候选改为标准可加总风险贡献：`MRC_i=(Σx)_i/sigma_p`、`RC_i=x_i*MRC_i`；自身分量 `IC_i=x_i^2*Σ_ii/sigma_p`，仅当 `RC_i>IC_i>0` 时按 `IC_i/RC_i` 缩手。
- 协方差估计器冻结为 `sklearn.covariance.LedoitWolf`；不扫描 shrinkage 或替换估计器。
- 资料：Alexander/Fabozzi 2026 leave-one-out RC decomposition、Roncalli risk budgeting、Ledoit/Wolf 2004、scikit-learn 官方实现、pysystemtrade GitHub。

## 本阶段结果

- 本阶段未运行回测。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数和胜率均不适用。
- 下一步先完成外部一手资料/GitHub 调研和仓库数据/引擎可行性审计，再形成 Stage001 预声明。
