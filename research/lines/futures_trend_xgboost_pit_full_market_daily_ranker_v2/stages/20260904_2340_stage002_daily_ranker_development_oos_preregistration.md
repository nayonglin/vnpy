# Stage002 日级XGBRanker Development OOS预注册

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker_v2`
- 记录时间：2026-09-04 23:40 CST
- 阶段性质：固定标签、单模型、单selector、单次development OOS资格实验；不是sealed holdout，不是正式回测或上线。
- 前置：Stage001 V2决策`stage001_daily_ranker_v2_contract_pass_allow_stage002_preregistration_only`。
- 用户授权：后续研究操作默认授权；执行前仍需生成绑定实现与全部输入SHA的单次receipt，生产/CTP/订单继续禁止。

## 调研与判断

- XGBoost 3.2官方LTR要求同一qid连续且按qid排序，`rank:ndcg`输出组内相关性分数；本阶段使用日级qid和`ndcg@10`，不把输出解释为概率。
- 过去月级XGBoost失败的核心问题包括样本少、代理目标错位和整体替换；本阶段有1,046个日级标签计划qid、最后一折最多1,045个成熟训练qid，并保留线上逻辑回归，只允许一个池外候选挑战rank10。
- 判断：这是同时接入逻辑回归和XGBoost的保守结构。A保持正式LR Top10+固定fu；C仅在模型同月分数严格胜过A的rank10时替换一席。

## 冻结输入

- V2 receipt manifest/summary：`7428e753607ff44b39f0e3510e29493ec96b4163a35fa261791da7d819b27b79` / `a25817cbbd6da47dde8d711adf35ef70cc37422476060a2e652db37aaed7536d`。
- 模型特征面板：`1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac`。
- 标签日期计划：`426c40e5f0bc1a819e291abcc66c7f35eae6b9c5015634ddf8c42878c6afbc42`。
- 正式评分计划：`ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2`。
- fold计划：`3c9514e7fe10b36a775cd8c9bfd16641d493cc8a64209319780326ba0f9fbb32`。
- 日线：`f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
- 运行前后复验SHA、size和mtime；final存在即拒绝；不得读取其他行情、标签、正式分数值或holdout。

## 冻结标签与逐折开放

- Stage002禁止预先生成全量52,484行收益或relevance。价格源可在一次性事件消费后加载，但只有状态机按计划键执行entry/exit lookup时才计为标签值访问。
- 每折训练前仅打开`label_end < test_eval_date`的完整成熟qid；首次打开一行时读取同一实际合约entry和exit close各一次并缓存，后续折不得重复读取。
- `forward_log_return=log(exit_close/entry_close)`；entry/exit必须正且有限，身份和日期必须与Stage001计划一致。
- 每个成熟训练qid内对收益使用`rank(method='average', pct=True)`，再以`ceil(rank_pct*5)-1`裁剪到0..4；完全相同收益必须得到相同relevance，不用产品代码拆散并列。
- 每个成熟训练qid至少2个relevance等级；标签不使用正式LR分数、策略账户或产品ID特征。
- 最后推理折`2026-06-30`只允许52,425个成熟训练行/1,045 qid；Stage001剩余59行均来自`2026-05-29 -> 2026-06-30`，不得作为该折训练标签。
- 若36个效果月全部能在seal后打开锚点和最高挑战者，唯一标签值访问总数精确52,427行：52,425个最终成熟训练行加2026-05-29效果月的2行；close lookup 104,854次、收益计算52,427次。任何提前或额外读取均技术失败。
- 全部标签属于已观察development；sealed holdout行固定0。

## 冻结特征与模型

- 特征顺序精确为Stage001的19项rank与missing flag；产品、交易所、月份、年份、正式分数和标签不进模型。
- 每折训练只使用`label_end < test_eval_date`的成熟qid；最低252，实际37折训练qid范围261..1,045。
- 每折固定按`query_date, product_vt_symbol`稳定排序，`query_date -> 0..N-1`整数qid；断言每个qid只有一个连续区段，并显式调用`fit(X, y, qid=qid)`。实际booster特征名和顺序必须精确等于19项冻结特征。
- 固定一个`xgboost.XGBRanker`，参数：
  - `objective=rank:ndcg`
  - `eval_metric=ndcg@10`
  - `n_estimators=64`
  - `max_depth=2`
  - `learning_rate=0.03`
  - `min_child_weight=5`
  - `gamma=0`
  - `subsample=1`
  - `colsample_bytree=1`
  - `reg_alpha=0`
  - `reg_lambda=10`
  - `tree_method=hist`
  - `lambdarank_pair_method=topk`
  - `lambdarank_num_pair_per_sample=10`
  - `lambdarank_normalization=true`
  - `lambdarank_score_normalization=true`
  - `ndcg_exp_gain=false`
  - `random_state=42`
  - `n_jobs=1`
