# Stage023 样本选择与可执行动作域核验

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 当前模式：无标签值的候选库存和调用顺序审计，不训练、不回测，reviewer0。
- 记录时间：2026-09-06 05:49 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 是否重要突破/是否触发A/B：均否；没有新增策略或绩效。

## 调研与判断

- [Selective Labels研究](https://proceedings.mlr.press/v139/wei21a.html)讨论因历史决策而无法观察部分结果的问题。判断：必须先定义预测服务的动作域；不能见到未成交记录就宣称缺标签是模型失败的原因，也不能直接套用其在线探索策略到实际账户。
- [mlfinpy meta-labeling源码](https://github.com/baobach/mlfinpy/blob/main/mlfinpy/labeling/labeling.py)区分主模型方向与是否接受信号的次级模型。判断：经济对象和标签形成时刻先于模型选择；不复制示例的未来补齐、末端处理或稀有类删除来补本线标签。
- 旧`futures_trend_signal_quality_ai/LINE.md`已记录信号质量及路径标签失败。当前拟议问题只是“原未批准候选能否补为同义训练样本”，不是把旧静态桶/路径标签换成XGBoost再跑。
- 当前读取的Stage010合同还引用[序列决策分布变化研究](https://proceedings.mlr.press/v15/ross11a.html)，明确不能只因A/C状态不同就把失败归因于分布漂移；本轮没有引入DAgger或额外历史策略迭代。

## 执行与代码证据

- 约05:40至05:47只读审计。没有新增/修改/删除脚本，没有交易或模型参数变化；仅新增本记录并更新本线状态。
- `qmt_roll_portfolio_strategy.py:1250`先记录计划快照，1263行检查`candidate_status`，1266行才进入`_open_position`；5545行将`is_opened`定义为`int(candidate_status == "opened")`。因此该字段在此处是预批准动作标记，不是未来成交成功标签。
- `stage007_runtime_gate.py:75`在已批准快照之后、原开仓调用之前插入XGBoost否决门。`stage001_history_qualification.py:37`的原276事件筛选与这个决策域相符；此前识别的真实0/0撤单已经保留，不是仅因最终未成交就删掉。
- 原策略先做方向、手数和AI池判断，再规划持仓名额。3571行附近的`short_signal_rejected`、3579行附近的`sizing_zero_volume`、3582行的`ai_product_pool_blocked`与4076/4125行的`concurrent_limit`不是同一种缺标签状态；快照`passed_initial_filter=1`不表示通过所有后续门。
- 源码逐文件对照Stage009输入manifest，4个唯一源码身份匹配。没有import策略类、执行on_bars、连接行情或生产账户。

## 无标签库存核验

- 原冻结A候选共856行，全部为`flat_entry`；排除固定FU后801行。原批准非FU根事件276行，与Stage001事件的candidate_index集合精确相同；其余525行全部是skipped。
- 只读身份、时刻、状态、原因、原池允许标记和计划量，没有读这些行的未来收益、MFE/MAE或策略标签。

| 原拒绝原因 | AI池允许 | 行数 |
| --- | ---: | ---: |
| short_signal_rejected | 1 | 202 |
| short_signal_rejected | 0 | 93 |
| sizing_zero_volume | 1 | 42 |
| sizing_zero_volume | 0 | 33 |
| concurrent_limit | 1 | 21 |
| ai_product_pool_blocked | 0 | 134 |

- 6组相加525。只有42+21=63行属于“池内但手数为零/名额不足”的记录，这不证明它们当时可成交，也不代表新增63条合法、同义的接受/跳过账户标签。原因字段有先后优先级，不能把一条记录的首要原因当作唯一约束。
- 标准库csv/Counter分组与内存SQLite的四列GROUP BY计数完全一致。没有依据未来结果挑样本或删月份。

## C新增事件来源

- 只读Stage009冻结C的284条模型决策身份，不读取分数、skip或收益。按完整带时区决策时刻、品种、实际合约、方向、signal、entry_context严格一对一匹配；两边键均无重复。
- 与A批准根事件共同276条、C新增8条，重现旧Stage010计数。进一步与全部A候选对照：6条有原快照且均为`concurrent_limit`，2条没有原候选快照。

| C决策日 | 实际合约 | 方向/信号 | 原A快照 |
| --- | --- | --- | --- |
| 2021-07-21 | jm2109.DCE | long/long_case2 | candidate174，concurrent_limit |
| 2021-09-30 | jm2201.DCE | long/long_case3 | 无 |
| 2022-01-13 | hc2205.SHFE | long/long_case2 | candidate234，concurrent_limit |
| 2022-01-14 | MA205.CZCE | long/long_case2 | candidate236，concurrent_limit |
| 2022-01-14 | au2202.SHFE | long/long_case2 | candidate237，concurrent_limit |
| 2022-03-03 | hc2205.SHFE | long/long_case2 | candidate251，concurrent_limit |
| 2022-03-07 | lh2205.DCE | short/short_case1a | candidate253，concurrent_limit |
| 2025-06-10 | cu2507.SHFE | long/long_case3 | 无 |

- pandas连接与内存SQLite LEFT JOIN/IS NULL复算8/6/2一致。新事件是“进入模型决策”，不自动等于最终新增成交。
- 本轮没有进一步读取原日内持仓来解释两条无快照的具体原因；仅证明原A表不能完整代表改变策略路径后的所有潜在根事件。不能把不存在记录归因为数据损坏或直接补一个A标签。
- 6条原A名额受限的事件，在C不同账户状态下可能成为合法动作；但A状态强制接受的结果不是C状态接受的效用，不能只按日期和合约复制训练标签。

## 来源与验证

- A候选：上游V4 `artifacts/stage004_counterfactual_validation/workers/A/entry_candidates.csv`，SHA `f62ea228198d06b709b02c31c40787c60d46e7a0cfdf9ed8d90335450cb118a8`，1,406,884字节，与原A回执一致。
- 本线Stage001 `event_features.csv`，SHA `33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1`；仅读candidate_index用于集合一致性。
- 本线Stage009 `workers/C/model_decisions.csv.gz`，SHA `2466ae26963ac81095ac07f52aaeb4d5a208a195215021e5724b3b71a7a220ff`，42,843字节，与Stage010输入回执一致；只解析上述身份列。
- 冻结源码SHA：策略`982977374be58ece5c5ee351a0bf60d0d1e8e213b7c480cc47d46c84ab90b45c`，Stage001特征构造`a235e8cb9d645ee8c7a366ba4678ac1d812a476a4ae86ee35aa2255b0fc95257`，Stage007运行门`8e9fd15b3ff588a2a2595c9bb03fdca23ff098777afb9a12f91735126d63e4f1`，旧候选样本生成器`039ec6cd1f76b8eb2de275d8fcc310557e2e70005f25c98c8478e6cc42066dd4`。
- 旧生成器`build_qmt_roll_ai_candidate_training_samples.py:159`是市场前瞻标签，使用固定未来窗、末端截短及风险距离下限；与当前真实账户反事实不是同一经济对象。本轮只读代码，未调用或将其产物视为可复用的合格标签。
- 本轮没有代码更改，不重跑pytest；上一阶段289通过仍只是上轮测试。当前实际验证是原文件SHA、冻结源码、候选集合/分组双算法、A/C身份连接双算法，全部执行命令正常退出。
- 05:48生产目录干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。没有遗留任务、CTP/订单/生产写入/commit/push，不改其他线、registry或根总账。

## 回测与结论

- 新增/修改/删除回测结果均无；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用。新标签/历史fit/predict/策略回放/reviewer均0。
- 决策：`reject_naive_unopened_candidate_label_augmentation`。不将525未批准候选当作缺失的同义训练样本，不强行突破容量或AI/方向门生成接受标签，不启动扩样重训。
- 该结论不证明没有样本选择或状态漂移风险，也不证明现有276样本足够。当前A原路径预测已弱，新增6/2事件身份事实不是其失败的因果解释。
- 后续若研究新的状态条件策略数据，必须定义合法干预及状态依赖标签，并验证其能提供原特征/标签之外的有效信息；不是改名重跑本模型，不能以补齐表格替代新机制或完整C收益证据。
- 总目标仍未达到，未产生值得启动reviewer的版本。

## 反思

- 开始过拟合判断：不是收益调参；值得核查样本选择是否构成可修复的结构问题。
- 结束过拟合判断：没有读新标签或按盈亏筛选，但本轮来自失败后探索，整个历史研究仍有选择偏差。不得用上述8个事件反向设计策略。
- 开始继续价值判断：是，先查动作域避免错误扩样。
- 结束继续价值判断：核对有价值；直接添加未批准候选标签、强行接受或把旧市场前瞻标签替代当前账户效用，无价值。只有新的合法经济对象和机制证据才值得继续实验。
- 合入：仅更新本线`LINE.md`及本记录；不改registry/根总账。
