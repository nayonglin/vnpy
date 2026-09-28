# Stage043 新旧持仓标签联合快照

- 2026-09-06 11:57 CST；非重要突破；本线只读归档汇总，沿用持续授权。Stage042已验证黄金观察，原14项不重跑，本阶段只归并来源，不产生新回放/特征/标签定义/模型参数。
- 读取完整Stage040的1002观察及276根、9特征、原双头规格；旧14项按Stage041C冻结verified集合，使用Stage041B原manifest/receipt和98归档校验，新项使用Stage042原manifest/receipt。复用Stage042.completed_labels重新核验两类来源、观察前缀、当前特征、实际库存、账户损益与标签，不跨合同混算回执身份。
- 输出1002行observations.csv，label_source_stage明确stage041b_holding_labels、stage042_holding_labels或pending空来源；源信息不在9特征白名单。pending两标签保持空值，不能填0；旧14项、新数量、全部观察已完成的根数分别统计。原2删失根通过原jobs.json保持，无合格观察就不生成假特征。
- 完成数为全1002集合的并集，重复调度旧ID、未知ID、未解决新工作目录、特征列增减/重复、非有限或身份错配标签均拒绝。只有1002全部通过才training_ready=true，当前部分完成无训练资格。
- 共用run.lock，所有worker结束后才生成不可覆盖时间戳快照；输出前后验证源身份。counterfactual_metrics.csv逐任务保留同截止A/E权益、收益、DD、Sharpe、滑点/手续费、成交记录和非零日胜率，不合成完整模型C曲线。
- 新增/修改/删除科学参数及回测结果无；只增加来源字段和联合快照。研究源、代码、测试、合同与所有新旧标签回执身份进入summary。生产、CTP、其他线、registry、总账、全局记忆不动，不commit/push，不启动reviewer。
- 调研沿用本轮Python浮点文档与pandas官方格式源码，判断：来源归并必须保留各自冻结身份，不能把旧回放改标新版本。开始/结束过拟合判断：本轮否，没有依效用选标签或参数；历史反复开发选择偏差仍在。继续价值：是，完整且可追溯的标签是固定XGBoost训练的前提，不是模型收益证据。
