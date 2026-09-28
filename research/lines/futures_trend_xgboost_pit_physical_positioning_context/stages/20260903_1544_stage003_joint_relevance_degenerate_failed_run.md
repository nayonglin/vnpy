# Stage003 联合相关性标签退化技术失败与闭线记录

- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 当前模式：day
- 记录时间：2026-09-03 15:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：唯一一次已授权的development OOS冻结运行，训练前技术失败并闭线
- 是否重要突破：否；这是路线废弃证据，不是收益突破
- 是否触发A/B：是；A/B/C及停止规则均已预注册，但本次未产生任何A/B/C效果结果
- 线上逻辑回归基准：`m0005_20260901T165450+0800_1961d98ccb2b`

## 外部调研与判断

- 参考资料：XGBoost Learning to Rank按同一决策月组织`qid`组，<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>；商品期货basis与库存基本面的经济研究，<https://www.nber.org/papers/w13249>。
- 我的判断：每个训练`qid`至少两个联合相关性等级是排序学习的必要可辨识条件。冻结首月不满足该条件时，应该按合同停止；看到退化月份后再删月、换标签或改目标属于结果后救援，不能用来证明模型可穿越周期。

## 冻结规格与授权

- A：线上逻辑回归月度`rank10`。
- B：固定六项物理供需/会员持仓特征、32棵深度2树的单头`XGBRanker`诊断排序。
- C：A与B月内percentile各50%的固定融合。
- 样本：153行development、26月；13个active OOS折共91个测试行；首折训练为62行、13个`qid`；另有4个fallback月。
- 标签：月内收益相关性与回撤相关性分别形成dense relevance，再逐行取`min`得到`joint_relevance`；每个训练`qid`必须至少有2个唯一等级。
- 用户明确授权范围：`one_new_stage003_development_oos_run_only`，只允许运行固定入口一次，不授权holdout、真实引擎、生产、CTP或订单。
- Authorization SHA256：`8b7b77c037419702e40390945e48a274bdb61d10722a0d583ce82c099b4c348f`。
- Consumption receipt SHA256：`11cbb1af3806707368e6269c8aff5c5441fa36ef8bbf381b51f80116f16ab127`。
- nonce：`558332d4683c115524391c6ca430eb467b9016db510b2b1f7881987a7a8e4161`。
- 27项绑定文件canonical identity SHA256：`e6355d8a06161cfa36968fdf10f0865ca8514301d7fed8afb100700b069d000c`。
- Runner SHA256：`2bbd6af436af2b761720269695e1c052aee3980ed7bedcc4969b1483b10d0a86`；contract SHA256：`e800b2b347bcb92472234a0a391b77b487de27de1f79ee191354b635232c15a2`。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 执行命令：`.py311/bin/python research/lines/futures_trend_xgboost_pit_physical_positioning_context/tools/stage003_joint_ranker_development_oos.py`，只执行一次，authorization已原子消费。

## 技术失败结果

- 终端错误：`Stage003Error: joint_relevance_degenerate:2022-01-28`。
- 失败位置：首个active fold的`_prepare_ranker_fold -> _build_joint_relevance`，未满足训练`qid`联合相关性标签至少两个等级的冻结门。
- 合同处置语义：`stage003_contract_or_pit_invalid_stop_no_effect_claim`。
- 操作处置：`STOP_STAGE003_FROZEN_SHAPE_NO_RERUN`。
- 持久现场：authorization receipt存在且权限`0600`；`artifacts/stage003_joint_ranker_development_oos.tmp`存在、权限`0700`、条目数0；final结果目录不存在。
- 没有发布模型、预测、selector、效果指标、manifest或结果bundle。
- 绑定runner控制流可推断初始62行development main标签已打开，而fit、预测、选择、seal、OOS测试标签、A2、holdout和结果工件均为0；但异常路径没有持久化nonce绑定事件账本，因此这些精确计数只能标记为控制流推断，不能标记为独立耐久审计事实。

## 回测/归因参数

