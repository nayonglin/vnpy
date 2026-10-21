# Stage298：reopening q20 源、六标量与四现金独立总审

记录时间：2026-10-20T01:58+08:00。本线 `futures_full_market_long_signal_ai`，唯一独审记录；不是重要突破版本。仅新增298审查记录/输出，不改作者、LINE、registry、其他线或生产。

结论：**核心阻断0，算术/实现核验通过，固定包研究门与主经济门失败。** 真实root终态295/session19065、296/session35084、297/session64702均exit0；本轮实际6scalar fit/4候选cash、0旧52refit/旧控制重放，累计 **447 fit / 242 cash**。reviewer自身0fit/cash/SQL/网络/旧suite。原全市场高质量long→窄损→加注总目标未完成，不认证alpha/PIT/实盘。

本版本唯一新增q：同真实合约21根连续完整源bar，以20项 `O_t−C_(t−1)` 之和除 `sqrt20 × own11算术rolling20TR`；原52及每fold缩放、目标、权重、风险/止损/退出/K/费用均冻结。新参数仅固定20项q与六个无截距alpha1标量；未修改/删除旧策略参数。293反例成立：固定旧COMMON26与023 ordered20×4、当前Open及上下文，改变历史Open可改变q；信息新增不等于经济alpha。其时间解释仅为daily-bar reopening，不称9am/纯隔夜收益。

源295一次五cache成员与129三identity列流独核完整1552456行。用独立convolution与own11 readiness恢复全部q，availability/state/epoch/u全匹配，最大差6.66e−16；1092011可用、460445未知、7186合法零。未知为首21历史不足182511、源calendar gap重暖277934；不补0、不跨epoch。全部可用q满足自身数学界 `|q|<=sqrt20`。同一接受132 cache/valid、completeu收盘时钟和stat闭合，不读D未来。没有旧大预hash或重审历史价格清洗。

六原train共1386540行各只一流12列；成熟日期、原w/Y直接float逐位、held sha256家族排除核齐。COMMON只一次common/columns；每fold own52/scaler恢复s52和残差误差0，compact7arrays全支持行核对通过。独立fsum正规方程gamma最大差1.67e−16，z/delta最大误差约1.78e−15。main两gamma约 −0.02524348 / −0.01335261；held0约 −0.01110365 / +0.00331618，held1约 −0.03037610 / −0.02860907，均如实保留，不借main/不按效果换符号。

独立从旧score/q/ownfold gamma重构全部1933480前向值并重建K过滤→positive argmax→ordinary/F family priority，全main与held选择身份零差；选中score误差≤1.11e−16，实际保存12anchors误差0。没有和不存在的全row新score文件比较。原399252母行/98产品保留；main与held union各161014母行完整。

对同K旧控制：main **4365→4337，changed420=93新增+121取消+206换月**；held **5877→5858，changed593=131新增+150取消+312换月**。newscore内部未K约束vsK重选的main1844是另一比较，不能当作对旧156的增量420。

held最小5label列单流独核：held0已知equal-u平均增量 +0.00093850470256，distinctunknown2；held1 −0.00054701034478，unknown6。同动作未知增量0，异动作未知绝不填0；各family-u后equal-u。这里是原129首次退出R，不是共同K funded现金标签。最终执行澄清ff8c...在任何新q/成绩之前固定：main动作变化仍跑原4cash，held负不替代现金结论；原held研究支持门仍保留并失败。

四候选账本独审结果如下（closed根为交易次数，胜率为closed净PnL>0；滑点已在成交价中，不能再从现金重复扣减）：

| 账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总费用 | 总滑点金额 | closed交易数 | 净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020 / base | 2,445,451.91 | 144.5452% | -12.2066% | 1.082648 | 58,728.09 | 155,400.82 | 1331 | 12.8475% |
| primary_2020 / stress | 1,573,602.66 | 57.3603% | -12.1113% | 0.843225 | 71,687.34 | 173,619.15 | 960 | 12.5000% |
| cold_2023 / base | 1,821,274.74 | 82.1275% | -9.9353% | 1.316512 | 20,815.26 | 53,797.49 | 498 | 13.0522% |
| cold_2023 / stress | 1,535,277.99 | 53.5278% | -5.5013% | 1.306106 | 36,892.01 | 84,781.83 | 425 | 13.8824% |

四账户×9账本各一次读取，独立Decimal tick/费用/滑点、成交realized、根库存、closed/open净PnL、每日positions/权益/保证金、u预留与D仅减量、拒绝集合及容量未知守恒均通过。4337新动作完整准入，未局限旧4365；canonical来自完整母体，K/anchor/原退出冻结。44年度切片与22paired年度全重算通过，2026标partial；它们不是独立冷启动试验。净盈利右尾集中度也从closed重算。四账户execution_unknown均为true；两primary有historical stale，cold两窗无historical stale，均保留披露。

旧157仅四summary/daily一次读核曲线，不重放。固定070两个indices各一次，4×2000 paired每日log增长分布及CI逐值核对通过，四CI均跨0。primary stress权益差 **+45,182.9455**，但DD差 **−0.751961pp**（更深），所以原严格主门失败；cold stress权益差 +8,632.167、DD差 +0.921464pp。base仅描述；不挑表现较好的窗口替代主门。两窗口重叠、日/动作相关，CI不是独立发现alpha的置信认证。

审查范围边界：原52、目标与旧原价资格沿已接受来源继承；本轮核新增q、六标量、完整选择和新账本会计，没有原生策略重放/重新证明原价清洗/生产资格。一次5cache成员用于源q后已释放，不为重复旧价格审计重新加载；新成交的经济报价与费用基于冻结点价字段和经济规格核算。静态margin、历史first-seen/vintage、容量未知、stale及实盘可执行性仍unknown。唯一审查器适配是最终打印numpy bool转普通bool；所有证据留RAM，未重读/重训金融。

本次网络/GitHub结论沿用293/294已接受原文及代码先验：收益分解有动机，但跨市场/1分钟/股票证据不等于本日线q；未追加探针或新文献资格门。开始与结束均无按成绩调参；历史多次同史择题风险仍是。固定20项/ownTR/线性offset包继续价值为**否**：主stress DD与held1研究门失败、所有CI跨0，按原协议关闭，不救窗口、符号、标准化、阈值、品种、模型、label、止损或risk。其他目标的后续方向由root另定。

完整证据：[receipt.json](../outputs/stage298_reopening_independent_review/receipt.json)，包含295/296/297精确manifest绑定、读取预算、全核结果与限制。root写299决定后本298停止，不新增试验。
