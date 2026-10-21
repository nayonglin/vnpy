# Stage205 单 q / COMMON53 一次性训练实现（未 actual）

- line_id：`futures_full_market_long_signal_ai`
- 记录时间：2026-10-19 19:07 CST；19:09 CST 已完成源码预审并冻结最终 source bundle。
- 当前模式：全市场全品种独立做多研究的实现；不接正式策略/生产，不操作 Git 发布。
- 阶段性质：按已冻结 Stage204 的有限信息假说实现一次六折训练，供 root 审核绑定后唯一 actual 启动。
- 是否重要突破：否；没有训练或收益证据。
- 是否触发正式 A/B：否；204 已固定为本独立线 COMMON52 的内部对照，不是 C9 晋升。

## 外部调研与判断

本轮外部论文和 GitHub 调研沿用 Stage198/199 已完成记录，不重复检索或下载。文献中的期限结构/曲率价差不能视为本线 long-only 收益承诺。当前 q 仅表示同 exact product、同 u、严格相邻名义月份价格弦上的局部便宜程度；原 COMMON 无法代数恢复这个三点关系，但经济先验较弱。97 个有 action 的品种存在 q 不等于可交易性/PIT/alpha 认证。

判断：值得仅做已声明的一次有限反证；不按方向、年份、品种、scope、窗口、alpha 或模型救参。q 加固定训练均值插补构成一个预测增量包，不能声称已因果隔离数值和可用性。

## 本次变更

- 新增 `tools/stage205_local_curve_information_fit.py` 和 `tools/test_stage205_local_curve_information_fit.py`。
- 未修改 Stage129/130/156/201/204 源码、已接受源或本线/根账本。
- 新输入槽：第 52 槽（0-based）的训练折 finite q 加权标准化；总维数 53，新增 missing 输入 0。
- 模型参数不变：Ridge `alpha=1, fit_intercept=True, solver=cholesky`，单线程；scope 为 main/holdout_0/holdout_1，各 2020/2023 cutoff，共最多 6 次新 fit。
- 训练标签、成熟时间、family-u 权重和 COMMON 六个 scaler 不变；直接读取接受的六个 training identity/weight 表，先逐列匹配当前原始成熟训练身份及目标，不重算权重。
- 旧大数据只继承 SHA/size 并记录前后 stat；原 actions 指定列读一次，mothers/COMMON/q 各一次；不重读全投影，不访问 SQL/原始价格或旧模型。
- 六折先完成 q finite 正方差和完整 53 维训练 design finite 预检，之后每折仅 fit 一次。保存 portable53、scaler、训练 q/sequence 支持、正规方程和残差。
- 全六模型持久化之后，六个 q 系数必须全部严格小于零，才允许候选预测及任何新选择。任一为零、正或非有限，则 `completed_hypothesis_rejected`、`cash_eligible=false`，预测/选择/现金均为 0；不翻符号、不重训、不缩 scope。
- 若通过，候选完整 main 966,740 / held union 966,740 child-model 行、main / held 各 161,014 母事件。按接受的 156 完整池 score>0、D<K 先过滤再母内重选及 family 固定优先。q missing 不额外过滤。
- 旧 main 控制直接引用 156 冻结 choices；只对接受的 130 held scores 做必要的同 K 新选择，不重算旧 main、旧预测或旧现金。
- held diagnostic 沿用 130 的原 firstexit net_R_stress：family-u 后 equal-u；同 action 的未知增量为零但披露，distinct 未知保留 NaN；经济名义门固定为严格正且 differential unknown 为零。
- actual 只接受 root 对最终 source bundle/204/input bindings 的精确授权和 fresh `stage205_local_curve_information_fit/actual_run1`；本实现者未启动。

## 验证与结果

解释器 `.py311/bin/python`。仅运行新文件的 3 个 fixture（未运行旧 suite），全部通过，耗时约 1.4 秒：

1. 训练折内 finite q 的加权均值/方差排除缺失权重及未来极端 q；零方差/全缺失不支持。
2. 原 COMMON52 精确保留，53 维，无新 missing 槽；缺失 q 和恰等于训练均值的 q 均设计为精确 0。
3. 所有六折严格负向后才调用 forward callback；零/正/NaN/Inf/None、五折或重复折均无预测/选择副作用。

新增两个 Python 文件语法编译通过。physical fit=0、prediction=0、selection=0、cash=0、SQL=0、源投影=0。Stage207 独立 reviewer 核心源码预审通过，核心阻断为 0；其独立 3 个新 fixture 也全部通过。最终源码 SHA `632f36e933709a104c3d4d98126062c094dee031f4e6bc1cb70c25f46ce5d1d1`，fixture SHA `484d30aa549c7cad2a31ebad5f37e5ceb92dcc6f6bdc16ff0d82925837e447a0`；预审后仅追加三个兼容计数别名，执行/训练/闸门逻辑未改，已告知 reviewer/root；源码与 fixture 现已停止修改。尚无实际模型、候选选择或回测结果；期末权益、总收益、最大回撤、Sharpe、滑点、总交易次数与胜率全部为不适用，不能填旧结果。

## 反思与后续

