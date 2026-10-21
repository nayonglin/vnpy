# Stage099 固定风险效用代理：仅曲率的有限对照

- line_id：futures_full_market_long_signal_ai；2026-10-18 18:47 CST；重要突破否，当前357研究fit/86现金，goal active未完成。
- 唯一当前目标：国内六所全部历史真实品种/合约long-only、高质量做多、成本后更高收益且更低回撤。正式月池/生产不在范围；不救097固定RFF包。

## 科学对象与判断

098基于Kelly、风险约束Kelly论文及作者GitHub、SPO论文/作者代码，指出非线性效用改变条件期望偏好，不新增信息。单事件log不等于重叠组合财富log，也不等于最大回撤约束。原log1p(f*y)/f被否决：070按含u成本风险预留，不是单纯价格止损分母。仅接受下述同经济量的曲率代理，不称实现Kelly、发现新信息或加注资格。

y为070自身NARROW stress净R，c为接受053 COMMON26中stress_u_cost_R=cu/(2*N*M)，沿083同源/同stress单位。d=.25*N*M，a=d/(d+cu)=1/(1+8*c)，z=a*y。唯一f=.0025来自原单family风险，不选择新风险小数。L目标z，G目标log1p(f*z)/f；L只是隔离曲率的必要同单位控制，不复活083为新alpha。两臂逐事件同号不意味着条件均值同号；有限Ridge投影效果也不能冒称oracle信息改善。

实际共同缩放、integerlot、margin及D只减使风险不同于f*a；目标只代理u的孤立连续计划预算，不写入未来q、equity、拒绝或释放资金。

## 数据、同容量与四fit

完全复用070完整399252母体/自身标签、053 COMMON26及身份；0新数据/标签/SQL/旧资格。只COMMON26标准化+26缺失指示，共52项+intercept；无RFF、外部标量、外部缺失槽、序列或新COMMON选手。两臂同成熟行、当前family并发唯一性→u等质量→mean1权重、train-only有限值均值/总体std、均值填补和缺失位；沿071接受函数。不能跨实验直接认定优于旧不同背景的COMMON。

2020-01-01与2023-01-01两cutoff，只有main L/G，最多4fit；Ridge(alpha1,intercept,cholesky)，单线程。训练仅本NARROW closed_complete_bar_model、u<cutoff且非空label_known_date<cutoff。2020预测20—22、2023预测23+至2026-10-16；每臂161014完整前向，共322028分数，notready/noref/未知不删。动作仍ready20 & finite score>0，再走070原经济/生命周期/现金规则；不因a或未来效用未知门控预测/交易。没有family留出，不宣称泛化；若此有限对照失败不花额外held实验。

## 定义域的整候选停止

仅在每个cutoff的自身已成熟训练域计算目标。任一训练行c无效/负、a非有限或不在(0,1]、y非有限、1+f*z<=0、log非有限，记录reference_ruin_or_domain_failure并整候选停止。不得删行/置零/clip/epsilon/改f/换品种/补数据/换模型继续，不先扫描未来最差值决定阈值。若第二cutoff才失败，已有fits保留；不清空重启或拼旧模型。

预测后仅在label_known_date<=end的闭合已知结果计算OOS目标域诊断。将来闭合结果发生同一边界，整候选反证，不回改之前预测或入场；完整母体仍保留。未知/open/取消依原状态，目标null，不变负类或0。若训练完成但后验闭合目标域已反证，停止候选、cash0，不为已否决模板再跑八账户；由102独审域和已完成fit。历史全部有定义也不证明总体正财富或负log尾可积。

## 八现金与单次独审

仅当目标域前置未失败，L/G×2020持续/2023独立冷启×base/stress=8cash，原070现金/报价/预留/费用/持仓/换约/缺价/破产规则：100w、单family.25%/总2%、bufferedmargin25%/1.10、.25Wilder20N/因果20low/noPT，u预留D只减不回收。不用080预过滤/OI/RFF、无加注。

主G−L 2020stress：收益差>0、DD不更深、同252源日块/2000次/seed20261018 paired日log CI低端>0。base和2023两成本收益差>=0且DD不更深；G自己四收益>0，所有账本正财富。空对照DD NA，不能机械通过。主预算/价格/经济未决按既有070/095未知定义分别报告；未成交潜在标签unknown不是实际cash暴露。若名义门过而实际unknown可翻转且无接受有限界，只给unknown，不给继续资格。实际历史stale不能因期末归零而抹去。

任何门或定义域不支持，停止这一固定log目标；不继续CARA/CRRA/CVaR/均值方差/f/阈值/Nfloor/风险扫描。通过也只称本固定代理曲率对照支持后续研究，没有family held/完整多起点/新盲OOS/生存资格/正式晋级或加注。

100模型/域0SQL，101现金共享一次SQL，102独审0新SQL/fit/cash；0新labels/download/旧金融重跑/大DB-H5hash。保留52特征契约、原输入精确引用、train IDs/weights/scalers/两target/域状态、4model/portable/NE、完整main scores和8账本/费用/年度/全family含零/CI/风险未知，不保存重复大head矩阵。源+最小新tests freeze→一次有限代码预审→root精确phase授权，失败保存不自动重跑。每次实际结果由独立agent全面核数据、逻辑、置信度和bug。

## 反思

存在实质历史选择/多轮目标尝试的过拟合风险：是。新增按本包结果选参：否，当前本包0actual。继续价值：仅一个固定风险偏好代理与同单位控制的反证，不靠变换声称新市场信息。目标未达，工程进展不等于收益进展。交易参数新增/修改/删除0；f取既定.0025；新增实验目标z/G曲率、共52项同容量，两窗/成本/风险不变。当前所有金融指标N/A。
