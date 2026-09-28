# Stage003 条件PIT逻辑回归特征合同修复结果

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 完成时间：2026-09-02 12:58 CST
- 决策：`stage003_feature_contract_fix_pass_allow_frozen_xgboost_design`
- 是否重要突破：否；建立了可信的同构LR参照系
- 策略回测/CTP/订单：`0/0/0`

## 技术结果

- 原始samples冻结特征恰`108`项；非法future/target/PIT标签特征`0`。
- 条件样本`1,163`行、72个月；删除非完整60日标签36行、未上市样本133行，上市过滤后重算target变化28行。
- 8个有效fold、47个OOS月、797条OOS预测；`wf_09`因完整标签测试行不足45机械剔除。
- PIT违规、OOS未上市、OOS非完整标签均为0。
- 8 folds各训练两遍，共16次；预测、Scaler、系数和完整模型状态最大差均0。
- 全部14项技术门通过；旧XGBoost sealed holdout读取0。

## 预测层基线

- ROC AUC=`0.498437`。
- 月均/中位Rank IC=`0.003071/-0.017644`。
- Top10月均未来60日产品净利润合计代理=`71,507.34`。
- Top10月度未来净利润10%分位=`-88,428.00`。
- Top10 target命中率=`51.4894%`。
- 上述均为旧基础策略的产品贡献代理，不是账户组合收益、最大回撤或Sharpe。

## 产物身份

- `conditional_pit_samples.csv` SHA256=`22fc20b184f1f0e283d0bc2041a37d9bc778646c6fcaad662235c87f2e216cfc`
- `fold_audit.csv` SHA256=`92082f0791376e3b1df337e4b07a4bc7cb1ef0e0fd3c1672141e809e3e773c69`
- `oos_predictions.csv` SHA256=`9ec713fd03d9f1131b22b5378a4b8feb9b1065660052cbeb427ab327b51ccce3`
- `monthly_metrics.csv` SHA256=`bb92514aee157b89fffdb9c3a6889ce2a21276f1d87215f8f48139127defe120`
- `model_parameters.csv` SHA256=`d2d724cfcc0097dc0d14e351ff72fcda87cfadaa85f96decabd9a70ef84b4b2a`
- `stage003_summary.json` SHA256=`ea9766e9a2fa1856d1e178754350f7a805825dfb94ccb4c5758cced91d8cef83`
- `artifact_manifest.json` SHA256=`30ab79bd2373d0ad9c9e15ea1b0d013f657cd38b3474299146bb4b4140e40c59`
- 测试：20项通过；py_compile通过。

## 版本变更与回测记录

- 新增参数：无。
- 修改参数：无；只修正特征来源合同。
- 删除参数：无。
- 新增/修改/删除回测结果：均无；策略回测0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。
- `back_log.md`未追加。

## 运行后反思

- 是否过拟合：本阶段**否**；全部规则和参数在有效结果前冻结，且没有效果晋级门。
- 是否值得继续：**是，但只值得一次冻结XGBoost检验**。净化后LR接近随机，说明线性关系弱；浅树可能捕获非线性，也可能只是放大小样本噪声，禁止参数扫描。

