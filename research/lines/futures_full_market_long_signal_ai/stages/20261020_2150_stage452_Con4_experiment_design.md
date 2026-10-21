# Stage452：Con4单一增量实验的只读冻结设计提案

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 21:50 CST。非重要突破；只读源码/小元数据审查和设计，不是actual授权。
- 用户独立全市场98产品/95家族/六所long-only目标不改。研究A严格是130 COMMON52 Ridge→156自愿K→157四现金；不重绑正式C9、月度AI池、promotion。
- 已读registry与本LINE头部、450 next_scope、128/155/432协议及130/156/157/205/433相关源码；未import被审程序，未读training CSV/common/labels/scores/价格缓存，不训练/回测/API/SQL/网络，不改旧工具、LINE/registry或其他线。

## 设计判断：推荐53列，不把N.A单独送入模型

固定原26值的train-only z与原26 missing列，按130 `design`逐位保留，再只在index52追加`Con4Net_All_visible_train_weighted_z`。mu/sd仅按该fold原成熟训练行及原sample_weight在可见finite子集计算；raw未映射/例外/未发布/过期仍是null+reason，标准化新项贡献0。8个原映射不扩，另90 N.A保留全母域；同一产品-u快照复制所有原child，不按收益/月挑source。

**不推荐简单54列的missing flag。** 它会直接告诉模型8映射/90结构N.A和异常时期，A52→C54只衡量值+availability整包。要证明数值超越availability，公平控制应是同52+同可见flag+恒零数值的真实mask-only训练，共另6fit，合计12，不能用手算系数/正规方程伪称0fit。本提案只推荐C53六fit；不追加这个控制、随机mask或grid，结论相应限于单标量包，不能宣称已剥离所有缺失机制。

53也不是N.A行逐行score不变：联合重估会改变原52系数和截距，须披露N.A行score/选择与现金的间接变化。原rawCon4=0与缺失不可混淆；缺失新项0只是有限线性设计中性值。

## 严格复用与最小接入面

- 原130六份`training_identity_weights`逐行复用identity/Y/sample_weight，不重算mature interval-union权重，不因Con4缺失删行/重新归一；原fold scaler及52输入不变。原17g按round_trip/astype(float)恢复，避免重复to_numeric更改末bit。
- 已核130 `design`原公式只按列z并append原missing，**没有sqrt(p)维数因子，容量尺度为1**。新Con4也用scale1，不将52基底改除sqrt53；Con4恒0时原52目标/正则数学等价A，不真实重fitA作检查。
- 同2020/2023 cutoff×main/held0/held1恰六次新Ridge(alpha1/intercept/cholesky)，不改y、止损、K、风险、阈值、模型；旧A52 scores只读、不重算。新53正规方程含截距54×54，仅53项惩罚，保存portable与全forward一致性。
- 205已有`q_statistics/design53/prepare_folds/fit_arrays`纯数学复用路线；不承接其旧方向gate。433只借原训练源/完整ID核验和`select_scope`，不借HGB或其成绩。
- 原156 `select_full_pool`硬跳非main，held按433局部alias成main后恢复scope；仍全child先u资格/正分/D<K过滤，再产品argmax/tie及普通优先F family次序。原COMMON52的main156及held205/207选择只读。
- 现金采用原157 `make_voluntary_signals/apply_boundaries`的私有适配和131 unchanged kernel；完整原mothers用于canonical。**旧157 CLI/authorize/baseline_references不能原样用**，其旧比较是131B；Con4新wrapper必须把accepted157自身四本绑定为A。

## 前置source门与停止界

451仅clock设计，不是可见数值。root先接受451并完成必要源clock join及独审后，才能做支持报告。先只读原训练identity/u/family/w，usecols排除Y；六fold支持全部通过后才读原Y并启动六fit。支持按distinct availability group及episode/channel去重，同时报各年和held覆盖，不能把835 asof、6680行或child/daily复制数当独立周。

硬门限于可识别性：六fold原身份/权重/52 scaler一致、有限Con4正方差且至少2个独立可见发布时间组、训练和held预测各有至少2个映射family、训练及各预测块可见episode跨至少2个源年份。逐2020—25/held年度覆盖和权重集中度必须完整披露；2026没有新源就N.A，不延长ffill。旧406的400周/每年35仅作历史参考，不机械强制，也不由这个最小门冒称功效足够。任何源资格/硬门失败就0fit/cash停止，不动clock、映射或期限来过门。

## 四现金、CI与置信度

有实际不同main选择才最多4新账：2020连续/2023冷启×base/stress，原100万、0.25N、family风险0.0025/总0.02、margin0.25/buffer1.1、1%日量与往返半量、预算/费用/滑点/退出全部冻结。旧157四本只读不重跑，其他历史好臂不作控制。

沿原157经济门：四本自身收益正、财富正；主2020stress相对收益严格更高且DD严格更浅、原252日×2000配对日log差CI95下端>0，另三相对收益不低/DD不深。原stale/entry/capacity/生存unknown分层不变，禁止epsilon修复或重复扣滑点。两held仍用原129 first-exit而非K现金，独立披露增量/未知，不能替代四现金门；同史重叠与多轮择题使CI只属历史条件区间。

## 调研、反思与记录

本次复用447/448/449已核CFTC定义、Liu等2023原研究及维护者血缘，452新网络0。判断：美国周频、主要4周风险溢价不等于中国发布后0.25N first-exit/K/成本后收益，但无需另做4week价格代理工程才可检验当前一个固定新信息；负结果也只否决本配置，不能否决论文或所有COT。

开始/结束新增按本轮收益过拟合：否，0Y/fit/cash且不按新分布选参；长期同史择题风险高，不能归零。继续价值：是，仅这一次固定增量证伪与必要源资格；追加网格或无限来源工程否。后续实际每次回测必须独立agent完整review结果/数据/逻辑/置信度/bug，不能以作者自检代替。

新增/修改/删除策略运行参数与回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。未获金融、增加投注或生产资格。累计沿450的460fit/250cash及1旧partial不变。

机器提案：[proposal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage452_Con4_experiment_design/proposal.json)；SHA `1f6fb9ba37d8c55b0223709dacb900597fcbc74fc19f43bd90be5f2e3efb6566`。本agent仅写本唯一stage与proposal，由root读取并决定最终冻结，不改LINE/registry/总账/Git/账户/production。
