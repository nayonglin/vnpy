# Stage079 0.5%风险版执行事实修复及v2回放前冻结

- 时间：2026-10-20 00:47 CST；本线futures_trend_full_market_noai_one_lot，继续codex/full-market-noai-one-lot原分支。不是重要突破，是真实数量/计划语义修复；只改本线新增文件。
- 用户合同仍为上一轮N交易合约自身完成周线，仅多头MA5>10>20>40，单笔信号总权益×0.5%=0.005，取消1手帽，其余native数量及资金闸门，100万/全市场93产品/六所4328epochs，不加仓，无AI/无4品种限制；日线近似及缺供需过滤停用授权不变。比例最初笔误0.05%未金融运行，修正为0.5%后才有首轮回放。
- 参数/信号/价格数据/费用/生命周期/经济阈值新增修改删除：均无；仍仅相对N新增stage068_risk_fraction.005、max_position_size技术哨兵1→2147483647，固定预算替换旧金额计算的原合同不变。原trigger/target/priority/max reductions保持。

## 首次失败事实与独立审查

金融源码07254b5c9，输出run_20261020_contract_weekly_risk05_v1，在2017-03-13因Stage074_requested_close_direction_mismatch硬停止；无最终manifest/完整结果，不报告前缀绩效。341次前缀成交重建实际a空20/SR空18，TA16/p17/v29是零实际仓位的待OPEN意向。Stage076独立复现两P1：native forced-margin候选把未成交OPEN层当可平仓，欲生成CLOSE及暂估PnL；同时003真实margin floor正确保留actual，native循环误当计划无效而将应减2手排成2+2+1全部5手。074守卫不应放宽，不能用skip queue掩盖PnL/风险状态污染。具体真实触发意向未记录state，p只是排序强推断而非直接观测，Stage076明确P2快照缺项。

原失败目录、协议/日志/前缀/source快照与旧070/074逐字节保留；新run必须另名v2，失败不当成绩、不调风险阈值/年份/品种救收益。

## 新078/079机制及证据

078仅在强制减仓规划scope投影margin：真实abs(actual)扣有效pending CLOSE，再加未成交OPEN layer；按当日close/因果缓存计价。超原trigger时先按原priority整单取消未成交OPEN至原target或无意向，发生在任何native Close event/PnL/streak/outcome之前；不修改原receipt，另归档取消记录，清旧OPEN/未同步层/目标/诊断/本模块见证pending预留，不释放真实持仓margin或真实pendingClose。

再复用原native while与实际剩余已同步层候选。新排CLOSE立即降低规划数量、使需平2手只排2，重复同日/跨日不重平；外部实际_estimate_margin_usage、券商保证金和实际头寸直到真实CLOSE才释放，finally恢复scope(含异常)。adds仍关闭，不推广未跟踪的加仓预留路径。旧forced计数仅实际规划减仓，取消另计，不制造真实成交或费用。

079为隔离复制070的新入口，078置FeeStrategy最前MRO并绑定codehash；新增execution_state_policy与prior_failed_protocol_sha256，原预算068/账本069/周075/待平护层074均不改。无论on_bars还是成交失败，快照均含真实pos、targets、层/是否同步、原授权、pendingClose、活动单与资金；成功导出完整unfilled_intent_cancellations.csv和forced_margin_deleverage_events.csv(无事件也有表头)，支持实际逐事件投影复算。只增加诊断输出不改经济规则。

TDD：078先8场景4失败4异常精确复现两P1，后41项真实栈测试GREEN(070+078及最终079，含074分平守恒)：实际0/未成交17只撤意向；actual5/eq750/price110/size10/margin.1/broker1.65仅排2、target3、actual5与真实margin550保留；多空、优先级、mixed synced/unfilled、跨合约移仓、缺当日bar缓存、预留追踪、旧单不复活、异常scope恢复与跨日幂等。079两项在旧070 RED后GREEN，补P2完整快照。

root标准整线332 tests/28.587秒GREEN，独立审查332/28.747秒GREEN和42项额外投影oracle GREEN；完整事件导出后079定向回归再核。未参与实现的Stage080_preflight绑定最终hash，无阻断后sourcefreeze提交再启动v2。最终成功审查另Stage080_actual，显示另Stage081，交付Stage082；不以预审或渲染成功冒认金融成功。

## 运行与反思

计划新完整金融输出run_20261020_contract_weekly_risk05_v2；实际2015-01-05—2026-10-16/2862日，2014热身，同一全部行情/映射/metadata/期限/calendar哈希，原N为冻结对照。首次失败后第二次金融回放；其它未执行第三个参数或成本/窗口搜索。通过条件仍为完整终点/预算0违规/全部long周门/会计误差<=1e-5/整手与部分平仓守恒/期限无过期仓/代码数据hash闭合，严格风险比较不加容差。

新增回测结果：此记录写入时无完整结果；旧结果修改/删除：均无。所有权益/收益/DD/Sharpe/滑点/交易次数/胜率等待新完整回放及独审后报告，不将2017前缀数字列成业绩。原N对照见Stage070。

开始过拟合操作判断：否。修复依据actual与intent、计划与真实资源的恒等式，不看任何收益，不调整0.5%或弱年份救参；新结果仍是同样本后验研究。继续价值：是，只有先保证执行事实与会计/数量一致，风险比例研究才有可解释性；如仍失败继续按真实错误处理，不能放宽守卫冒认成功。

调研沿用[CME风险定仓](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)与[vn.py官方组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy)：目标委托不是实际成交，未成交意向撤销没有平仓现金PnL，已排CLOSE可减少规划敞口但真实margin须等fill。此为实现判断，不声称文档给出了本研究的完整现金模型。无下载/生产/CTP/订单接口，不合入master或正式策略。
