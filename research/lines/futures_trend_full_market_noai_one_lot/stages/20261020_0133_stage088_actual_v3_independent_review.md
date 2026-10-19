# Stage088 v3 完整实际结果独立审查

时间：2026-10-20T01:33:23.542592+08:00。结论：**PASS_WITH_LIMITS**，remaining P0=0、P1=0。本次是指定daily proxy研究合同与账本通过，不是盈利评价、完整C9或生产资格。没有重跑金融、修改源码/冻结输出/LINE/Git；不是重要策略突破。最新steering将另研究0.25%周门/无周门两版，本报告只归档已完成0.5%，不能当新两版验证或新UI交付。

源：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_contract_weekly_risk05_v3`。manifest SHA256：`f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860`；提交：`83e7669aca75811e50e009c3095c015311e646df`。基准N manifest：`859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`。v1失败前缀、v2撤回源与本次完整v3分开；未复用v2绩效。30个输出、22代码hash、23快照及起止代码/原输入绑定通过；使用086实际MRO，未混用070/079入口。

## 公式、因果与数据

独立以原始clean冻结行情、完整交易日历、metadata重算，未导入068/069/085金融算法。N与本轮行情/映射/metadata/截止表及输入overlay同hash；全部93品种、6所、4328 epochs，实际83品种有成交。只批准的cap移除与0.005风险分数发生参数变化，无AI/月池/pairwise，无加仓，无最大4品种门。

全部1310笔OPEN的原始receipt、数量、方向、signal/stop及实际entry_risk对齐；信号预算=总权益×0.005，实际预算=min(原信号预算, 开盘逐仓mark并扣前序真实成交成本后的权益×0.005)，总风险=整单量×max(|真实open−有效stop|×size,tick×size,1)。全部通过，最大risk/budget=0.999947977，开盘权益最大误差2.1e-09。550整单拒绝=449超预算+101已穿stop，均无对应实际成交；无unbound receipt拒单。未把拒单变一手，最大真实单量112手、最大同时15产品。

周线由exact实际合约已完成周重算：93545行、1851查询合约，保留9291无效周不拼接；MA最大误差2.73e-12。116笔long的signal与preopen双授权、2964候选闸门全核；short/close没有周线门。全部真实fill对应有效原bar，bar量≥整单量；两笔execution-only报价均为AL平仓（2021-04-26三手、2021-09-24两手），没有新开。4328截止日重算通过，无到期deadline持仓/新开违规。2023起仍有1009笔成交。

## 延期生命周期与资金

59条事件逐条绑定原收据：39次preserve对应18张原receipt，10次映射取消，10次缺bar缓存派单；合计19张不同receipt。原授权从不重写，真实低量/缺bar证据、EOD actual0、原量target、因果mapping均吻合。最终1张后来真实成交（WH202101，BACKTESTING.1024），6张后续风险拒绝、2张forced取消、10张mapping取消；无遗失授权后孤儿成交或虚假CLOSE。2021-09-08 pg202110三手在真实V68122足量时，先发现map改pg202111而取消；22笔普通首次T→T+1在当日map变化时仍保留原信号执行语义，符合本次预登记区别，不偷加新门。缓存只用于派单/估值，十条均无当日真实bar，报价回溯原真实close/asof，不能作为成交资格。全59行衍生证据见审计代码目录CSV。

2027条entry诊断的权益与真实EOD权益全同；实际保证金floor全量重算。在17条同时可见真实持仓与preserved OPEN的entry诊断上，reserved保证金≥真实持仓+未成交原意向之和，最小差仅−5.82e-11浮点量级；cluster cap未见低于事实保留的记录。逐日事实cluster PNL由真实entry basis和剩余量独算，未把未成交OPEN当浮盈亏；但未导出全部私有中间缓存，不能声称逐回调核了每次内部PNL变化，冻结代码与83项scope oracle提供补充。

156次forced整单取消（1941手）原receipt全部归档、释放计划风险算式正确，均未成为实际现金平仓；实际forced close事件CSV为0行且完整19列表头。实际margin在真实填单前保留，取消不擦真实持仓。

## 真实账本与结果

2862个daily账户日期完整（2015-01-05—2026-10-16）；2621次fill=1310开+1311平，1302个完整entry，9次额外部分平仓分段。所有原始手续费/滑点、整entry费用与分段/FIFO、部分残余桥接及EOD positions独立重建。holding/trading/net最大误差分别1.82e-12/1.82e-12/3.64e-12。

| 指标 | 独算结果 |
|---|---:|
| 期末权益 | 758,087.52 |
| 总收益 | -24.191248% |
| 最大回撤 | -66.316210% |
| Sharpe（240日log，同冻结口径） | -0.152013186 |
| 手续费 | 75,067.478520 |
| 总滑点金额 | 313,295.00 |
| 完整entry胜率（不含8未平entry） | 34.792627% |
| 2024净PnL | 157,181.146755 |

期末实际8个残余entry共55手，均仍在有效deadline前且有真实mark；无残余部分平仓段。已闭entry净额-320,570.203460+未平mark浮盈79695−未平entry成本1037.27506，与资本合计758087.5214797。另有区间最后一天SF202701 short_case1a六手未成交意向诊断：不计入实际55手，不外推次日执行。最大名义敞口18,789,780、最大名义敞口/权益24.9109，0.5%逐笔止损距离预算不等于组合或极端gap最大损失。亏损结果不支持称为稳健盈利策略。

## 边界、置信度与复验

潜在P2：继承native换月规划会释放cached cluster PNL。共享cluster合成probe可改变live heat，但当前有效heatgate=False；90个非空cluster各自独立产品，l_F/pp_F/v_F三个空cluster不受原heat/cap保护。换月后continue，同产品当日不再消费该缓存，次日refresh恢复事实PNL；未证实本轮主动风控受影响，不据此热改代码或经济参数。未来若修改cluster/启用heatgate须另做合同与回归，不能默认为已覆盖。

高置信部分是账本、实际budget、周线与可见生命周期身份；全量private中间状态、逐时交易所规则、交易量可得性/排队/涨跌停及日内stop顺序仍有限。metadata/保证金/费率/规格不是完整PIT，C2/C9日内与缺供需过滤按授权禁用；execution-only报价不生成信号。没有未来收益或生产资格保证。

实际执行脚本/结果/59事件CSV原字节在`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0133_stage088_actual_v3_independent_review_audit_code`，每项SHA见配套JSON。reader最初遇到CSV `113.0`字符串解析错误；另存v2仅适配解析，随后从头全量重算成功，失败日志也留存，未改金融文件。原0114预审、0121脚本附件均保持不变。

过拟合反思：否，没有扫描经济参数或按收益剔样；保留失败、withdrawn与本次负结果。继续独立记录和如实展示有价值，但多次修复后的样本内结果不等于预测力，不自动晋升或调参。参考CME仓位风险说明与官方vn.py组合策略文档用于方法核验，本报告实际结论依据冻结源及独算，而非外部性能断言。
