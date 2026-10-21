# Stage593：重复赢家信号原额度上界独立审查

- line_id：`futures_full_market_long_signal_ai`；建立时间：2026-10-21 07:06 CST。
- 当前模式：收益前协议审与实际独审准备；当前没有probe实际结果。
- 先读registry；全六所98历史产品/95family目标active，547fit/282完成cash＋1旧partial不变；与正式C9隔离。
- 只写本唯一593stage和本593输出，不改LINE/registry/根总账/Git/正式/生产或其它agent文件。

## 冻结592协议审查

协议为`outputs/stage592_winner_addition_upper_bound_protocol/protocol.json`，root冻结SHA `c5b06c8614cac7e1e820dd156d1decc4c6e3de8c7d8b7a78a9a502d4cd780323`。本轮已实读完整协议，没有读其绑定的signals、经济投影、四A daily/positions实际数据表。

**协议GO，无实质矛盾，不要求修改冻结或另加gate。** 590已实读的原发布页/维护者GitHub证据沿用，作为机制约束参照，不重复web/大源或声明Turtle收益。590指出的共同scale在floor前造成挤出风险已准确固定：新增候选上界不足lot，须在任何共同batch、预留、排序影响及有效状态写入前无副作用剔除；没有存活新增时普通A集合/顺序/参数/转移均不动。

四个157 OWN book、cutoff与原winner顺序固定；先原家族winner再同actual epoch，不改次优；u余量净profit按剩余qty扣原BUY每手费和u不利SELL费，原fee_at(entry_fill)等价基础正确、不二次扣滑点/收费。F0保持原entry risk×剩余qty；u的risk、buffered-margin（分母不加fee）及完整entry-cap是单候选乐观必要上界，忽略竞争/未来旧仓容量占用，D只能减量/取消，不读D行情/退出释放预算。

完整枚举、无关键unknown、四A全零且batch-neutral时，才签冻结研究模型内条件路径恒等并免四C；正界不等于联合可分配量或真实C机会，关键unknown不填0。只读589 source-ready后的新增函数/必要fixture设计；源ready前不读真实大表。root真实唯一actual终态后才全输入/全部候选bounds/support独立复算，0fit/cash/A replay/SQL/native，不扩任务。

## 当前记录与反思

新增本stage；策略/模型/参数与回测结果修改0。期末权益、收益、DD、Sharpe、滑点、交易次数、胜率全部N/A；当前593的fit/cash/SQL/行情GET/实际数据表读取全部0。

开始/截至协议审按新收益过拟合：否，没有新收益/阈值搜索；同史自适应研究风险仍高。继续价值：验证一个必要界而先免不必要现金有价值；不能把粗上界当收益证据或据其分布救参数。完整目标未完成，无加注/正式/生产资格，历史工作不等今日日线。

后续在本stage顺序补source审与真实actual后的独审结果，不新开同号文件。

## 收益前592 v2完整域纠正，07:07

589实现追踪原156/157时发现592 v1“primary2020固定2020 cutoff”会漏掉该账户2023以后的原2023模型信号。root在任何actual前保留v1并唯一冻结v2；本593早先协议审未指出此漏项，已如实纠正，不用初始GO覆盖后续事实。v1没有实际实验，不能称为失败回测或产生两次probe。

实际仅允许`protocol_v2.json`（16,793B，独算SHA `6f7dbff2b321af3953c38ad05e1544338480e3bdaeacb82112453c978ab2ec20`）。本次只读这份小协议的窗口/source绑定：按每本saved daily的完整日期窗口使用全部157 signals，并逐u验证`cutoff_for`（u<2023用2020，之后用2023）；primary2020跨两模型，cold2023只覆盖后段。新增156/157源绑定，原成本/资格/上界/batch-neutral/0fit-cash预算不变。源码审及实际独审将按此完整域核，不按初始book名称固定模型、不重读大源或另开设计门。

## Source与唯一actual全面独审终态，07:15

