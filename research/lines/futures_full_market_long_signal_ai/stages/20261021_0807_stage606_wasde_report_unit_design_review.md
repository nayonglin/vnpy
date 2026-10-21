# Stage606 WASDE报告单位、月份控制与MY验证方法审查

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 08:07 CST。
- 先读registry及604/602/603小结；未读原件、标签、价格或大表；0fit/cash/SQL。唯一606方法建议，非重要突破，不改LINE/registry。

**建议有条件采用B月份均值、C同B＋一个训练月份内中心化revision斜率。** 它能检验固定旧52之上的报告平均预测误差，不能直接证明新增交易利润、独立因果alpha或稳定跨品种优势。

## 先冻结目标和权重，避免train/OOS不一致

root已说明538有原Ahat/y/w缓存，但OOS未必有可复原的原training w。推荐接受root的新口径：`e_i=y_i−Ahat_i`；每u的已知eligible DCE.C child等权平均，再每报告r内已知u等权平均，形成唯一`e_r`。**train/OOS同式，原w只audit，不重建。** 此目标是新的“等u机会平均残差”，不是原130重叠持仓区间加权目标，也不是实际选中交易R。

报告只作用于原当月、release+2自然日NY00后合法u，沿603 targetMY/条件vintage和缺失合同。同一label不能重复分派多个report。资格/feature来源可用域只依赖u已知事实，不能用未来label完成性筛动作；训练目标再要求原eligible、finite y/Ahat、u<cutoff且label_known<cutoff。OOS诊断仅用评估截止已知同一标签交集，不知值不填0；各report的known-u/child比例单列。无known u的报告是target unknown，不造零报告。

训练仅`MY_start+1<cutoff_year`，从而2020排2019/20、2023排2022/23，另外逐条成熟闸门仍不可省。完整MY源边界与目标成熟是两件事，不能互相替代。

训练report全局等权`a_r=1/M`、sum1；**这不是MY等权**。若每MY报告数不同，二者不能同时成立。此处MY用于后继成组验证；不把日/子合约复制增加样本权重。

## 可直接实现的最小头

同一有效报告集合上，训练公布公历月m的`b_m=mean(e_r)`，作为B。C共用原b_m，不重估一套更灵活月份项。

训练月内revision均值`mu_m=mean(x_r)`；全训练单个尺度`S²=Σ a_r(x_r−mu_m)²`；`z_r=(x_r−mu_m)/S`。不逐月标准差（零值季节会除0），不逐月gamma、不加MY截距、年份/交互或额外lag。

唯一新增斜率为：`gamma=Σa_r*z_r*(e_r−b_m)/(Σa_r*z_r²+1)`，无截距；目标`Σa_r(e_r−b_m−gamma*z_r)²+gamma²`。sum1必须写入协议：all-ones与1/M会让同一个“Ridge1”有效强度相差M倍。因为训练z每月均值0，训练共用b_m不会因新增斜率暗中改变；所有均值/尺度只用该cutoff训练。

该cutoff没有训练报告的月份：B/C共同offset0，精确退回A；不借全局均值/未来月份/其他折。宏观缺失或不可用也共同退回A，合法零revision仍是已知值，不当缺失。S无正方差或无有效报告剩余识别空间即不fit；不制造方差或临时换标准化。

月份控制不是0自由度：B有K个已见月份均值（至多11，May无pair）；C相对它只增加1斜率。相比裸scalar，它牺牲功效以排除公告季节效应，不能事后因系数小就删月份项。应报告每月报告数/MY数、有效K、within-month方差和零/非零支持，不用收益决定合并月份。

## 原52残差要不要OOF

**本次不必为了条件前向校准重训52做OOF。** 只要旧A、B/C所有训练/标准化都严格停在cutoff前，未来固定前向比较仍可证伪这一个组合；但train Ahat是同训练资料的in-sample nuisance prediction，存在meta过拟合、收缩偏差/增量衰减，不能把残差回归系数当DML、因果效果或“已排净价格信息”。

若做precutoff leave-MY-out而Ahat仍来自看过该MY标签的旧52，至多是**条件头敏感性**，不是整套OOF。真正全管线OOF需在各外层内重训52及其统计，违背本轮0旧模型重训边界；不假造OOF、不因此扩6×MY训练。月份中心化也不会神奇消除旧模型同样本偏差。

[原作者DML论文](https://arxiv.org/abs/1608.00060)将预测与因果估计区分，并为其正交推断用cross-fitting；[sklearn官方Stacking文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingRegressor.html)警告同数据prefit stacking风险。实读[维护源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/ensemble/_stacking.py)，prefit分支直接全训练预测，非prefit才调用cross_val_predict。我们的判断是保留偏差边界、用严格前向证伪，而非声称实现了该正交方法。

## OOS完整MY怎样预声明

主比较为同report已知target的paired squared error：B误差平方与C误差平方之差；每MY先对报告取均值，再各MY等权汇总，并逐MY列正负/最差MY。源完整、报告target可评估、跨cutoff/尾部未完与unknown分别标记，清单先于结果冻结。预测误差改善不是现金收益改善。

2019/20、2022/23跨模型cutoff，不能作为整MY未见头的主验证；可另列真实部署混合预测的描述值。2026/27未结束、2025无pair造成缺段的MY不能冒充完整。完整MY应按源中固定目标MY的实际预测周期及应该存在的相邻Proj报告配对界定，不机械等于12个月或中国合约到期年。

root603数据只有160pair/17MY，2023+25pair、14非零，且2025无pair；这些是源上限，不是成熟标签支持。完整前向MY可能非常少。普通[GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html)只保证group不重叠，不保证时间方向、原52未见该组或足够功效；本轮不随机打乱MY做伪前向。

建议先冻点值否决：完整MY总体C−B MSE不改善，或两个前向时代方向反转，即关闭精确校准包；若某时代没有完整组则明确inconclusive，不能算通过。即便全部可见组方向好，也只保留条件线索，不承诺95%效力；三组全同号仍不可能靠双侧精确符号检验取得5%显著性。无行IID/按日bootstrap/逐子合约t值，无为得到CI扩多套重采样。原52并未按MY重分折，必须披露，不能称全管线MY盲测。

后继若root另授权选择验证，先看全98/95原域的选择身份与参与改变；没有动作变化就省现金，不能放大gamma/降低门让Corn成交。当前仅DCE.C、没有跨family可推广证据。

## 结论与记录

方法有一次低容量条件证伪价值；本606只给建议，未授权/运行模型或金融。新权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A，累计仍547fit/286cash及1旧partial。开始/结束新增拟合过拟合：否；长期同史择题与低MY数风险高。开始/结束继续价值：有，前提是固定上述目标/对照与有限声明，不能称稳定优势或扩作物救参。

小decision：`outputs/stage606_wasde_report_unit_design_review/decision.json`。原USDA语义复用603/604，不新找农业数据；另核[Ridge官方目标](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)以锁定权重/λ含义。
