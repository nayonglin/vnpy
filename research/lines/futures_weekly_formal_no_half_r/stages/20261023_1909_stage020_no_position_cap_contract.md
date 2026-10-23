# Stage020 取消四持仓约束固定合同

- line_id：futures_weekly_formal_no_half_r；day；时间：2026-10-23 19:09（Asia/Shanghai）；重要突破：否；当前无M绩效。
- 用户指令“把4个的限制也去掉试试”。M从当前L（允许MA10下穿MA20空头）出发，仅max_concurrent_positions从4改为固定池容量19。每产品一个state且最多一仓，19是池内理论最大品种数，等价取消额外数量约束，不是优化出19。0会被基类max(1,...)变1，故不用0；若池扩容本合同不自动生效。
- 不改策略类/方法，仍为ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy。spec.capital.max_concurrent_positions、spec.overrides.max_concurrent_positions、最终setting/actual同义参数都19；其他全部参数逐值与L同。portfolio_env_gate明确False，不能暗中按环境缩回名额。真实planner测试4已有仓+2合格候选原拒新过、18+最后1允许、0手仍拒绝。
- L_attempt001为冻结对照，不重跑/重命名；新增M_attempt001一条金融回放。原19品种、15万、2020-01-01—2026-10-22（实际2020-01-02首日），预热2019-06-01、21真实完整周ready/41存储、周线MA5/10/20及其他指标。MA40/MACD/全部AI/0.5R/C2仍关闭。原日级止损/风险热度减仓/RSI95半仓退出/5交易日换月/不加仓不反手均不变。
- 最大数量约束移除不等于无限杠杆；风险预算、相关性降权、单品种25%保证金、总资金与券商保证金层等保留。原固定滑点/0佣金，同份真实逐合约次交易日日K开盘模型，无分钟/proxy/AI模型读取，数据冻结至10/22，不把数据更新混入此差异。
- 外部调研：vn.py官方组合回测 https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py 与组合策略文档 https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md 。判断：持仓数量门、资金/保证金门与成交会计是不同作用；保留执行和会计规则，只放开数量门，不能仅由旧23次被拒信号假算反事实利润。
- A/B判断：本轮仅既有周线研究版L的部署参数单项对照，非正式接入，不扩展正式A/B/C；复用version-ab-experiment预声明、隔离与反拟合纪律。假设：检验四仓约束是否阻挡有效机会，收益提升不是预设结论。
- 测试与实现先红后绿，新增配置/真实planner/0哨兵/其他参数漂移拒绝测试，所有旧工具与账本字节冻结。源码设计独审认为19在当前固定池内非约束，待完整M实际验收；如仍有concurrent_limit先解释/拒绝，不继续抬cap救结果。
- 接受闸：M完整1647日、所有候选effective/configured均19、concurrent_limit=0、环境动态名额门False，真实最大品种数<=19，requested/actual仅一个参数、effective仅同义双路径差；weekly_bars/readiness一致、L全部输入与输出冻结。全部原执行/质量/禁用闸保留，独立agent全面审数据/逻辑/会计/FIFO/末仓/结果/置信度/bug。
- 预声明输出：期末权益/收益/DD/Sharpe/滑点/费用/实际开平成交/实际品种、FIFO胜率平均赢亏盈亏比PF、期末未平、年度、最大持仓数、各类拒绝次数、旧23条最终路径。参数只改4→19；新增/修改/删除绩效此时均无，等M完成，不扫cap/风险倍率/过滤组合。
- 运行前是否过拟合：本次不做参数拟合或弱窗口补丁；已看同历史多版结果，存在样本内选择风险，不是新OOS。继续价值：是，数量门只有23次拒绝也可能通过持仓资金路径影响账户，固定对照可判断其实际作用；结果差也保留，不救参。
- 无正式晋级、生产修改、下载、push、订单、邮件或定时任务。多agent同线只新增各自唯一文件，不改LINE/registry与根总账，不写个人持久记忆。
