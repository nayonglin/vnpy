# Stage034 逐日entry episode参考driver结果

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:29 CST记录；day。不是收益突破。
- 新增`tools/stage034_episode_driver.py`、`stage034_run_episode_probe.py`与driver11项测试；连接Stage031/024/026/当前C2。研究halfR/retry关闭、C2保留，正式代码未改。
- 初次完整合成run21:23:42，校验修复后的run21:25:55；两run inputs/outputs字节SHA相同，首跑及旧代码绑定保留。

11合成case/12显式分支/211逐日trace，9known/3trajectory_unknown。预声明pending→nextopen→新entry C2→close decision、RSI整数部分退出、delay5 roll、新entry C2风险与旧episode货币R分离、部分roll失败保留旧腿、成本缺失、59/60/61成熟边界均实际走通。root全线105测试通过。

root初测8项通过；独审发现configured C2 guard与effectivefill tick被混用，新增回归先红后绿，缺configured guard记unknown；root发现unknown snapshot仍暴露假定继续持仓净R0，新增回归先红后绿，改为只保留recorded legs且whole-path值与actual qty未知。上述在首probe前完成。后独审发现NaT时间与bool数值可接受，新增第11项回归先红后绿，修复后另存新probe，未重定R或调参，合法结果不变。

本driver输入全共同source日历与signal、observed_through，horizon固定由signal后source day计算。mtm与exit_next_open分别D60估值与D60排平/D61fill；未成交请求不作平仓，缺anchor、分钟或路径不填0。费用/mark未知与trajectory未知分开；未知持仓数量、金额不暴露伪确定点值。

roll局部shape/stop为冻结AST、目标变化delay首次0/后5日due；root校验目标41窗全局calendar连续。旧close后newopen顺序仅支持非逆序，tie close-first为额外研究限制，不能称完整正式queue等价。完整旧账户volume sizing、heat/forced规则排除；新qty须外部给定。普通退出后fresh重入尚未实现，此entryepisode不替代完整连续月度源。

新增研究参数：horizon1..60、terminal_mode mtm/exit_next_open、max_paths256及显式anchor/guard/path/roll_qty/经济字段；未新增修改删除正式模型或alpha参数，无金融账户回测结果删除。权益、收益率、最大回撤、Sharpe、总滑点、真实交易次数、胜率N/A；模型fit/正式池/发布/真实订单0。真实两个条件episode另Stage036，不把合成金额当绩效。

调研判断：实际日终与次session时钟、roll两腿及C2都来自冻结/当前绑定方法和本轮官方vn.py/Backtrader执行资料检查；通用文档不替本地来源资格。独审结果另Stage035，root最终接纳另Stage037。

开始/结束新增真实收益选参过拟合否，固定机制例子不作收益选择；继续价值是，逐日组件已联通并进入真实case，但月度训练源仍需fresh重入和全候选聚合，不以局部完成宣称模型提升。
