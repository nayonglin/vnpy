# Stage005 全合约历史区间底部20%禁止新开空：固定合同

- line_id=futures_weekly_short_ma_slope_gate；2026-10-30 12:28 Asia/Shanghai，实际回放时间以terminal为准；day；非重要突破；根沿用版本实验规范。
- 用户明确：关闭刚新增的所有多头和空头MA斜率拦截；空头位于历史区间底部20%不新开。已确认范围为“该合约截至信号时的全部历史”。新Stage005版本保留旧版本不改。
- 精确定义：L=min(low)，H=max(high)，覆盖本地冻结DATA中同一个真实合约物理epoch、日期<=信号日的全部有效真实日线（包括信号日），不局限accepted完成周；当前价P为已完成信号日收盘价。若P<=L+0.20*(H-L)则拒绝新开空（含等号）。H=L时无区间、拒开并记录，禁止除零；缺数据/非有限值失败。
- 不跨合约、不拼主连、不混同代码不同年代物理epoch，不用未来价格/次日开盘预判，不下载数据。这里“全部历史”仅本地已有有效真实日线，不能将其叫作已证完整上市首日以来行情；早期数据缺失的影响保留。
- 仅short_case1a新flat_entry/env_probe/reverse_entry；多头没有新增过滤，换月续仓/平仓/风险退出/原MA信号/其余风控均保持。sizing先完整调用父级，再对原选量>0者归零，不预占保证金/写target。final open guard防旁路。
- 原19品种、15万、动态底仓、不加仓，2020独立空仓起点；实际2020-01-02—2026-10-29（当前10/30中午当日日线未完成），同冻结DATA和原始无MA斜率门Stage001 A003对照。原滑点、手续费0、静态margin×1.65、41存储/21ready、完成周技术退出/同约下一日真实开盘保持。AI/MACD/半R/C2/RSI退出/short_case2仍关闭。
- 唯一新增候选C001；A=原始无斜率Stage001 A003已独审账本。阈值固定20%，不扫描10/15/25/30或窗口。权益更高、DD不更差、Sharpe不更低三项同时过才算本窗支持；全部NO_PROMOTION。
- 所有新增文件stage005；Stage001/002/003/004和LINE/registry/总账/44品种/正式物料与生产均不改。现有离线HTML副本不涉及策略。

## 调研与反思

已查Backtrader官方源码https://github.com/mementum/backtrader/blob/master/backtrader/indicators/stochastic.py 及最高/最低操作https://github.com/mementum/backtrader/blob/master/backtrader/indicators/basicops.py ：(close-lowestlow)/(highesthigh-lowestlow)可表示区间位置，本次取全同约已知历史且无K/D平滑，不套用其默认14窗。低位追空可能承受反弹，也可能捕获新低趋势；区间低位并不证明价格便宜，不预设效果。

- 过拟合风险：有，仍在已看过结果的历史内改规则。本次固定用户指定结构和20%，无参数搜索，不是新OOS。
- 继续价值：有，一次固定反证能检验避免低位追空是否改善原版；不因失败再救阈值/合约/年份。
- 计划：新类与前缀因果/同epoch/边界/多头换月不变测试先RED→GREEN；完整引擎一次；新报告复用纯会计不伪造身份；独立agent全面复核；中文结果、净值图和冻结交付哈希。技术产物不等于策略晋级。
