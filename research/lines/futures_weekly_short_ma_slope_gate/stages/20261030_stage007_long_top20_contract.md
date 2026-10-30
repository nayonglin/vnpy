# Stage007 多头历史顶部20%拦截，严格突破历史新高豁免

- line_id=futures_weekly_short_ma_slope_gate；day；2026-10-30，实际分钟级起止见terminal；非重要突破，结果待验证。用户指定“多头加顶部20%，超过历史最高价依然可以开仓”。
- 新C在Stage006 C（仅空头底20%）上加多头门。多头历史只用同合约同physical epoch、date<信号日的已有有效真实日线，不含信号当天。P=信号日close，L/H=此前全缓存low最低/high最高。
- 顶部区间[L+0.8*(H-L),H]，P在其中（含两端）拒绝long_case1a/long_case2新开；P>H严格突破豁免这条门，P==H仍拒开，P<顶部下界允许。P<L也不属于顶部，不额外拦截。
- H==L：P==H拒开；P>H创新高豁免；P<H允许；缺prior或非有限行情失败。创新高豁免只解除本新增门，不能绕过原信号、资金、手数、止损和风险门，不保证必有成交。
- 空头继续原Stage005已冻结包含signalday的底20%门，源码原字节复用，不改成strict prior。两侧口径有意区别：本轮只新增多头规则，不能暗改空头。多空新增MA斜率门仍关闭。
- 多头flat_entry/env_probe/reverse_entry生效，换月续仓/已有仓/平仓/风险退出不加门。先完整父级sizing，再对正手数拷贝归零，final open guard防旁路；短门父级仍运行。
- 原19品种、15万、2015独立空仓起点、动态底仓、不加仓，2015-01-05—2026-10-29（2871日）；当前10/30午后未收盘，无新完整日线。原滑点、手续费0、静态margin×1.65、21周ready/41storage及原信号/退出、AI/MACD/半R/C2/RSI退出/short_case2关闭均保持。
- 仅新C跑完整回放stage007_C_attempt001。控制复用已独审Stage006 C001(仅空头)及A001(原始无门)，同初资/数据/参数/执行/日期；不重复未变引擎。与short_only比较权益更高、DD不更差、Sharpe不更低三项同时过才算本窗支持；亦报告原始版差异。任何失败固定保留，不扫参、不救阈值/合约/年份。
- 新代码、入口、输出、阶段、报告仅stage007，旧Stage001—006、LINE/registry/总账/44品种线/正式物料/生产不改。全程NO_PROMOTION。

## 调研与判断

- 已查Backtrader维护者Donchian代码https://gist.github.com/mementum/1adc2aea1102f222bfa8b93ef892aae8 ：排除当前bar后，当前价才可能突破此前通道；若包含当前high则当前close无法严格超过通道最高。本次采用同样的因果边界理念，但不是其默认20bar窗口；本次是此前同约全部已有有效日线。
- 执行仍按官方next-open模型https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/ ：信号close判门，次日真实open执行，不在次日另用未来日线重判。
- 过拟合风险：有，是同一已见历史内继续修改结构。固定20%与strict breakout豁免，无附近参数搜索，不是新OOS。
- 继续价值：有，一次固定验证可区分历史高位追多与突破新高，不能预先认定改善，且顶部过滤可能错过持续趋势。
- 计划：边界/创新高/当日及未来排除/跨epoch/flat range/case1a&2/short保持/不变父级等RED→GREEN；完整新C；同源账本/年度/净值报告与独立agent全面审查。最终JSON锁定SHA后才出已审图收据及中文结果。
