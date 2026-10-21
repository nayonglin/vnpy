# Stage635：K日预计划平旧换新——源码可行性预筛

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 10:24（Asia/Shanghai）。
- 模式：只读方法及小源码；非重要突破，尚未形成现金候选或触发正式版A/B。独立全98/95研究，不修改正式C9。
- 隔离：未读取Stage632/634的新归因、任何新Y/大score/native/现金旧账；未实现模型或策略。0 fit、0 cash、0 SQL、0下载数据。只写本stage及小decision，不改已冻631/630、LINE、registry或Git。
- 开始判断：有条件值得核查一种执行机制；经典“滚仓”故事不能证明收益。固定一个问题、不根据新收益选规则，当前不构成新的参数过拟合，但它仍是长研究链中的事后候选。

## 外部调研与判断

1. [CME：Understanding Futures Expiration & Contract Roll](https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll)：真实roll包含结束旧合约及建立另一月份合约，不能靠更换价格序列完成。CME的到期/结算说明不等于中国市场的K或统一换月日期。
2. [QuantConnect官方期货文档](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures)：连续合约及其调整价格用于数据呈现，实际订单指向具体mapped合约。feed的symbol change时点不是本线u时钟或K规则。
3. [QuantConnect维护者GitHub示例](https://github.com/QuantConnect/Documentation/blob/master/03%20Writing%20Algorithms/03%20Securities/99%20Asset%20Classes/06%20Futures/02%20Handling%20Data/99%20Examples.html)，实际读到`on_symbol_changed_events`：旧合约`liquidate`，新合约另发`limit_order`，并按最小变动价位处理报价。这证明需要两笔真实交易的工程结构；示例复制旧数量，不证明跨月份同风险，也没有给本线成本后优势或原子成交保证。

判断：真实替换在机制上可描述；旧价与新价、基差、合约N、保证金、成交失败均不能被连续feed拼接消除。保留原不利报价、手续费与滑点；旧平仓在A本来发生，差分不能重复扣它，但完整两腿记录也不能把它或新开仓费用抹掉。没有引用美国换月参数、主力切换、spread保证金优惠或调整价回测来构造候选。

## 既有谱系及小源码事实

本次仅定向读LINE的K初次选月相关索引及596—601已关闭加仓前提、156/131/157小源。该范围未发现同一“已持仓、纯K日、提前计划平旧后换入原m=1新月”的实测。此结论是有界排重结果，不宣称全库从未试过。

| 已核对象 | 事实及边界 |
|---|---|
| `stage156_voluntary_choices.py` | `D<K`先筛月份可行动域；原正分规则、每product的score排序及family优先规则再产生winner。不是简单取整个family全局最高分。已有选月是初次准入，不自动绕过现金层已持仓限制。 |
| `stage157_voluntary_cash.py::apply_boundaries` | 已保存source生命周期、voluntary K及effective origin；有效expiry取两者较早。只有K严格早于source才标`voluntary_calendar`；同日是`same_source_and_voluntary`，不能当纯K例外。 |
| `stage131_contract_choice_kernel.py::prepare` | u先把所有已持仓family放入`occupied`，选候选时同家族已经被挡。原普通预算以旧仓F0及保证金仍占用为基础，没有预先释放K日退出额度。 |
| 同源D执行循环 | 旧仓强制平仓后把family记入`closed_today`；pending新开仓又因该集合或仍有持仓而取消。因此只改u选月仍不会产生K日替换。旧仓报价缺失/延迟退出不能视为已平。 |
| 同源position初始化 | 传入position的是effective expiry，原K/source origin未完整带入root；`anchor_request`的`lifecycle_exit`合并了多种生命周期原因。不能仅凭这个字符串放行替换。 |
| 596—599赢家加仓 | 留旧仓、盈利条件下新增独立root且原额度内共同分配；固定四现金门失败后关闭。它没有先结束旧root，和本问题不同；不可借本问题救回盈利阈值、加仓数量、间距或扩大风险。 |

小源码绑定（仅文件hash，不运行）：

- 156：17,062 bytes，SHA256 `4c56ad2f0e812a10aca9a153e3328c8a8aa6e8df1a1b588f3aecf898713f7200`。
- 131：15,527 bytes，SHA256 `85205ef9bc309a34283fc0082ac09c53d1f156ca788b8efe6bbd9743f5f430b5`。
- 157：28,964 bytes，SHA256 `367d8202040fd30eb05b0070895c9a03706645446bd102c6d5de04f22824ba9b`。

## 唯一后继机制的最小合同草案

这是待冻结的设计约束，尚非完整现金协议或实现授权。

1. **只处理纯K日退出。** u已知次日D等于旧root的voluntary K且严格早于source生命周期；旧仓无stale、deferred、其他force、risk reduction或资不抵债冲突。先保留/恢复entry signal至root的K来源链，禁止把所有`lifecycle_exit`改成可再入。
2. **只用原AI意图。** 在该u、该原cutoff，先取得原156正分准入及pureK后的原family winner，再与旧仓及K条件相交；winner须另一真实epoch且D<K_new。不得先筛替代月再选next-best，不补选新月份、不偷用未来名单、不改变ordinary/F优先。没有原m=1替代项就照原A退出。
3. **u只冻结旧槽的替换预算。** 普通fresh请求、原顺序和共同预算保持原占用口径；不提前释放旧风险去放大别的订单，替换请求也不能挤压普通单。新root风险和资金上限不超过旧槽及原family/组合/保证金约束；同数量并不满足这个条件。具体risk、buffered margin、fee与D减量公式必须在后继协议中冻结；本stage没有证明当前源直接满足它们。
4. **D必须真实平旧后才开新。** 先确认旧leg完全有效平仓；未知报价、未平/部分平、异常退出就不发新leg。新量最多为自己的u冻结量并只能依原D规则缩减/取消，不能动用D实现利润、别单取消额度或临时重新分配资本。还需明确D跳空后权益/费用的只减量约束；u风险不增加不保证真实最大亏损或D资本上限。
5. **新合约是普通新root。** 使用该新epoch原不利BUY报价、费用、滑点、容量及原`0.25N_new,u`初损公式、原low20/anchor/新K生命周期；old/new root仅做审计链接。不能把旧绝对SL0直接贴到另一价格/基差的合约，也不以调整连续价格平移stop。这会重启新root止损路径，必须公开承认这一行为，不能声称经济上原止损无变化。如果要求严格保持旧root连续止损，这个最小方案不满足，应停止而非同时增加stop转换参数。
6. **不修改其余事件次序。** 只给预先绑定的纯K替换一个狭窄例外；日内stop、anchor失败及其他退出不得因此同日重入。不复用赢家加仓kernel或重构整套D事件排序。

可能改变的是：A在u因occupied未计划新月，D被K平仓后需等待后续u再入；本机制只在u已存在原m=1替代意图时尝试少空一段。它不延长旧epoch持有期，不取消K，不保证连续趋势或即时成交。

## 无法由当前证据证明的事项

- 有多少旧K退出在前u具有另一原m=1、经济已知且至少一手的替代项；当前没有读数据作支持率断言。
- 新月的未来路径是否改善净收益/回撤；换月可能增加成本，换入趋势较差的合约，或因新root止损重启扩大损失。
- `Y_raw−Y_K`若为损失，也不是roll的可恢复金额。raw继续持有旧epoch，roll持有新epoch，基差、N、退出、费用与现金竞争均不同。
- 日线条件报价不证明真实两腿原子成交、排队、可交割身份或足够流动性；不能把CME spread处理当成本线现有能力。
- 不能从已关闭的赢家加仓或初次K选月，直接移植收益、置信度或合格结论。

## 决策与反思

- **结论：CONDITIONAL_GO_DESIGN_ONLY。** 源码存在两个明确阻断及K来源缺失，机制有结构差异；允许root在独立归因确认值得后，再冻结唯一后继合同。当前不授权实现、probe、四现金或正式接入。
- 前置否决：若独立旧raw相对K并未显示有意义的截断代价，或原m=1替代/原槽至少一手支持不足，就不因“滚仓常见”继续。判断该前提归root，本stage未看632/634，也不预设其方向。
- 参数：新增/修改/删除均N/A；没有阈值、间距、等待窗、月份名单或风险网格。源码新增/修改/删除：均无。
- 财务结果：期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。本轮没有新回测或现金结果，不引用未读新归因。
- 结束过拟合判断：本轮未调参、未接触新收益，设计预筛本身不新增收益选择；但反复提出后继机制存在研究者自由度，应只保留一个合同，不根据后来收益救风险/stop/选月。
- 继续价值判断：有条件，仅限一次后继设计决策；没有证据支持现在直接跑现金。若需要同时修改月份排名、旧stop映射和资金授信才可运行，则NO_GO，不扩大成滚仓工程。
- 合入：本agent不更新LINE、registry、根总账；无正式C9改动。

输出：`outputs/stage635_K_replacement_roll_feasibility/decision.json`。
