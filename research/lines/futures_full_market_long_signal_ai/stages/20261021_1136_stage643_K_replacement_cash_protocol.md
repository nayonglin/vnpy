# Stage643 原u旧槽换月续接：单一四C现金协议

- line_id：futures_full_market_long_signal_ai；day；2026-10-21 11:36 CST；codex/ai-training-data-expansion；非重要突破，独立研究A/C，正式C9不改。
- 上一goal turn为progress（640/638支持接受），本轮不等今日，不重复637支持统计。
- 假设：原u旧仓额度内将纯K强平后接到原同u m1不同合约，可能改善成本后收益/DD；需真实C现金检验，不从旧raw-K推利润。
- 调研：[QuantConnect原BuyingPowerModel源码](https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/BuyingPowerModel.cs)将费用纳入订单资金要求；CME原文区分平旧开新。判断：新腿需独立预算、费用与成交，保留国内原经济参数。
- A：157原四OWN直接读已接受summary/daily，不重放；C：644独立适配131普通政策，加原槽续接，每个u用C自身state不拿28组作白名单。
- 原100w、单族0.25%E/组合2%E/保证金25%E/buffer1.10、窄损0.25N、两窗2020/2023×base/stress保持；原4365main m1保持，无新fit/Y。
- 精确合同/输入/固定门：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage643_K_replacement_cash_protocol/protocol.json)。u oldslot只归指定parent，不提前给普通单。D旧净不利变化只减额、旧费不重复扣；旧完整nativeopen平仓且原容量known后才开新；共享scale及整手余量不循环。
- root裁决：D资金单位同时保留原buffered-margin+RTfee与原adverseBUY实际margin+BUYfee，用二者max，不新增小数阈值。D virtualE/R/M仅u快照及确认K腿损失，不读已经mark D.close的ledger.totals，不宣称真实D任何时点硬cap。
- 新root自有rawDopen/N_u/low20/anchor/sourceK，原ordinary保留排序和预算。未知取消该新腿、保留旧退出/unknown，不选次优。
- 预算：至多4本新C现金，0fit/标签/SQL/下载/原A重跑；全部新结果纳入，无一手则取消意图，不救额度。新实现金融结果前固定全部门与原bootstrap。
- 固定门：四C自身收益正、四C收益优于A、四C回撤不恶化、四配对日log固定CI下界正、模型执行known；全部满足也仅promising research，不给AI跨品种/窄损加注或正式资格；否则停止精确包。
- [x] 644新kernel/runner+8类必要synthetic TDD并冻source_ready；不运行旧suite。
- [x] 645一次sourceGO，root唯一actual；原native/cache/econ/signals/mother和A各只一次读/hashparse，无actions/E/Y。
- [x] 645一次全新literal复核现金/费用/预算/时钟/unknown/统计/置信度/bug，不策略重放；root646结案。
- 运行前是否新增按成绩过拟合：否，先固定一机制；长期同史反复择题风险高。继续价值：是，已有实际结构承载，直接检验金融效果，不再延长支持工程。
- 当前期末权益/收益/DD/Sharpe/滑点/笔数/胜率N/A（尚无新actual）；累计551fit/290cash+1旧partial；完整98/95全市场高质量做多AI目标active未达。

## 结果前口径裁决（2026-10-21 11:42 CST）

643的full ordinary u allocated按原reserve_capped返回全部ordinary rows的实数allocated计入D virtual Rother/Bother，包含qty_cap=0行；不得把整手舍余或无一手额度借给replacement。原131日表ordinary new_order_reserve仍只计pending qty>0保持不变，二者在audit分列。此为原full/no-rounding-recycling的解释，JSON/阈值/选择不变；尚无新金融载荷读取。

## 唯一结果前经济口径修正v2（2026-10-21 11:45 CST）

- 0actual、未读新金融数值。root和645发现v1的qu整数再Ra=qu*r/Ba=qu*(m+f)会人为二次取整：旧risk110、新u单位100、qu1，D100.01即被砍为0，尽管仍在独占旧110内。
- 采用一次v2：target=min(cap,Rslot/r,(Bold-oldfee)/(m+f))；qu=floorlot(target)；Ra=target*r、Ba=target*(m+f)。保留同parent事前实数资源，D仍<=qu；不跨单/取消/舍余回流、不增加旧槽、不用D盈利。它恢复原070 prefloor预算含义，但不宣称与070容量后截逐字相同。
- v1原文件完整保留；新唯一实际以[protocol_v2.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage643_K_replacement_cash_protocol/protocol_v2.json)为准，SHAb017e3480dafd4eff14f318c78551a658383c07cc22283f6839919597e56ea32。除该u额度解释与既有全ordinary实数口径外，选品/止损/成本/窗口/固定门均不变；后面不改参数救结果。
- 现有必要用例覆盖风险110/100→100.01及资金约束对应例，非新增数据探针/资金重跑。

## 结案（2026-10-21 12:10 CST）

644唯一4C/645独核均exit0，固定门close_exact_policy、不救参；见[646结案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_1210_stage646_K_replacement_cash_root_decision.md)。4新现金/0fit，不等今天日线。
