# Stage169：会员持仓集中度新实验的独立完整审查

- 时间：2026-10-19 02:48（Asia/Shanghai）。
- 研究线：`futures_full_market_long_signal_ai`；只写本唯一阶段记录，不修改 LINE、registry、167/168源或结果。
- 类型：冻结166的新实验独立复核；不是新一轮策略、模型训练或现金回放。不是重要突破版本。
- 结论：**接受新模型/选择/现金结果的算术与映射，固定门结论仍为 `unsupported`。** 不能把算术接受写成alpha成立或生产资格。
- 累计研究计数维持 **409 fit / 218 cash**；本审查及显式续核新增 **0 fit / 0 cash**，0 SQL、0下载、0原始会员数据重算、0策略回放。

## 冻结规则及独立性

166协议 SHA `ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a`。复用接受的163/165会员观测测量与原129成熟标签；不再读取1.26GB原始会员归档，也不重算q。两臂均为54维：COMMON52、同一个q缺失标志；CONTROL末列严格0，Q末列为当折有限q按原样本权重缩放后的值，q缺失时末列0。

审查器不导入167/168计算函数，不调用Ridge.fit或现金内核；仅复用固定132/158中经静态确认不依赖旧arm/count的独立权重、账本数学和诊断函数。129/COMMON和接受的q投影通过精确接受链、必要身份流和不可变文件状态继承SHA，没有为hash另读334MB actions。

训练始终用原129 stress first-exit目标，严格 `u<cutoff`、原eligible、closed完整且 `label_known_date<cutoff`。不因q缺失或K早晚改训练域。六折共享原family-u区间并集权重、同折COMMON缩放与q缩放，两臂共享训练身份与权重绑定。所有六折q支持均为有限正加权方差；held训练排除整个固定SHA256家庭组，预测只来自对应组。

K继承159/155，用052完整5,587日历（不是cache内日历），不把样本外K夹到样本末日。完整child先按 `D<K`、原eligible和正分过滤，再做原产品argmax/tie与ordinary先于F的family规则；main与held union每臂完整保留161,014母事件，无观察母事件也保留，输出恢复每臂原母序。有效现金边界是 `min(source lifecycle,K)`；K日禁开，前一session收盘申请次日开盘退出，缺价继续defer，不能创造成交。

## 两次审查进程与故障留存

第一次为 root 唯一启动 `actual_run1`，用时 **39.780208666秒**，exit1；输入闭包、完整身份与接受q对齐两phase已完成。首折训练权重已核，但在区间并集端点JSON转换处遇到 `np.int64` 的 `TypeError: Object of type int64 is not JSON serializable`；尚无任何model/book checkpoint。该失败是审查器序列化问题，原receipt记I1，不能抹除或改写为首跑成功。

原源52101B SHA `501e0ae60292732756adc793af98996714de8de84575bb5d7790fa6bc6d9cd1e`、原测试7780B SHA `45201a09c7bccf371cd30a7a01f15f3be2bf7f1a1997c36600d34bd738ac6a64` 已保存到 `actual_run1/failure_source/`。保留原terminal/receipt/两个checkpoint；snapshot manifest719B SHA `611bfcbfa5a8cc793d43dab8d8cb171281bb2e159ac3a1cb1c920c5da5395aaa`。

修复仅在真实区间JSON边界使用 `json.dumps(safe(values),...)`，转换NumPy整数为同值Python整数；没有改训练、权重、预测、选择、金融逻辑或门。新增嵌套np.int64区间fixture先复现同TypeError，修后 **12/12有限合成测试GREEN，0.036秒**；没有为修复运行金融或重训。

root另行签署显式 `continuation1`，没有重新进入原 `review()/input_closure()/load_data()`。继承原两完成phase，绑定原失败receipt、terminal、started、两个checkpoint、snapshot与原三inputSHA；前后核229个binding的文件状态，并要求原运行没有任何完成model/book checkpoint。恢复必要原数组/列供未完成model/choices/book/CI检查；不重复完整旧身份/q审计、大文件hash或已完成金融phase。首折尚无持久化model checkpoint的前缀，属于未完成模型phase，续核该phase需要重新构造权重。

