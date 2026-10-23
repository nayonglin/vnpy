# Stage008 原19品种周线三均线消融合同

- 记录时间：2026-10-23 14:46 CST；line_id=futures_weekly_formal_no_half_r；day；重要突破：否。范围明确的既有周线策略修改，按用户直接指令执行。
- 用户指定：去掉40周均线，只判断3均线，用原始19品种跑回测。解释为保留MA5/10/20周，删除所有MA40消费及20/40交叉；MACD方向/触发、RSI退出、原有资金与价格风控继续保留。半R/C2/AI仍False。
- 本次仅E/G：E=已独审E_attempt009四均线周线19池，335420/+123.6133%/DD−17.3234%/Sharpe0.731551/108笔/17品种，E010已证明批量合并逐笔等价；G=本次三均线19池。没有独立B收益模块，正式日线A只作材料身份来源，不额外扫描其他组合或周期数值。
- 同窗2020-01-01—2026-10-22，实际账户首日2020-01-02；启动时10-23尚未完成，为隔离策略变化不把新一天行情混入E/G。本金150000、风险倍率0.4、品种上限0.25、最多4持仓、换月5交易日、target_contract_only、0手续费/正式固定滑点保持。
- 正式身份现核：ai_top10_plus_fu_official_live_v1；ruleset stage037_stage034_long_short_mirror_hard_block_v1；m0008_20261008T204054+0800_2a7420a9f955；材料source_commit=2a7420a9f9550ab912b5c4a302a61acc5740b04c，release_commit=334d18f069de06df3aa7728203e942e3ecb94ce9，manifest SHA94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474。当前worktree与原checkout身份一致；不声称其它机器production资格已核。
- 实现只新增stage008工具；不改任何既有tools、原始行情或旧输入SHA，不修改正式策略/生产配置。复用stage005_data独立SQLite、mapping、metadata与原19universe；原19全窗28565非空目标产品日、501目标合约真实日线正量且OHLC合法，缺口0。

## 三均线语义与预热

1. 删除_generate_signal中的MA40计算、其当前/前值finite门、20/40交叉与四线排列；只保留5/10与10/20交叉及三线排列，MACD分支不顺带删除。
2. _is_simple_ma_trend改为5/10/20三线，按原保守公式need=20+slope_lookback+2；默认3时为25周。旧公式need45但AM仅41，原分支恒False；三线化允许该分支生效，是此次删除MA40的真实作用，单列审查，不偷改阈值。
3. _rollover_shape_continuation_snapshot三线排列，按原helper公式require20根；普通交叉信号就绪21。原on_bars换月路径可能在普通信号未inited时调用续仓helper，不新增全局21续仓门，不声称所有续仓都至少21周。MA20止损、RSI95半平和其他退出保持。
4. 历史缓存容量仍41，就绪门槛独立降为21（当前及上一根MA20）。_build_history_df与所有信号/RSI输入只见真实已观察bar，不允许前置0污染。达到41根后保留原MACD/RSI及量仓历史数值；21—40根以真实可得长度计算，不能把缓存永久缩21。
5. 30周期量价风险层需要31根，21—30根保留原insufficient_history和nonconfirmation_multiplier=1.0语义，31根起正常生效，不永久关闭。缺真实日或零日量的周拒绝；终点未完成周不用；同周交叉不重复。
6. ma_extra_long=40字段如为基类兼容仍存在，只能作未使用遗留字段，G决策路径不得读取或计算MA40；不能简单设为20造成20>20恒False。

## 数据和执行接受门

- 使用真实已完成canonical首分钟，原19时段网格不变；缺锚先停，补真实序列/证明后整窗新目录重跑。data-only规划必须用G真实类、原19和观察门21重扫；不构造账户/订单或模拟资金，不沿用旧AM41的242条候选当G。
- 冻结成交时间与价格定义，不改09:01、不用日线open替代，不按坏成交删除品种。此前F016零量平仓已确证，不能再把OHLC有价当可执行。
- 全窗账本完成后确定性逐fill检查精确canonical分钟唯一、finite正成交量、price对应raw；任一实际零量/非法量则最终状态REJECT_EXECUTION_ZERO_VOLUME，只保存明确标注的条件诊断，不能认定有效绩效。该门为结果接受层，不偷偷跳过信号或改写资金路径；严格接受必须另由独立agent复验。持仓/成交日真实日线正量和会计硬闸同时保留。
- 冻结所有已消费输入SHA、实际DB绑定和有效参数；所有0.5R/C2/AI事件与AI加载应为0。缓存新增不得改旧key值，冲突拒绝；原始bar/parent proof/完成边界逐层验证。

## 预声明评价与停止规则

- 完整期末权益、收益、回撤、Sharpe、滑点、成交/闭合匹配胜率、平均赢/亏、盈亏比、PF、实际品种数、期末未平仓；年度（2026YTD）、就绪/候选/拒绝原因、曝光和E/G差。费用0、非PIT/OOS、盘口容量未证继续披露。
- 优先执行/会计/因果硬闸；失败不救成绩。若G收益或风险路径不优，保留负结果并停止，不扫MA数值、产品黑名单或另加条件。单窗即使改善也不晋级；独立起点、成本压力或新OOS需另冻合同。
- 开始过拟合判断：否，本次是用户预设删除一层长均线，不用已知赢家或小数参数调优；但已反复使用同窗，不能称新样本外。
- 开始继续价值判断：是，直接检验单合约41周可用历史/四线排列对覆盖与信号的结构限制；观察门21与历史容量41分开，避免顺带破坏其他风险逻辑。
- 网上/GitHub调研：VeighNa ArrayManager https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py 和官方组合文档 https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md ，Backtesting.py完整高周期例 https://kernc.github.io/backtesting.py/doc/examples/Multiple%20Time%20Frames.html 。判断：completed周期因果对齐与可用历史必须分开；借鉴容器机制，拒绝零填充、未完周或把市场扩大当信号自动增加。
- TODO：最小实现/真实边界测试→G data-only候选扫描/缺分钟预取→严格整窗→独立agent全审→中文结果/图表/状态更新。本合同不训练AI，不启动实盘或定时任务，不推远端。
