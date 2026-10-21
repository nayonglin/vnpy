# Stage213：既有成熟训练域与固定K行动域的单次盘点协议

- line_id：`futures_full_market_long_signal_ai`；记录时间 2026-10-19 19:38 CST。
- 工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`。本轮为有界机制验证，不是正式A/B、模型改造或回测；非重要突破。
- 当前完整目标仍为全市场高质量做多、收益提高与回撤降低，窄止损和加注须另有证据。本协议不改风险，不接生产或Git发布。

## 调研和判断

已读取registry/LINE、208关闭决策和209识别边界，并核129标签、130训练及156同K门。互联网核[Shimodaira2000原出版页](https://www.sciencedirect.com/science/article/pii/S0378375800001154)及[SPO作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)。作者1998草稿open超时，不重复请求，不据未读正文作推断。

判断：训练/使用分布不一致在错定模型下可能影响预测，但筛选训练也会损失效率、改变经验loss；论文没有保证金融增量。原训练不含当前D<K不是代码bug，旧K本来是后加执行政策。K重标还会改变目标值、成熟时钟、持有区间权重，因此不能把这些混为单轴。先仅确定原训练里被当前政策排除的行数和旧权重质量，有实证差异才讨论独立实验，不能凭差异大就自动训练。

## 冻结范围

- 协议：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage213_training_domain_probe_protocol/protocol.json)；SHA `17805a9fa6dd2df655ea9f4bebb84993f9c6beb6733d0772ea2c5812abee1033`，冻结早于214实施和实际盘点。
- 只读原130六个已接受training identity/weight cache指定身份列与sample_weight，以及小metadata和同源5587日calendar；每缓存只读一次，继承旧SHA和前后stat，不重hash大文件。
- gate完全沿156：先before-calendar blocked，再D源日历哨兵；K超calendar时仍可按D_date<K_target_date判定，否则D<K_index；相等不允许。不夹K到样本末，不以实际entry/close/收益或分数选择作为筛选。
- 旧sample_weight直接round-trip解析，只求和与分区，不归一、重算或截断。分fold/year/family/product报告三域行数、旧权重质量和份额；重叠fold不当作独立市场样本累加。
- 不读取Y、X、原actions、q、native价格、SQL或现金账本；不建新训练子集，不重标。新增fit/prediction/selection/cash/labels/SQL/价格读/大输入hash均0，预算仅6次缓存读。
- 最多16个按原sequence机械均匀抽取的gate anchors；只核新gate/分区数学，不重新验证原训练和旧账本。214实现与有限新fixture后，root精确绑定一次actual，215独立审查。

## 停止条件与结果

六折域全相同则没有domain轴；任一折无admissible或未解决时钟未知则不fit；身份/守恒失败先停止。即使有非空差异，也只进入另一次研究价值判断，不授权模型或现金。不能按年份/品种/份额门槛挑赢家。

本阶段新增脚本、训练、标签、预测、回测及结果均0；新增此协议及记录。原回测与参数修改/删除均0。权益、收益、最大回撤、Sharpe、滑点、交易、胜率全部N/A。累计实际427fit/230cash不变。

## 反思与TODO

- 开始/结束过拟合风险：是，历史择题风险仍有；本盘点不读Y或按成绩调参，不能称全程没有选择偏差。
- 继续价值：是，仅一次成本很小、能否决没有差异轴的直接盘点；继续扩展旧资金审查、立即K重标或复杂SPO无授权也无价值依据。
- TODO：214冻结代码与有限fixtures，root一次实际，215核新gate/分区小产物，root216决定有无值得实验的结构假说。总体goal active，不晋级或加注。
- 本普通阶段只写本线，不追加根memory/back_log；LINE/registry由root完成实际后统一整理。