原失败进程尚未走到cache：**root在续核授权时另行核对**110,273,488B native cache、948B cache manifest及052小protocol的原SHA，并在授权 `not_yet_visited_cache_bindings_verified_by_root_now` 明示归属；不能冒称这些在首个closure已核。续核自身没有额外大文件hash。

显式续核由root唯一启动，**180.250048041秒、exit0、C/I/M=0/0/0、errors=[]**。失败进程与续核进程各留原状；没有自动重试，没有重训或重放现金账簿。不能简写成“整个169首跑一次通过”。

## 完整模型、预测与选择覆盖

逐项核六个成熟域全部训练身份/标签/并集组/样本权重、COMMON/q加权缩放；两臂绑定相同训练表和scaler。十二portable模型均固定Ridge `alpha=1, fit_intercept=True, solver=cholesky`，独立构造55维含截距正规方程（仅54特征罚项，截距不罚）核解，不重拟合。所有 **3,866,960** 前向预测及q raw/missing/design、child身份、main/held完整父选择和原序已核；不借作者旧赢家过滤新域。

| scope | cutoff | 成熟训练行 | family-u并集组 | 有限q训练行 | q均值 | q标准差 | 该折预测children | 母事件 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| main | 2020 | 247,795 | 82,929 | 46,155 | -0.0047163654 | 0.0485701805 | 366,634 | 71,344 |
| main | 2023 | 445,475 | 125,955 | 81,320 | -0.0048345925 | 0.0493001338 | 600,106 | 89,670 |
| holdout_0 | 2020 | 171,712 | 55,688 | 27,692 | -0.0096502050 | 0.0436733065 | 138,837 | 28,392 |
| holdout_0 | 2023 | 297,404 | 82,519 | 47,417 | -0.0066531413 | 0.0429683739 | 249,829 | 35,685 |
| holdout_1 | 2020 | 76,083 | 27,241 | 18,463 | 0.0026804572 | 0.0515931142 | 227,797 | 42,952 |
| holdout_1 | 2023 | 148,071 | 43,436 | 33,903 | -0.0010290063 | 0.0546540357 | 350,277 | 53,985 |

每臂main child966,740，main parent161,014；held两组并集也各同一完整前向域。full mother399,252的canonical身份接受链保留，现金锚定来自全部原母事件。CONTROL和Q机会选择分别 **4,901 / 4,894**，这是机会数，不是成交数；所有已选择信号有效边界来源在本次实际均为voluntary_calendar。

最大前向score误差 **3.552713678800501e-15**；独立lhs/rhs与保存矩阵误差0；最大正规方程残差 **2.136221155524254e-8**，在事前数值容差内。父选择score最大误差4.440892098500626e-16。无依成绩改容差或门。

held仍核原first-exit目标，不称K现金target。main已知equal-u均增量 `2.8521190586617343e-5 R`；holdout_0为 `7.557592272947191e-5 R`，holdout_1为 **`-8.459416254548117e-5 R`**，后者未过事前非负门。三个域distinct unknown差异事件均0；相同未解决动作仍分别披露61/35/41，增量0不代表该动作绝对结果已知。

## 八本新现金账簿

全新两臂×两个窗口×两成本各本独立核算，没有旧cash控制回放。完整核 **13,722 fills、10,232 daily、17,853 positions、27,398 budgets、6,845 closed roots及22 open roots**。逐fills价格/费用/滑点、cash与未实现桥接、持仓边界与持续退出申请、D开盘容量/分配、完整canonical、closed/open胜率、收益/DD/Sharpe/summary、gap无封顶及各unknown状态全部核。

132预算/核算最大误差 **5.820766091346741e-11**；158归因桥最大误差 **4.656612873077393e-10**。全family/year零行网格 **4,180**，sector/variant合计 **32** 行，年度含零 **176** 行；普通/F、金融/商品、无观察/零贡献家庭均保留，不按效果裁减。

