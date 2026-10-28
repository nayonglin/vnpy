# Execution ledger — plan: 20261028_1625_stage032_implementation_plan.md

- 2026-10-28 16:25 Asia/Shanghai：用户指定改为2020年至今，继续已确认设计，不再征求许可。
- Ruling：2020起点必须新账户重跑A/C，不能从15年权益截段；最新截止先准入后声明。
- Pre-flight：Task1数据接口→Task3 runner消费旧规范receipt/maps/DB；Task2 factory→Task3使用固定公开接口；Task3真实成交→Task4独立复核。
- Ruling：本线隔离约束优先，执行账本放本线stages，不创建跨目录SDD工作区。
- Task1进行中：stage032_data_scope_audit补新日数据；旧数据不覆盖。
- Task2待派发：加仓适配器+TDD。
- Task3 root实施入口及报告；Task4完成后才交付。

- Task1：数据已准入至2026-10-28，新增56条真实合约日K及38条主力mapping；最终receipt dce2ac8a312d31ab557d1b588b02e09022c0c65e5cf2bf02456b2639fb9fb4ee；待新独立review。
- Task3：run_stage032_daily_addon.py新增入口，runner合同测试11项通过；保留初始缺实现红测及effective schema回归红测。发现effective spec不含setting-only margin字符串，已仅修校验器以兼容真实schema，风险参数不改。
- Ruling：A/C都新账户2020-01-01起算、实际首交易日2020-01-02，部分末周不进入周指标；日K加仓仍可使用完成日K。
- Task3：实际加载addon开关必须与A/C一致，增加RED→GREEN校验；runner合同测试更新12项。Task1独立preflight已复算2607新source和3603旧绑定零变化、56行raw/SQLite一致。Task2作者22测试通过，待freeze与新独立逻辑预审。
- 2026-10-28预审发现P1：同批跨品种pending加仓独立预算快照，开盘小幅gap会合计突破原cap（103+103计划cap206，首单104、后单103均放行）。金融回放尚未开始；交实现agent先RED反证再修共享批次预算，普通底仓订单仅记录gap占用，不新增拦截。独立review将复验后才放行。
- 预审修复阶段：共享预算P1与退出原因P2作者RED→GREEN；独立24条跨品种成交排列路径、不同cluster、ordinary父开仓gap、D3 close极端反前视测试通过。真实Stage847父update_trade混合全平及3→1部分强平（addon优先）、重复调用/费用/净仓守恒独立核验通过。最后同品种已持底仓open margin gap回归待作者freeze。
- 研究线全回归：399 tests /12.207秒，exit0（包含旧pandas测试FutureWarning，不是失败）；最终源码若继续变更须重跑。
- Task2最终源码560232fc...冻结；28 adapter +48旧Stage029回归通过。Task3/整线最终400 tests/11.884秒 exit0；待独立最终签字，金融回放仍0。code_package_frozen_v3.diff提供完整新代码。
- 独立预审正式签署PASS_BOUNDED_A_C_FINANCIAL_REPLAY_PREFLIGHT，P0/P1/P2剩余0。A/C金融回放attempt001已并行启动（独立进程、同一只读批准DB）；会话A65733、C73755。start2020-01-01/end2026-10-28，初始15万，旧输入均未改。输出outputs/stage032_A_attempt001与stage032_C_attempt001；日志同名前缀.log。下一步必须检查terminal/postflight/全部acceptances，再新独立结果审查。
- A/C attempt001完整exit0，但报告严格owner守恒拒绝C：FG401 BACKTESTING.315 base开10却平11、漏addon1，SM505/cu2509亦有同类问题。C001明确INVALID_SLEEVE_OWNERSHIP，不使用headline作有效成绩；保留原始账本/源码快照。疑因无真实成交旧计划减仓污染新owner待平queue；只修新增归属正确性，不改账本或参数救结果。修后需重新A/C并独审。
- owner V2冻结e601f44f...、test1e6b3542...；34 adapter与48旧回归通过。整线406 tests /12.711秒 exit0。新增actual-fill inventory、仅预约真实余量、逐fill与期末owner守恒，原父queue/风控/参数保持。等待unique owner_fix独审签字，再启A/C002；完整diff owner_fixed_v4已封存。
- owner V2独立复核PASS，源e601f44f...，3真实失败序列/未fill/重复预约/成本/孤儿/关闭原路径均通过。A/C002已并行启动，A会话65599、C88100；旧001不覆盖。必须A1/A2账本等价，C2新独立全面结果审查。
- Task1/2/3/4研究工作全部完成：A2/C2有效、A复现12文件SHA相同；最终新独立review PASS_WITH_LIMITATIONS/P0P1P2=0/NO_PROMOTION，定稿及仅标题变化的reviewed图补审PASS。研究线406测试通过，无结果后调参；C001拒绝/旧源码与全部原始账本保留。下一步只做交付哈希闭环及本地Git提交，不push/merge/生产。
