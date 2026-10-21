# Stage069 全市场结算信息×跨日窄初损：一次联合实验冻结

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 16:28 CST。
- 当前 checkout/分支沿用 `/Users/mac/Desktop/fian`、`codex/ai-training-data-expansion`。只隔离新增研究文件，不建工作树，不改正式版本。
- 重要突破：否。当前是实现前科学合同，新增实际 fit/cash/label build 均0。Stage067的一次来源投影另行运行，不能计成金融进步。
- 采用068的联合路径B，加入066提出的必要OHLC代理对照：**12次Ridge拟合、24个资金账户，一次完成；不再附加全ready机械pilot的8账户**。

## 调研、判断与研究问题

已读取registry、本线066/067/068及049、053、061、042/054现金边界。继续沿已核一手资料：[Kaminski/Lo原始研究](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee)、[RQAlpha维护者源码](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/base_data_source/data_source.py)、[vn.py回测器](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)。研究并不证明0.25N具有普遍优势；已知日线low/open可以确定预先存在的单止损的理想触价分支，但不能证明真实排队、停板或跳空成交。结算价包含同OHLCV不能唯一重建的价格分布信息，方向也可能均值回归，不能手定正偏离必买。

本轮只有两个问题：同一种退出政策内，真实结算信息是否优于共同信息及同容量旧价格代理；各自正确训练后，窄初损模型/政策包是否能在真实资金竞争和成本下保留跨日右尾，改善收益与回撤。跨宽度比较是学习器与政策包比较，不是纯止损因果效应。

本轮按`version-ab-experiment`的隔离、冻结和失败即停原则执行；不是正式候选晋升或正式A/B/C，不启动正式池/生产资格全套，也不将旧正式池限制带入全市场研究。候选真有可复验证据后，再讨论正式对照。既有EIA失败包已关闭，不借新结算字段、止损或新门重判其成绩。

## 母体、时钟与输入接受

1. 保留049全部399252行、原sequence/event/product/family/u/真实epoch身份、六所98目录产品、普通与F、所有unknown/cancel/open。不存在月度Top10、55突破或未来共同闭合筛选。没有有效新增字段的行仍由共同信息预测与参与预算。
2. u为源交易日全源收盘后；D为严格下一源日、同一真实epoch的open，不能跳到下一有价日。新增字段固定v=u前一个完整源日，不换约拼接。
3. Stage067只是候选数值/来源投影，它的`training_accepted=0`不改。后续独立接受收据必须绑定其completed manifest和实际终态/完整母体，明确另行产生本轮研究mask。只有`projection_state=observed_historical_reconstruction`、`value_observed=1`、`N_state=N_v_ready20`、同epoch/date、OHLC固定1e-8一致、C/S/N有限正值、v严格前一源日、lifecycle在vendor边界前，才可观测；真零偏离合法。任何冲突/无成交/缺行/坏值/未知最终边界不可变成0。
4. 规则族为历史重建，不要求把所有日期伪签成已核首发。已知benchmark族、包括明确标注的`family_default_assumption_no_primary_rule_bound`，可以在**vendor/官方历史日结算字段＋固定一完整源日滞后**的研究假设下进入；保留逐行rule状态、按交易所/年覆盖。`rule_family_unknown`和F未知定义不能由root猜测补齐。此接受不声称全天VWAP、首发PIT或全历史规则已认证；回溯修订和跨所窗口差异是实质限制。
5. SETTLEMENT：x=(C(v)-S(v))/N(v)。OHLC_PROXY：x0=[C(v)-(H(v)+L(v)+C(v))/3]/N(v)，后者从这次新标签必要native载入同时提取，不再额外SQL。二者严格共享真实x的研究可用mask，COMMON也看见同一external_missing。缺失标量在标准化空间置0。来源选择及mask不参考收益/退出标签。
6. 使用接受的053 prepared_common.npz的26列和原顺序（28,214,904 bytes，SHA e3174cf1d2067611e6a2538d25aafee17772adcd1889a68408d727fdc4fc1fd3），不重建旧特征。原26列含以2N表示的成本/low20距离，本轮**两种政策都保留相同原X量纲**，不暗改成0.25N使信息对照混入特征变更。

## 两政策、新标签与学习器

- WIDE：初始保护SL0=原始D.open−2N(u)；NARROW：SL0=原始D.open−0.25N(u)。N沿042/049 Wilder20，区别于旧DAY简单均值ATR。各自从入场起使用max(SL0,当时已完成日的20low)，不新增单调max(旧stop)，不设PT、不日终强平、不设持有上限、不盘中重试。
- 开盘F<=low20(u)或该臂SL0<=0沿049已接受的quote取消。入场日内low触价允许理想止损；其后gap先于bar内low，gap按open，价差可远超1R。反向/到期/旧epoch切换、missing与吸收unknown沿049，不将终点开放强平制造目标。
- 复用已接受WIDE049经济标签，不重建它的真实全套。**NARROW逐event新模拟first exit/成熟日**，不把WIDE Y除8、不用其成熟日、不筛WIDE赢家或完整路径。新输出完整母体、全部状态、base/stress每lot净CNY、kN*M归一化净R及共同2N*M诊断、退出原因/持有区间/成熟日期、两政策状态交叉表。
- 每policy的成熟训练必须同时满足u<cutoff、label_known_date非空且<cutoff、closed_complete_bar_model；目标为该policy自身net_R_stress。不同政策支持域照报。只在该训练集计算同family入场至退出日（两端含）并发唯一性，再按u均衡、全体均值1。不能用测试/删失事件计算训练权重。
- 3信息臂COMMON/SETTLEMENT/OHLC_PROXY × 2政策 × cutoff2020-01-01/2023-01-01 = **12 fit**。固定Ridge(alpha=1,fit_intercept=True,solver=cholesky)，无树、网格、交互、family单模、后验阈值或其他字段。
- 54槽：common26＋26缺失indicator＋external_missing＋单scalar槽。COMMON scalar严格为0；两信息scalar用同一成熟训练集内两臂各半权重的共同mean/scale。common标准化/缺失均值填补均仅来自对应policy/cutoff训练集。同policy/cutoff的三臂训练行/权重/预处理完全相同。
- 两训练截止点组成固定前向拼接：2020模型只预测2020—2022，2023模型只预测2023至终点。每个信息×政策组合保留全部2020+的161014行，六组合合计966084分数，无重叠event。2020连续账户到2023按预定时钟更新为2023模型，旧仓仍按原政策退出；2023冷启使用同一段预测但无旧仓。ready20且score>0才能请求，不能用未来标签状态选测试交易。没有家族训练外留出，不称新family零样本泛化。

