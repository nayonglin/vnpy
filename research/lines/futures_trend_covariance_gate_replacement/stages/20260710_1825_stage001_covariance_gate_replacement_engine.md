# Stage001 相关门替换 A/B/C 真引擎

- line_id：`futures_trend_covariance_gate_replacement`
- 当前模式：`day`
- 记录时间：`2026-07-10 18:25 CST`
- 阶段性质：一次冻结 A/B/C 真引擎；独立审查后因执行语义 P1 作废
- 是否重要突破：否
- 是否触发 A/B：是；A=当前 C9，B=关闭旧相关门，C=边际协方差替换旧门

## 外部调研与判断

- 参考边际风险贡献、Riskfolio-Lib 和趋势组合相关风险资料。
- 开始前判断：不属于过拟合，检验的是叠加与替换的结构差异；有继续价值。
- 结束后判断：没有过拟合；本线无继续价值。两阶段 forced-margin preview 虽属语义修复，但与 marginal 手数存在循环依赖，且缺陷实现已同时远离全部绩效门槛。

## 本次变更

- 新增脚本：`research/lines/futures_trend_covariance_gate_replacement/tools/stage001_covariance_gate_replacement_engine.py`。
- 新增只读归因：`research/lines/futures_trend_covariance_gate_replacement/tools/stage001_covariance_gate_replacement_attribution.py`。
- 新增参数：C 关闭旧 `20` 日同向相关门并启用 `63` 日日期对齐边际协方差；B 只关闭旧门。
- 修改/删除正式参数：无；未改官方配置、实盘、CTP、邮件或 launchd。

## 结果

| 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 滑点 | 交易次数 | 非零日胜率 | 逐笔胜率 | broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| B | 5,329,186.30 | 3452.7909% | -59.0163% | 1.3559 | 746,170 | 643 | 52.7054% | 46.8085% | 95.7795% |
| C 缺陷实现 | 3,787,533.70 | 2425.0225% | -55.7874% | 1.2924 | 509,470 | 638 | 52.7483% | 44.2724% | 92.2180% |

- 收益保留：`0.6222`。
- C-A 全周期/2022/固定压力窗回撤变化：`-0.4173/-4.3359/-0.4173pp`。
- C-A broker10：`+3.8782pp`。
- AI：三臂均 `504` 行、`55` 个 eval_date、归一化 hash `df020c940d576868`。
- C 协方差 available `288`，严格 63 日、未来违规 `0`；这些不足以消除执行顺序 P1。

## 独立 review

- `P0=0/P1=1/P2=3`。
- P1：前序同日候选使用 accepted plan 手数，没有先经过当日正式 forced-margin 最终目标 preview。`2020-05-11` CF `6 -> 2` 手例证直接污染后续 rb 协方差。
- P2：压力窗使用局部 HWM，A/B/C 入窗 carry-in 回撤分别约 `0%/-24.9766%/-9.3943%`；公式不是严格 Euler RC；本线最初缺 stage 记录和源码/config hash。
- A/B 数值可信；C 对缺陷实现的描述值可信；C 对预声明最终目标量 replacement 的估计无效。

## 结论

- 决策：`invalid_semantics_and_close_no_rescue`。
- 不做逐半年、不晋级、不做参数补救，也不实现两阶段 preview 后复跑。
- 后续转 `futures_trend_stage013_current_ai_revalidation`。

## 输出

- report：`research/lines/futures_trend_covariance_gate_replacement/outputs/stage001_covariance_gate_replacement_engine/cov_gate_replacement_stage001_covariance_gate_replacement_engine_report_stage001_covariance_gate_replacement_engine_v1.md`
- summary：`research/lines/futures_trend_covariance_gate_replacement/outputs/stage001_covariance_gate_replacement_engine/cov_gate_replacement_stage001_covariance_gate_replacement_engine_summary_stage001_covariance_gate_replacement_engine_v1.csv`
- chart：`research/lines/futures_trend_covariance_gate_replacement/outputs/stage001_covariance_gate_replacement_engine/cov_gate_replacement_stage001_covariance_gate_replacement_engine_equity_drawdown_stress_stage001_covariance_gate_replacement_engine_v1.png`
