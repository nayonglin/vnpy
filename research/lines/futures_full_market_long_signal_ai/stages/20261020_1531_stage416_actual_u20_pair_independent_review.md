# Stage416 实际 u20 双冻结模型配对前瞻独立复审

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-20 15:31:20（Asia/Shanghai）。本次为真实 Stage415 的独立只读复审，非旧回测、非收益突破。
- 裁决：**接受一次含显式采集偏差的真实配对资金方案封存；最终剩余 P0/P1/P2=0/0/0。** 不代表 alpha、稳定、加注或生产资格；完整目标尚未达成。

## 实际执行与调研判断

作者唯一 Stage415 实际 session21166 已 exit0，UTC 07:25:09.299449—07:25:16.084673，6.785098459 秒；terminal、profile_results、四个新 checkpoint 及原两 model_journal 追加项均存在。本审没有调用415/376、context loader或初始化器，没有网络/API/SQL/Y/fit/cash/旧suite，也没有复算737整套N、特征或模型分数。主复核脚本真实 exit0，一次107项；其后仅补三项原定义核，真实 exit0，没有重跑107项或作者策略。

先读取363接收、411操作修正、412原状态独审、362修正批次独审、375事前评价计划及415指定物料。此次不是新alpha假设；网上/GitHub训练时序方法已由375引用的[scikit-learn说明](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)及[维护者文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)审定。本审没有再联网包装成新调研。判断依据是实际源/冻结/初始化/资金封签的时序与原版资产，而非一天信号多少。

## 采集偏差与同输入

原33703因sandbox DNS失败、exit1/no raw仍完整保留。411只授权一次执行环境修正；9175第二批成功，其source已被362run2独审及363根接收。415绑定的是修正后manifest和review，不借原第一次空输入unfunded seal。attempt2明确记录，原始single-acquisition承诺并未完全遵守，不称无偏差确认性cohort，也无第三次授权。

两个模型的 accepted composed identity 都为 `e7eb22a97dd40185029883f43a401137dc3185665595af3b1a50833c56db13b7`，恢复后未被更改；两原journal的 `input_snapshot` payload SHA同为 `355f667fe22547c2d77ec968641705b632ccc619b57f4d71531191997b533458`。原98产品/95家族保持，实际737当前观察、完整prescore执行域448；未知/无观察没有变成零值或被删除。

实际source_completed_at为北京时间 **15:15:00**，原采集received_at为 **15:19:57.252448**；模型journal再次接收为15:25，不能把任一个接收时刻当source结束。vendor finality、原first-published仍unknown，clock_provenance_certified=false，不从操作就绪提升为官方PIT认证。

## 模型、初始化与新资金封签

| 项目 | baseline | latest |
|---|---|---|
| 实际训练cutoff | 2023-01-01 | 2026-10-20 |
| 真实模型冻结（20日北京时间） | 04:21:56.703789 | 04:48:38.399842 |
| 各自原T_init（20日北京时间） | 04:34:30.535301 | 05:03:07.185431 |
| 此次模型input receipt | 15:25:12.653134 | 15:25:14.217932 |
| 新完整资金proposal seal | **15:25:13.196838** | **15:25:14.678247** |
| 事后timely classification | 15:25:13.197415 | 15:25:14.678833 |
| 完整D执行域最早open | 20日21:00，交易日21日 | 同左 |

两个模型的真实冻结、自身原初始化均严格早于source完成；两个新完整proposal已在source完成及本次模型接收之后、21:00之前记录。proposal内容包含双方各自base/stress完整candidate states，其字节对象SHA、journal引用及四个新checkpoint都对应；classification只确认此前完整proposal，未倒签或自行创建旧seal。

latest的实际模型/scaler文件及内嵌actual对象cutoff都是2026-10-20，T1真实事件未被旧tag替代。`engine_fold_tag=2023-01-01`是原376兼容旧API的元数据；实际代码只改cutoff并附actual_training_cutoff、source_artifact_sha256、engine_compatibility_mapping，模型系数、截距、特征和scaler数值未变。本次实物scope没有变化；不因为旧标签就错误认定latest仍用2023权重。

四个原model/scaler小文件SHA未变。412列明12个初始账户相关文件中，10个不可变文件字节SHA完全未变，两journal原sequence0字节前缀完全未变且按预期各追加6项，共7条。四个原账户ID没有重建、换用或交叉借用，均从各100万元原空ledger推进；原初始state文件未覆盖。journal新增顺序是accepted_composed/input/observations/decision_start/complete proposal/classification，无重复初始化或第二次decision_start。

## 数量、预算、成本与尚未执行

