# Stage267 source独立实审结论

结论：**PASS_WITH_RESEARCH_SCOPE_LIMITS**。本审查source范围P0=0、P1=0、P2=5；月度数值审查委派另一位未实现月度生成器的独立agent，P0=0、P1=0、P2=1。两者均不认证生产、历史PIT、模型可盈利性或独立产品收益。

- 核32份已登记输入/源码/输出指纹；837个epoch与六位年月VT一一对应、原主映射保留，无十年串号。只查询本次选择的190,168个clean行，没有重复全市场原包清洗QA。
- 1,633笔成交全部有真实epoch/当日clean键，成交审计与trades逐笔相同。0次guard延期，故恢复日撤单/旧价分支只有静态审查，未被本次回放动态触发；不为此补金融重跑。
- 276次pairwise输入均等于精确epoch截至候选日的完整prefix，末日=候选日，开盘OI缺失计数与clean原值相等。22次prefix不足140观察，最少124；这是原AM120/未定义派生值默认处理的继承边界，不能称19项均成熟。
- 对1,440,036逐合约日行独立重算昨日持仓/收盘价链、真实价或估值carry、成交方向/仓差、turnover、cost、holding/trading/netPNL。价链和持仓链误差0，净PNL最大误差`5.68e-11`；合约和对组合净PNL`1.46e-11`，累计balance误差`3.49e-10`。
- 1,894条候选estimated_equity均与“前一日vendor balance＋当日holdingPNL（撮合/成本前）”匹配，最大误差`3.49e-10`。这是候选发生时点的实证，不冒充未导出的全日strategy equity轨迹；vendor可核账本是标签事实源。
- 对所有成交价另核当前真实收盘与tick：1,633笔价位均在当前native tick网格，最大舍入误差`3.64e-12`；相对真实close偏移为-1至+1.5 ticks。原引擎同日close/委托价成交是冻结研究约定，不能据此宣称实际市场可成交。
- 独立重算源日历预热/held缺失：AM120覆盖41,043产品日、额外140覆盖36,442；6个held missing产品日与实际账本起始持仓＋缺真实bar逐键一致。

元数据读取器和qmt固定参数原值已只读重建，导出`current_native_metadata_reference.json`及元数据CSV指纹。所有交易/账本size、commission、slippage均与此独立公式吻合；原run未绑定该metadata数据CSV、也未导出运行时tick/margin全字典，不能倒推历史PIT元数据资格。固定模型的2020–2022训练数据与缺行情后的账户路径影响均按协议披露，source是conditional retrospective fixed-policy。

月度108/60未重复全量计算；绑定`tools/stage267_monthly_independent_review.json` SHA`bea343656b6719403e29499056fe6e170d356b7b0d66c3e83518281ade5bfd5d`。该独立证据核3,618月产品行、544个字段/覆盖合格行（55月），其中535个有信息的候选（54月）：2020前61/7、2020后474/47；精确60标签误差`2.18e-11`，14,595个PNL特征哨兵误差`1.93e-9`。这些是同源历史候选计数，不是已训练模型或独立统计样本。

完整source报告：`source_final_review.json`，SHA`59a5a894b0f6b1db6e7eea9b95e5d78bf3895c4fc90d61d062a2d2092140cee1`；其monthly状态为DELEGATED_INDEPENDENT_REVIEW，无PENDING。32份输入核对、逐笔真实键、经济公式最大误差、1894条权益对照、当前metadata与成交价侧证均可追溯。初次执行报告按原字节保留为source_only_review_initial.json；source_only_review.json与source_final_review.json是同字节最终报告别名。首次数学执行script SHA与最终整理script SHA分别记录，未重新执行全审计。

独立金融回放0、模型训练0、模型预测0、下载0、主库/clean修改0；只执行只读审计和派生审查文件写入。过拟合判断否：未据收益改规则或挑数据；继续价值是保留有限研究资格和已识别的时间/缺口限制，避免把数据源通过说成PIT或训练已完成。