收益前一次实读589完整源码及source_ready，未重跑5fixture、未预读真实表。源码SHA `54b120d1199f921b2788cabb6530a74292453867ffbb1990e5e1a8a4aff32a97`；v2跨cutoff范围、原winner顺序、原fee_at净利润、原F0与乐观risk/margin/cap、近零profit/一手边界unknown、无副作用条件声明及纯函数AST抽取均符合协议，无实质阻断。

root唯一589 actual session7714，文件终态exit0，3.965549917秒，4485候选，0fit/cash/A replay/SQL/GET/CI。root终态通知后才启动本独审：唯一session7857，exit0，3.833193792秒，**3805项核验全部通过，critical/important/minor=0/0/0**，没有失败、恢复或重复扫描。断言数不是样本N。

独立对每一原输入read/hash/parse一次：signals、8.15MB经济投影各一次，四OWN daily/positions各一次；不读native/fills/模型，不调用589算法或旧账户入口。独立重建逐u cutoff与原cash家族priority、u快照risk/margin/count对账、Decimal不利报价/剩余BUY费用基础、全部候选资格/上界/unknown，以及四本完整支持摘要。全部4485行的身份、状态、每个数值字段及support逐项相符。

| 原A book | 正上界行 | 不同u | 不同原持仓root | 正界涉及family | unknown |
|---|---:|---:|---:|---:|---:|
| primary2020 base | 686 | 341 | 204 | 39 | 8 |
| primary2020 stress | 479 | 315 | 142 | 31 | 3 |
| cold2023 base | 178 | 96 | 63 | 16 | 0 |
| cold2023 stress | 137 | 95 | 52 | 15 | 0 |

总计1480正界、1020零界、1974原规则排除、11unknown。11条均为`other_stale_valuation_affects_bound`，qty保持未知，不填0；四A原execution_unknown均仍为true。正界表示单候选乐观一手空间，不是实际C成交、独立机会或可累加的手数，更不是新增收益。原始跨成本/冷启动同史也不能当独立样本。

primary正界年份均覆盖2020—2026；cold覆盖2023—2026，但cold base的147/178行集中2026（50个该年原root），stress106/137行集中2026（38个原root）。同一个原root可在多个u重复触发，跨年root也不能把各年数相加当独立root。完整逐年不同u/root/family已在小summary中派生保留，未做CI或据近期分布补救。

**裁决：接受算术及非零技术支持，`no_first_modeled_divergence=false`；不能签全零路径恒等。** 当前有理由继续准备一个固定、原额度受限的新批次机制反证，但必须先冻结真实C的联合分配、开盘时序、多批次/共享容量；本probe不自动授权现金，也不声称稳定优势。11未知保留，不修数、不重跑或调整年龄/盈R/unit/风险/stop。

最终输出统一在`outputs/stage593_winner_addition_preflight_review/actual_run1/`：

- `acceptance_summary.json`：8,635B，SHA `7b69562cad4093b68e76956c20c2105b7d3df44d87d93bf5cf60daf97340981d`。
- `review.json`：488,157B，SHA `0f5c7506a4eadb3c05842fa8e8e4cc619d196eb64f9b44a4c53d02762fba3131`。
- `review_receipt.json`：1,846B，SHA `250565590602151c80149cb8db60a1d6408879205d613ce44f480033f156fb2f`；另存执行脚本与独立候选表。

审计最初输出前缀与root优先建议不同，完成后只做一次目录rename并更新小summary的review路径；原审计脚本保持实执行版本，receipt明示迁移，未重读原源/重算。

本阶段新增金融结果及参数改动0；权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A。547fit/282完成cash＋1旧partial不变，新增仅1次0fit/0cash可行性probe。结束反思：没有新增收益后择参，仍有高同史择题风险；必要界审完有价值，误把1480行当独立胜率/收益证据则无价值。整体目标active/未完成，无正式/生产/加注资格；593只此唯一stage，不改LINE/registry。