| 模型/情景 | 原选中budget数 | 正数量pending | 一手/预算拒绝 | pending qty_cap合计 |
|---|---:|---:|---:|---:|
| baseline base | 7 | 6 | 1 | 15 |
| baseline stress | 7 | 5 | 2 | 6 |
| latest base | 2 | 2 | 0 | 8 |
| latest stress | 2 | 2 | 0 | 8 |

baseline选中BZ/EB/JM/PP/LU/BU/FU，base的BZ不足一手；stress的BZ和JM被一手/预算门拒绝。latest选中LU/FU。正数量pending均与reserved budgets一一一致，非正数量拒绝保留，未伪造实际成交。数量为整数round lot，未超过prefloor向下取整或原容量上限；各budget风险、保证金和费用保留量等于其prefloor乘原unit值。

原四账户kernel身份、成本和risk参数均未变：单风险0.0025、总风险0.02、margin cap0.25、buffer1.10、初始止损0.25N；base为原fee/slip1档、stress为原3档。每budget allocated risk≤2500，全部budget（含拒绝预算）的总风险分别为9231.2899258、5234.8591862、5000、5000，均≤20000；同口径buffered margin分别为250000、250000、118759.6668174、211876.4683364，均≤250000。这里是原分配预算审查，**不是已使用保证金或已支付费用**。

在共同LU/FU上，baseline qty_cap各base2/stress1，而latest各base4/stress4；原因是选中集改变后原固定预算分配规则联动，不是调高风险参数。以后若有资金绩效差异，比较的是**选择＋不变分配规则的整体政策**，不能把差异全部归为独立信号质量，也不能说“选少必然更好”。本审没有为此另开反事实回测。

四个账户全部 `phase=awaiting_D`、last_u5290、next_u5290、last_D/last_advance=null；D5291尚未推进。positions/fills/closed/daily/position_days全空，全部D_qty=0，fees/slippage/realized仍0，没有真实订单。100万元为未执行原ledger本金，不能拿此计算新净收益、回撤或胜率；期末权益表现、总收益、回撤、Sharpe、实际滑点、交易次数和胜率均尚未形成，不借历史回测结果填充。

## 审查器自身假设及有界厘清

主107项初查中104项通过，3项失败来自审查器schema假设，原receipt和失败项均保留，没有覆写成全绿：

1. 两journal hash-chain核验最初用无末尾换行的compact JSON；原321 `_canonical`明确包含末尾换行。只按原定义各核7条后，sequence/previous hash/entry hash/单调时钟全部一致。
2. latest兼容视图最初仅豁免cutoff改变；原376还明确增加三个来源说明字段。仅核这四字段，模型/scaler全部数值与特征一致。

`resolve_definitions_once.py`只处理上述三个假设，没有再次执行主107项、模型、737源计算或资金流程。最终剩余实际问题P0/P1/P2均0；未修作者代码，也没有为了metadata启动新采集或策略重跑。

## 产物、置信度与下一步

- 入口：`outputs/stage416_actual_pair_review/final_review_receipt.json`，10531B，SHA `30e598b253124580cbddf0375bdc215d2f9eef0c5100ba2f7bfe3a643502d285`。
- 初查原件：`outputs/stage416_actual_pair_review/actual_review_receipt.json`，54860B，SHA `7c9b61353f8c3bb90a835ce96ca11805054feb4d7aba1d2b39807343cc791170`，保留3项审查器假设失败。
- 本阶段仅新增该outputs目录与唯一stage，不改LINE/registry/其他源/原journal。原journal追加由此前415产生，不是本审写入。
- 身份、资金封签时序、完整proposal、账户连续性与预算算术置信度高；原737源正确性依赖已接受362run2，不重复整套独审。盈利、稳定或加注置信度没有获得结果证据。
- 375事前评价计划仍固定：主要看相同起点各自状态的stress净收益/回撤，base也报告；不能按短期结果换赢家。12个月初评也不是跨周期稳定证明。当前没有D结果，只完成第一个真实配对方案，不应抢先声称latest更好。
- 运行前是否过拟合：**否**，只审预先冻结模型与账户的同批真实新输入，不看未来Y、不调规则。
- 运行后是否过拟合：**否，就此次执行审查而言**；采集环境修正偏差真实存在、明确保留，不能升级成原协议无偏差cohort或单日alpha证据。
- 运行前是否值得做：**是**，首次真实资金proposal需要核时钟/身份/预算，防止把空未出资seal借来。
- 运行后是否值得继续本审：**否，本轮已经足够**；后继是按原范围等待真实D观察及独立记账，不是反复复算同一日、改小metadata或扩大训练。此receipt不授权额外行情、D执行或生产。
- 是否更新LINE/registry/根总账：本agent均否，由根统一裁决。本阶段完成即停止。
