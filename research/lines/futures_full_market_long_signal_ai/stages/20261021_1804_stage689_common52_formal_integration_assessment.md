# Stage689：COMMON52研究AI与当前正式策略的接入评估

- line_id：futures_full_market_long_signal_ai；当前模式day。
- 记录时间：2026-10-21 18:04 CST；工作区/分支：/Users/mac/Desktop/fian，codex/ai-training-data-expansion。
- 阶段性质：用户询问兼容性后的只读源码、既有证据及外部方法评估；不是重要突破。
- 是否触发A/B：若真正实施正式叠加候选则触发version-ab-experiment；本阶段仅建议，未创建实验臂、修改正式规则或启动回测。

## 结论

技术上可以结合；建议先把当前研究模型作为正式“多头首次开仓候选”的旁路评分，观察迁移效果。当前证据不支持直接合入、替代正式月度AI、给空头使用或提高风险。可优先复用特征与时点/缺失处理框架，权重、阈值和正式交易收益关系均待验证。

最近0.25%、0.5%、1%三个版本用的是同一AI和5246个预算前信号，仅风险预算不同；不能把0.5%当作经过新训练的升级AI。研究100万元的现金结果也不能线性映射为正式15万元的整数手账户。

## 已核事实与兼容性

1. 正式物料：子agent只读调用assert_official_checkout_matches_active_material(Path.cwd())成功。m0008_20261008T204054+0800_2a7420a9f955；strategy ai_top10_plus_fu_official_live_v1；ruleset stage037_stage034_long_short_mirror_hard_block_v1；source 2a7420a9f9550ab912b5c4a302a61acc5740b04c；release334d18f069de06df3aa7728203e942e3ecb94ce9；manifest94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474。这只核checkout正式配置与active物料，不证明当前生产运行、receipt或调度。
2. 正式AI是月度品种资格：10个模型排名非fu＋固定fu，共11个；原StandardScaler＋LogisticRegression学习未来60日来源策略净贡献是否为横截面前半。它不决定每笔价格方向/胜率。正式有long/short，保留C9的C2、broker10、0.5R stop/retry-once与Stage037对称拦截/5日换月延迟/目标合约历史。
3. 研究COMMON52为26原指标＋26缺失标记；Ridge alpha1回归旧一手own路径net_R_stress，输出连续净R分数而非胜率。只学long，D.open入场、初始0.25N/20low/anchor退出；K后加到选择与现金截止，训练target未随K重造。当前模型没有学正式的退出、日内止损与重试路径，也没有学short。
4. 研究还选择每个exact product最高正分的真实合约月，再按普通/F家族顺序取舍；不能把它直接塞入正式月池模型或现有pairwise runtime。输入/目标/分数尺度/目标合约规则都不同。
5. 629已有跨族反例：conditional_support=false、full_E_support=inconclusive，holdout_0后段AI自身负值；675/688账户盈利不等于“正式策略＋本AI”增量，更不能证明稳定泛化或可加注。

证据：

- [正式15万配置](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_official_live_config.py:56)；[Top10＋fu政策](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_official_ai_pool_policy.py:9)；[C9日内执行开关](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py:36)。
- [COMMON52/Ridge/训练目标](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:144)；[long自有标签路径](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:297)；[K与旧target边界](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage155_voluntary_calendar_protocol/protocol.json:63)。
- [真实合约月选择](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage156_voluntary_choices.py:117)；[泛化/条件增益不通过](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage629_full_admission_root_decision/decision.json:29)；[三风险只改预算](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage688_halfpct_risk_root_decision/report.md:13)。

## 最窄可检验的结合方式（仅方案，未实施）

正式月度11品种资格 → 原正式信号与native/risk闸门 → 仅long+flat_entry候选附加COMMON52分数 → 原仓位/入场/退出/执行。首先只记分，不改变交易；模型未覆盖、时点不明、特征缺失分别留状态，不能事后当低质量样本删除。

