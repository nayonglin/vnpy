# Stage230：固定K单动作收益测量协议

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 21:03 CST冻结；非重要突破。上一目标轮229完成全量时钟盘点及独审，属于progress。本轮只测单动作收益定义，不改特征、止损、风险或正式策略。累计433fit/234cash。

## 调研与判断

先读registry/LINE/229及231/232的有限源码判断。231核SPO/CME/Dwork原文与作者GitHub；232用备用search_service实际核SPO原文及作者仓库。root首选网页请求连接失败，未据未取得内容新增主张，沿用已提供主源正文与两独立核证。判断：当前问题是预测payoff与实际K退出对象是否不同，不是均值学习天然错误，更不应立刻上SPO或复杂模型。约2%潜在域可能涉及趋势右尾，但并无可预测或alpha证明。

## 唯一实际与收益合同

完整1552456动作、399252母体/186400nochild；一次129动作49列（227原30metadata＋exit_reason＋232的18numeric）、一次原母7身份、一次calendar、一次132缓存NPZ只epochs/offsets/days/values/valid五成员。明确授权这个原recovery快照的新研究复用，保留原purpose字段及acceptedSHA，不调用恢复器、不重hash旧大输入、不SQL/下载；NPZ成员物理会整体载入，不伪称磁盘只读14k点。

主域仍原u资格且D<K，不看score、选择、未来闭合来改域。673478原closed_beforeK精确复制原Y/clock；16468原取消为policy诊断0/tradeYnull；仅14254潜在行新算Kopen两成本退出。K日forceopen优先gap/stop，τ==K必须重算；原force并发不重复卖出/收费，保留oldexit_reason与Kdue。unknown<=K吸收，open/intent/pending保持null，不用deferred或样本末价造known。非主域已知不行动policy0与tradeYnull分开；calendar未知不伪零。

每cost独立state/known/clock；base可quote不代替stress可quote。net=M×(Ksellfill−原entryfill)−原entryfee−新sellfee，滑点已在fill中不再扣。主窄R分母沿原0.25N×M；辅助common2N只审单位，绝非当前130/218训练目标。复制原Y token与clock不重算；新known保守为K日after_all_source_close。

原完整closed不保证K报价可表示：231给出tick1、Kopen2、stress3tick导致SELLfill非正的合法前缀反例。报价失败仅该costunknown，不改费用/tick补救；声称原完整前缀却找不到validKbar属源一致性错误，停止排查而非掩成新known。旧closed新quote通过时才有新成熟钟<=旧成熟钟；本轮只给全主域该条件计数，不读六traincache、不自动认证218同C控制。

## 验证与边界

233仅4新tiny行为后冻结，234独立3新tiny及源预审，root精确绑定一次actual。实际后234一次全新数值/时钟/母体/分区与新K点价核验，独立Decimal公式；不重复读原actions/mother、不再旧价格清洗/原路径或旧模型资金重放。无新增fit/cash。输出完整紧凑labels、14254点quote evidence、母体、有限统计及16机械anchors。

身份/源绑定/状态/时钟/守恒矛盾停止、终态保留，不自动重启；若数值及状态全无差异关闭target轴。存在差异也只证明对象不同，不授权训练、duration输入、重算权重/scaler、改K/模型/stop/risk、加注或生产。完整goal active。新增/修改/删除参数与资金结果均0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。

开始/结束过拟合风险是（同史适应性）；本协议未读新数值收益来选规则。继续此一次测量有条件是，重复旧盘点/弱scalar/恢复大系统否。root235结合最终独审决定是否还值得设计纯target对照。

机器合同：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage230_K_payoff_measurement_protocol/protocol.json)；SHA `ba46ca70fd2bc6387f0cd89d9c7bb7313283b1de38cc9893442487e7ec754f85`。
