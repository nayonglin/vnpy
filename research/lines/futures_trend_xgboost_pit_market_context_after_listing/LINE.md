# AI选品XGBoost上市后PIT市场上下文线

## 研究线身份

- `line_id`：`futures_trend_xgboost_pit_market_context_after_listing`
- 创建时间：2026-09-02 13:12 CST
- 当前状态：Stage003已完成并失败停止；模型充分分裂且高频替换，但Rank IC、未来策略利润和未来市场路径回撤同时变差，本特征/标签/Ranker家族关闭，未回测
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 研究目标：在上市资格先于排序的条件PIT逻辑回归基线上，引入与原108项策略损益特征不同的逐合约市场收益上下文，检验XGBoost能否提高全周期收益并降低最大回撤。
- 隔离边界：不修改生产checkout、正式release、CTP、订单、邮件或launchd；不读取原XGBoost线sealed holdout文件；只有真实策略回测产生结果后才触发独立reviewer。

## 为什么另立本线

- `futures_trend_ai_pit_scorer_rebuild` Stage004已证明：108项旧策略损益特征、未来TopHalf二分类标签、固定浅树和50/50融合下，XGBoost月内退化为常数，继续扫参属于事后救援。
- `futures_trend_xgboost_pit_contract_returns`已冻结一份可审计的T-1持仓量选约、同合约日收益；其失败只发生在原正式排名把未上市品种放入历史横截面。
- Stage003已在排序前删除未上市样本并重算横截面标签，因此可以重新审计“上市后但历史长度不足”与“完整可用”两种状态，而不是用缺失值掩盖上市前事实。

## 第一性原理判断

- XGBoost只有在输入包含逻辑回归没有的信息时才可能有增量。把相同108项特征换一组树参数，不会解决月内不可分问题。
- 候选与Top9的相关性、共同下跌和组合路径是横截面选品问题的直接信息；它们来自独立市场价格，不依赖正式策略是否曾持有该候选。
- 上市不等于具备稳定历史。正式逻辑回归A仍可给所有已上市品种排序，但XGBoost覆盖层只允许使用满120个PIT收益日的产品；历史不足时必须回退A，不得补0或让missing分支把“新上市”当作收益信号。

## 外部调研与判断

- QuantConnect官方期货文档把合约链、持仓量映射和连续价格归一化视为不同问题，并展示从当期合约链按持仓量选约：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- XGBoost官方Learning to Rank文档要求同一查询内样本以`qid`分组；`rank:ndcg`优化的是组内排序而不是独立二分类：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- XGBoost官方实现要求传入`group`或`qid`，且训练数据按组排序：<https://github.com/dmlc/xgboost/blob/master/python-package/xgboost/sklearn.py>。
- 我的判断：若Stage001覆盖通过，新的模型候选应优先研究“月份作为qid的紧凑Learning-to-Rank”，而不是再做TopHalf二分类；但模型、特征和参数必须在Stage002另行预注册，Stage000不授权训练。

## Stage001覆盖门

- 输入只读取Stage003 OOS文件的`eval_date/product_vt_symbol/pit_logistic_probability/window_id`四列，以及冻结PIT产品日收益；不读取未来标签、未来损益或效果指标列。
- 每月按`pit_logistic_probability`降序、`product_vt_symbol`升序得到A排序。rank1..9为Top9，rank10为A基准，rank11及以后为挑战者。
- 每个`eval_date`使用收益产物中不晚于该日的最后120个全局`return_date`。完整产品必须在120日均有`status=ok`有限收益，且每行满足`selection_date < return_date <= eval_date`、无fallback、无跨合约比价。
- XGBoost覆盖层的活跃月要求：Top9和A rank10全部完整，且至少两个挑战者完整；不完整挑战者只禁止进入覆盖层，不从A横截面删除。
- 通过门：47个OOS月中活跃月不少于36；2022、2023、2024、2025每年各不少于6个活跃月；Stage003的8个有效fold各不少于3个活跃测试月；全部PIT和输入身份门通过。
- 任一门失败，整线决策固定为`stage001_market_context_coverage_fail_stop_no_features`；禁止降120日、补0、删月份、删A品种、降低候选数或按结果修改门槛。
- 全部门通过，决策固定为`stage001_market_context_coverage_pass_ready_for_feature_preregistration`；只授权Stage002特征与模型预注册，不授权训练、标签评估、回测或生产接入。

## Stage001结果

- 决策：`stage001_market_context_coverage_pass_ready_for_feature_preregistration`。
- 输入797行/47月；Top9/rank10/挑战者为423/47/327行，完整窗口为421/45/313行。
- 活跃月`43/47`；年度2022-2025为`11/11/10/11`，8 folds为`6/5/5/6/4/5/6/6`。
- 四个非活跃月均由`si/SH`上市后未满120日且进入Top9或rank10造成；机械回退A，没有删除横截面成员。
- PIT/fallback/跨合约违规均为0，双跑一致；标签列、sealed holdout文件、模型、回测、CTP和订单读取/调用均为0。

## Stage002门

- 只取43个活跃月中窗口完整的rank10与挑战者，共328行；A横截面和四个回退月不被删除或改写。
- 冻结六项特征：候选相对rank10的Top9相关/下行相关差、波动率/下行偏差对数比、加入Top9后的复利回撤改善和Sharpe改善。
- rank10六项必须按同一公式得到精确0；全部特征非退化、跨8 folds有非零值且双跑一致才允许预注册XGBRanker。

## Stage002结果

- 决策：`stage002_market_context_features_pass_ready_for_ranker_preregistration`。
- 矩阵328行/43月；rank10/挑战者`43/285`，每月6至9行，六项全部有限且rank10精确0。
- 每项在挑战者上均有285个唯一值，8 folds均有非零值；最少Top9下跌日47，PIT和双跑门通过。
- 结果只证明新信息源可计算且非退化，不证明Ranker有效，更不证明账户收益或回撤改善。

## Stage003门

- 月份作为qid，未来60日策略净利润在候选组内转为整数relevance；只用标签已经在测试月前完整成熟的历史OOS A月份训练。
- 至少18个训练月和120行后才测试；固定64棵深度2 `rank:ndcg`，双拟合，不扫参。
- C只保留Top9并替换第十席；预测层未来策略利润和60日市场路径回撤必须同时改善，才允许预注册真实引擎A/C。

## Stage003结果

- 决策：`stage003_stacked_ranker_fail_stop_no_backtest`。
- 19/19技术门通过；21个测试月、42次训练、双跑差0，模型最少185个split且月内最少8个不同分数。
- 效果门仅1/12通过；A/B月均Rank IC=`0.089192/-0.131471`，C月均未来利润代理比A少`30,537.62`。
- 2024/2025利润差均负，A/C月均未来市场回撤=`-8.6920%/-9.0716%`，C更差。
- 不运行真实引擎；禁止在本六特征、组内未来利润等级和rank10+候选上调参、换阈值或改方向救援。

## 当前反思

- 是否过拟合：Stage001-003固定实验本身**否**；结果后修改本家族任何参数或标签再跑将明确是**是**。
- 是否值得继续：本线**否**；总XGBoost目标仍可继续，但必须换独立信息机制并另立研究线。
