# Stage063：EIA全市场事件信息与12研究现金账本独立结案复核

- line_id：`futures_full_market_long_signal_ai`；初次协议预审2026-10-18 15:13，完整结案记录2026-10-18 16:01 CST；当前checkout，不新分支/工作树。
- 仅写本stage与`outputs/stage063_eia_event_independent_review/`；不改060/065/061/062、LINE、registry、他线、根总账或正式策略，不commit/push/生产。
- **最终作者结果Critical/Important/Minor=0/0/0，接受研究算术；新鲜EIA库存信息未取得可继续资格。** 主配对资格因差异历史stale为未知/未知，名义门本身也未通过；不能声称alpha、全市场高质量long、极窄止损、加注或完整goal完成。
- 独审启动2次、完整1次：首次为独审行号dtype适配失败，保留现场；root授权最小修复与新RED/GREEN后，仅续审一次成功。研究实际仍为首次6fit与首次12现金，没有重训/重放。

## 调研、冻结合同与事前判断

先读registry/LINE、057最终提案、059全市场协议/计划。协议SHA `ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158`，057 `8ec1ef71ffc4bfee59dace77ebb10b6ed746cbd093a87cdf2cc8cdb5270cfbb2`，计划 `e717d8ac9dfc53ff356e6866cb7393e180d629efd6b5e3bd998255e2b8f00677`；源码预审收据精确绑定全部生产者/测试。全95family同报告事件训练与交易资格，4油品仅诊断；全局共同系数重估属于完整信息模型包效果，不声称纯油品因果。

