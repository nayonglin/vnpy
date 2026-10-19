# Stage061：当前交易合约周线开多门独立预运行审查

- line_id：futures_trend_full_market_noai_one_lot；审查时间：2026-10-19 20:12 CST。
- 工作树/分支：/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian；codex/full-market-noai-one-lot。
- 审查性质：独立代码/时序/数据合同/无金融回放联合验证；无金融重跑、无生产读取，不改实现、旧source、LINE或Git。
- **结论：PASS_WITH_LIMITS，无P0/P1阻断；当前058/059/060可按root预登记冻结后运行唯一新候选。** 仅允许按已确认合同运行，不代表收益改善或正式晋级。
- A基准：87487e32d36a443942f612ac7eeef71ede9ea46a；A manifest SHA256：a8696e2b73b25399251d1efc46e47dfd49f89d23bfc80f6bc1f33bfdbe5237c3。
- 旧主力周线C只保留为历史错误口径研究对照，manifest SHA256：7e6f2647de1d99253ba2cbade3e0852158d50d3cbfde19e8da4afdba6f16fed4，不替代当前exact-contract合同。
- 拟唯一新输出：outputs/run_20261019_contract_weekly_long_v1；本阶段尚无金融结果。
- 是否重要突破：否，修正用户要求的信号语义。新增参数：只改周线来源为当前交易合约自身；窗口5/10/20/40、strict>、40完整周、双相位不改。修改/删除原native参数：均无。

## 调研与判断

沿用此前已核验的[pandas官方resample](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html)及[backtesting.py官方实现](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)。判断：周期结束可见性仍必须通过独立交易日历和开盘/收盘相位保证；本次关键是合约身份，不能以主力连续、产品别名、其他合约历史补齐40周。本实现符合该约束，上市不足40周会减少机会，是已确认合同的结果，不允许为增加成交借历史或放宽门槛。

## 逐路径审查

1. Stage058 `WeeklyContractTrend(market,contracts,calendar)`只按vt_symbol定位该合约的日线，完全不接收主力mapping。metadata绑定product与contract双身份；本地周范围从listed_date开始（缺失时按本合约最早行情），先由完整独立calendar确定自然周最后会话，再裁本地周。读取整段历史但查询只取asof之前允许的证据，未来价格/新增其他合约不能改变过去lookup。
2. 周末只取本合约accepted-clean正close/正volume；execution-only、expiry/quote-only、显式禁止新开报价、缺失或未知资格均不进入周均线。坏周保留NaN、不中断网格、不drop、不ffill；少于40根或最近40周有坏周不开多，均线严格MA5>MA10>MA20>MA40，相等拒绝。
3. signal_close只允许week_last_session<=signal_date；open严格要求week_last_session<fill_date。节假日末会话按完整calendar，整周休市不造周K；行情周中截断不能把周三错当末周。若合约本地历史结束而独立calendar已经有更新完成周，返回missing_latest_completed_contract_week拒绝，不能无限沿用旧bullish快照。
4. Stage059实际long `_calculate_entry_sizing`以vt_symbol查询；`_open_position`以contract_vt_symbol查询；原native flat、reverse、rollover重开全部动态进入这两层，rollover使用新target_contract自己的周K。原日线rollover形态等baseline逻辑不改，周门不借那段历史。
5. 未成交层绑定不可变原signal授权，实际 `_fill_order`仅Offset.OPEN且Direction.LONG才检查；授权和当前快照都核product+contract，因此同品种其他月份的bullish证据不能授权当前月。旧单重挂仍用本order.vt_symbol并校验原layer.entry_date，不能用reissue日期替代原signal日期。
6. short定仓、short `_open_position`、全部CLOSE和env_probe直接super，不查询周提供器；Direction.LONG+Offset.CLOSE的空头买平没有误加门。没有因周转弱强平已有多仓。组合现金、保证金与持仓路径仍可能间接改变空头成交或收益。
7. 新strategy MRO在039 native预算之前施加周门，成交MRO在041开盘风险之前校验周证据，通过后完整执行原039/041、生命周期、CleanExecution闸门。native零手不能因周多头复活；原风险预算floor/cap、倍率、1手上限、不加仓、全市场自然容量和保证金闸门均保留。
8. Stage060与052差异仅新provider/strategy、exact-contract政策和证据字段、完整calendar及导出scope绑定；数据加载和设置构建相同。集成测试将生成native设置与A manifest逐键比较通过；039/040/041源码hash与A完全一致。仍为100万、2014热身、2015-01-01至2026-10-16、无AI、每品种最多1手、无4品种上限，分钟C2/C9和供需过滤继续按授权停用。
9. 最终060移除了未调用050旧provider的hash名单。新 `trading_calendar.csv(date)`冻结完整2005—2027源日历，进入输出hash；`manifest.weekly_feature_export`记录scope、queried_contracts与rows。`weekly_contract_features.csv`只导出实际查询过合约的完整本地周历史，不冒称4328合约全量周网格。future local rows可在该导出出现，真实授权仍由双相位截断。

