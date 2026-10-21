# Stage639 原研究账本换月替换的结构支持协议

- line_id：`futures_full_market_long_signal_ai`；day；2026-10-21 10:54 CST。
- 工作区：当前 checkout / `codex/ai-training-data-expansion`，不新增分支或工作树。
- 性质：有界可行性探针，非盈利策略版本、非重要突破、非正式 A/B 或生产变更。
- 上一 goal turn：只解释为什么不必等今天日线，属于 no progress；本轮恢复历史证据工作。
- 目的：检验原157四本研究账户是否真的在纯日历K退出前持仓，并存在同u原m1的另一真实合约意图。不得把潜在标签当持仓、把原合约K前后收益差当可回收换月收益。

## 调研与判断

CME 原文说明换月包含平旧、开新两腿；QuantConnect 维护者示例也对旧、新真实symbol分别发单。只借交易结构，不把美国交割、保证金、映射规则套入国内，也不据此宣称两腿原子成交或盈利。

- https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll
- https://github.com/QuantConnect/Documentation/blob/master/03%20Writing%20Algorithms/03%20Securities/99%20Asset%20Classes/06%20Futures/02%20Handling%20Data/99%20Examples.html

我的判断：先查实际研究持仓与原意图有没有相交，能避免直接构建没有承载机会的换月引擎。131 的 expiry 优先级会掩盖同u原canonical变化，须独立核旧product/u的canonical与旧entry anchor；旧实际epoch不必等于anchor。

## 实施计划与接口

- [x] 读取636字段设计和638独立方法审查，保留635原设计。
- [x] 冻结同目录输出的 `protocol.json`：0fit、0现金、0新标签、0行情、0收益比较、0新金融门。
- [ ] 637实现 `tools/stage637_K_replacement_support.py` 及必要合成边界测试，提交小source_ready；不由实现者启动实际。
- [ ] 638检查协议与源码/新测试证据，一次源码GO；不是现金GO。
- [ ] root唯一启动实际探针，生成原研究账投影、u计划/D观察分列、全原因漏斗、四账户年/族/月零格和读取收据。
- [ ] 638唯一完整检查新literal投影与结果，不重放策略、不再读原大表。
- [ ] root640结案，更新本线LINE/registry，报告本版本结论与下一步；普通诊断不追加根总账。

## 固定合同

1. 只继承原157完整4365个main正分m1意图及其原piecewise cutoff，先固定同family/u赢家再与旧仓相交，不重排、不用fallback或next-best。
2. 四本旧A研究账的u收盘真实剩余持仓是基底；按account/root/action event/product/family/epoch连entry signal，不拿mother_event_id替代action身份。
3. 纯K须已知 `effective_origin=voluntary_calendar`，且 `K_old=D=u+1 < source_lifecycle`。同日source/K不是纯K。u stale、原其他force、减仓请求、超限或永久破产暂停均保留冲突/未知。
4. 旧product在u的原canonical须等于旧entry anchor；缺失/重复为unknown，已变为blocked。该项独立于expiry显示的force标签。
5. 新意图必须原同u赢家、同family、不同真实epoch；原potential/ready/N/cap/cutoff与D严格早于其有效生命周期检查不变。不得用D行情、D利润或释放额度补选。
6. u结构状态与D旧SELL观察分列。D旧root完整lifecycle平仓、原capacity状态及冲突证据仅属事后观察，不能倒灌u计划；部分/缺记录不视为全平。
7. 新root预算、最少一手、D新腿报价和两腿成交资格全部unknown；原A上的结构支持不是C路径收益或订单。原风险0.25%E、组合2%E、保证金25%E、buffer1.10和初损0.25N均不修改、不重新分配。

## 输入/输出与停止条件

输入白名单和精确binding见protocol：157 signals、627原calendar/母identity瘦字段、四账positions/fills/reservations/daily、既有95family身份清单。不读334MB原actions、原母表、E、全score、Y、模型或native。

按固定条件节省IO：先读signal/四账；无纯K另一epoch原意图时不打开19.56MB母identity。存在待核意图时，母identity仅一次hash+parse，持久化所需canonical给独审。不能把未核canonical说成已通过；有实质未知不判零支持。

完整覆盖、无实质未知且原纯K仓无同u另一epoch意图，则停止精确同日替换机制。若非零，只可讨论下一份独立预算合同，不自动启动现金。四账有共同窗口/信号，不当四份独立样本；年度2026为不完整年度。所有金融指标N/A。

## 反思

- 运行前过拟合：本轮不按盈亏选条件、不新增阈值，否；长期同史反复择题风险高，失败后不得换K、放宽冲突或next-best救它。
- 运行前继续价值：是，只值得这一次最小支持探针；全市场跨品种AI优质信号、更高收益低回撤、窄损加注仍未证明，goal保持active。
- 新增参数：仅结构审计状态与IO条件，无交易参数；修改/删除策略参数、已有回测结果：无。期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率：N/A。