源码已存在可规划位置：_plan_flat_entry_candidates在4670汇集候选；_build_flat_entry_candidate_plan中4134保留原AI月池；4680已有评分调用、4683取native_openable集合，之后才分名额与资金。可以新增隔离的研究适配器，但不能直接将COMMON52权重装进原pairwise模型。不要在_open_position总闸门笼统接入，否则会把反手、换月和C9日内retry一同改掉。

- [候选规划与资金分配前接口](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4670)；[原月池闸门](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4134)。

若进入后续实施，先检查正式候选上的coverage、可得时点与分数/正式路径成本后收益关系；既有权重只作迁移诊断，不把score>0直接解释为正式交易期望盈利。只能使用正式信号决定前完整可得的数据，不能把之后收盘日线用于更早执行。训练若要改变，应另冻正式信号机会、正式止损/退出/费用目标与时间留出，保留被资金名额/池子拦截的机会状态，避免仅训练已成交单产生选择偏差。原52特征是否有新增量也必须验证，不能因换标签就默认有用。

最小未来A/C建议：A为当前正式精确物料/15万/原11池；C仅增加预先固定的一条“多头首次开仓质量过滤”，空头/反手/换月/止损重试/仓位/资金全部原样。先通过迁移诊断再定过滤合同，不现在扫阈值或挑赢家；不同时修改合约月、K、0.5%风险或初始止损。比较必须重放组合现金与名额竞争，不能简单从旧成交表扣掉被过滤的亏损。评价成本后收益、回撤、弱窗口、多起点、压力费用和漏掉的大趋势，不以胜率提高代替增益。若实际创建候选，须先完成正式六身份及相应A/B和多周期合同，本次未完成这些资格或新实验。

## 外部调研与判断

- [López de Prado原文：The 10 Reasons Most Machine Learning Funds Fail](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf)：原策略产生机会、次级模型判断是否执行的结构可参考，但次级目标要围绕原策略机会结果建立。它支持模块分工，不证明本模型已经可迁移。
- [mlfinpy项目原始标签实现](https://github.com/baobach/mlfinpy/blob/main/mlfinpy/labeling/labeling.py)：side给定后按其结果建元标签的实现可借鉴；本次不复制库、不安装包，也不把当前Ridge评分改称已验证meta-label。
- [Bailey等：The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)：重复使用同一历史挑选模型/规则会产生选择偏差。判断：先做最小迁移检验、保留失败和已尝试次数；训练内普通OOS切分不能自动抹除长期人工多试偏差。

## 本次变更、参数与结果

- 新增脚本0；修改/删除脚本0；新增/修改/删除策略参数0；只新增本阶段说明。
- 本阶段0fit/0新cash/0旧回放/0下载/0CTP或委托，数据区间、账户规模、成本与样本过滤均未执行新实验。
- 期末权益/收益/DD/Sharpe/滑点/交易次数/胜率：本阶段均N/A，不把688数字当集成结果。累计588fit/300完成cash及1旧partial保持，完整目标active。
- 两个独立只读子agent分别核研究目标与正式接入源码；未修改他线、正式/生产配置、模型或Git。旧stable路径与默认private状态缺项不由开发checkout替代认证；本轮无部署请求，不扩大生产搜寻或连接。

## 开始与结束反思

- 过拟合风险：是。研究跨族条件证据不稳，重复同史/阈值选择和改交易政策会产生选择偏差；独立盈利不能证明正式叠加增益。本次没有通过更多回测、重训或阈值救参改变结论。
- 继续价值：旁路/迁移评估有条件值得做；直接合入/上线或提高风险不值得。用户本轮问兼容性，已完成评估，未自行开新资金实验。
- 下一步建议：先固定正式long首次开仓的只读评分覆盖/时点/迁移诊断，再按证据决定是否值得冻结单一A/C；目前未启动。
- 本阶段不更新LINE/registry当前回测状态；不写根memory/back_log，不改全局memory。普通可行性讨论不当重要突破或正式候选晋级。