## 实际独立测试

- 本审查独立运行本线联合206 tests：**25.561秒，OK**。
- root最后060改动仅calendar/身份/导出后，本审查重新对最终版060跑3项真实runner集成：**0.045秒，OK**。覆盖最终FeeStrategy/Engine+058原始周价多头通过并保留041预算、bear拒绝且不留费用/幽灵意向，以及native设置与A逐键相同。
- 额外独立组合验证：同品种rb202010有40周严格上涨，而实际目标rb202005仅3周；用真正058提供器接059真实native定仓，flat_entry、reverse_entry、rollover_reopen三个context均查询rb202005、history_weeks=3、selected_volume=0。另一合约bullish不能补40周。
- 实际断言最终MRO顺序、039/040/041旧源码hash与A一致；新058/059/060及其3份测试的6个SHA256写入JSON，并在落记录前复核未变化。
- 058最终SHA256：546f2097b80117be1a0b0c2c29f4a39c380c9313270a6e31056bf29029eee491。
- 059最终SHA256：b0f340fe6c800b291225f42fadecf995d32f08ba8369f9471027c5dbecc387b8。
- 060最终SHA256：3aabda24cf36506b3af2ae76cf5d5bc56515688eace06b670115422005b1b07e。

## 尚未产生的结果与边界

本阶段没有金融回放。期末权益、收益、最大回撤、Sharpe、总滑点、成交次数、胜率：均不适用、不预测。新增/修改/删除金融结果均无，旧主力周线C结果不移花接木为本候选结果。

预审不替代实际全量账本审查；日线近似/静态规格与非历史PIT费用、private pending逐项和真实开盘流动性限制继承。合约上市日期是已接受供应商metadata快照，不是独立历史公告时点认证。未来金融结果如果因新合约寿命不足40周而少开多，应如实呈现，不降低窗口、借其他合约或改用户条件补救。

## 反思和后续

- 开始/结束过拟合判断：**否，本次是用户明确纠正合约口径，固定窗口与门槛不变，没有按收益选参**；但已看到同一历史区间旧主力周线结果，新候选仍不是样本外证明。
- 开始/结束继续价值判断：**是，正确实现并证伪当前交易合约周K合同有价值**；不能预设收益必然改善，也不因拒单多主动放宽条件。
- 下一步：root完成预登记/冻结提交后只运行唯一新full候选；完成manifest且进程退出后，本独立agent按Stage064对每笔actual vt自身原价自然周末独立重算两相位/40周/evidence_id，不用mapping凑历史，再全面核预算、费用、日账本、生命周期、残仓、端点和A/旧C/新候选比较。
- 本阶段仅新增独有Stage061 MD/JSON；不修改LINE/registry、正式模块、旧源、Git或金融产物。显示层063另行验证，不在本预审中冒认通过。
