# Stage034：一次构建严格同行池的三scope上下文

line_id=`futures_full_market_long_signal_ai`；2026-10-18 13:05 CST。沿`codex/ai-training-data-expansion`，不新分支/工作树。重要突破：否；仅实现033冻结输入，尚无模型、金融或alpha结果。完整全市场高质量long、净收益/回撤和后续小止损加注目标未达成。

## 合同、调研判断与范围

实施前读取registry、LINE及033 spec/protocol，protocol SHA`6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b`。033沿032已查原作者同行网络论文/GitHub的判断：关系对应信息值得一次有对照检验，不把相关当因果，不直接上GNN/PCA或改标签。本阶段只是实施冻结合同，没有新调研分叉、外部代码安装或参数选择。

新增`tools/stage034_peer_alignment_dataset.py`及六行为测试。只读009/011已接受的归一CSV、source calendar和小绑定，不读audit/原始绝对价格，不访问SQLite，不读取新政策成绩，不复用旧模型。除了诊断计数的label_identified，特征函数不使用任何label/D字段；该标记不进入ready、family面板、rho、pool或null。

开始新增按结果救参：否；固定20日关系窗、t=u−1、null和9列，不根据经济成绩改门。继续价值：是，为新增事前同行对应信息提供真实输入，不用数据文档代替模型结果。

## 实现与数值合同

- family r1先按(date,family)对全部ready均值，含未知D，去_F。u的shock在t=u−1；rho仅[t−20,t−1]，20个有限值齐全且各自demeaned平方和>0。按日期一次矩阵化相关，不逐事件逐peer逐20bar做Python标量循环。
- main同行池全可观察family移除own/F；holdout_g池剔除hash%2=g，再移除own/F。market4同样使用其scope允许池，但不要求关系窗口完整。测试query自身历史许可，用于自身关系，不进入训练同行池。
- 有效边包括所有正负与零rho；n保留有效边数，Z=sumabsrho；n0或Z0则q0/missing1，不把无数据当真实0。没有topK、sector、显著性阈值、前填或新暖机删除。
- null每query按固定prefix、u、own、peer做SHA排序，将原peer shock按hash顺序送入字典序rho槽。全pool hash排序跨scope复用后过滤，等价于每scope独立按相同key排序；不移日期、改变集合或重新估rho，不强制去除identity排列，one-peer相同。
- 保存`contexts.npz`唯一三个key：main、holdout_0、holdout_1，各shape`[194709,9]`、little-endian`<f8`。九列为market median/breadth/IQR/missing、peer_count、rho_abs_sum、relation_missing、q_aligned、q_shuffled。IDs两列sequence_index/event_id沿009原ready顺序；上下文原因状态另存gzip，无原始价量/大图。

## 六行为RED/GREEN与唯一真实构建

RED实际tool`0eee24` exit1：六项缺实现断言失败，errors0。实现后GREEN实际`c1059e` exit0，6/6通过、0.086秒。覆盖未来前缀、own/F shock完整排除及query历史许可、held反事实不污染训练上下文和四摘要、缺失/恒定/新上市与未知ready保留、null同值集合及onepeer、main分布和原ID存储合同。未跑旧suite，fixture fit/SQL/金融均0。

037独立设计审查已直接确认033实核C/I/M0/0/0无阻塞，故按root既有授权启动一次fullbuild，无额外确认。真实初始tool`9c74e0`，session`44167`，最终`6c10a5` exit0；2026-10-18 13:05:01—13:05:17 CST，耗时16.051261792秒。完整构建1、启动1、失败0、重跑0，未因观察等待重启。

## 构建结果及边界

- 父母表399252行；194709 ready全部保留。541 unknown保留，已知194168沿父合同不变，没有按未来状态删除。95个catalog family由98产品去_F形成，其中ready family94；全目录身份不作为模型X，不用未来可用性筛pool。
- 完整calendar为5587日期的绑定小NPY；研究scope为其中4074源日。窗口不足/缺失保持ctx missing，三scope均为16018 query_history_missing、178691 relation_ready；状态覆盖相同不代表同行值或q相同，scope按各自池计算并保存。
- main market4全ready共778836个标量与009原四列对照，最大绝对差`6.661338147750939e-16`，满足033的1e-12数值合同。此容差不是经济门。
- Pearson矩阵超[-1,1]的最大roundoff同为`6.661338147750939e-16`；共41064个矩阵标量发生舍入夹边，包含计算矩阵的对角等项，不能解释为41064个交易信号被改。全部在033允许1e-12内，无预测clip。复用hash共8724581次digest，不增加null种子。
- contexts压缩NPZ为24275877字节，SHA`ba38c6386d56c290f5dbaf3770b9db21c754e8e4f9185e32a9328c0ce45ab272`。
- ID gzip为8193711字节，SHA`b829623c1c1d716a7af3cdc21a0dc0cbab3adba9ae85dfc98fe7ada93e98963d`，与原ready映射口径一致。
- 最终manifest SHA`2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990`；源代码SHA`9b3e7ac37cbe46e0124af9905e63d4d457d37f9853a3ca3d69e28650d7ba5f25`；测试SHA`cde2cfc3062d054ddd12343e05ca7a1a8674d50e452bba49d0fd7e5fa6f8fb0d`。

manifest稳定提供context_npz、event_ids_csv、parent_manifest、parent_review、source_calendar及source_calendar_scope_dates、counts、source/test/actual_terminal绑定。已发给root和035消费；源码、manifest和数据不再改。真实session、起止和tool exit另存tool_execution_receipt，RED/GREEN日志与收据保留；artifact_inventory明确角色与required，未复制原库、audit、OHLC、绝对ATR、凭证或模型缓存。

## 财务与后续

新增fit0、SQL0、盘点0、下载0、金融回测0、provider/CTP/订单0，大库未访问/重hash。修改/删除原策略参数与旧成绩均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、真实胜率全N/A；没有执行容量、组合生存或加注资格。

结束新增选参过拟合：否，未看经济成绩也未改输入；20日相关噪声、已有研究选择及历史重建不是PIT字节证明的限制保留。结束继续价值：是，供035按冻结108fit和037独立数值审查；不把这次构建视为关系有效或完整目标完成。本agent到此停止，不追加新设计或扩大检测。
