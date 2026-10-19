# Stage101 含周门 0.25% 完整实际回放独立审查

时间：2026-10-20T02:03:07.496053+08:00。结论：**PASS_WITH_LIMITS**，remaining P0=0、P1=0。仅认证已冻结含周门v1的指定daily proxy合同、实际账本与资金导出；不认证盈利能力、完整C9或生产。审查者未重跑金融、未改金融源码/旧输出/LINE/Git，不是重要策略突破。

源目录：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_risk025_contract_weekly_v1`。manifest SHA256：`7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35`；金融提交：`9feb5784d7757ee81cbab007a610a0d64da64ca6`。基准N manifest `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`，父.5完整源 `f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860`；099预审字节保持不变。

关闭臂v1因生命周期真实退出失败且没有完整manifest，本报告不评价其部分绩效，不能把本完整源与关闭臂前缀拼成完整双臂对比。后续模型即使另获授权，也不覆盖或取代这次原规则事实。

## 数据、公式与周线

独立固定.0025算式，不导入090/069/092金融算法：30输出hash、22代码hash、23快照及起止源码/原输入绑定通过，实际源与N的accepted行情/映射/metadata/日历/4328截止表、execution-only qualifier数据绑定一致。覆盖93产品6所4328epochs，实际80品种有成交，2023起1088次fill。未调用AI或在线下载；非PIT规格/费用/保证金限制如实保留。

1318笔真实OPEN全部绑定唯一原receipt/合约/方向/整数qty/原signal/stop。信号预算=marked总权益×.0025；开盘预算=min(原信号预算,因果开盘mark后扣前序真实成交cost权益×.0025)，整单风险=qty×max(|真实open−有效stop|×size,tick×size,1)，原预算不扩大。实际最大风险/预算0.999673235，开盘权益误差≤2.33e-9。562整单安全拒=456超预算+106已穿stop，无对应fill；没有unbound receipt拒绝。保留所有原quantity/env/ATR/资金/cluster门，无一手fallback、无加仓，最大真实量72手、最大同时14产品（无4产品帽）。

周线独算93546行、1851查询合约，9291坏周保留不压缩，MA最大误差2.73e-12。109笔long的signal收盘与严格早于开盘的完成周双授权逐笔通过；2963信号候选闸门、172次实际尝试preopen周门（含所有未成交尝试）全核，weekly拒/实际违规均0。全部使用exact实际交易合约accepted-clean，不用主力连续补历史；short/close不加周门。

## 全量EOD意向、真实资金与PNL

1911个原entry意向按原(date,contract,side,signal)重建生命周期：1910个由真实fill、budget拒、forced取消或092映射取消终止，剩1个是2026-10-16 SF202701 short_case1a三手新区间末意向。2862天全部独算actual、未成交pending、fresh当日预留、reserved和逐cluster资金，不使用实现函数求自己的答案：actual最大误差2.91e-11，actual+pending/reserved/fresh/cluster资金最大5.82e-11；真实entry basis及所有部分平仓后的cluster浮盈亏**逐日0差**。1245天有pending、1084天actual与pending并存，避免把未成交CLOSE提前释放或把OPEN意向当真实浮盈亏；最高未成交计划保证金476354。全日衍生账见代码目录books_daily.csv。仍不声称导出了每次private内部回调或所有候选优先级集合。

55条延期事件=34保留（16原receipt）+11映射取消+10缓存派单，共17张原receipt，原收据/数量/stop/预算全程不重新授权；最终1张后来真实fill、5张risk拒、11张map取消。10缓存派单均只用先前真实asof close，没有当日真实bar，不产生AM/fill资格。3次延期后已有足量真实bar仍因当前map失效在fill前取消：bb201601 2015-11-26（2手/V2）、pg202110 2021-09-08（2手/V68122）、bb202501 2024-08-29（1手/V11）；27笔普通首次T→T+1继续按原信号合约成交，符合冻结的首次与延期边界。全部逐事件衍生证据见pending_trace.csv。

19次forced取消原未成交整单（591手）归档/计划保证金释放算式通过，不造现金CLOSE、不擦真实仓；实际forced close事件为0且保留完整表头。

## 完整账户、分平与结果

2862个daily账户日期完整，2641次fill=1318开+1323平；1311个完整entry，12次额外部分平仓。原始费用、全部partial/FIFO整entry分配、每日holding/trading/net及EOD positions独算通过，三分量最大误差2.27e-13/1.82e-12/3.64e-12。所有fill来自合法真实bar且V≥原整单量；3笔execution-only均为平仓：AL202105两手（2021-04-26）、AL202110一手（2021-09-24）、rb202410五手（2024-07-15），逐笔evidence ID与源报价绑定，无overlay OPEN。4328截止日独算通过，actual无deadline残余/违规新开。

| 指标 | 独算 |
|---|---:|
| 期末权益 | 809,719.744577 |
| 总收益 | -19.028025542% |
| 最大回撤 | -37.111968009% |
| Sharpe（240日log同源口径） | -0.196569984424 |
| 手续费 | 47,445.255422787 |
| 滑点金额 | 207,215.00 |
| 完整entry胜率 | 31.884057971% |
| 完整entry平均净赢/平均净亏绝对值 | 1.953592406379 |

最大回撤峰2015-07-08→谷2026-09-21。期末实际7entry/29手均仍在有效deadline前、有真实mark；没有残余partial段。资本+完整已闭净额-230,950.501082788+残余mark41235−残余entry成本564.75434=809719.7445772；末日另3手未成交信号不计入实际29手，不外推后续成交。总收益和Sharpe均为负，不能据此声称稳健盈利。

## 限制、反思与审计闭包

0.25%是到有效stop的名义风险距离预算，不是费用、极端gap或组合总亏损保证；最大名义敞口/权益22.9291。原AON成交量近似、次日真实开盘、非PIT费率保证金规格、无盘口排队，以及授权停用C2/C9日内与缺供需过滤仍限制实盘解释。继承90非空独立cluster+3空cluster和换月规划缓存释放的P2：本轮有效heatgate=False，换月continue/次日refresh，完整EOD实际PNL已独算0差，不扩大为已发生本轮P1或未来共享cluster资格。

审计脚本、日志、结果及全日/逐事件CSV原字节在`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0203_stage101_risk025_weekly_enabled_actual_review_audit_code`，全部SHA与manifest/源码闭包写入配套JSON。三个实际reader都0错误；source_manifest顶层精确绑定，不能将099预审当本次实际PASS。

过拟合反思：有样本内选择风险，在看过.5结果后新增.25与两周门臂；当前不调阈值/不剔亏损品种/不放宽截止，保留本次负结果与关闭臂失败事实，不用partial前缀比较收益。继续保存和审计已授权研究有价值，任何新统一执行模型须另预登记、同源双臂新跑并各自独审，不自动晋升。

外部方法参考：[CME仓位风险](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[官方vn.py组合文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)；实际判定依据冻结本地数据及独立算式，未借用外部收益结论。