- 运行前过拟合判断：是，有同一历史上多轮择题及新字段尝试的选择风险；固定方向/训练/预算/停止策略限制新增自由度，但没有新盲 OOS 保证。
- 实现验证后过拟合判断：仍是历史研究选择风险；本阶段没有看新 fit/预测/收益、没有用成绩调参，不能声称消除了选择风险。
- 运行前继续价值：是，仅限一次低先验的便宜方向反证。
- 实现验证后继续价值：是，待 207 源码预审并由 root 精确绑定后，一次 actual；全六方向门不支持则终止固定 q53/Ridge/K 包，0cash，不开展符号/范围救参。
- TODO：协调预审发现，冻结 source bundle，root 唯一 actual，完成独立实际结果审查；若全方向通过才按204另做最多4个新候选现金账本。
- 本阶段不更新 `LINE.md`、`research/registry.md` 或根 `memory.md/back_log.md`，交合入者依据真实终态统一处理。

## 19:09 CST 授权前缓存数值往返修正

root 在小纯数反例发现：原 Stage130 先对 actions 使用 `pd.to_numeric`，再以 17g 导出 training cache 后，对缓存再次 `pd.to_numeric` 并非幂等，会使精确 target identity 检查假失败，也会轻微移动原 sample_weight。尚未读取 actual 大表或运行模型。

本次只增加 `parse_cached_numeric` 并使 cached NUMERIC / sample_weight 用 `astype(float)` 恢复已接受的 IEEE 数值；原 actions parser 仍完全保留 Stage130 的 `pd.to_numeric`。不放宽任何容差，不改标签、数据、协议、特征、训练或选择逻辑。

新增一个 seed204 / 1,000 行的独立缓存往返 fixture：源数值经原解析→17g CSV→字符串缓存→缓存解析。先在旧解析下失败，标签 277/1000 个值漂移，最大差 4.4408921e-16；改为直接 float 往返后，标签、sample_weight 和所有数值身份均精确 `array_equal`，字符串 action identity 保留。仅新增 fixture 红绿各一次，原三个 fixture 未重跑，大表读取、fit、预测、选择、cash、SQL 仍全部为 0。

最终源码 SHA 更新为 `a1d506d20110bd82bc9baf74546659d5ea46b8af86717328f18fadf456096b01`；最终 fixture SHA 更新为 `c8dbdbc121b4635c23bc1e0ea837f01696ffb8ba7b26dde5ab184071f9b881a2`。已通知 root / Stage207 只复核这项最小 delta；源码/fixture 再次冻结。此修正没有使用收益信息，不增加策略自由度；继续价值仍仅为冻结协议的一次实际证伪。


## root唯一actual终态（2026-10-19 19:17 CST）

- 最终source `a1d506d20110bd82bc9baf74546659d5ea46b8af86717328f18fadf456096b01`、fixture `c8dbdbc121b4635c23bc1e0ea837f01696ffb8ba7b26dde5ab184071f9b881a2`；授权f6abfdbb4c1e2feaad0754f05b30544ad943848677b4c3f7660d4b8cebbf2397。原始actions沿130解析不变，仅cached17g数字用roundtrip恢复已接受浮点数，避免二次pd.to_numeric假identity失败；此修正发生在任何actual之前，没有新金融试验或模型重跑。
- root唯一session61331 terminal exit0，status completed/cash_eligible true，terminal计时120.816378秒。全六q正方差支持先于6个新53维物理fit；原weights/scaler复用且匹配六成熟训练域，0旧模型训练/权重重算/SQL/源重投影。
- 六q系数按main2020/main2023/held0-2020/held0-2023/held1-2020/held1-2023为：−0.037260388331、−0.040347351287、−0.044853425067、−0.039716630821、−0.016952634958、−0.030876948944。事前便宜方向必要门全过，不代表OOS或经济alpha。
- 方向门后才完成1,933,480候选child模型分数；main161,014母、held union161,014母和只补科学必要K选择的旧held161,014母都保留。候选main已选4,470（2020fold2636/2023fold1834），原控制156已选4,365；这些是选择不是交易，source selection_summary的内部changed_parent_choices是本候选K相对无K，不能误当新特征相对COMMON的变化数。
- 原target held0已知等u增量+0.002263041394R/held1−0.000802009474R；两组distinct unknown均7，same-action unresolved分别23/31。原标签不按K截断、R不是资金，因此即使训练同方向，也未过事前held泛化门；不得把unknown填0或现金好就覆盖此失败。
- manifest 43188B SHA `a373ba2e5d8e8835131f0752b3c2b4f6fc73af71a84b3c484d9f158c013ef13f`。源码/原数据stat未变化。原actions/mother/common/q各一读、六cachedtrain各一读，旧control score一次流读仅做heldK，旧main选择/模型/现金重跑0。
- 新增实际fit/cash=6/0，累计427/226。207独立模型/预测/held数学核待精确授权后一次运行；206依原204完整经济检验获准实现4本候选现金，actual尚0，旧157四账本继续复用。由原R与实际funded现金不同，仍量化完整收益/DD；本包held门既已不支持，后续不能改门晋级。
- 结束新增按结果救参过拟合否；历史择题及本次新增feature选择风险仍是。一次方向＋泛化检验有价值，继续改sign/模型/邻居/年份/止损风险救参无价值。完整目标active；权益/收益/DD/Sharpe/费滑/交易/胜率此模型阶段仍N/A，待单独206新现金。
