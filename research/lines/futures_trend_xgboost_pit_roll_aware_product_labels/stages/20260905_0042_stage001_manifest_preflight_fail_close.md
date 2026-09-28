# Stage001 source manifest预检失败闭线

- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels`
- 记录时间：2026-09-05 00:42 CST
- 决策：`stage001_roll_aware_label_plan_manifest_preflight_fail_close_no_data_opened`。
- 是否重要突破：否；唯一入口在研究数据解析前因manifest verifier契约不兼容停止。
- 授权nonce：`484d473f-8b58-4c38-bdb4-6854f55cd875`，已消费，不重跑本线。

## 失败事实

- V1 `verify_published_bundle`把`artifacts`字典的key解释为文件名。
- source rebuild manifest的key是`mapping/normalised_bars/...`等逻辑名，真实绝对文件路径在每个entry的`path`字段。
- 错误verifier因此把真实存在的`pit_main_contract_mapping.csv.gz`等文件报为unmanifested，同时把逻辑名报为missing。
- final产物目录不存在，临时产物条目0；不能运行`--verify-only`。

## 数据与副作用

- 输入文件只在SHA身份校验时按字节读取；没有解析基础面板、label plan、mapping或bar表。
- bar值列打开：0；close值读取：0；收益计算：0；标签读取：0。
- fit：0；predict：0；策略回测：0；holdout：0。
- CTP：0；订单API：0；生产写入：0。
- 新增/修改/删除回测结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。

## 关闭纪律

- 本线关闭，不修改授权后绑定的runner/core/tests并重跑。
- 若继续，只能另立V2；唯一允许差异是按source manifest entry的`path/size/sha256`验证逻辑名格式。
- V2不得改变56,272行、1,046 qid、20段、T-1映射、bar存在门、canary或零副作用门。

## 过拟合反思

- 运行后判断：否；没有打开价格、标签或效果，失败来自静态manifest接口不兼容。
- 边界：不能借V2改变标签全集或路径规则，否则会把技术修复扩张为结果后研究自由度。

## 继续价值反思

- 本线继续价值：无，关闭。
- V2继续价值：有；单一、可证明的manifest适配修复后，原无标签资格问题仍未被实际检验。
