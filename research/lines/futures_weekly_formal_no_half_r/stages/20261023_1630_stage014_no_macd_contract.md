# Stage014 周线三均线关闭MACD固定消融合同

- line_id：futures_weekly_formal_no_half_r；day；时间：2026-10-23 16:30（Asia/Shanghai）；重要突破：否。当前无K绩效。
- 用户要求“关闭macd跑一下回测看看”。K从H（三MA5/10/20）仅去掉MACD消费：普通入场hist方向门/finite依赖、MACD金死叉case3、shape换月MACD门、非shape继承重开MACD门。MACD-only信号删除，不以无交叉排列常驻信号替换。模型计算器Forbidden，任何漏读直接拒绝，不用0/NaN伪造方向门。
- H为已冻结H_attempt001控制，K为新增no_macd真实策略类，不重跑/重命名H。原19、150000、2020-01-01—2026-10-22（实际首日01-02）、2019-06-01预热、21完成周ready/41存储、所有非MACD指标周频、日线风控/RSI95半仓退出/5交易日换月/资金和风险数值不改。RSI入场filter原False保持。MA40、半R/C2/全部5个AI选品开关继续关闭，分钟/proxy/AI模型零读取，真实逐合约次日日Kopen主模型不改，普通周交叉在次周open成交。
- 外部调研：GitHub官方Backtesting.py Quick Start的SMA交叉与Backtrader官方MACD Settings将MACD触发独立定义。https://github.com/kernc/backtesting.py/blob/master/doc/examples/Quick%20Start%20User%20Guide.py ；https://www.backtrader.com/blog/posts/2016-07-30-macd-settings/macd-settings/ 。判断：MACD方向过滤和MACD触发是两个作用，完整关闭二者才符合用户要求；不照搬示例的品种/周期或优化参数，没有可靠理由预认必然改善。
- 用新增隔离工具/测试/输出K_attemptNNN；旧所有tools和结果字节不改。接受闸：真实NoMacd类、MACD计算尝试0、候选case3为0、换月诊断hist非空0；H/K实际settings/effective/cost相同，周bar/覆盖相同。MACD退出依赖源码扫描未见其他启用项。
- 测试先红后绿：反向MACD下MA交叉仍生效、MACD-only无信号、周fresh/21ready41存储/RSI和继承风控保持、两种换月及其他过滤不被旁路，计数Forbidden。冻结代码/合同/输入后只跑一个K，完整后独立agent审数据、执行因果、财务、结果与bug。报告区分FIFO已平与期末未平，不强平救成绩。
- 结果指标预声明：期末权益、收益、最大回撤、Sharpe、滑点/0手续费、开平成交笔数与实际品种、闭合段胜率/平均赢亏/payoff/PF、末仓、年度和风险暴露。只检验固定消融，不按结果扫参数/品种/起点。全窗收益与风险权衡，不以收益单项自动晋级。完整成本/PIT/OOS/容量与独立起点不在本单窗授权内。
- A/B适用判断：当前仅对既有周线研究候选H做用户指定K消融；不是向正式版本接入的新模块，无合理独立B腿。复用版本隔离/反拟合规则，不扩为正式A/B/C或多周期晋升实验。正式材料身份仍按m0008/Stage037对账，只核当前源身份，不声称生产资格。
- 运行前过拟合判断：否，预设一个模块删除、无看K成绩后救参；同历史已多次使用，仍非新OOS。继续价值：是，可分辨MACD整体作用；若负结果保留停止，不另扫窗口。新增/修改/删除绩效均无，待完整回测。
- 后续：先实现与冻结，完成K和独审；记录中文结果到本线，更新LINE/README/registry；非重要突破不写根总账，不改个人持久记忆，不push/实盘/邮件/定时任务。