调研沿057的[EIA官方archive](https://www.eia.gov/petroleum/supply/weekly/archive/)、一手库存公告论文及维护方GitHub，061另核官方Ridge文档/源码。判断：实物数量是不同于旧q的观测，但公告分钟效应不能外推到中国下次收盘后仍盈利；固定Ridge系数可以独立正规方程审计。独审不新增下载或扩信号。最大反证在收益前写定，失败不换分量/52周窗/模型/alpha/seed/时钟/止损救参。

新增独审源、精度诊断/测试、两次审查现场、最终收据/记录；正式策略参数与作者成绩修改删除0。固定10槽Ridge1/intercept/cholesky、2020/2023 cutoff、严格成熟/训练内family并发与报告cohort同权、全399252母体、stress netR目标；100w、单family0.25%/总2%/margin25%/buffer1.10、2N/20low、两成本均不改。累计研究矩阵321fit/42现金；不把源导入/离线恢复或独审当新训练/账户。

## 输入精度问题与独立修正决策

060旧实装要求打印值严格相减等于Difference。root在首个新fit/cash前停止仅下游调度，原060下载继续且保持原样。独审只读5份缓存/15库存行，8行非零残差全部位于各打印Decimal量化界：2016-10-19原油`468.7−474.0−(−5.2)=−0.1`百万桶，界±0.15；2020-02-26馏分油残差−0.001百万桶，界±0.0015。

root提供[官方Table1 PDF](https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf)第0页line92的直接说明：差分基于未舍入数，独立舍入可使打印数不完全相加。独审没有再抓PDF；上半库存百万桶×1000到千桶，不混下半日流量。此前有限源审遗漏该打印精度假设，本轮真实样本表明它是系统性假缺失问题，不能据旧预审说源已完整正确。

新增不可变修订SHA `46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729`，仅允许另建065，用完成060的已下载字节离线恢复原算术拒绝，三行都须满足`abs(current−prior−Difference) <= 0.5×(三个原打印quantum之和)`；原known三数与官方Difference不改，日期/字段/真实越界/缺源仍unknown。4项独立目标测试先2预期FAIL/2pass，再4pass；原060与旧source_preflight不回改。该修正早于所有本次金融成绩，属于来源正确性修复，不能叫按收益救参。

065源 `3f9334595653cd825e4d7d2841db0492b6c0b77226645811e459877068e9c30e`，明确producer/normalization_stage。原060下载启动1、新065下载启动0/离线归一化1分别核对；双manifest、原actual/source bindings及新精度逐格audit全部保留。打印相容不等于恢复未舍入真值或证明当年captured-byte PIT。

## 实际清单闭包、独审现场与数值验证

完整060 manifest `00a964468d6fc2cd272d522ae1343227df13b05e3a17dc216305c890a30ba923`；065 `41e3018e0a22ac0bd993f4f47518888af1b5f4347be5e673a9815bc7ebc5c8b6`。root唯一新控制链完成后才授权独审：061首次6fit/25.3117秒，manifest `646cc2f475c9f2060b22780b9e766ed2ed94d658ded5a85d7c9960e9651403cd`；062首次12现金/45.4338秒/1SQL，manifest `b902d63e3bd55d6728c8c1c063bfb087820eb6ad0ec4abc7cc1c53d4cd92211c`。先独核上述最终manifest/terminal与父子SHA闭包，不以partial输入择优。

首次独审0.424秒在行号元数据`int('3.0')`失败，尚未进入模型/现金核。已保存唯一命令、start、日志、失败terminal；根因是独审CSV表示适配，不是作者数值错误。root显式授权后，新2项测试先RED2再GREEN2：Decimal严格有限且整数，`3.0→3`，`3.5/NaN/±Inf/sNaN`均拒绝，仅修独审器。原失败版本已按start SHA精确恢复为`source_checks_first_attempt.py.txt`，与原字节SHA匹配，first_attempt所有现场不改。

**受控review2 session84521，2026-10-18 15:56:02—15:56:21 CST，19.163813秒，exit0；2启动/1完整。** 独审总计0fit、0现金策略重放、0SQL、0网络、0作者核心import。两条pandas FutureWarning来自空成交表的dtype前向兼容提示，当前固定环境下零交易账户完整核对，无数值影响；未为警告改源或再算。最终独审源SHA由actual_terminal/review2_start绑定，执行后保持稳定。

- 全794 official release cells与连续data-week ordinal、2382库存行；789已知raw小表逐行独立Decimal重算，596份原known的current/prior/delta全体差0，193份恢复逐格残差/界和原拒绝一致。5unknown保留：2网络超时、2019-07-03周不符、2023-12-28真实量化越界、2025-12-29日期格式拒绝；不把它们压缩掉或补现代修订值。
- 全52完整ordinal创新、上一archived current分母、严格过去52slot固定hash sham/共同missing、NY保守日末UTC/China16:00首u/下一nativeD/superseded均独算。s最大误差9.98e−17；730个s可知、729对共同可知、787保留事件/7superseded。2020+349事件、340共同信息可知；不是数十万独立公告。
- 全6模型训练成熟/ID/普通F同family并发、报告同权、训练内共同/半pooled scalar scaler、10槽及全部投影核对。2020三臂各15643训练行/438报告cohort/69family；2023各23602/591/77。全母体每臂161014预测，共483042，非事件行也保留；selected只由event&&ready20&&score>0，不以未来闭合/stale筛选。
- 直接重算带截距加权中心化的`XtWX+I`/`XtWy`，核6个便携系数/截距正规方程（不重新拟合/求新模型），系数方程最大残差1.37e−12；全部分数`X@coef+intercept`最大差4.45e−16。训练U/weight差8.69e−14/2.93e−13，正规矩阵差4.55e−13。
- 全12现金、234fill、15348账户日、4060持仓日、988预算/905新分配，实际existing reduction0。独立从保存fills重建remaining qty、cash=初始+realized−fees、mark unrealized/equity、margin/buffer/risk、未解置零情景、全部收益/DD/Sharpe/闭合净胜率；所有fill报价/Decimal tick/fees/slippage、u实数联合分配后floor、D own cap/risk/margin+fee与不复用释放资金一致。滑点已入fill价，不二扣现金。全部比较最大误差`5.456968210637569e-11`。
- 全95family×年（含无活动0格）、四油/其他归因、年度连续切片/赢家集中、未解签名、同2000×1643索引的252日circular MBB分布/CI及冻结资格均独核；bootstrap分布最大差6.78e−21。6个有限native case的N/20low/close及16个局部fill参考价/触发关系核对，最大N差1.43e−14；不是第二次完整原生策略重放，raw未复制。

## 12个账户完整结果

每账户初始1,000,000，截止2026-10-16；2026为部分年。滑点是已计入成交价的金额归因，闭合次数不等于fill条数；未完成仓不填闭合。空仓零收益的Sharpe/胜率均N/A。

| 账户 | 期末权益 | 收益% | 最大回撤% | Sharpe | 滑点金额 | 闭合次数 | 净胜率% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| COMMON_EVENT / base / 2020连续 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |
| COMMON_EVENT / base / 2023冷启动 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |
| COMMON_EVENT / stress / 2020连续 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |
| COMMON_EVENT / stress / 2023冷启动 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |
| INVENTORY / base / 2020连续 | 1,025,396.94 | 2.539694 | -1.939453 | 0.286801 | 1,049.41 | 42 | 35.71 |
| INVENTORY / base / 2023冷启动 | 996,984.14 | -0.301586 | -0.647907 | -0.345263 | 38.60 | 2 | 0.00 |
| INVENTORY / stress / 2020连续 | 1,027,697.85 | 2.769785 | -1.981782 | 0.331955 | 2,647.27 | 39 | 38.46 |
| INVENTORY / stress / 2023冷启动 | 996,892.41 | -0.310760 | -0.654235 | -0.355982 | 98.60 | 2 | 0.00 |
| PAST_SHAM / base / 2020连续 | 1,045,759.21 | 4.575921 | -0.957717 | 0.916647 | 414.03 | 16 | 62.50 |
| PAST_SHAM / base / 2023冷启动 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |
| PAST_SHAM / stress / 2020连续 | 1,047,260.84 | 4.726084 | -0.725383 | 0.948841 | 1,092.49 | 15 | 66.67 |
| PAST_SHAM / stress / 2023冷启动 | 1,000,000.00 | 0.000000 | 0.000000 | N/A | 0.00 | 0 | N/A |

COMMON_EVENT全2020+只有1个正分动作，因单手risk/margin限制被拒，所以四现金账户都未成交；不是隐藏过滤器或完整市场本来没有机会。INVENTORY有401个动作，主base324个因risk/margin/整数手拒绝、18期限拒绝、17family占用，实际42笔闭合/24family；PAST_SHAM75个动作，主base17个开仓、16闭合/15family。低DD很大部分来自低活动与固定预算，不能直接视为高质量信号或可加注。

## Alpha、置信度、未知与运输范围

主2020base INVENTORY对COMMON_EVENT平均日log差+1.526464e−5，95%CI **[−8.451762e−6,+4.340843e−5]**；对PAST_SHAM为−1.196795e−5，CI **[−4.234962e−5,+1.274956e−5]**。两者都跨0，无法通过共同要求的正下界；相对COMMON的DD更深，相对PAST_SHAM收益低2.036227pp且DD深0.981736pp。不能单挑库存正收益说已经有增量，也不能凭区间跨0说所有EIA信息无效。

INVENTORY主stress自身+2.769785%，但成本/保证金会改变手数与接受交易，不能解释为提高费用反而改善同一组交易。2023冷启动base/stress均仅2笔闭合、0胜，收益−0.301587%/−0.310760%；显然没有跨期稳定优势。库存连续账户2020—25仅2020/22正、2021/24负、2023/25零，2026部分年负；零活动年不是盈利穿越周期。

主INVENTORY中仅3个source日曾stale，期末无仓；但有6条历史未解路径签名记录（不是6个独立公告）。PAST_SHAM主账户918个stale源日、922条未解签名，期末1仓/stale1；不能把它的名义4.5759%/4.7261%推荐为胜者。其末开放long全部置零情景为997919.21/999420.84，低于本金；不是普适下界。按收益前冻结的未知规则，两继续资格均**unknown**；名义CI/回撤/冷启动门本身也失败。历史stale不被删除或臆测平仓，不能用未知结果美化任一臂。

全family资格保持，四油品只事前诊断。主库存base四油净贡献14086.73、其他family11310.21；最大赢家FU11813.33，占**正贡献**24.14%（非净利润分母），前五占70.67%。没有family留出训练，不能将24个实际成交family视为独立宏观实验、strict held或全品种普适。2020+仅349个报告事件、历史多次择题与小数量闭合限制置信度；2000个重采样不新增市场。

库存绝对收益只在固定静态vendor规格、close mark/延迟退出和重建archive时钟假设下成立，不是历史broker settlement、当年原字节PIT或真实盘中成交资格。有限路径证据也不能证明极窄止损生存或额外手数边际价值。

## 结论、反思与交接

接受来源修正及保存研究计算；**未支持这一个新鲜季节库存创新/日级决策/Ridge/现金政策包继续晋级**。未知资格不等于通过，名义失败也不靠删stale、加活动、改风险、缩损/seed/模型救参。不把它扩大为所有外生信息或AI无效，不推广PAST_SHAM或COMMON_EVENT为目标策略。

开始与结束新增按收益调参过拟合：**否**，输入精度修复与独审dtype修复均不改变收益算法，源/模型/成本/动作冻结且金融实际各一次；多轮历史择题、条件标签、少数公告与尾部估值风险仍**有**。继续本固定包调参价值：**否**；继续完整全市场高质量long目标：**是**，尚需不同且能在合法决策后保留净价值的信息/机制。现在不启动新实验。全期更高净收益低DD、极窄止损与加注均未证明，goal保持未完成、生产资格false。

receipt SHA `44994ff68ef91b8b98fcc24f179dc7a67be5e7dfed752b67e3f439eadf516262`；actual terminal `148ce1fa43069534c0af71008cc8876cecad36c0fe567f7ed944be54219027b8`；review2总计收据 `721345be86f450ad238b7dbb6f2399aa2e33a90aa8b958d35543b739066ee886`。第一失败terminal SHA `2cce93058314ef59404922f3452338b644f58de983e42772ac6c76c4a23bd10d`保留。`artifact_inventory.json`列必要最终源、两次现场、精度/协议证据与本记录；早期preflight是当阶段证据，最终可执行代码绑定以review2_started/actual_terminal为准。root负责最终决策、状态更新与局部登记，本agent未改LINE/registry/根账。
