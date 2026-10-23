# Stage018 周线三均线放开MA10下穿MA20空头入口固定合同

- line_id：futures_weekly_formal_no_half_r；day；时间：2026-10-23 18:50（Asia/Shanghai）；重要突破：否。当前无L绩效。
- 用户指令：“空头限制打开吧10下穿20也交易，注意依然去掉40”。L继承当前K无MACD三均线研究类，只覆盖 `_can_open_short_signal`：从只允许short_case1a扩大到short_case1a和short_case2。short_case2仍要求MA10下穿MA20且MA5<MA10<MA20；不把排列常驻当新信号。其他MA5/影线/ATR/资金/相关性/四持仓限制不变。不自动加仓或反手。换月规则继承不变。
- MA40保持从入场、趋势豁免、shape及非shape换月判断移除；兼容参数40不是交易条件，41存储不变、21个真实完整周ready。合成Poison测试覆盖各判断路径，MACD计算继续Forbidden。
- K_attempt001冻结对照；L_attempt001新金融回放，不重跑/重命名K。原19品种、150000、2020-01-01—2026-10-22（实际2020-01-02首日）、2019-06-01预热、周指标和原日线风控、RSI95半仓退出、5交易日换月、原滑点、0佣金。半R/C2/全部5个AI选品继续关闭，分钟/proxy/AI模型0读取，真实逐合约次日日K开盘成交。冻结同份截至10/22数据，避免数据更新混淆唯一入口差异，不宣称覆盖10/23。
- 单一假设：取消原本不对称的短侧交叉类型限制，能否改善账户结果与风险路径。仅允许新增入口，不强迫旧96条拒绝候选全部成交。新增入口会经由资金/四名额改变原有交易路径，不把全部权益差直接解释为该类空头独立alpha。
- 外部调研：https://github.com/kernc/backtesting.py/blob/master/doc/examples/Multiple%20Time%20Frames.py 与 https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py 。判断：沿用完整周后指标可见、下一根真实日K开盘成交，以及逐日持仓MTM核算原则；不复制示例参数，不引入分钟数据。
- 测试先红后绿：真实短case2从旧gate拒绝到新gate允许、case1a保留、未知/long/case3不扩放、零手数和short关闭仍拒绝、fresh及其他过滤保留、MA40 Poison、继承风险退出不变。独立设计审查认为最小覆盖可行。
- 本次只是周线研究线的用户指定单入口对照，不向正式版本接入，沿用version-ab-experiment隔离/反拟合纪律，不扩为正式A/B/C或多周期晋升。实际settings/effective/cost须与K完全同，唯一差别为该方法；weekly_bars/readiness一致，旧K及其532输入SHA不变。
- 接受闸：真实L类；新增短case2可通过gate且short_signal_rejected=0；全部其他禁用/执行/数据完整性闸仍通过；逐笔开盘/次bar时钟、MTM、FIFO、末仓及指标独立复核，无未解决影响结果的缺陷。即使没有新增成交也保留结果，不放宽其他限制救参。
- 预声明输出：期末权益/收益/DD/Sharpe/滑点/0佣金/开平成交数、胜率/平均赢亏/payoff/PF、期末未平、年度、实际品种和短case2候选/开仓/拒绝原因。研究限制：零佣金、无分钟价差深度容量资格、同历史非PIT/OOS、无独立起点，不作晋级证明。
- 开始反思：没有扫描参数或按某个亏损窗口补丁，结构性多空对称有检验价值；历史已反复使用，存在样本内选择风险，不声称新OOS。新增/修改/删除绩效当前均无，等待固定L及独立审查。
- 只新增本线工具/合同/输出/阶段记录；旧工具和结果字节冻结。无push、实盘、生产配置、邮件、定时任务或个人记忆更新。
