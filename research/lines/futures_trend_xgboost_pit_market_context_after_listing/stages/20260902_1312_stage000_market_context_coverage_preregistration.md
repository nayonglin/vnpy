# Stage000 上市后PIT市场上下文覆盖预注册

- line_id：`futures_trend_xgboost_pit_market_context_after_listing`
- 预注册时间：2026-09-02 13:12 CST
- 是否重要突破：否；标签前可行性门
- 策略回测/CTP/订单：`0/0/0`

## 单句假设

上市资格先过滤后，冻结T-1持仓量选约的同合约日收益应能为大多数条件PIT OOS月份提供完整Top9与候选组合上下文，从而允许后续用组内排序模型检验与逻辑回归不同的信息。

## 冻结输入

- Stage003 OOS预测：`oos_predictions.csv`，SHA256=`9ec713fd03d9f1131b22b5378a4b8feb9b1065660052cbeb427ab327b51ccce3`。
- Stage003 fold审计：`fold_audit.csv`，SHA256=`92082f0791376e3b1df337e4b07a4bc7cb1ef0e0fd3c1672141e809e3e773c69`。
- Stage003 manifest：`artifact_manifest.json`，SHA256=`30ab79bd2373d0ad9c9e15ea1b0d013f657cd38b3474299146bb4b4140e40c59`。
- PIT产品日收益：`product_daily_returns.csv.gz`，SHA256=`ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa`。
- PIT收益manifest：`artifact_manifest.json`，SHA256=`32ead9d84ff97d6722a4491e389912c40d9c6558f5f4c6afbfdaa11a64c0c9b5`。

## 冻结算法

1. Stage003 OOS CSV只用`usecols`读取`eval_date/product_vt_symbol/pit_logistic_probability/window_id`，预期797行、47月、每月15至18品种。
2. 每月按概率降序、代码升序稳定排序；分为Top9、A rank10、rank11及以后挑战者。
3. 从收益产物取得不晚于`eval_date`的最后120个全局`return_date`；逐月逐品种核对精确120个`status=ok`有限收益。
4. 逐行验证`selection_date < return_date <= eval_date`、`fallback_used=False`、`cross_contract_price_used=False`，并验证同一`return_date/product`键唯一。
5. 活跃月要求Top9与A rank10全部完整，并至少两个挑战者完整；上下文历史不足的产品保留在A排序审计中，但不授权XGBoost覆盖。
6. 双跑后要求逐值结果和发布SHA一致；输入运行前后SHA与大小一致。

## 预声明通过门

- 输入行/月/横截面范围精确为`797/47/15..18`。
- 排序后Top9行数精确为`423`，rank10行数精确为`47`，挑战者行数精确为`327`。
- PIT违规、fallback、跨合约、重复键、`status=ok`非有限收益均为0。
- 活跃月`>=36/47`；2022至2025每年活跃月均`>=6`；8个有效fold各活跃测试月`>=3`。
- 每个活跃月完整挑战者数`>=2`；双跑差0；输入身份稳定。

## 固定决策

- 全部门通过：`stage001_market_context_coverage_pass_ready_for_feature_preregistration`。
- 任一门失败：`stage001_market_context_coverage_fail_stop_no_features`。
- Stage001不读取标签值、不计算特征效果、不训练、不回测、不读取sealed holdout文件、不连接CTP、不调用订单API。

## 运行前反思

- 是否过拟合：本阶段**否**；通过门不使用未来收益，但研究路线整体仍有高自适应风险。
- 是否值得继续：**是**；这是判断独立市场上下文能否真正部署的最低成本必要门。

