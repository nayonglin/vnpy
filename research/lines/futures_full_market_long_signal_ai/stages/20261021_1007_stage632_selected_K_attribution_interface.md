# Stage632：原准入动作同K损益归因接口

- 2026-10-21 10:07 CST；先读registry，仅 `futures_full_market_long_signal_ai`；独占本stage与632输出，不改627冻结源码、LINE或registry。
- 非重要突破，只读接口可行性；恰读233、129、627 actual三份小manifest及必要源码schema，无真实score/Y/成本/native载荷读取或统计。0实现、fit、cash、标签、SQL、网络；所有财务指标N/A，累计551/290+旧partial1不变。
- 判断：**同K毛走势/佣金/滑点可用既存字段做精确代数分解，不需要重造路径；但要覆盖全部原selected已知交易，仍需授权一次129 actions投影读取。跳空只在原copy-before-K gap_stop子域有精确边界，不是全路径可识别。**

## 字段与原件

精确绝对路径、列、hash和读取建议见 `outputs/stage632_selected_K_attribution_interface/input_handoff.json`。本轮大表仅stat、hash继承已验收manifest，未重新读取内容。

| 角色 | bytes | SHA256 | 可识别范围 |
| --- | ---: | --- | --- |
| 627 `E_linked.csv.gz` | 26661451 | `d120d07db693d00b660aad84608627c57f4c916dab207fe861ecdf3b65f9dc22` | 已冻结完整E、m、score、known及K净R；无成本两端 |
| 627 `selected_K_literals.csv.gz` | 15461967 | `cbfc8190c1bf84f2dcd7beda9123a81cf13a7dd06204cffd9e07b9d14fcd4574` | 同K支路、known/取消/未知/END时钟；无entry费用/滑点 |
| 233 `K_quote_evidence.csv.gz` | 4821117 | `640706867bf958cc71153bde757ed501f2c22815c60039c3c44319e82308cc3d` | 只覆盖quote_K支路；原入场参考/填价/费滑、K原开盘/卖填价/费滑、risk及同K时钟齐全 |
| 129 `actions.csv.gz` | 334909637 | `b5b76bd670e9bd6240ea198da4f854cee61ba5f72fd6762f071345a4c0824e7c` | copy_before_K所需原两端ref/fill/fee/slip/gross及stop边界/原因/原已知时钟齐全 |

233 `measure_action` 对copy_before_K明确把原129净损益、exit及known clock复制为K结果，然后返回 `out,None`，所以4.8MB evidence**不含此支路**，不能用它代替全部原selected。quote_K的 raw exit是同K `native_open`，并重用原entry成本；它不能用129将来最终退出的费用或边界。129继承070 schema，真实保留entry/exit_reference、gross_R_reference、两侧stress fill/fee/slip及total、R0/cash_risk_unit、exit_boundary与exit_reason。schema及源码事实已核，没有打开表头或行情。

## 最小可执行设计边界

若root冻结完整成本归因：627 E_linked、K literals、4.8MB evidence、129 actions各一次hash＋必要列流式parse，按原action/mother/anchor/u/epoch逐值连接，仅给固定m=1动作缓存成本投影供独审。不读原124MB score、205MB K标签、COMMON或native；不重选、不新标签。显式primary已知取消=0且无成交成本，未知/未成熟仍未知；所有known依原K时钟截至2026-10-16，不等待今日数据。

同一支路、同一risk=`.25*N*M`下：

- 毛价格R=`M*(raw_exit_ref−entry_reference)/risk`。
- 佣金R=`(entryfee+同K exitfee)/risk`。
- 滑点R=`M*((entryfill−entryref)+(exitref−exitfill))/risk`，应与保存的双边adverse slippage一致。
- 同K净R=毛R−佣金R−滑点R。填价net已经包含滑点，不能再减第二遍；base−stress之差也不能代替成本绝对额。

629 held0后段负数是**每u的 `sum(mY)/nI` 再完整source日历等u**。因此保留全部E的known分母nI，只给m=1分解，各组件同权相加才能复原原A_I。只筛已选交易再平均会换指标。全scope、两时代、年度/所有家族及unknown分母保留，不能仅截held0负段求最有利解释。

精确跳空范围：129原 `price_exit_reference` 先force、再O<=B的gap_stop、再low<=B。**仅copy_before_K且reason=gap_stop**时，exit_reference=O、exit_boundary=此前冻结B，模型化超越量 `(B−O)/R0` 可由既存字段识别，毛R可代数拆为 `(B−F)/R0−(B−O)/R0`。quote_K只保存K.open，没有当时冻结B；不能借可能晚于K的原最终exit_boundary补齐。强制开盘退出也不等于gap_stop。任何净亏超过1R的桶只能叫亏损深度，因为费用/滑点在0.25N分母下亦可推过1R。

原52训练目标是**无K原NARROW stress净R**，不是K净R或157现金。固定已知selected的 `K_Y−score` 只能叫当前政策绝对偏差，含K目标变化；原目标校准要另核原label_known<=END，同copy支路原Y=K，quote_K原最终Y可能未知/更晚，不能把全部差都归为原模型校准错误。

10:10 root倾向批准上述一次129＋quote-evidence字段读，成本只测Y前已固定m=1 union、不测fallback成本。预测桥也保留同一I/nI：H是两目标同时known/mature的子集，`A_I = sum_I(m*score)/nI + sum_H(m*(oldY−score))/nI + sum_H(m*(KY−oldY))/nI + sum_(I\H)(m*(KY−score))/nI`，各项再同完整日历等u。I\H剩余误差单列未归因，不补oldY、不重分母或只在H均值化。gap另按原entry_index==exit_index与后续持仓日分别披露；quoteK缺B仍未知，不能填0。小handoff已按此补齐字段/公式/branch/unit，等待root正式冻结，不实施。

