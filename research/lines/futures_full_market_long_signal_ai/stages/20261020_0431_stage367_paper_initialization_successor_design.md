# Stage367：未注资参考之后的有限双账本延续设计

- line_id：`futures_full_market_long_signal_ai`；记录完成于2026-10-20 04:30 CST；独立只读设计，非收益突破，不触发正式A/B。文件名0431只是整理标签，不是实际freeze/init时间。
- 先读registry；本文是唯一新增文件，不改LINE/registry、359/360或其他线。0实现/测试/模型推断/金融回放/API/SQL/Git；未创建资金状态。只重算131、070两个小源码SHA，均与317一致。

**结论：GO一个独立的初始化后继范围。** 在u20真实完成前，用真实新事件`T_init`签两个各100万、空仓且无pending的研究初态有价值；这不是359的未注资T0，也不是u20资金决策。360仍只执行一次observe-only批次。单批边界不把用户完整目标永久改成无资金快照；本建议没有真实资本含义。

## 已有接口与缺口

下列行号均属本线`tools/`现有源码，本阶段未运行它们。

| 证据 | 判断 |
| --- | --- |
| `stage322_continuous_paper_state.py:74–83` | `new_state`只建立空态并绑定kernel身份；`start_u`须取冻结日历中u20的真实索引。它没有初始化时钟，不会自行签T_init。 |
| 同文件`:48–55,176–215,217–258,260–272` | 原核/风险/成本身份、seal_u、advance_D、保存恢复已存在。base/stress各用自己的状态，无需新账本算法。 |
| `stage325_forward_caller.py:43–57,67–104` | policy identity只绑定4个调用源；future要求显式双态，observe-only拒绝states/kernel。初态来源与131源码须在外层补绑定。 |
| 同文件`:145–168` | 完整candidate预算进入真实`decision_proposal`后才按其receipt分类；不是借未注资观察时间作资金seal。 |
| `stage321_forward_journal.py:134–162` | append提供实际UTC、完整payload hash与幂等key，可签双初态；这是本地证据，不是外部时间戳。 |
| 360 `next_scope.json:24,40,44–52`；357`:162–178` | 360 paper_state=0、仅u20/D21；357研究seal始终active=false/states=null。后继必须另存scope/日志，不能混入该批次。 |

## 最小实现方法

只需一个小初始化工具：后继payload相邻保存未改的131/070/042三文件，按精确SHA正常加载131定义。131`:12–22`仅校070身份后导入，070`:18–32`仅校042身份后导入，042`:9–33`是标准库/np/pd和常量，`:591`将main置于guard下；正常定义加载不运行数据入口。它保留原函数globals/closure，维护成本小于另写三层AST白名单。只用359的321/322/325，绝不导入`stage131_contract_choice_cash.py` runner，也不调用run_cash_account/load_market_bridge/CLI。

320已有AST机制`:45–62`，但SOURCES无131、helpers缺完整资金定义（`:34–42,70–84`）；它可作备选，当前没有必要扩写。正常导入“纯kernel”与启动旧金融runner必须区分。

042/070已在359 payload；131没有，后继需单独绑定其15,527B源码。SHA=`85205ef9bc309a34283fc0082ac09c53d1f156ca788b8efe6bbd9743f5f430b5`，本次与317 refs`:235–243`相符；070亦与`:195–203`一致。定义闭包只需这三源，初始化不读旧raw/cache、SQL或经济投影。

工具建立独立base/stress账户ID，各调用322.new_state一次。完整双态和export摘要、131/070/042及实际调用源的尺寸/SHA、运行版本、冻结模型/scaler关系、359 freeze_event/T0、start_u日期/索引、后继scope一起进入一次321 `research_account_initialization` payload；其实际recorded_at才是T_init。初态caller_policy绑定仍用原325 identity，初始化receipt关系放外层封套，避免循环hash或改写359。费用公式、单family0.0025/总risk0.02/margin0.25/buffer1.1、0.25N与原退出/F0全固定，不因空态或未来盈利改参。

## 一次验收后的衔接

361接收、362独审、363接纳后，下一范围最多先用同一u20已接纳snapshot，另跑一次325 `mode=future`形成双场景资金研究proposal；不重取行情，不把357未注资seal升级。此时新input/proposal receipt取真实当下时间。外层另核`T_init < source_completed_at`，并核原T0后的完成、真实接收及完整资金proposal时间严格早于完整执行域D_open。325当前只以旧T0分类（`:81–83`），不检查T_init，这是必须补的薄校验。

缺完成时钟、迟到或未获接纳就保留无及时资金决策；若T_init晚于u20完成，u20资金演算只能标为事后重建。322`:178,219`和325`:104`不允许start_u=u20静默跳成u21：保留未激活初态/缺口，后续另列有限恢复或真实新起点，不能伪装连续零仓或倒改T_init。

下一真实D行情到达，沿322.advance_D推进两个原账，随后seal下一u，保持同一状态链。357当前日期硬编码（`:19–20`），且主入口execution_dependencies为空（`:316–319`）；更多日期必须另给有限接收范围并带入双态持仓/pending依赖，不能直接称永久日更。本阶段不实现该扩展。318§5固定复核时点继续有效，任何unknown/中断都保留，短期表现不决定是否重置。

## 调研、反思与结果

只核[Freqtrade维护者lookahead说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)：全时段数据可能暴露未来，且单品种切片会误判跨品种排名。判断是保留全peer域、真实接收/资金seal和原状态链，不运行它的历史回测工具，也不从该文推断本策略有alpha。

开始/结束新增过拟合：否，未读新成绩或选参；原纯52参考的历史择题偏差仍在。开始/结束继续价值：是，有限初始化能使下一批新证据真正检验连续预算及成本，不让未注资阶段替代完整目标。高质量、极窄损可承载性与提高下注均未证明。

模型/科学参数/回测结果新增修改删除均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。本文只建议后继，不创建初态、不签T_init、不运行资金proposal。
