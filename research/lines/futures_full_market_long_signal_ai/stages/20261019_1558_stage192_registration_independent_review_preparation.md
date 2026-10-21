# Stage192 仓单登记实验独立静审、数值检查与管线续算

- line_id：`futures_full_market_long_signal_ai`
- 记录时间：2026-10-19 15:58 CST。
- 阶段性质：Stage189 冻结实验的独立实施核验；下文保留15:58准备记录，末节记录合成完整审查终态。
- 是否重要突破：否；无收益结果，无 alpha 晋升。
- 是否触发 A/B：否；本线独立于正式 C9/月度 AI，执行既定固定验证，不提高投注。

## 外部调研与判断

已核对 [scikit-learn Ridge 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ridge_regression.html) 与 [官方 GitHub `_ridge.py`](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)。判断：按样本权重写成带未惩罚截距的正规方程，可在不重新训练 Ridge 的情况下校验已保存模型；不据此选择新超参、算法或特征。

## 独立静审结论

Critical=0、Important=0、Minor=0；目前不阻断 Stage190/191 的既定入口。复核源码和作者测试的 SHA 与 root 给定值逐字一致。只静读作者 8 fixture，未运行作者 suite 或旧 suite。

静审覆盖：原129全域 action/parent 身份与新188一一绑定；186/188/187以及root接受五项精确binding闭环；两新54维 arm、共同且未缩放missing、CONTROL末列恒0；六个原成熟fold和SHA256 family留出；原family-u区间并集及等u权重；训练有限q的加权scaler与全6fold先预检后任何fit；原old-target不改成K目标；全域自身分数先D<K筛选再argmax、ordinary/F family优先级和parent保留；共同K/source/effective三边界；主组两arm×两起点×两成本各自独立递归；12fit/8cash预算、物理完成先记账、部分失败保留及禁止已完成重放。

另由窄范围独立子agent静读Stage192及190/191/helper接口，完整返回C=0/I=0；未运行测试或数据，确认9类账本缓存与102/132/158纯数学接口兼容。

静审不是实际结果接受，且不能证明所有输入故意破坏情形。作者显式继承旧accepted大输入SHA并以文件stat前后守卫；本检查器遵循同一已接受身份边界，不泛hash大库或重建源行。

## 本次变更

仅新增本线 `tools/stage192_registration_review.py`、`tools/test_stage192_registration_review.py` 和本阶段报告/receipt；未改190/191、策略参数、训练参数、正式配置、其他线、LINE或registry。数值算法参考本线169的独立数学模板，并只载入已固定132/158及102纯审查函数，绝不导入190/191作者函数计算期待结果，不读取旧模型/分数/账户结果。

新增或修改金融参数：无。删除参数：无。新增/修改/删除回测结果：均无。

## 检查器的完整有限范围

- 对新12模型检查实际attempt/completed顺序、原成熟身份/target、每折完整权重和组区间、六套COMMON/q scaler、54列设计、CONTROL最终系数0及带截距正规方程；不拟合模型。
- 对3,866,960新forward score逐行算术核对，对两arm全部main与held_union parent各161,014行做完整K过滤/选择/family优先级核对；检查全域K边界和两held组原target诊断、annual/unknown/common unresolved。
- 对八账本核对已存fills→现金、数量→positions、daily权益/保证金/风险/预算、手续费/tick/slippage、开平仓和胜率/Sharpe/回撤、native参考价和逐日强制退出请求、容量/entry未知、gap不封顶、source/voluntary/effective边界、summary及family/year含零表、sector/variant和尾部报告。这里是重算保存交易的算术，不运行账户策略或递归生成任何新金融账本。
- 对四份配对比较使用原070固定2000×252索引核对分布、CI、门槛、wealth、DD unknown、stale、execution unknown、held differential unknown；不生成新bootstrap索引。
- 新CSV解析时同步SHA核验并统计磁盘单次读取；每账本仅从磁盘读取一次，独立helper得到内存副本。旧accepted actions/common/mothers/projection/cache继承digest并stat+单读；不SQL、不下载、不重处理源数据、不hash原数据库。

## 有界fixture验证

仅运行本检查器新增5个核心fixture，5/5通过。故障覆盖时间错位、missing冒充true0、parent错绑、错误beta、K前筛选与ordinary/F优先级、严格主门与unknown、物理完成计数、拼接gzip流SHA/缓存副本和篡改拒绝。首轮暴露检查器自身macOS `/var`/`/private/var`缓存键别名，已统一resolve后复测通过；无金融结果参与修正。

## 当前结果与停止点

actual review尚未启动；新fit=0、新cash=0、新SQL=0、新下载=0。当前由root维护的执行前累计仍为409fit/218cash；只有上游12fit与8cash实际完成才为421/226。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：本阶段无回测，均不适用。

等待root提供190/191完成终态的精确manifest和Stage192 exact-source授权，届时最多一次完整数学审查。本准备receipt不允许作为actual结果接受证据。

## 风险、置信度与判断边界

静态实施一致性的置信度较高；actual数值/账本/置信区间的置信度当前未建立。186/188源行接受只证明在既定条件下的规范化及投影算术；不证明物理库存单位、首次公布PIT、无修订或alpha。依root本次源审报告，known母22,270，其中2020+为20,193；230,490 child只是共享product-day值的重复投影，不能当独立信息样本。2010–2013、2016–2019、2026全q missing，有限早期支持限制首折识别力。2026全仓单scalar missing必须原样披露；两arm共用missing不能把缺失当observed0。ideal-bar、gap实际亏损可能越1R、stale/entry/capacity unknown以及重叠历史条件CI均不升级。held old-target不是K现金目标，不据此宣称完整泛化。

