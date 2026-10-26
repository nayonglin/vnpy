# 周末止损、空头case2与RSI退出消融实施计划

> 执行方式：原隔离研究工作树内测试先行实现，独立审查后回放；用户已确认第4项空白、按前三项执行。

- line_id=futures_weekly_formal_no_half_r；登记时间2026-10-26 19:24:39 CST；来源HEAD2c8aa6b66。当前formal m0008/Stage037已核；本轮不改正式材料/生产，不作晋级A/B/C，研究线做固定W0（旧N002）与W1（本次用户指定）的最小对照；止损模块无法独立交易，无独立B。未提供生产稳定目录及运行资格不阻止已授权的隔离研究，但禁止声称正式资格。
- 结构假设：周线入场的价格风险也用已完成周线确认，减少日波动触发与周趋势不一致；同时取消short_case2新开、取消RSI减半。三项是一个预声明组合，不能把结果单独归因某一项。不搜索阈值、不删品种、不收益择源，不做后验救参。
- 固定参数：原19商品、150000本金、MA5/10/20、MA40决策off、21有效周就绪/41容量、MACD全部消费者off、五个AI选品flag off、0.5R/C2 off、maxpos19（无额外4仓）、资金/保证金/相关性/形态/量仓规则和固定滑点/零手续费均沿用。long_case1a/2保留，short仅case1a。
- 周止损合同：初始技术止损引用本合约最近已接受完成周OHLC；普通层止损/阶梯锁盈/ATR中点/MA20/前两根止损只在该合约本日刚完成有效周时判断，用周close确认（不改成周内high/low穿价）；动态极值和浮盈也按周更新。prev2须入场后至少2根已接受完成周；日龄不替代周龄。周中换月引用目标约最近完成周，手数与保证金仍按当日计划参考close，必须记录两者及方向有效性，不能偷取未完成周。无完成周/跨epoch旧completed/错误方向均失败并报告，不以日K回退、换价或延期救结果。
- 每日保留：账户真实盯市、资金/保证金硬约束、热度减仓、5交易日换月、position/reconcile/epoch安全；它们不属于本次价格技术止损频率改动。RSI exit参数False且退出事件0；普通/Donchian/post-quality加仓、反手和排列破坏退出保持关闭。target_contract_only硬锁。无layers的持仓兜底若重建出日线stop，计数非0即拒验，不能默称周止损通过。
- 安全周识别：要求当前AM inner.count>0、最新已完成周值与当前inner尾值一致；fresh须周末日期等于请求交易日。WeeklyAM跨>366天复用同码的旧completed不得引用。非周末即使daily close穿stop也不技术退出；MA内联路径同样被fresh gate覆盖。
- 成交：严格信号后下一全市场交易日、同一真实合约正量日Kopen，无分钟/代理、无缺日顺延。周期末无下一日行情的pending不强平。周末停市/节假日按交易日历完整周末日，不硬编码Friday。
- 数据：W0已冻结N002与stage025已审计日库截止2026-10-23，1883数据SHA/2448原输入全核符。先同冻结2015-01-01—2026-10-23运行W1，旧W0复用。客户端今日2026-10-26白盘已完成，本机暂无合格26 bar；允许独立新增小规模只读Tq probe，并另建快照与同截止W0/W1双臂至26；若真实来源/资格缺口无法补齐，明确未覆盖26，不把23称today，不插价格或强迫出成绩。
- 最新日补源预声明：只原19的fresh当前main、上一主力、冻结末仓/待成交同约与现有8 off-main tail，最多48具体合约；Tq duration86400、每约<=64条raw作证据，实际接纳新交易日10/26，另仅允许铜cu2612缺的10/19—23周源。fresh Tq历史main response按取得时点/原SHA保存，不把旧forward日历当26真实映射。metadata真实YYYYMM/上市到期一对一；日OHLC合法、V>0、single-sided/closeOI，forming27不接纳。旧392080条和身份/数值保持原样，新键与新mapping单列；缺/零保持失败，不新搜品种或允许carry。source authority为本次预声明Tq，不虚称多源共识。
- 结果门：先通过时间因果/周bar/全部技术退出只在fresh周、无RSI/short_case2、保留long_case2、下一日同约open、会计守恒、原SHA不变；再报告期末权益/收益/DD/Sharpe/滑点/成交/闭合轮与FIFO胜率、平均赢亏/Payoff/PF、逐年及2015—2020切片、未平贡献。任何收益均不构成OOS/PIT/容量或晋级证明，保留Stage028源争议/跳周/主力原始时点局限。
- 继续门：若收益改善但回撤或早期生存明显恶化，结论mixed不晋级；若失败保留负结果，不扫stop阈值/窗口/品种/仓位来救。本轮不自动展开多起点/成本矩阵或正式晋级。

## 实施任务

- [ ] 在tools/test_stage029_week_close_exits.py先写行为测试并记录旧行为red：日内穿stop不触发、周close才触发、周内极值≠触发、holiday周末、weekly initial/ATR/lock/prev2周龄、旧合约/跨epoch/fresh残留、short2禁long2留、RSI零、每日margin保留。
- [ ] 新tools/stage029_week_close_exits.py包装现有研究类，仅覆盖必要stop方法；旧工具/数据不修改，导出逐判断诊断。
- [ ] 测试green及本线现有相关测试回归，独立代码review；锁源后新tools/run_stage029_week_close.py与独立不可覆写outputs。
- [ ] W1冻结窗回放，必要时独立最新日快照和同截止W0/W1双臂；失败attempt保留并按根因决定是否实现修复，无alpha调参。
- [ ] 回放后独立agent复核数据、逻辑、数值、bug、置信度与SHA；输出中文stage、对照表/权益回撤图/逐笔、最终交付闭包。

- 外部调研：Backtesting.py官方多周期文档与GitHub lib.py说明高周期指标应按完成周期重采样再使用，执行价是独立假设。本轮采纳因果边界，不复制其策略/参数；https://kernc.github.io/backtesting.py/doc/examples/Multiple%20Time%20Frames.html ，https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py 。
- 开始反思：本轮无新增拟合/阈值搜索，结构选择有第一性原因；但此前同窗多次比较，样本内适配风险仍在。继续有价值：检验频率一致性与更长持有的收益/风险交换。不是重要突破版本，NO_PROMOTION。