| 臂 | 窗口 | 成本 | 期末权益CNY | 总收益 | 最大回撤 | Sharpe | 已闭合交易 | 闭合净胜率 | 期末开放 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| CONTROL | 2020主窗 | base | 2,160,944.09 | 116.094409% | -15.597626% | 0.931026 | 1,435 | 12.6829% | 2 |
| CONTROL | 2020主窗 | stress | 1,469,984.98 | 46.998498% | -10.824285% | 0.718663 | 1,029 | 11.6618% | 3 |
| CONTROL | 2023冷启动 | base | 1,545,749.63 | 54.574963% | -8.678663% | 1.014974 | 524 | 11.8321% | 3 |
| CONTROL | 2023冷启动 | stress | 1,447,487.77 | 44.748777% | -7.954556% | 1.074857 | 434 | 12.6728% | 3 |
| Q | 2020主窗 | base | 2,177,670.85 | 117.767085% | -15.591458% | 0.936874 | 1,437 | 12.6653% | 2 |
| Q | 2020主窗 | stress | 1,470,182.86 | 47.018286% | -10.810388% | 0.719026 | 1,028 | 11.6732% | 3 |
| Q | 2023冷启动 | base | 1,545,749.63 | 54.574963% | -8.678663% | 1.014974 | 524 | 11.8321% | 3 |
| Q | 2023冷启动 | stress | 1,447,539.65 | 44.753965% | -7.954556% | 1.074971 | 434 | 12.6728% | 3 |

| 臂 | 窗口 | 成本 | fills | 手续费CNY | 滑点归因CNY | 未知容量fills | 入场执行未知 | 历史stale日 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| CONTROL | 2020主窗 | base | 2,872 | 58,985.9120 | 156,624.7589 | 43 | 4 | 8 |
| CONTROL | 2020主窗 | stress | 2,064 | 71,935.0170 | 178,903.7486 | 19 | 3 | 5 |
| CONTROL | 2023冷启动 | base | 1,051 | 19,680.3655 | 50,983.4537 | 8 | 0 | 0 |
| CONTROL | 2023冷启动 | stress | 873 | 35,712.2295 | 82,377.4373 | 6 | 0 | 0 |
| Q | 2020主窗 | base | 2,876 | 59,559.1465 | 157,339.9229 | 43 | 4 | 8 |
| Q | 2020主窗 | stress | 2,062 | 71,927.1390 | 178,834.4400 | 19 | 3 | 5 |
| Q | 2023冷启动 | base | 1,051 | 19,680.3655 | 50,983.4537 | 8 | 0 | 0 |
| Q | 2023冷启动 | stress | 873 | 35,710.3545 | 82,375.9863 | 6 | 0 | 0 |

滑点已在fill price中；表中滑点是归因，不能从equity再扣。闭合交易与fills计数各有含义，开放episode不能填成闭合胜负。全部八本wealth保持正，但历史stale及执行/容量unknown仍存在，不能由尾日无stale推回全历史可成交。全开放头寸归零情景只是压力披露，不是普适经济下界。

## 四固定CI与门

沿用070既存2000组、252日块indices，逐完整paired source日历核四个分布；未重生indices、未epsilon修复log。以下差额为Q减CONTROL，收益/DD单位为百分点，CI为平均日log差：

| 窗口 | 成本 | 收益差 | DD差（正为更浅） | 平均日log差 | 条件95% CI |
|---|---|---:|---:|---:|---|
| 2020主窗 | base | 1.67267655 | 0.00616799 | 4.69305284788e-06 | [-1.89022376549e-05, 3.23261547736e-05] |
| 2020主窗 | stress | 0.01978780 | 0.01389695 | 8.1925258729e-08 | [-2.54660593792e-06, 2.78979431069e-06] |
| 2023冷启动 | base | 0.00000000 | 0.00000000 | 0 | [0, 0] |
| 2023冷启动 | stress | 0.00518750 | 0.00000000 | 3.9166460921e-08 | [-2.68073561307e-09, 1.18182710873e-07] |