## 现金、资金竞争与有限预算

3信息×2政策×2独立冷启（2020、2023）×base/stress=**24账户**，各100万元，止于2026-10-16；期初无仓，可用首个交易日之前已完成u的因果意向。2020和2023窗重叠，不当两个独立样本；各年仅分解现有曲线，不新增逐年账户。

风险率固定单family0.25%、总2%、缓冲保证金25%、buffer1.10。所有u/D/持仓/风险缩减中的每手风险同步为kN*M＋既定往返fee＋两侧不利slip，风险冻结到实际初入场；不可只改止损或只改手数分母。u共同缩放、整数floor、family普通优先、D只减不增、不重分配取消余额、不用当天卖出释放额度，同日已平不再入、破产永久停止均沿042。0.25N理论8倍手数不等于实际8倍曝险：手续费、round_lot、保证金和gap须逐一报告。现有连续barrier＋不利tick填价口径保留，披露损距小于tick情况，不临时删品种/调stop。

未知行情保留qty/初始风险/旧mark，持续退出请求沿既定下一合法旧epoch open的研究延迟处理；对应主标签仍unknown，不回填成熟。期末stale及全部未决long零价情景单列，不称有限真实损失下界。不能用末日无仓掩盖历史未知。

实际预算：067来源一次SQL已另计；新窄标签一次SQL（同时取代理）、12fit零SQL、24账户共享一次SQL。总新SQL最多3次，均有不同必要用途；0整DB/H5 hash、0下载、0旧EIA/期限/DAY金融重跑。代码新行为合成检查和一次独立静态复核足够后再root精确SHA授权；不为等UI或小报告格式重跑金融。每阶段fresh输出、保留失败、禁止自动重试。真实金融完成后必须独立agent全面复核数据/逻辑/预算/置信度，不能作者核心导入自证。

## 预先声明的解释与停止规则

主信息证据为NARROW SETTLEMENT在2020 stress自身净增长>0，并同时胜同宽COMMON和OHLC_PROXY；同源日配对log增长差采用252日circular block、2000次、seed20261018，两个95%CI下端均>0。base全披露；2023冷启两成本自身净增长>0且对两参照方向非负，矛盾不可隐藏。WIDE同样计算作为同政策信息证据，不用其结果改NARROW协议。

主政策证据为NARROW SETTLEMENT相对WIDE SETTLEMENT的2020 stress收益提高、最大回撤不更深，base同方向；2023两成本不出现相反的收益/DD结论。报告同source配对CI，但不把R分母放大或不同成熟训练包说成纯止损效应。总体目标需要有实质敞口的主动参考；若对照全程0手，其DD比较为N/A，既非自动失败也非通过，不能声称相对现金实现更低DD。若所有臂都空，则本实验不识别。

只将上述作为本固定包的继续证据；未知差异或历史stale无法有限界定而可能翻转时，资格标unknown，即便点估计好看。年度/family含零活动表、最大净赢家及前5贡献、实际退出净CNY右尾、手数/名义额/保证金/换手、成本、gap超1R与未决完整披露。胜率不是单独门，低DD由0手造成也不是成功。CI只描述固定历史曲线，不含重拟合/研究择题偏差，历史多次选择风险不能消失。

任一失败只停止相应固定信息/政策包，不扫相邻stop、滞后、阈值、family、年份、成本或换模型救成绩；负结果不否决所有AI或所有有条件窄损。获支持也不自动加注/发布，后续投注时钟和额度需另冻。实盘/正式版/推送/生产/CTP/邮件/订单均0。

## 当前反思与执行交接

新增研究参数仅0.25N和本轮真实结算标量/代理，既定风险率不加；正式参数和旧成绩改删0。期末权益、收益、DD、Sharpe、总滑点、交易数、胜率当前全部N/A。源候选存在、方案更直接，均不算目标实现。

开始是否在新增过拟合：**否，限本次实现前冻结的单点联合证伪**；研究者已见大量历史，择题和模型条件闭合标签风险仍在。继续有价值：**是**，它直接验证原目标中的全市场AI筛选和跨日窄损，避免先跑无信息机械pilot再重复账户。当前目标active且未达成。root在来源接受、代码冻结与独审后才授权实际；owner只实现本线各自唯一stage，不改LINE/registry或根总账。
