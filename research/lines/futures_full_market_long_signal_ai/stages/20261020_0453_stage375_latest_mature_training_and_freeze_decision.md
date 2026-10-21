# Stage375 最新成熟样本单次训练与独立冻结

- 研究线：`futures_full_market_long_signal_ai`；整理时间：2026-10-20 04:53 CST。
- 非收益突破、非正式候选晋级。本次完成1次真实训练、0次新资金回测；完整目标继续active，尚未达成。
- 改动：形成独立版本`PURE52_LATEST_MATURE_20261020`。原2023参考359及370两个空研究账户不变；不把新权重塞进旧账户。

## 调研与判断

[scikit-learn时间序列说明](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)及[维护者交叉验证文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)支持将时间顺序、训练与未见评价分开。我的判断是：固定学习规则吸收后来成熟经验值得检验，不能把已看过的旧历史再称盲测，也不能因样本更多便认定收益更高。

开始及结束的过拟合判断：本轮没有按新收益调参；长期适应性择题偏差和增加一个训练版本的自由度仍在。继续价值：是，增加了915个成熟训练日期及17个品种族；下一步应比较真实冻结后的新决策，而非再跑旧收益寻找赢家。极窄损、加注和跨周期优势均未得到新资格。

## 固定参数与实际训练

372协议在训练前固定：main cutoff=`2026-10-20`，来源快照仅至`2026-10-16`。原26值+26缺失共52列、原stress目标、成熟门、family-u区间并发uniqueness/组内均分/等u权重和train-only scaler规则不变。Ridge `alpha=1`、intercept、cholesky、thread1不变。新成熟全集重新估计权重、scaler和系数；没有新增特征、seed、模型、风险或成本参数，没有删除旧版本或旧结果。

| 项目 | 原main2023 | 新版本 |
| --- | ---: | ---: |
| 成熟训练动作行 | 445,475 | 788,336 |
| 新增成熟动作行 | — | 342,861 |
| 训练日期 | 3,139 | 4,054 |
| 品种族 | 77 | 94 |
| family-u训练组 | — | 191,284 |

完整输入1,552,456行，排除764,120行。最大u为2026-10-15，最大label_known为2026-10-16；19/20日没有被补造标签。unknown/open/censored/取消诊断不填0目标。动作重叠、同市场相关，78.8万行不是78.8万独立交易或独立经验。

373唯一actual从北京时间04:43:23.727828至04:44:04.308457，40.580642秒、exit0、1次启动/1个完成模型。必要actions/common实体各读1次；历史预测、历史重选、held、cash、SQL、下载、重标均0。未运行原130强制六fit/旧预测入口，未重跑金融来验证训练。

累计完整真实fit=454、完整cash=246，另保留此前1个金融不完整尝试；合成fixture不计真实fit。本轮新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率全部N/A，不沿用旧历史收益冒充新模型结果。

## 独立复核与保存

374独立复核全部训练门、788,336权重、191,284组、26列训练统计及52列设计/53维正规方程；0 reviewer fit/solve/predict/cash。独立方程scaled residual约`1.23e-13`，P0/P1/P2均0，算术置信度高，盈利与泛化置信度未获得新证据。审查器17位CSV解析产生最大约`5.68e-14`的浮点差异，已通过原输出Python解析说明，不重读actions、不改作者模型、不重复训练。

- [实际训练manifest](../outputs/stage373_latest_mature_refit/actual_run1/manifest.json)：SHA `7b6d0fa0ad5c27484330925ea2035ad96fc8eadca7f6c76eb47da305eab03cbe`。
- [独立训练收据](../outputs/stage374_latest_mature_refit_review/actual_training_review_receipt.json)：SHA `8eab6012aeae1d016ef83b92db61eb45a3e09040b9271ebc6fbfb66f38a5df72`。
- [本地闭包清单](../outputs/stage375_latest_mature_decision/reference_manifest.json)：SHA `a0f810e1bd68c9aca27f34f707e94414905c51c455c39dd9881fb1017c5f1d37`。登记17项：15小副本、2个新训练身份/分组实体原地只读保留；另保留4个原训练输入引用、原359源码/时钟依赖和runtime。没有复制规范化大矩阵或再读71MB身份表。
- 新模型SHA `2ca97cd4b8c9f4b21f59f74d7ba3e1693a7a9316e640540ab887d0de9252ec10`；新scaler SHA `9d163fcc521c741535cf1eadbe670f2711a25f2d33e2f09db0ba6113b4c93132`。

接受训练及保存后，以原321真实事件另签T1：`2026-10-19T20:48:38.399842+00:00`，即北京时间20日04:48:38.399842。训练manifest中的T1=null是冻结前记录，不能拿cutoff、文件名或mtime代替真实事件。[冻结结果](../outputs/stage375_latest_mature_decision/freeze_result.json)与[小型冻结独审](../outputs/stage374_latest_mature_refit_review/newT1_small_freeze_review_receipt.json)一致；旧359/370没有混入。仅本地研究保存，没有跨机runtime认证、生产启用、Git staging/commit/push或正式物料发布。

## 评价与下一步

[评价计划](../outputs/stage375_latest_mature_decision/candidate_evaluation_plan.json)在首次未来评分前固定：原2023与latest版本共享同一实际新输入、各自独立base/stress100万空态、相同执行/成本/风险。原0.25N、单风险0.25%、总2%、margin25%/buffer1.10、退出F0均不变。不能借旧账户、旧未出资seal或按短期收益换赢家。主要比较配对stress收益与回撤，base也需披露；12个月初评仍不能单独证明跨周期稳定优势。

当前新模型账户状态尚无，future预测0；370原两个初态inactive、无资金proposal。下一376只接新模型独立初态和共用输入薄接口，不训练、不重跑旧金融。今天原360行情接收仍仅15:15后且21:00前一次874×3；先361终态/362独审/363接收，双方再复用同批输入，不多抓行情。

每个版本须满足模型冻结早于实际source完成、自身初始化早于source完成、新完整资金proposal真实seal早于完整prescore eligible-or-unresolved执行域Dopen。错过保留gap，不跳u重置、不追认。超过u20/D21另定有限日历范围，不声称已有永久自动日更。

[结构化裁决](../outputs/stage375_latest_mature_decision/decision.json)接受本次数值与未来保留资格；[唯一下一范围](../outputs/stage375_latest_mature_decision/next_scope.json)约束376。无新alpha资格，不改正式C9、生产、CTP、委托、邮件、launchd或其他研究线。日常记录不追加根总账。
