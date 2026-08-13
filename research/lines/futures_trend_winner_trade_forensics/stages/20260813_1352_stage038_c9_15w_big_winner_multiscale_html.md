# Stage038 C9/15万历史大赢家周/日/15分钟多周期 HTML 图集

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：只读历史重放与可视化
- 记录时间：`2026-08-13 13:44-14:21 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前工作分支
- 阶段性质：历史大赢家逐笔视觉复盘工具
- 是否重要突破：否；不改变策略，只把当前正式口径的右尾交易变成可交互多周期图集
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Plotly 官方 Candlestick 与 Subplots 文档；TqSdk 官方 K 线对象/TqBacktest 历史回放接口。
- 我的判断：vn.py 现有 `show_chart()` 主要服务资金曲线、回撤、日盈亏和盈亏分布，不适合逐笔多周期交易复盘。复用当前正式成交账本、日线库和 TqBacktest 15分钟K，再用 Plotly 单一交易日坐标组织六层图，是更直接且低耦合的实现。

## 本次变更

- 新增脚本：`research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`--end`（回放终点）、`--reuse-market`（只复用本阶段已经物化的15分钟数据，不改变账本）。
- 修改参数：无策略参数修改。
- 删除参数：无。
- 图表结构：周K、周成交量、日K、日成交量、15分钟K、15分钟成交量，共用按交易日映射的横轴；蓝线为开仓日，紫线为平仓日，淡黄色为持仓区间。
- 窗口：日线至少覆盖开仓前30个交易日到平仓后30个交易日，并向两侧扩展到完整周；15分钟覆盖开仓前5个交易日到平仓后5个交易日，中间包含全部持仓交易日。

## 回测/归因参数

- 请求区间：`2018-01-01` 至 `2026-08-12`；策略账本实际末日 `2026-07-22`，summary 已分开记录。
- 账户规模：`150,000`。
- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 成本口径：正式 `1.0x` commission/slippage。
- 样本过滤：先把全部 `418` 个 FIFO closed lots 按 `open_trade_id` 聚合为 `402` 个开仓 episode，再在 episode 层按正 R 的80%分位定义大赢家，阈值 `5.834627R`；另补入 R 缺失但 episode 盈利额前20%的交易，避免漏掉 FG601 的 `950,000` 元赢家。
- 策略/归因口径：当前 C9/15万只读历史重放；不改信号、风险、止损、重试、保证金或退出逻辑。

## 结果

- 期末权益：`12,652,824.10`
- 总收益：`8,335.2161%`
- 最大回撤：`-56.2069%`
- Sharpe：`1.3410`
- 总滑点：`1,611,870`
- 总交易次数：`821`
- 胜率：closed-lot `173/418 = 41.3876%`；非零日胜率 `52.4577%`
- closed lots：`418`
- winner lots：`173`
- big winner episodes：`30`，覆盖 `35` 个 closed lots。
- 大赢家阈值：`6.249011R`
- 大赢家合约数：以 summary/manifest 为准，全部逐笔生成。
- 15分钟K：`21,933` 根。
- 15分钟窗口缺失交易日：`0`
- Plotly JS 内嵌，可离线打开。
- 精确合约缺少前/后窗口时，仅对缺失日期显式切换到当日主力合约上下文，共 `146` 日；页面以灰虚线和来源字段标明，不伪装为同一合约。15分钟窗口内日K由同一批15分钟K聚合。

## 输出文件

- HTML：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/index.html`
- summary：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/summary.json`
- closed lots：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/closed_lots.csv`
- big winners：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/big_winners.csv`
- 15分钟K：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/winner_bars_15m.csv`
- quality/manifest：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/chart_manifest.csv`
- strategy daily：`research/lines/futures_trend_winner_trade_forensics/outputs/stage038_c9_15w_big_winner_multiscale_html/strategy_daily.csv`

## 结论

- 本阶段结论：已完成用户要求的当前 C9/15万历史大赢家可交互 HTML；30个完整开仓 episode 都有完整周/日/15分钟价格与成交量，三周期按交易日对齐。
- 是否进入下一步：图集可立即人工复盘；不自动进入策略修改。
- 下一步：人工观察后若形成假设，必须补 matched loser/普通赢家对照和跨年份盲测，不能直接从32张赢家图反推交易规则。

## 过拟合反思

- 运行前判断：否；本阶段只按既有正R前20%定义生成图，不调阈值、不选品种、不改规则。
- 运行后判断：绘图本身不构成过拟合，但 winner-only 浏览有显著幸存者偏差。
- 原因：图可以积累路径直觉和提出假设，却不能证明某种视觉形态具有事前预测力。

## 继续价值反思

- 运行前判断：有价值；旧图册只覆盖日级 PNG 或入场日前5日15分钟，无法同时观察完整持仓和退出后结构。
- 运行后判断：仍有价值；30个大赢家 episode、21,933根15分钟K、0缺失日，已经形成可直接使用的交互复盘工具。
- 原因：它改善的是研究观察能力，不是回测指标；后续价值取决于是否用对照样本验证，而不是继续美化赢家图片。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage038 工具完成状态。
- 是否更新 `research/registry.md`：否，本线定位未变。
- 是否追加根目录 `memory.md/back_log.md`：否，不是策略突破或正式候选。