## 过拟合与继续价值反思

运行前与准备完成后判断：本次新增过拟合为否。没有按收益调参、增特征、改目标或重放金融实验，只按冻结189排查身份与算术；历史累计搜索和条件PIT风险仍存在。继续价值为是，限于对既定12fit/8cash做一次完整独立结果审查；如该固定实验负面，不能靠符号/窗口/coverage/lag/产品/模型/止损/风险救参。

合入建议：本agent不更新LINE/registry或根总账，由root在实际终态合入时统一处理。


## 2026-10-19 18:13 合成完整审查终态

完成方式必须保留：首进程93358在148.214561秒内完成12模型、3,866,960分数、全部main/held parent K选择、六fold与held诊断checkpoint后，附加只读观察器错把args[9]模块作为输出目录，在原数学return后触发TypeError。首receipt仍为 **C=0/I=1/M=0、completed=false**，源码和执行入口已归档 `actual_run1/observer_entry_used.py`；原7-file frozen bundle仅覆盖数学检查器，不覆盖该额外wrapper。非必要main变化计数已放弃。

root签发精确恢复授权后，32008只续未启动的signals/8book/4CI数学，66.779488秒后 **completed/exit0，C=0/I=0/M=0**。没有重新训练、预测、选择、账本或金融递归；为恢复丢失内存，额外读取一次旧actions选中行及mothers，明确不再声称全审所有大输入仅一读。q/COMMON未再读，cash每本九类账本各一磁盘数据遍历。它是已完成模型checkpoint加独立现金/CI续算的**合成完整审查**，不是一次无事故终态。原错误保留，当前金融/逻辑剩余C/I/M=0/0/0。

覆盖实际全量12模型、3,866,960分数、每arm main/held_union各161,014 parent、8账本、4比较；0新fit/0新cash/0SQL/0下载。金融累计421fit/226cash。正规方程最大残差2.1478627e-08。完整receipt见 `outputs/stage192_registration_review/actual_run1/recovery_cash_ci/receipt.json`，小合成receipt见 `actual_run1/composite_receipt.json`。

| 账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | fills / 已平交易 | 已平净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CONTROL54_primary_2020_base | 2,234,951.12 | 123.495112% | -15.639825% | 0.942773 | 144,311.88 | 2553 / 1275 | 11.9216% |
| CONTROL54_primary_2020_stress | 1,611,549.69 | 61.154969% | -9.966785% | 0.844736 | 184,394.05 | 1957 / 976 | 11.6803% |
| CONTROL54_cold_2023_base | 1,881,198.85 | 88.119885% | -7.937231% | 1.385274 | 52,914.49 | 993 / 495 | 13.3333% |
| CONTROL54_cold_2023_stress | 1,520,906.23 | 52.090623% | -7.308762% | 1.276444 | 83,363.00 | 864 / 428 | 13.0841% |
| REGISTRATION54_primary_2020_base | 2,237,470.28 | 123.747028% | -15.634672% | 0.940639 | 144,451.25 | 2551 / 1274 | 11.9309% |
| REGISTRATION54_primary_2020_stress | 1,711,793.36 | 71.179336% | -9.966785% | 0.982191 | 189,737.66 | 1973 / 980 | 12.2449% |
| REGISTRATION54_cold_2023_base | 1,871,553.17 | 87.155317% | -10.071805% | 1.375997 | 53,927.76 | 995 / 496 | 13.3065% |
| REGISTRATION54_cold_2023_stress | 1,542,311.94 | 54.231194% | -7.291799% | 1.329344 | 86,070.89 | 881 / 435 | 12.8736% |

收益和DD差为REGISTRATION54减CONTROL54，正DD差代表更浅；CI单位是日均log增长差。

| 固定比较 | 收益差pp | DD差pp | 固定95% CI |
| --- | ---: | ---: | --- |
| primary_2020/base | +0.2519157 | +0.0051531 | [-3.274802957e-05, 3.898810991e-05] |
| primary_2020/stress | +10.0243675 | +0.0000000 | [-5.093184789e-06, 8.511937436e-05] |
| cold_2023/base | -0.9645676 | -2.1345744 | [-8.885823878e-05, 7.193905018e-05] |
| cold_2023/stress | +2.1405716 | +0.0169633 | [-1.461906341e-05, 4.405460592e-05] |

结论：**unsupported**。主stress收益虽多10.0243675pp，DD完全相同且CI跨0；cold/base收益少0.9645676pp，DD更深2.1345744pp；四份CI全部跨0。两held原target均值分别-0.0004390637R、-0.00009852934R，均不通过；holdout0差异unknown=1，common unresolved分别24/33。8本wealth全正，但历史stale、execution unknown、held unknown仍在；held不是K现金目标。

数据与信心：全域q known子行230,490已经逐行身份/时钟检查，它们共享product-day，不能充当独立样本；accepted投影known母22,270，其中2020+20,193。2010–2013/2016–2019/2026全q missing保留。源规范化/PIT/原时钟/条件单位未升级，ideal-bar、gap不封顶与未知执行风险保留。已核对账本算术的置信度高；该固定特征的可交易增量证据不足，不能推广为所有仓单信息无效。

运行后反思：新增结果导向过拟合为否，只有预声明固定验证和独立数学检查，没有回看救参；继续同一registration scalar/Ridge/commonK包的价值为否，按负结果停止，不扫符号、窗口、coverage、lag、产品、模型、止损或风险。原全市场long-only目标仍未完成，正式资格/提高投注均为false。
