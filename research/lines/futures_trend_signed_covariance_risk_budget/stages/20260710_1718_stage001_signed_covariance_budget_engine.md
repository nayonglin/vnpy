# Stage001 方向协方差组合风险预算 A/C 真引擎

- line_id：`futures_trend_signed_covariance_risk_budget`
- 当前模式：`day`
- 记录时间：`2026-07-10 17:18 CST`
- 工作区/分支：当前共享工作区；研究目录隔离
- 阶段性质：最小 A/C 真引擎验证
- 是否重要突破：否；独立 review 后关闭
- 是否触发A/B：是；A=当前 C9，C=A+方向协方差风险预算

## 外部调研与判断

- 参考资料：AQR managed futures、Active Risk Budgeting、pysystemtrade position sizing/portfolio correlation。
- 我的判断：不再修 AI 排名，改为保留机会并治理组合相关风险；当前 C9 已有相关性门控，新增层必须用真实结果证明增量价值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_signed_covariance_risk_budget/tools/stage001_signed_covariance_budget_engine.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：配置 `lookback=63`、`min_observations=32`、Ledoit-Wolf、只降不升、至少保留 1 手；独立审计确认正式 AM41 下实际只有 40 个收益观测。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前 C9 真引擎滑点、手续费与 broker10 保证金口径。
- 样本过滤：当前官方 AI 月池；A/C 归一化 eligibility 完全一致。
- 策略/归因口径：只在 flat_entry 正式相关性门控后缩放候选手数；止损重试、退出、加仓、换月不变。

## 结果

- A 期末权益：`5,996,631.00`；总收益 `3897.7540%`；最大回撤 `-55.3701%`；Sharpe `1.3967`；总滑点 `759,970.00`；总交易次数 `641`；非零日胜率 `52.8302%`；逐笔胜率 `45.8716%`。
- C 期末权益：`4,699,250.60`。
- C 总收益：`3032.8337%`。
- C 最大回撤：`-56.1133%`。
- C Sharpe：`1.3293`。
- C 总滑点：`614,710.00`。
- C 总交易次数：`639`。
- C 非零日胜率：`53.3659%`；逐笔胜率 `44.9231%`。
- 其他关键指标：收益保留 `0.7781`；回撤变化 `-0.7432`pp；Sharpe 变化 `-0.0674`；broker10 峰值变化 `7.3372`pp。
- 语义审计：局部 transform 只减不增且不归零为 `True`；63 日窗口兑现为 `False`（实际 `40 -> 40`）；候选边际风险语义兑现为 `False`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_report_stage001_signed_covariance_budget_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_ac_summary_stage001_signed_covariance_budget_engine_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_a_daily_stage001_signed_covariance_budget_engine_v1.csv.gz` / `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_c_daily_stage001_signed_covariance_budget_engine_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_covariance_audit_stage001_signed_covariance_budget_engine_v1.csv` / `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_signed_covariance_risk_budget/outputs/stage001_signed_covariance_budget_engine/signed_cov_budget_stage001_signed_covariance_budget_engine_ai_parity_stage001_signed_covariance_budget_engine_v1.csv`

## 结论

- 本阶段结论：`stage001_stop_no_parameter_rescue`。当前落地是 40 观测绝对 inflation 版本，不能表述为真正 63 日边际风险版本。
- 是否进入下一步：否；独立 review 为 `P0=0/P1=2/P2=3`，关闭本线且不做逐半年。
- 下一步：禁止扫描窗口、阈值、weight floor 或整数规则；日期对齐、同日批量感知的候选边际风险贡献若未来研究，必须另开新线并重新预声明。

## 独立 Review

- 审计结论：`CLOSE`；`P0=0/P1=2/P2=3`，禁止逐半年和结果后救参。
- 统计闭合：summary 与 daily/closed lots 独立重算最大误差不超过浮点误差；权益、累计净损益、交易次数和 broker10 均闭合。
- P1 1：配置窗口为 `63` 日，但正式 AM41 只有 41 个 close，`454/454` 个 available 样本均为 `40` 个收益观测。
- P1 2：公式计算的是候选加入后的总组合 inflation，并把权重只施加给候选，不是候选边际风险贡献；分散化候选也可能被误伤。
- P2：数组按尾部位置拼接，未保存交易日期；未发现未来函数，但缺 bar 时无法证明严格日期对齐。
- P2：局部 covariance transform 为 `0` 次放大、`0` 次把正手数归零，但后续 selection tilt 有 `10` 行最终手数高于 covariance 前手数，原 `semantics_ok=true` 已修正为 `false`。
- P2：A/C 路径分叉为共同交易事件 `625`、A 独有 `16`、C 独有 `14`；不是 AI 漏接，也不能把成本变化解释成固定路径等比例缩手。
- 置信度：对“当前实现应停止”的置信度高；对“真正 63 日、日期对齐的边际风险贡献无效”没有证据，本阶段不作该结论。

## 过拟合反思

- 运行前判断：低到中等；单一结构、固定 63 日、无坏窗口或品种补丁，但协方差估计可能噪声化。
- 运行后判断：当前结果本身没有通过调参制造过拟合，但继续救参会转为高风险过拟合。
- 原因：四项绩效闸门失败，且实际观测/边际语义与研究表述不一致；不允许扫窗口、收缩强度、weight floor 或整数规则救参。

## 继续价值反思

- 运行前判断：有价值；它保留 AI 机会，只治理组合层相关风险。
- 运行后判断：本实现无继续价值。
- 原因：收益保留、回撤、Sharpe、broker10 和语义审计均未通过；只保留失败证据。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：待 review 后统一更新。
- 是否追加根目录 `memory.md/back_log.md`：按 A/B skill 追加 `back_log.md`；不更新 `memory.md`。
