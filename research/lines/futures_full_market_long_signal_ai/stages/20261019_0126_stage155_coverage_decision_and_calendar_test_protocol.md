# Stage154结案与Stage155：固定一次完整候选域自愿退出实验

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 01:26 CST；非重要突破；完整目标active。

## 154实际结果与接受范围

root唯一actual 13.810574500秒、exit0；目录10880 epoch/98代码/六所，18精确metadata缺项保留，F总45（精确metadata42＋符号尾期3）、clean9520。全399252母行与2020+161014完整保留，分别186400/44788无reference；已观察212852/116226引用均在目录，product mismatch0、已观察reference精确metadata缺0。没有按数据缺项删除品种、时期或母行。

候选表达目录10852、单品种公式未知PS28；母域候选表达395178/2020+159371。**表达存在不等于日期可计算、适用版本已证或可成交**；严格账户截止认证仍0，新生成清零日0。

独立154完整新表/原身份逐行一遍核验11.181442125秒，C/I/M0/0/0；未import作者计算，只复用accepted265 ID归一。作者6关键fixture RED缺实现→GREEN，最后0.021s；CLI help/无副作用/fresh-output通过。原表与新映射均未重跑。root新增raw pk字段probe确认本地9.7MB原快照本身无settlement_method/个人截止，不是JSON导出遗漏。行情/SQL/fit/cash0，累计397fit/206cash不变。

调研依据：[RQData官方字段](https://pypi.ricequant.com/doc/rqdata/python/generic-api)、[RQAlpha官方Instrument](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/model/instrument.py)。判断：metadata生命周期/结算方式概念不能代替个人规则和发布时钟；不从Commodity或同日交割推认证。152/153分级官方/署名历史来源保留，不继续无限补源。

## 下一实验的取舍

选择一次**明确自愿研究政策**，不把历史法定日伪造为已知。K为完整合约月前一月首个来源日历交易日；从K起不新入场，prev(K)收盘申请K开盘退出，原生命周期更早仍保留。现金合约也同K，这是额外市场退出选择，不是禁止实物推出来的法律义务。无法成交仍保留未决，不自动结算、不旧mark合成平仓。完整年月是已挂牌合约身份，但当前目录/日历/经济参数历史PIT局限不消失，也不证明K早于每次特殊法律/券商截止。

独立选项建议原先只对固定旧选择作后置veto，root纠正为**完整前向child先过滤D<K，再按原模型分数重选**：逐产品最高正分/原tie、普通优先F的family顺序不变。旧B选中的近月被排除时，仍允许当时其它合格月竞争，避免为容易实现而缩到旧已选集合。没有重训、重预测或按成绩改模型，旧标签目标不改，所以这只识别固定模型在新约束下的政策经济影响，不证明新AI信息或新目标最优。

K是现在收益前固定的一个日历单位，不是唯一最优日的推导，更不是2010当时已预声明；当前研究也受到已有stale案例启发，有叙事/历史择题风险。只试这一项，不扫描前月第几日、提前n天、个别品种年份豁免、止损或风险倍率救参。

## 预算与验证

新增参数：calendar_lead_months=1的自愿准入/退出约束；新旧生命周期分别记录，有效边界取较早者，不改源法定字段。新增/删除AI特征、训练参数、标签均0；原0.25N、100万元、family风险0.0025/总0.02、margin0.25/buffer1.1、1%往返容量、anchor/20low、费滑不改。

只新增VOLUNTARY_RESELECT一个臂：2020连续/2023冷启×base/stress **最多4资金、0fit、0SQL、0标签/下载**。旧131B四本只读，旧A/FX/随机不再跑。使用accepted132缓存及130完整main分数；现金原完整canonical母表保持，不能从新selected集合反推anchor变更。源完整性失败则0cash停止，不缩已核品种；恰无新机会则披露退化状态停止，不扫描低机会阈值。

四新本完成后一次独立审全部新选择/四账本/预算费滑/资金/未知/四配对CI/置信度与bug，复用原070固定2000×252日块indices；不重审旧6模型/大库/旧资金。主stress要求自身正收益、较旧控制收益严格更高/DD严格更浅/日log CI下端>0，另三自身正收益、相对收益不低/DD不深；新策略即使名义过门也不消除执行/PIT/券商/开放义务未知，不晋级/加注或完成goal。

本阶段实际新增金融仍0，新权益/收益/DD/Sharpe/费用/滑点/次数/胜率N/A；旧数值未改。最终协议[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage155_voluntary_calendar_protocol/protocol.json)包含固定源引用、四对照与窗口、排序/边界/停止和独审预算；实现与actual须root另签，不自动启动。

## 反思与证据

开始/结束按本轮收益调参的过拟合：**否**，K在新金融成绩前固定且全域同规则；已有案例启发/同史择题风险：**是**，不伪称全新样本外。继续完整全市场long目标和一次有限机制检验：**有价值**；继续全版本资格工程/旧数据重跑：**否**。本实验仍未证明稳定优势、极窄损上界或增加投注资格。

- [154真实manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage/actual_run1/manifest.json)，两张完整新表由其精确引用。
- [154独立receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage_review/receipt.json)；[独立stage](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0121_stage154_review.md)。
- [实施记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0115_stage154_implementation.md)；[独立方案取舍](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0116_stage154_next_economic_test_options.md)。
- [154root前置边界](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage_protocol/protocol.json)与同目录raw_field_probe/actual_authorization/CLI log保留。

普通研究记录，不改根memory/back_log/外线；不Git/新分支/worktree/正式生产/CTP/订单/邮件/自动化。
