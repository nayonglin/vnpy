# Stage355：输入完成域与执行截止域

2026-10-20 04:08 CST；`futures_full_market_long_signal_ai`。只读判断，344 compact结果仅读一次；0模型/行情/API/SQL/旧cache/金融重放/实现，未改354、LINE或registry。[计数](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage355_clock_domain_judgment/counts.json)。

**第一性原理支持分域；当前354严格全726结论仍原样保留。** 来源完成回答“计算用了哪些u信息”，执行截止回答“下一D哪些原动作或既有义务可能执行”，两者不必同集合。分域不能用最终两赢家、正分或排序结果决定。

一次读取确认：u19评分726，原u_action_eligible=427、其余299。指定13个到期合约全匹配，13个原资格均0：8条首要原因是known_entry_ineligible_lifecycle，5条先因历史不足/gap不合格；13条已存source lifecycle均为10月1日/index5282，早于D20/index5290。DCE.PP610甚至正分仍原不合格，不能拿分数替代资格。本次没有重新判定u20资格，**427只是u19事实**；账户states=None、T0=None，无真实position/pending。

建议未来规范：

- **输入完成域**保持完整因果输入。即使某月不能入场，它的u价格/量/OI仍可能参与母anchor、同品种peer及相对月份特征；不能先删13行再评分。对实际完整输入域取最大session_end；输入自身完成未知，不能靠排除执行资格绕过。
- **D执行域**可在score/argmax之前，按原u_action_eligible全集，加上已有position/pending及其实际执行依赖定义；原资格unknown也不能当0排除。这是比赢家域更保守的执行可达域。已证明不能入场且无既有执行义务的合约，其D日程未知不应仅因“被评分过”就拦其他动作；不替13合约编时段。

这一区分不改52特征、scaler、score、156的原资格/正分/K/family选约或070/131预算公式。但它改变**运行准入解释**，可能改变哪些日子可产生及时决定，不能以“公式没改”声称执行路径必然完全等价。若采用，须在T0前写明两域、已有状态依赖和unknown处理、逐日记录版本；新的u必须重新计算自己的原资格，不能照搬u19的427。

318允许按品种D首开理解，321/325接一个外部D_open时钟；但root在353/354前明确本次按**选约前全726**同时汇总maxclose/minDopen，354也写了该domain。因此当前全726 globalflag=False不是本阶段可静默纠正的错误。本次不将它改True，不回写已完成354，不把u19的交集0冒称u20已获执行资格或前瞻许可。未来分域另行显式冻结即可，无需改变原金融政策来“通过”现有证据。

开始/结束：无收益调参；有价值的是澄清真实因果依赖，保留当前严格结果。未新增金融成绩或生产资格，累计fit/cash不变，完整用户目标仍未达。
