# Stage000 换月感知产品标签计划预注册

- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels`
- 记录时间：2026-09-05 00:25 CST
- 是否重要突破：否；这是数据与标签路径合同，不是模型或策略候选。
- 当前权限：只允许读取日期、产品、交易所、合约身份、PIT映射和文件身份；禁止读取close数值、计算收益、训练、预测、回测、CTP、订单或生产写入。

## 外部调研与判断

- CME连续期货把Active Contract定义为按流动性画像切换，并明确连续序列用于风险分析；它不支持把到期旧合约强行持有到固定远期日期。
- QuantConnect LEAN把合约映射与价格归一化分开，并通过mapped contract与symbol-change事件表达真实换月；连续代码本身不可交易。
- XGBoost官方支持`reg:quantileerror`和`quantile_alpha`，但当前阶段不选择目标或训练；只有标签路径覆盖通过后才允许另行预注册模型。
- 本地判断：换月标签必须保存逐段实际合约，收益只能在同一合约内计算；跨合约价格比、事后备用合约和未来映射都属于错误标签。

## 冻结输入

- V1 Stage001 final manifest、`model_feature_panel.csv.gz`、`label_plan.csv.gz`、`rejected_label_plan.csv.gz`。
- PIT全市场source rebuild Stage002 final manifest、`pit_main_contract_mapping.csv.gz`、`normalised_daily_bars.csv.gz`。
- 所有输入在运行前后记录SHA256、size和mtime；两个上游manifest必须离线复验通过。

## 冻结全集

- 基础面板：1,067个qid、57,528行。
- 旧固定合约标签分区：已计划52,484行、`exit_bar_missing` 3,788行、`exit_date_outside_cutoff` 1,256行；三者必须一对一覆盖基础面板。
- 本次理论可计划全集：前两类合计56,272行、1,046个qid；最后21个qid/1,256行因数据截止后没有20日终点，继续保持不可标注，禁止缩短窗口。

## 换月路径语义

- 每行沿用旧计划冻结的`query_date/entry_date/label_end`，持有期固定为entry收盘后20个全局交易日，不改窗口。
- 第一段持仓合约固定为query日已知`main_contract_vt`；禁止用entry日收盘后的映射改写入场合约。
- 后续每段`[previous_date, return_date]`只使用`previous_date`已记录的PIT主力映射决定合约；映射日期必须严格早于收益段终点。
- 每段要求同一合约在起止两日都有日线行；Stage001只检查行存在，不读取close列。
- 合约切换时，前一段旧合约终点与后一段新合约起点必须同为换月日，保证可表达收盘换月；禁止跨合约直接比价。
- 每行必须精确20段，保存每段日期、合约、映射日期、是否换月和bar存在性；不得按结果fallback。

## Stage001硬门

1. 两个上游manifest及直接输入身份全部稳定、离线复验错误0。
2. 57,528行基础面板与三类旧标签分区一对一一致，重复键和遗漏均0。
3. 理论可计划全集精确56,272行/1,046 qid，截止外集合精确1,256行/21 qid。
4. 56,272行全部生成20段路径；总段数精确1,125,440，日期逆序、未来映射、跨合约比价均0。
5. 每段所选合约的起止bar都存在；缺路径、缺映射、缺起点bar、缺终点bar均0。
6. `2024-01-31/sc.INE`回归canary必须从`sc2403.INE`开始并至少发生一次换月，完整到2024-03-08；它只验证执行语义，不进入任何效果判断。
7. close列读取、收益计算、标签值、fit、predict、策略回测、holdout、CTP、订单、生产写入全部为0。
8. final manifest离线复验通过，报告完整列出失败明细，不只发布成功子集。

## 决策

- 任一硬门失败：`stage001_roll_aware_label_plan_fail_close_no_labels`，本线关闭；禁止补值、fallback、删行/品种/月、缩20日或训练救援。
- 全门通过：`stage001_roll_aware_label_plan_pass_allow_label_model_preregistration_only`；只允许另发Stage002标签值与模型合同，仍不授权读取close或训练。
- 旧日级Ranker V2不论本线结果都保持关闭，禁止重跑。

## 回测记录占位

- 新增/修改/删除回测结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。

## 过拟合反思

- 运行前判断：否；合同来自可执行换月恒等式，尚未读取价格值或效果。
- 风险：已观察到一个技术失败样本，因此该样本只能作为语义回归canary，不得用于选择参数、窗口或效果门。

## 继续价值反思

- 运行前判断：有；一次性审计能直接决定是否存在足够、完整且不含跨合约跳价的XGBoost标签基础。
- 若失败，本线停止；若通过，也不代表XGBoost能提升收益或降低回撤。
