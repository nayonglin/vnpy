# Stage467 已有前缀状态与时钟测量独立复核

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20T23:10+08:00。
- 性质：独立只读state-clock测量复核，不是backtest，不是重要突破。新增策略参数、目标、窗口、权重、模型、现金账和金融结果均0；不修改466/LINE/registry/Git/生产。
- 调研与判断：本阶段直接核原129 `simulate_action`、070 `after_all_source_close` 和130 `fold_slices` 的小源码语义，复用464定位及465冻结范围；不展开新网络/GitHub研究。判断是已观察前缀可构造，既有Con4 alpha/收益/加注结论不变。

## 核查结论

最终`status=completed`、`core_blockers=0`、`core_problems_remaining=0`。代码及派生数据未发现核心分类、时钟或守恒问题。重建1,552,456个完整动作、399,252个完整母行、186,400个无子母行，98产品/95家族/六所全保留；后期上市或无子母行不要求在早cutoff已有观察支持。

- 两个cutoff分别严格截至2019-12-31（source index3645）、2022-12-30（4373）；在派生母表日期/索引映射上独立重建，不重读原calendar。日期等于cutoff不可用。
- D=u+1；entryunknown/cancel/entry-cost-unresolved不造entered暴露；`u_action_eligible`单独于`filled`，原129有容量不合格后仍继续模拟的行，不将其挤入eligible支持。
- heldmissing在k发生，则event-free前缀至多k−1；exit-costunknown虽然last_path=k，但该k是事件可能已发生、金额未知日，不能当alive。未来closed只用于审计此前连续无未知前缀，不导入后来的收益/退出原因/退出类型作特征。
- 57,153,959次标量条件核对，并非独立样本数。1,026个精确年龄行、5,891个family/year覆盖行、六fold计数、全母子和逐母alive子数均与独立重建一致。完整派生action_id全局唯一，逐序号/母/epoch/普通与F家族身份一致。

## 严格cutoff的全动作分类

| 状态 | 2020 cutoff | 2023 cutoff |
|---|---:|---:|
| future_u | 966,740 | 600,106 |
| u_ineligible | 329,860 | 491,710 |
| intent | 169 | 313 |
| cancel | 6,950 | 11,035 |
| entry_unknown | 90 | 653 |
| closed | 247,795 | 445,475 |
| alive | 541 | 982 |
| held_missing | 311 | 2,182 |
| event_mark_unknown | 0 | 0 |
| other_unresolved | 0 | 0 |

eligible已进入且连续观察至cutoff的额外alive动作541/982，分别覆盖53/58家族；family-u支持数248/279。未来最终closed仅作为此前连续观察证明的动作529/967，其未来exit原因和金额未被读取。原meta final label不是cutoff分类本身。

本批无label_known_date恰等于cutoff行，且无exit-costunknown实测行；两类关键边界已核代码语义，但不声称在本批正样本中出现。未知k从未计为observed alive，事件日没有重复算event-free；未知中断和行政截止分别披露。

## 六fold成熟数交叉核

| cutoff | scope | metadata严格成熟eligible closed | 原130 training_rows |
|---|---|---:|---:|
| 2020-01-01 | main | 247,795 | 247,795 |
| 2020-01-01 | holdout_0 | 171,712 | 171,712 |
| 2020-01-01 | holdout_1 | 76,083 | 76,083 |
| 2023-01-01 | main | 445,475 | 445,475 |
| 2023-01-01 | holdout_0 | 297,404 | 297,404 |
| 2023-01-01 | holdout_1 | 148,071 | 148,071 |

六fold全部相等。这只是继承原129 closed/finite-Y不变量后的metadata计数交叉核，没有读取numeric Y或重验finite-Y。holdout_j的历史训练家族使用hash≠j，前向家族使用hash=j；普通/F共用family，未用forward关系替换train关系。家族-u多月份/多状态重叠，状态支持不能相加成独立观察。

## 审查器恢复记录

首轮467审查器将年龄计数器误声明为`defaultdict(Counter)`，首个event的`+=1`触发AttributeError。错误在审查器，不在466测量/策略/数据；失败receipt与精确失败源码保留。首轮完成一次派生mother全读，动作仅早期partial，精确partial行数/压缩bytes当时未持久化，以null披露而不猜测。

root明确授权一次紧限恢复；只修Counter声明。为恢复丢失的内存母映射，派生mother累计完整读2次；派生action累计1个partial加1个完整流。恢复后独审exit0并终态完成。未重读原actions、原mothers、原calendar、Y/COMMON/scores/q/价格/native/数据库；466测量、fit、cash、SQL、API、下载均0重跑/新增。这不是回测重跑，也未增加第三轮review。

## 支持边界、反思与TODO

接受的是`PREFIX_STATE_CLOCK_SUPPORT_ACCEPTED_ONLY_MODEL_CASH_NOT_AUTHORIZED`。原源payload未由审查者重读，依赖已接受129及466精确派生流血缘；observed maximum age不证明未观察终端尾部支持。前缀可构造不识别payoff、reward censoring假设、alpha、IPCW/hazard模型、辅助loss、新标签/效用、模型或现金许可。期末权益/收益/DD/Sharpe/滑点/交易次数/胜率均非本阶段对象，无新金融成绩。

开始与结束过拟合判断：机械metadata复核本身否；若据支持表选新horizon/家族/年龄阈值或推导收益则有事后选择风险，因此未这样做。开始时继续价值是，值得一次核清可观察边界；结束时此测量复核已完成，继续修饰计数或重复扫描价值否，模型/收益识别不属于本任务。后续由root按465范围判定结构信息用途，不据本receipt直接训练。

输出：`outputs/stage467_prefix_support_independent_review/review_receipt.json`；失败证据`failed_attempt1_receipt.json`、`failed_attempt1_review.py`及`recovery_provenance.json`同目录保留。一个合并最终receipt包含sourcebindings、覆盖和限制。