- 无验证集、early stopping、sample weight、自定义目标、参数/seed/特征搜索。
- 每折主模型与同参数重复模型各fit一次，共74次；预测最大绝对差`<=1e-12`且UBJ bytes SHA一致。

## 冻结A/B/C与封存顺序

- A：线上逻辑回归正式Top10 + 固定`fu.SHFE`，不改。
- B：日级XGBRanker对测试月formal rank10和全部池外挑战者输出原始相关性分数，仅作诊断。
- C：每月在全部池外挑战者中取最高分；仅当其分数严格大于formal rank10时替换第10席，否则等于A；并列按产品代码升序。selector不得使用未来标签计划可用性筛选候选。
- 若最高分挑战者在该效果月没有Stage001标签计划，立即技术失败、不给效果结论；禁止回退次高者、删除月份或改成只在有标签候选中选择。
- 预测、模型SHA和C选择必须先写入每折pre-effect seal；seal前测试月标签访问0。
- seal后才尝试打开formal rank10与最高挑战者两行标签；完整成功路径为36个effect折/72个测试效果行。任一行无计划则走上述技术失败；2026-06-30只推理，不打开测试标签。

## 技术门

1. 全部输入和授权receipt有效，运行前后稳定，final原子发布且manifest有效。
2. 标签计划52,484行/1,046 qid不变；完整成功路径只打开52,427行/104,854次close lookup/52,427次收益计算；训练relevance qid为1,045，至少2级且并列同级，同合约身份精确通过。
3. 37折、74 fits、训练`label_end < test`、未来训练qid 0、qid排序连续、实际estimator与参数精确。
4. 每折主/重复预测差`<=1e-12`、模型bytes相同、测试分数至少2个唯一值、模型至少1个split。
5. 37个pre-effect seal有效，当前测试qid在seal前标签值访问0；完整成功路径36折效果行72，最新折inference-only；候选无计划只能技术失败。
6. strategy backtest、true engine、holdout、CTP、订单和生产写入均0。

## 效果门

只在技术门全过后计算36个effect月的固定合约20日一席边际代理，全部条件同时满足才通过：

1. C实际替换月数`8..32`。
2. 替换月`C-A`正收益比例严格大于50%。
3. 替换月`C-A`中位数严格大于0。
4. 36个月`sum(C-A)`严格大于0。
5. 删除最好单月后的`sum(C-A)`仍严格大于0。
6. 回撤固定为`dd=min([0,cumsum(r)]-cummax([0,cumsum(r)]))<=0`；A/C月度累计log return路径之差`C_dd-A_dd`严格大于0。
7. 2023/2024/2025/2026四个自然年中，`sum(C-A)>0`至少3年。

## 决策

- 技术失败：`stage002_daily_ranker_contract_or_pit_invalid_stop_no_effect_claim`。
- 技术通过、效果失败：`stage002_daily_ranker_development_oos_fail_stop_no_true_engine`。
- 技术与效果全过：`stage002_daily_ranker_development_oos_pass_allow_true_engine_ac_preregistration_only`。
- 失败禁止重跑、调树、改标签、改20日、改selector、删月/品种、改效果门或读取holdout救援。
- 通过也只允许另行预注册A/C真实引擎全周期回测，不代表收益和回撤目标已实现。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage002不适用；本阶段只有固定合约一席边际代理。

## 过拟合反思

- 运行前判断：风险高但合同本身否。
- 原因：全部development历史已观察，但参数、标签、selector和效果门在打开标签前一次冻结且无搜索；任何执行后改变均视为过拟合救援。

## 预运行独立审查修订

- 2026-09-04执行前独立review首次结论为不PASS：发现全量标签预生成与seal前测试标签0访问冲突、无标签候选处理未定义、一次性消费和qid断言不足、回撤符号及并列relevance存在歧义。
- 本文件在任何真实标签lookup和fit之前完成上述修订；模型参数、19项特征、20日、37折、A/C一席selector和七项效果门未改变。
- 修订后必须重新通过独立预运行review，才能生成SHA绑定授权receipt。

## 继续价值反思

- 运行前判断：有，限唯一Stage002。
- 原因：直接检验日级LTR能否在保留逻辑回归主体的同时给rank10带来稳健正边际；若收益或回撤代理任一不改善，应立即停止。
