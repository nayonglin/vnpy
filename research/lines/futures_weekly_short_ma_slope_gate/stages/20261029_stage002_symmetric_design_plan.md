# Stage002 多头镜像MA斜率门设计与实施计划

- line_id=futures_weekly_short_ma_slope_gate；day；2026-10-29（具体启动/结束时间见terminal与结果记录）。非重要突破；用户明确要求在上一版增加多头镜像过滤，按已指定范围实施，不新增参数选择。
- 基准A：Stage001 C「只过滤空头」已独审有效账本 outputs/stage001_C_attempt003，期末1690065。对照O：Stage001 A原始无过滤账本。复用两份同源/同截止/同起点已验收结果，避免重跑未变控制。
- C：保留Stage001空头门，追加多头新信号long_case1a/long_case2：MA5[t]<MA5[t-1] OR MA10[t]<MA10[t-1]则拒开多；严格小于0，走平允许。使用同约已接受完成周，无新平滑或回归窗口。
- 空头门仍为任一MA正斜率拒开；long_case2必须覆盖。换月、平仓、风险减仓、已有仓位和全部父级资金/尺寸规则保持；多头final open guard防旁路。
- 19池、15万、空仓、动态底仓、不加仓，实际2020-01-02—2026-10-29，沿用本线同一已准入DATA；原滑点、手续费0、静态margin×1.65不变。AI/MACD/半R/C2/RSI退出/short_case2/5%减半仍关闭。
- 新代码/入口/输出独立stage002文件，Stage001源码、账本、报告、manifest及LINE原字节保持，44池不涉及。源HEAD865c9a8c2。

## 调研与判断

Backtrader官方https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/及此前TA-Lib GitHub斜率实现https://github.com/TA-Lib/ta-lib/blob/main/src/ta_func/ta_LINEARREG_SLOPE.c：保持完成bar→下一bar时序；当前方向用相邻周MA差，不引入回归窗口。镜像提高规则对称性，并不保证改善交易；均线在转折时滞后，可能屏蔽早期趋势。

## 预声明门槛与实施

- C相比只过滤空头基准A：期末权益更高、DD不更差、Sharpe不更低三项同时通过，才算本窗支持；任何失败不扫阈值/窗口/年份/品种救参。全程NO_PROMOTION。
- [ ] 先RED→GREEN验证long_case1a和long_case2、任一向下OR、0斜率允许、空头保持、换月不变、关闭镜像与旧类等价、缺周/非有限值失败、final guard。
- [ ] 复用Stage001冻结代码与数据，派生新类/runner，绑定所有stage002源和数据并校验旧交付哈希。
- [ ] 仅对新C做完整引擎回放；与两个已冻结控制做同源比较，逐日/逐笔会计和年度切片。
- [ ] 回测结束后独立agent全面审查数据/逻辑/会计/实际多空开仓门/bug/置信度；保存中文stage、图表和manifest，本地提交。

运行前过拟合：有历史内选择风险，本轮没有额外阈值扫描。继续价值：有，一次固定镜像结构反证；不自动开展其他窗口和优化。