主窗stress收益差虽为正，但平均日log差CI含0，事前严格CI门未过；holdout_1原目标增量为负。四窗口Q自身收益均正、收益差与DD差通过相应非劣门，不能覆盖CI与held失败。最终 `cash_nominal_pass=false`、`held_known_nominal_pass=false`、`nominal_pass=false`、`status=unsupported`，且 `financial_unknown=true`、`execution_unknown=true`、`any_historical_stale=true`。

## 限定解释、参数与后续

新增/修改的科学参数：无。删除科学参数：无。新增实现：独立169审查器与一次显式未完成phase续核入口、12个有限反例。旧结果未删除、未覆盖；原失败及两进程证据保留。此记录的八本值是167/168新实验既成输出的复核，不是本agent另跑回测。

开始与结束的过拟合反思：**本审查不是过拟合操作**，因为模型、q、共同K、数据域、12fit/8cash预算和门在成绩出现前冻结；未按出现的结果改规则。但原试验仍受历史最终归档、源公布时点未严格认证、条件CI非独立OOS、实际盘口/交割账户/容量与缺价风险限制。经纪席位不是最终客户或聪明钱，本q是可见双方份额集中度差，不赋予方向因果含义。

继续价值反思：**独立完整核验有价值，现已完成；沿本冻结q/Ridge实验继续调参没有当前证据支持，应停止该候选。** 失败不等于证明所有会员分布或其他模型必无信息，也不构成扩大搜索的授权。root负责Stage170接受算术、否决本候选并更新索引；后续171连续仓单source-only pilot是独立观测支持问题，不能把它当挽救旧q的重命名。全市场研究目标继续active，未声称目标完成、生产合格或可加注。

本阶段未新web/GitHub调研：遵循本轮明确0web/0download范围，外部方法判断与源调查沿160/163/165/166已接受材料；本次新结论仅来自冻结实验的独立有限审查，不扩大外部证据等级。

## 主要复核资产

- [166冻结协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage166_member_concentration_protocol/protocol.json)：16409B，SHA `ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a`。
- [167新模型manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage167_member_concentration_fit/actual_run1/manifest.json)：32254B，SHA `eca554f90cda62a887b0d59952f7e316cb0a9e2d98a860cb7062158653c465db`。
- [168新现金manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage168_member_concentration_cash/actual_run1/manifest.json)：125057B，SHA `c3d82f0bf1101e3b63a4bbfab9793a9e40b2b4aa6770c07bb9e230f179c0499f`。
- [首次失败receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage169_member_concentration_review/actual_run1/receipt.json)：6879B，SHA `d1e434981058f63d75c94fc3f38c59c5777355b264efd97b882dab1bbe43414c`；保留I1与原回溯。
- [失败源snapshot](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage169_member_concentration_review/actual_run1/failure_source/manifest.json)：719B，SHA `611bfcbfa5a8cc793d43dab8d8cb171281bb2e159ac3a1cb1c920c5da5395aaa`。
- [续核root授权](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage166_member_concentration_protocol/authorize169_continuation.json)：152174B，SHA `63bf7fe088ca254dbe9884c7c5d6ce1e769f96d3ca42b13f7593d138e18daded`；229 stat、原3inputSHA及root另核cache归属明确。
- [最终独立receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage169_member_concentration_review/continuation1/receipt.json)：95195B，SHA `477d5cbe7a7b4242ac6c566566dd663c508ef8a67b9d8cad25b6696f60b513dd`；C/I/M0/0/0、errors[]。
- [续核terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage169_member_concentration_review/continuation1/terminal.json)：1177B，SHA `6cd0137bdcb5e16622f56b623a34ea2f19066952198689ea18ca98204884661f`。
- [fixed reviewer](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage169_member_concentration_review.py)：52157B，SHA `6d4d293ec0112d14cd0a8643418ebbff239e9394b7818393a3d745cfe87022e5`。
- [explicit continuation](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage169_member_concentration_continue.py)：12177B，SHA `f3ab47eab7bba2eb7c25b327010464839511d73de15383e33883849f0939e661`。
- [有限fixtures](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage169_member_concentration_review.py)：8106B，SHA `a46d6b12345e86df4214232faa104133a38e3be72504936030756f7f796fd6f8`。
