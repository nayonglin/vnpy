# Stage006 双XGBRanker冻结Development OOS结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：一次性冻结 development OOS 训练与效果资格
- 记录时间：2026-09-03 02:25（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结模型训练、17折PIT OOS、账户边际效果门
- 是否重要突破：否；本形状被反证并停止
- 是否触发A/B：是；A=正式逻辑回归rank10，B=双Ranker等权月内百分位，C=两头原始分数均严格胜rank10时替换

## 外部调研与判断

- 参考资料：XGBoost Learning to Rank 与参数官方文档。
- 我的判断：排序模型只有在候选替换对正式账户收益与回撤同时产生稳定正边际时才有价值。模型能稳定分裂、替换次数足够，不等于产生alpha；本次七个核心效果门失败，已经足以否定当前8特征、双`rank:ndcg`与严格双头selector的组合形状。

## 本次变更

- 新增脚本：无。
- 修改脚本：运行前完成 `tools/stage006_dual_ranker_development_oos.py` 与专项测试的授权、estimator和seal治理修复。
- 删除脚本：无。
- 新增参数：无；执行冻结合同中的唯一参数组。
- 修改参数：无。
- 删除参数：生产入口删除路径与Ranker覆盖参数；不属于策略参数变化。
- 运行授权：`run_authorization.json` SHA256=`ba2622a276011b2e06615726e77155171ba6bc279a125a050a91df744df4f845`，固定scope与64hex nonce，只消费一次。

## 回测/归因参数

- 数据区间：development 2022-01-28 至 2024-11-29；OOS测试 2023-07-31 至 2024-11-29，共17月。
- 账户规模：正式口径 `150,000`。
- 成本口径：沿用冻结正式账户边际标签，不改手续费、滑点、保证金、整数手、相关性和最多4持仓规则。
- 样本过滤：35个development月、266行；前18月115行初始成熟，17个测试月151行逐折先seal后开标签。
- 策略/归因口径：8项冻结PIT特征；双`XGBRanker(rank:ndcg)`；每头17个主模型与17个重复模型，共68次fit；无搜索、无early stopping。

## 结果

- 期末权益：不适用；本阶段是互斥月度候选替换边际评估，不是完整组合资金曲线。
- 总收益：不适用；`sum_return_delta=-0.10596712219705573`仅为17月C相对A的月度账户标签差求和，不得称为完整策略总收益。
- 最大回撤：不适用；`sum_drawdown_improvement=-0.029383673739694305`是月度标签改善差求和，不是组合最大回撤。
- Sharpe：不适用。
- 总滑点：不适用；本阶段未运行新组合真实引擎。
- 总交易次数：不适用。
- 胜率：不适用；替换月双目标同时为正比例为`0.125`，不是交易胜率。
- 其他关键指标：17折、151条OOS预测、34个主模型、34个重复哈希、68次fit、17个pre-effect seal；重复预测最大差`0.0`；技术门全过。
- C替换：8/17月，覆盖2023与2024；九个效果门仅“至少4次替换”和“两个年份均替换”通过，其余7门失败。
- 收益稳健性：total `-0.10596712219705573`，leave-best-out `-0.13913129819254122`，2023/2024分别`-0.02589369581866796/-0.08007342637838777`。
- 回撤稳健性：total `-0.029383673739694305`，leave-best-out `-0.06689690950170868`，2023/2024分别`-0.008643798131113711/-0.020739875608580594`。
- 标签状态：initial `115`；测试标签seal前`0`、seal后`151`；aggregate CSV数据行`0`；holdout预测/读取/生成/训练/效果均`0`。
- 执行范围：一次入口、34主+34重复、总fit 68；搜索、early stopping、extra fit、生产写、CTP、订单、意外命令/产物均`0`。

## 输出文件

- report：`artifacts/stage006_dual_ranker_development_oos/frozen_run/report.md`。
- summary：`decision.json`、`technical_qualification.json`、`effect_qualification.json`。
- orders：无。
- daily：无。
- quality：result manifest SHA256=`3bbea68279d526b02cf3768088de91a7d39faeb18b0d0825dd77a7575527942d`，除manifest外64个文件全部size/SHA精确。
- 独立review：`reviews/20260903_stage006_postrun_independent_review.md`，SHA256=`9f631076a2b759db852aa3df669bd1a358c6348f018ff68018a04486fe508caa`。
- 独立decision：`CONFIRM_STAGE006_FAIL_STOP_NO_TRUE_ENGINE_NO_HOLDOUT`，`P0/P1/P2/P3=0/0/0/0`。

## 结论

- 本阶段结论：`stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout`。当前8特征、双Ranker和严格双头selector没有提高收益，也没有降低回撤，且两项目标均明显为负。
- 是否进入下一步：当前形状否。
- 下一步：不得二次运行、调参、删月份/品种、改selector/门槛、跑true-engine或读取holdout。若继续XGBoost，只能另立具有独立经济信息和新预注册假设的研究线，不能把本结果当调参反馈。

## 过拟合反思

- 运行前判断：本次冻结运行否，整体路线风险高。
- 运行后判断：本次运行本身否；任何围绕结果的救参都会构成明确过拟合。
- 原因：参数、特征、月份、模型、selector和九个门均在首次读标签前冻结，只运行一次；失败后未改任何规格。17个月和8次替换样本仍偏少，不能支持后验修剪。

## 继续价值反思

- 运行前判断：是；账户边际标签与全曲线信息值得一次严格证伪。
- 运行后判断：当前形状否。
- 原因：技术实现有效但经济效果在总量、分年、leave-best-out和联合命中率上同时失败。继续使用同一特征/标签/selector调参的边际信息价值低，过拟合代价高。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记Stage006失败停止。
- 是否更新 `research/registry.md`：是，标记本形状关闭。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 路线关闭摘要；不改根 `memory.md`。
