# Stage035/036：独立 B 真实 native 接合有限复审

- line_id：`futures_trend_triple_screen`；2026-10-18 03:45 CST；独立审查者：`ordered_execution_review_independent`；来源 HEAD `ed41e3578aa4fd64606b481a74003f9855d1fad5`。
- 权威合同：03:33 Stage035 execution contract / implementation plan；入口合同为03:38 Stage036。未改实现、LINE、registry、旧C或金融目录，只新增本 stage 和自己的审查目录。
- 结论：限定本次代码/fixture 范围内 P0/P1/P2=`0/0/0`。建议 root 冻结精确源码后按事前合同启动唯一 **B_TS attempt1**，A0复用；不代表经济验收、promotion 或总目标完成。

## 最终来源绑定

| 文件 | SHA256 |
| --- | --- |
| `tools/stage035_b_ts_pricing.py` | `d45e8a5b4b7503a33c137df7decbd56947c2d1df77b7c73c5e7524326ae1018f` |
| `tools/stage035_b_ts_strategy.py` | `fc357eb4a44a384d816acaff5fadaa99d91dfc7f8ec8fbd22954c9ca3837b09e` |
| `tools/stage036_run_b_ts_checkpoint.py` | `34563257e25e49b19c9631e06cd9107fc26cfd954713739e01a1bf67d574ff43` |
| `tools/stage037_b_ts_request_provider.py` | `19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1` |

035 pricing 已严格拒绝 unsupported native base，生产 factory 没有测试专用 fallback；035 strategy 的 tiny unit 隔离只存在测试 patch。036 精确 pin 两个新035模块及原028 shared helpers；原031、028及正式源保持原身份。037 对冻结032独立 diff 恰四增四删行：docstring 和 output/request/protocol 三常量，没有 provider 实际请求。

独立 AST 核对真实 qmt `_calculate_entry_sizing` 与035复制方法：除三处 `float(bar.close_price)` 换为 `entry_estimate` 及局部 pandas import，整个方法 body AST 一致。真实 MRO 保留847→830→827→804→772→PricingQmt→qmt；真实804 long S与原 short S不被T替换污染。

B在原planner前对同一flat context恰一次观察，unknown无native回退，generic filters显式复用，OI mode重新计算，新short精确权限开放；原持仓/退出路径不改。最终预算只处理原admitted B集合，风险/资本整数限额一致性检查先于任何修改，按原量gross前缀，不重排、补位或提前真实reserve。decision/frozen plan/snapshot/fill保留B身份、T预测与final budget字段；原gate快照不伪称最终再验。

036实际TradeData/synthetic母OPEN身份与可靠checkpoint采用已审031语义。B自有路径/writer/schema/arm=B_TS/attempt1均已核；C混入必须在反序列化前拒绝。raw仍在完整engine返回后、后处理guard前落盘，guard后seal；export-only早分支不走数据栈/引擎，失败后新目录恢复。两项历史anchor仍各精确一key，只可用于anchor，不扩大full-session资格。036使用真实0333合同/plan、0338入口合同和精确源码snapshot；A0、周/FI、AI、参数和完整日期/零吞错门保留。

## 唯一新增真实组合 fixture

命令：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage035_independent_review/native_b_composition_fixture.py`，最终 **exit 0**。没有只重复5+4个units；本次独立执行真实847策略constructor、实际AM合成暖机、**完整原on_bars产品循环**、真实generic filters/OI、原planner、035 T估量/最终预算、真实candidate snapshot与reserve，随后进入未改028 engine和真实827母单/合成成交。

仅native alpha generator是显式fixture：合法两方向返回无native信号，unknown反例故意返回旧native long信号。外部模型/AI/供需输入在fixture关闭；OI及通用MA/wick过滤是真实方法。没有加载行情、模型或调用run_backtesting。fixture选择确定性的测试资金/风险参数，并不据此声称真实完整profile已验收。

三项组合场景结果：

| 场景 | 真实链条证据 |
| --- | --- |
| long，无native | B标签`long_triple_screen`；同日准备/intent；T111、真实804 S99、rho120、contracts_by_risk10、最终q10；原loop reserve恰一次，T保证金111×10；一个真实初始订单，fill序列`111,105,111,105`。 |
| short，无native | B标签`short_triple_screen`；T89、原short S101、rho120、最终q10；精确short权限、reserve一次、一个初始订单，fill序列`89,95,89,95`。 |
| FI unknown+旧native trap | 当天观察一次、fallback=false；旧native信号不能发单；pending/reserve/order/fill/layer均0。 |

总计3次真实on_bars、2个真实初始订单、8个native fixture fills。每方向母entry与首次stop同11:00分钟，retry及retry stop在下一分钟。真实临时首bar视图没有修改原分钟，trade成本按独立逐fill公式核对；层/target/实际仓位最终一致。冻结T预测1200在真实成交同步以后仍保留于plan和B fill audit，没有被实际字段覆盖。

**真实synthetic经过真实036 clock处理**：原producer synthetic usage仍缺signal字段，使用实际TradeData显式身份及真实母OPEN episode关联，通过四笔一对一映射；全部signal datetime仍u，synthetic不冒充母订单。这一组合专门覆盖旧028审查曾漏掉的producer/consumer边界。旧028前置0P1确实漏审schema与raw持久化两个P1，旧receipt原样保留，不能作为本次新代码的证明。

fixture初次两次失败因reviewer漏设`short_entry_enabled=True`，原native gate正确输出`short_entry_disabled`；仅把fixture按真实short权限显式启用并设置max_position_size500，未改实现或策略规则。最后同一组合通过，不将该fixture设置遗漏伪称产品bug或产品RED/GREEN。

035 pricing5项、strategy4项、036 owner/recovery2项由实现收据及root实际终态提供，均exit0；036最终GREEN handle84914，2项0.076s。本review读取收据与测试而不重复运行这些组件suite；尤其没有重复旧26项、FI全流、旧行情资格或DB全hash。另对四个最终新模块执行stdlib compile，exit0。

## 置信度、反思与下一步

在最终SHA、已审delta和真实组合覆盖范围内置信度高；没有金融置信度。该组合是每方向单候选，tilt12→10/gross不回收/q0等多候选算术沿聚焦实现测试与静态核查；没有把未运行部分冒称独立全测。完整历史模型新标签域、全部真实参数组合、全分钟价格资格尚未由此验证；qualification callback只是记录no-op配完整合成分钟，真实签名数据门仍保留在runner。

T预算不是D实际gap硬上限；旧模型19数值特征含same_signal的新域外推、原佣金参数0/固定原滑点、历史选择偏差必须披露。任何双目标结论仍须真正金融terminal/完整sealed raw与账本、独立038经济审查及原七门；promising才可进入固定后续验证。

调研与判断：沿冻结CMT/LEAN/Backtrader与本地真实源码，本次按分工未新增联网。机械独立B信号、已知T估量与真实账务已可组合验证，不能凭其宣称alpha有效。开始/结束过拟合判断均**否**：无B收益、参数搜索或按收益改规则。开始/结束继续价值均**是**：独立B尚缺一次完整经济证据，事前固定唯一attempt仍可反证。

重要突破：否。正式参数新增/改/删0；金融结果新增/改/删0。权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。金融回放0、preflight0、模型推断/训练0、联网0、真实API0，production_qualified=false。

机器收据与fixture实际结果：`outputs/stage035_independent_review/review_receipt.json`、`native_b_composition_result.json`。只建议root按已冻结合同执行下一必要步骤，不以本次代码完成替代总目标完成。