若root不希望一次334MB成本字段读，更小备选是只复用627两个cache，将known净R精确拆为正收益、0至−1R的损失与低于−1R的额外损失，另列真实cancel0/unknown。该方案仍有价值且保留原权重，但**不能声称完成gross/fee/slip归因，更不能声称超过1R就是跳空**；不为归因补native或重造路径。

## 调研与反思

本轮复用625/629当天已冻结原作者/维护源码的方法边界，并以233/129/070/042现成小源核具体经济定义，没有为schema重复网络搜索。不是新alpha试验。开始/结束无新结果选参：否；长期同史适应性过拟合风险：高。继续有界归因有价值：可区分已获选择优势为何不等于绝对盈利，但不能自动修正阈值、增加仓位或承诺未来稳定性。下一步由root冻结一次测量范围/预算；本阶段不实施actual。

## 10:21 实施与 source-ready（尚未 actual）

root已冻结630科学协议：`outputs/stage630_fixed_K_accounting_protocol/protocol.json` 14322B，SHA256 `ded4457758a82ab79ea7297b031a95973a3ab691e735738ee2a9f16b3b1945e4`。另补身份专用 `family_coverage_addendum.json` 4439B，SHA256 `98ffe81c1364170fab1a53a0b35fa363e4331b95891336307ff3a7b2ce79f304`，来自root对627小family表一次身份列读取，main95/held0 38/held1 57互斥并集；本工具只读该4KB元数据补零，不从E猜95、不重读母表/原family表。身份补充不改变选品、科学口径或门。

按冻结协议新增且仅新增两份工具：

- `tools/stage632_selected_K_attribution.py`：26501B，SHA256 `1e2ec22f140bee759e63e830ad6867d4ffe3e5ba1bfc40726fd133bb9df470de`。
- `tools/test_stage632_selected_K_attribution.py`：5975B，SHA256 `534cfa4e49c8fe0244fbb90c8b81294d28fd1fc41a2c7a0d011c1eb17ca62fc5`。

只复用冻结627的纯CSV流式hash/写出/身份与K状态工具，并绑定627/156 helper源码，不更改它们、不调用选择、拟合、现金或CI函数。E所有行先规范保留，确定原m1 union后才读129/quote新增字段。实际时原E、K literal、334MB actions、4.8MB quote各一次结合hash/parse；成本只投影m1，所有m0 known仍保留nI分母。quote只用K价/费滑，不借原将来exit；copy按原同entry/exit/clock核对；K本身未知、J成本不完整、H旧目标未知分别保留。

同原I/nI和完整日历检验两桥：`A_I=G_J−Fee_J−Slip_J+已知但J外净R贡献`；`A_I=S_I+H旧目标误差+H的K变化+I\H剩余误差`。缺J/H不重分母。冻结残差阈值 `1e-8*max(1,abs(reference))` 检验risk、费滑、填价net、旧gross及净R，测量不符独立计数并阻止“全部精确归因”声明，不改阈值或经济参数。每u/window/era/年度与全部family零准入覆盖输出；gap分entryday/held-day，quote的边界未知保留，不把短缺再从净R减一遍。

8个必要新synthetic首次真实8 FAIL（新实现不存在的assertion），实现后8/8 GREEN；最终冻结源码对应unittest0.093秒、整个子进程0.137647秒、exit0。覆盖同参考/填价费滑不重复扣、copy/quote同路径区别、真实cancel与unknown、全nI/空日、不完整J净R剩余、H桥及I\H、旧目标晚于END、entryday/后续gap和quote缺B。未跑旧suite、真实预试或收益统计。`outputs/stage632_selected_K_attribution/fixture_receipt.json` 2567B，SHA256 `7c663c811a575b7b18e5ee53c5e288fb43b8364fb8c887495a86f936a8183383`保存真实命令、输出与源/测试hash。

最终literal cache字段在source_ready逐列冻结：完整 `E_slim_literals.csv.gz`27列、原m1 union `selected_K_literals.csv.gz`48列、`selected_actions_literals.csv.gz`40列、`selected_quote_literals.csv.gz`52列；不按结果完整与否删行。另存原小calendar、原627 windows参考及family元数据，供633从literal独立核nI/J/H/会计桥，无需再读原大源/native。派生daily/windows/eras/annual/type/family表没有新CI、bootstrap或金融门。

`outputs/stage632_selected_K_attribution/source_ready.json`：7863B，SHA256 `5ebe071be325d1a9e17230e2bf71ba16f9fd540fcb4a37678d87a5dc33f46756`，绑定630、新源/测试/收据、旧helper、family addendum及准确实际入口：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage632_selected_K_attribution.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage630_fixed_K_accounting_protocol/protocol.json --source-ready research/lines/futures_full_market_long_signal_ai/outputs/stage632_selected_K_attribution/source_ready.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage632_selected_K_attribution/actual_run1
```

本agent没有执行该命令、没有读取真实收益/成本载荷。已送root与633一次完整源审；source-ready不等于actual授权，待633 GO后root唯一启动。研究END仍2026-10-16，无当日收盘依赖。源已冻结，不为记录包装改程序。新增经济参数、策略动作、资金结果仍0，所有财务指标N/A、累计551fit/290cash+旧partial1不变；本次价值是解释原不变动作，不能当作策略改进或稳定优势证明。
