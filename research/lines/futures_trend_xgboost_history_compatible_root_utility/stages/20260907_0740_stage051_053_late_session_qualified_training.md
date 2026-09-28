# Stage051-053 尾盘新增信息资格与固定训练

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 当前模式：day；记录时间：2026-09-07 07:40 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 阶段性质：新信息资格、一次固定历史训练及只读另路复算；非重要突破，尚无新完整C。
- A/B：沿用版本实验纪律，原正式A与唯一退出层C隔离；本轮未执行新的A/C回测。
- reviewer：0。遵循用户最新规则，只在完整C收益提高、回撤降低并通过事前基本稳健性后启动；实现、测试、资格、训练和失败结果均不启动。

## 外部调研与判断

- [Hedging demand and market intraday momentum](https://www.sciencedirect.com/science/article/pii/S0304405X21001598)：论文摘要提出此前收益与最后30分钟的关系，也提示后续数日反转。正文页面受访问限制，未声称复核全文。其作用是提出可证伪假设，不证明本多日持仓策略获利，也不把价格/成交量代理称为真实gamma或订单流。
- [Intraday momentum in Chinese commodity futures markets](https://www.sciencedirect.com/science/article/pii/S0275531919311328)与[中国原油期货日内可预测性](https://www.sciencedirect.com/science/article/pii/S0264999321000134)：市场、日夜盘和时段关系并不一致；保留反证，不把日内论文外推为持续数日的退出优势。
- GitHub参考[nicolasdd1996/equity-intraday-momentum](https://github.com/nicolasdd1996/equity-intraday-momentum)的时段组织。未复制其策略、代码、NQ成本或绩效结论。均线距离、日线波动、持仓量迁移等旧输入已排重，不换名字重试。
- 判断：尾盘形成路径不能由相同日OHLCV唯一还原，具有新增信息资格；文献方向不统一，价值仅在一次固定真实C检验。UBJSON保存依据[XGBoost官方Model IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)，保留冻结本地3.2.0，未升级依赖。

## 本次变更与参数

- 07:18先冻结Stage051信息合同；新增Stage052工具及22项测试，缺实现RED后通过。07:22完成全部来源资格；07:25标准库另路验证。
- 07:26先冻结Stage053训练合同；新增独立训练适配器及18项测试，缺实现RED后通过。07:30执行唯一新规格训练，07:33另路核验完成。旧代码、测试、模型及失败产物不改。
- 新增输入仅两项：`directional_late_return_30m = sign(actual_position) * (close_14:59 / open_14:30 - 1)`；`late_volume_fraction_30m = volume_14:30..14:59 / full_trading_day_volume`。
- 窗口固定上海时间14:30含至15:00不含，30根区间起点分钟。按生产者`bar_date`归属交易日，全天量包含正确归属的跨自然日夜盘；不按自然日误切，不填补、不删失败点。
- 决策在完整日线`on_bars`后，15:00是当期信息边界；日线00:00为日期标签，不能当作此信息提前可知。实际C未来仍需逐决策复核。
- 修改参数：特征数9变11，其余不变；删除参数：无。标签仍原1002项，155成熟观察根，原276根/2删失库存保留。未重跑标签。
- 固定80棵树、depth2、eta0.05、min_child_weight20、lambda10、alpha1、subsample/colsample1、hist、n_jobs1及原seed、squarederror。每根总权重1；至少60成熟根；观察日和根标签终点均严格早于当月cutoff；目标仅训练折加权标准化。
- 目标比较区间仍2020-01-02至2026-08-28，本金150000。保留原LR、FU、成本和风控；没有新增入场、加仓、阈值扫描、品种/年度保护规则。

## 数据与训练结果

- Stage052全部1002观察、120合约、155根合格，失败0。30060尾盘分钟，706观察含前一自然日分钟；新增特征不同值分别943/1002。当前只证明A观察域，不证明487合约全局覆盖或真实可成交。
- 全日实际分钟时钟与expected精确相同，OHLCV与A快照及供应方日线一致，guard保留，正成交量/完整尾盘严格检查。498消费源、3输出身份前后通过。
- 标准库CSV/gzip/Decimal直接遍历原分钟，非调用Stage052计算函数；最大特征差`2.14279179086E-16`。这是另算法计算验证，不是独立reviewer。
- Stage053生成80个月metadata，其中60训练月、120个实际XGBoost回归头。首个训练月2021-09，60成熟根、428训练观察。1002原A点中574有预测、428未训练且预测空值；保存/重载预测差异0，网络尝试0。
- 189个A预测退出仅是双头严格负值的机械计数，不是实际C退出、独立交易样本或收益证据。不得与旧200预测退出挑优，也不能相加单事件标签代替组合收益。
- 4536消费源、3主要输出、80月metadata、120模型哈希通过；独立重建全部月前训练身份、根权重、完整CSV签名与80折训练签名。Decimal加权目标变换最大差`1.3877787807814457e-17`。未额外fit、原生predict或策略回放。
- 输入身份中原`model_spec_sha256`仍明确代表基底040规格，新增`candidate_spec_sha256`代表本次11特征规格，不混淆二者。
- 父训练器控制台末行沿用`stage044_holding_training`名字；新目录summary实际为`stage053_late_session_training`且feature_count11，已读回核对，未覆盖或重训旧九特征目录。

## 回测指标边界

本轮没有新回测，新增、修改、删除回测结果均无。以下仅列冻结历史对照，不冒充11特征结果；成交次数为成交记录条数，胜率为非零PnL交易日比例，不是闭合交易胜率。

| 指标 | 冻结原A | 旧九特征失败C | 本次11特征候选 |
| --- | ---: | ---: | --- |
| 期末权益 | 12,226,270.60 | 4,815,916.50 | 未执行C |
| 总收益 | 8050.847067% | 3110.611000% | 未执行C |
| 最大回撤 | -45.921573% | -47.936826% | 未执行C |
| Sharpe | 1.683943 | 1.474608 | 未执行C |
| 总滑点 | 1,100,560 | 803,570 | 未执行C |
| 手续费 | 0 | 0 | 未执行C |
| 成交记录数 | 655 | 665 | 未执行C |
| 非零PnL日胜率 | 54.241877% | 53.969957% | 未执行C |

旧C权益比A少7,410,354.10，双目标失败结论不变；新候选必须击败原A，不能以击败旧失败C代替总目标。

## 验证与证据

- 052/053及044关联测试83 passed in 13.51s。训练后本线`901 passed, 1 deselected in 70.57s`，命令：`.py311/bin/python -B -m pytest research/lines/futures_trend_xgboost_history_compatible_root_utility/tests -q -p no:cacheprovider -k 'not test_no_historical_catalog_exists_until_training_is_complete'`。
- 唯一未选原045测试硬编码历史模型目录不存在；保留旧冻结测试及原失败证据，其原断言由既有049B隔离空目录用例执行，实际完成目录错SHA拒绝亦测试。不得称未调整全套零失败。
- 原样归档本轮已经执行的两项核验命令及其输出：`artifacts/stage052_independent_verification/{command.txt,result.json}`、`artifacts/stage053_independent_verification/{command.txt,result.json}`。均为本轮实际输出后补落盘，没有重新计算后冒称原时间。
- 053原核验命令末尾检查了无关的`stage004_counterfactual_labels/run.lock`，该断言不能证明真正锁清理；07:35另行检查正确的`artifacts/stage004_label_batch/run.lock`不存在，052/053没有failure.json。保留原命令，不回改执行史。
- 07:33生产目录git干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。本轮未重新全哈希原A大数据库，不把既往SHA复核当本轮证据；未连接CTP、提交订单或写入生产。
- 本轮训练、核验、测试进程均已退出。只写本研究线，保留已有其他脏文件，不改registry、根总账、其他线、全局记忆，无commit/push。

| 身份 | SHA256 |
| --- | --- |
| Stage052 summary | `3a8ebe7ed70010886707f73de9115775af61a3ef9c537e016bb731bda35e0b20` |
| Stage052 input_manifest | `73131700ddd6940d620d46b5b03e6e52862224aa53e1eb00e122b40a3208621a` |
| Stage052 observation_late_features.csv | `bedf9ec2b676e308c4908551dbf7a9619ecb3af1d4383996f05d898366621d52` |
| Stage052 candidate_spec | `a97d84a0a324b9644fb65be00f506ef20d87fe8ec801a9ff434f2c2ed255dd43` |
| Stage053 summary | `9ca987c18819cd0e3ec0f6d56282825f2b0d4b5bea7a0e702d16471c5ab60715` |
| Stage053 input_manifest | `5caae241391ba4f7f021d529864f16a6ff31102f9fe2c344af51fdae4826bbd2` |
| Stage053 model_index | `c4746b80082fed35136a67f13f77c89d2a2b0e12a053449728baa6f78d3bfa7c` |
| Stage053 baseline_observation_predictions.csv | `75780171bcd1126628b7a537fcb426406767fe78caaa88ccdf3cc17c2a5c3f09` |
| 11特征合并表逻辑CSV签名 | `0066f1a44398f7649948242e6d58f3af5e3ed8660eff0be14aeb2eef0effc6e2` |

## 结论、下一步与反思

- 结论：新信息全量资格与唯一11特征历史训练完成，收益目标仍未达到，也尚未被本候选检验。不是重要突破或正式候选。
- 下一步有价值：是。实现新目录只读模型加载、真实C当前持仓/账户状态11特征消费及父进程全部合法决策重算，绑定实际C所需原始分钟源。禁止将052的A特征表查给C；不得在C内拟合或读标签。
- 上述实现和冻结输入门通过后只做一次同A全周期C。失败停本规格，不重训/扫窗口；通过才做原事前2倍滑点、完整干预年、最佳增量年剔除、保证金及滚动/独立起点检查，均过后才拉reviewer。当前不拉。
- 运行前过拟合判断：本次不是依据新收益调参；新增尾盘时段信息不能由原九项唯一还原，30分钟来自事前机制合同，而非结果后搜索。
- 运行后过拟合判断：没有新增收益择优或参数搜索，但历史失败启发新假设，整体历史选择偏差仍然存在，不能声称没有过拟合风险或未见样本验证。
- 运行前、后继续价值均为是：全量来源可用且模型能在关键回撤前开始学习，值得固定真实C证伪；训练完成和测试通过本身不构成交易优势。
- 更新本线LINE；不更新registry或根memory/back_log，不变更旧失败结论及生产状态。