- 数据区间：冻结development月度样本；运行在首折训练准备阶段终止。
- 账户规模：不适用，未运行真实策略引擎或组合回测。
- 成本口径：不适用，未产生策略回测。
- 样本过滤：未在失败后删除月份、品种或标签。
- 策略/归因口径：A/B/C冻结形状未改变，未进入效果评价。

## 结果

- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：不适用，未回测。
- 胜率：不适用，未回测。
- 其他关键指标：没有development效果指标，不能判断XGBoost是否提高收益或降低回撤。

## 独立复核

- Review：`reviews/20260903_stage003_failed_run_independent_review.md`，SHA256=`3709012c3a10ab0bfae7ff37b924c2dc6bccc90b45d60c97d689006d66b71cda`。
- Decision：`reviews/20260903_stage003_failed_run_review_decision.json`，SHA256=`a4e639795429b086837cb9bb233ca8919125f5a14104b7cc6943d8e73c25c7e9`。
- 结论：`BLOCK`，`P0/P1/P2/P3=0/0/1/1`。
- P2：异常路径未持久化事件账本或nonce绑定技术失败bundle，reviewer无法仅凭耐久状态独立复验精确label/fit/predict零计数。
- P3：既有预注册把receipt的两个SHA字段误写成“三个SHA字段”，不影响当前机器合同和单次消费。
- reviewer只运行4项无真实标签纯测试，`4 passed in 2.16s`；reviewer真实标签读取、fit和Stage003入口调用均为0。
- `BLOCK`不授权重跑或修复本线，只说明失败证据链未达到原定独立审计标准。

## 输出文件

- Authorization：`authorizations/stage003_joint_ranker_development_oos_authorization.json`。
- Consumption receipt：`authorizations/stage003_joint_ranker_development_oos_authorization.consumed.json`。
- Technical failure review：`reviews/20260903_stage003_failed_run_independent_review.md`。
- Technical failure decision：`reviews/20260903_stage003_failed_run_review_decision.json`。
- result/report/summary/orders/daily/quality：均未生成。

## 结论

- 本阶段结论：唯一授权已消费，冻结运行在训练前因`2022-01-28`联合相关性标签退化而技术失败；没有模型效果或全周期回测数据，不能声称收益提高或回撤下降。
- 是否进入下一步：本研究线否。
- 下一步：永久停止当前“六特征 + joint maximin + 单头32树 + 50/50融合”形状；禁止重跑、删月、换标签、改目标、调参、读取更多标签、访问holdout、真实引擎、生产、CTP和订单。更广泛的XGBoost目标只有在用户另行决定后，才可从新的经济目标或新的未见数据机制另立预注册研究线，并在任何敏感操作前设计nonce绑定的异常持久化账本。

## 过拟合反思

- 运行前判断：单次冻结运行本身不是结果驱动调参，但13个active OOS月样本较小，整体统计过拟合风险高。
- 运行后判断：本次运行本身没有按效果调参，不构成模型结果过拟合；现在针对已知退化月删月、换标签、改目标或重跑则会构成明确的结果后过拟合。
- 原因：失败已经暴露了标签结构信息，任何为绕过该失败而定制的修补都会使用development结果反向塑形。

## 继续价值反思

- 运行前判断：有，只值得执行一次冻结Stage003以验证外生物理信息机制。
- 运行后判断：同一研究线没有继续价值；更广泛的“提高收益、降低回撤”目标仍可研究，但不能以本次失败为线索救当前形状。
- 原因：当前标签机制连首个训练窗口的可辨识门都未通过，且唯一授权已消费；真正的新研究必须改变事前经济假设或等待未见数据，而不是技术性绕过失败月份。

## 合入建议

- 是否更新本线 `LINE.md`：是，闭线。
- 是否更新 `research/registry.md`：是，登记技术失败和禁止重跑。
- 是否追加根目录 `memory.md/back_log.md`：是；本次属于路线废弃，并需沉淀未来异常路径耐久审计要求。
