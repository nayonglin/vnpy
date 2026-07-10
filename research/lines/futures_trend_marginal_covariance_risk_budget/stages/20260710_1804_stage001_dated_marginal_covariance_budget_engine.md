# Stage001 日期对齐边际协方差风险预算 A/C 真引擎

- line_id：`futures_trend_marginal_covariance_risk_budget`
- 当前模式：`day`
- 记录时间：`2026-07-10 18:10 CST`
- 工作区/分支：当前共享工作区；研究目录隔离
- 阶段性质：最小 A/C 真引擎验证
- 是否重要突破：否；独立 review 后关闭
- 是否触发A/B：是；A=当前 C9，C=A+日期对齐边际协方差风险预算

## 外部调研与判断

- 参考资料：Euler marginal risk contribution、Active Risk Budgeting、Ledoit-Wolf、pysystemtrade 组合构建。
- 我的判断：边际风险必须只看候选给现有组合增加的协方差风险；上一版绝对 inflation 不满足该语义。本阶段冻结一次，不扫参数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_marginal_covariance_risk_budget/tools/stage001_dated_marginal_covariance_budget_engine.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`63` 个日期对齐收益、Ledoit-Wolf、解析边际缩放、同日候选批量感知、至少 1 手。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01 -> 2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：当前 C9 真引擎滑点、手续费、broker10 保证金和下一真实开盘代理。
- 样本过滤：当前官方 AI 月池；A/C eligibility 归一化一致。
- 策略口径：正式 candidate planning 完成后缩手；不改退出、止损重试、换月、已有仓或加仓。

## 结果

- A：期末权益 `5,996,631.00`；总收益 `3897.7540%`；最大回撤 `-55.3701%`；Sharpe `1.3967`；总滑点 `759,970.00`；总交易 `641`；非零日胜率 `52.8302%`；逐笔胜率 `45.8716%`。
- C：期末权益 `3,259,562.40`；总收益 `2073.0416%`；最大回撤 `-56.0209%`；Sharpe `1.2653`；总滑点 `419,580.00`；总交易 `634`；非零日胜率 `52.6519%`；逐笔胜率 `44.5483%`。
- 收益保留：`0.5319`。
- 全周期/2022/主压力窗回撤变化：`-0.6508` / `-4.2488` / `4.1617`pp。
- broker10 峰值变化：`5.8149`pp。
- semantics_ok：`False`；performance_ok：`False`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_report_stage001_dated_marginal_covariance_budget_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_ac_summary_stage001_dated_marginal_covariance_budget_engine_v1.csv`
- stress：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_stress_summary_stage001_dated_marginal_covariance_budget_engine_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_a_daily_stage001_dated_marginal_covariance_budget_engine_v1.csv.gz` / `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_c_daily_stage001_dated_marginal_covariance_budget_engine_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_marginal_audit_stage001_dated_marginal_covariance_budget_engine_v1.csv` / `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_ai_parity_stage001_dated_marginal_covariance_budget_engine_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_marginal_covariance_risk_budget/outputs/stage001_dated_marginal_covariance_budget_engine/marginal_cov_budget_stage001_dated_marginal_covariance_budget_engine_equity_drawdown_stress_stage001_dated_marginal_covariance_budget_engine_v1.png`

## 结论

- 本阶段结论：`stage001_stop_no_parameter_rescue`。
- 是否进入下一步：否；关闭本线，不做逐半年。
- 下一步：不扫窗口、阈值、floor、整数手、品种或日期；换结构必须另开研究线。

## 独立 review

- 结论：`P0=0/P1=1/P2=3`。
- P1：同日此前 accepted candidate 使用计划手数，没有先经过当日正式 `forced_margin_deleverage` preview 的最终目标手数。`2020-05-11` CF 计划 `6` 手但正式目标为 `2` 手，随后 rb 仍按 CF `6` 手计算。
- P2：A/C/官方 AI 独立复核均为 `504` 行且归一化一致；`288` 个 available 样本均为严格 `63` 个截至信号日收益，未来泄漏 `0`；解析公式和整数手逐行成立，但它不是严格 Euler RC；固定压力窗是局部重置，未展示入窗前 carry-in。
- 可信边界：绩效数值和失败方向可信；“全部语义通过”不可信，因此 `semantics_ok` 从 `True` 修正为 `False`。

## 过拟合反思

- 运行前判断：低到中等；一次冻结结构，不按 2022 品种/方向/日期调规则。
- 运行后判断：否；一次冻结验证后直接接受失败，没有按结果救参数。
- 原因：2022 是预声明压力窗，不是拟合标签。

## 继续价值反思

- 运行前判断：有价值；直接修复上一版两个 P1，并针对组合相关风险而不删除 AI 机会。
- 运行后判断：本形状无继续价值。
- 原因：收益保留只有 `53.19%`，全周期和 2022 回撤、broker10 均恶化，并存在最终目标手数 P1；实现复杂 preview 也不能合理预期跨越全部绩效缺口。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，登记本线关闭与 P1。
- 是否追加根目录 `memory.md/back_log.md`：按 A/B 规范追加 `back_log.md`；不更新 `memory.md`。
