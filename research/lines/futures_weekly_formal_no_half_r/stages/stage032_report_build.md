# Stage032 会计报告实施子任务

- 时间：2026-10-28 16:37（Asia/Shanghai，分钟级）。研究线：`futures_weekly_formal_no_half_r`。
- 状态：新增报告工具与失败回归完成；未跑真实A/C策略、未下载、未提交、未修改旧物料；尚待真实账本与独立审查。不是重要突破策略版本。`NO_PROMOTION`。
- 实施Skill：按冻结Stage032计划使用 executing-plans 与 test-driven-development；本子任务不派生agent。

## 变更与约定

仅新增 `tools/stage032_build_artifacts.py`、`tools/test_stage032_report_builder.py` 和本记录的 `.md/.json`。公开 `build_artifacts(baseline_dir,candidate_dir,out_dir,figure)`；CLI为 `--baseline --candidate --out --figure`。

复用Stage029的纯 `ordered_fills/inventory_accounting/pnl_stats/curve_metrics/position_aggregates/annual_rows/product_rows`，不调用其写死2015年/RSI开启旧基准的load_ledger。A/C按用户修订2020-01-01至可核验完成日；报告要求真实首交易日2020-01-02，end等于最后daily日。两臂所有实际参数/成本/完整effective、日历与四数据digest一致；只有独立addon配置enabled为False/True。任何未完成terminal、缺失或失败acceptance、源文件改变、输出已存在或与输入重叠均拒绝。

逐笔输出普通总仓FIFO、真实native flat-to-flat完整周期与末未平周期，并按每个addon_id的真实成交归属另配对。每个fill的分片volume、合约、方向、开平与price必须守恒；addon真实开1手，同约/同周逻辑round、entry_price/stop_price固定；计次按真实开仓，同一round最多两次。base资金路径差与直接addon净利润之和精确等于A/C总权益差。每个金融positions行从真实fills、start_pos、pre_close、close重算成本、净仓与日MTM；缺持仓行、漏交易日或伪造末标记拒绝。

报告包括summary.json/csv、annual/products/annual_products、全部交易FIFO/完整周期/末仓CSV、owner独立账本、第一次/第二次加仓贡献、退出原因/决策接受拒绝/事件次数、持仓日历及交易日时长、A/C同轴权益回撤图、源/输出SHA256与delivery_manifest。胜率、平均盈利/平均亏损/payoff与总赢总亏Profit Factor分别命名。保证金风险只标记配置静态交易所保证金×1.65，legacy broker10×1.1单独注明，不冒充历史实际券商保证金。

## RED → GREEN证据

1. 先新增真实现金流fixture测试，缺实现后显式NotImplementedError，6 tests/15子场景失败。
2. 最小真实fill会计：总FIFO已平−40、完整native周期−40、末未平190，总净150。C独立addon190、base−40；成本合计50。
3. owner与总仓FIFO的区别：总仓FIFO已平180，但addon实际已平80、base末未平240；总净320。改固定stop被拒绝。
4. 空CSV原先EmptyDataError，实际adapter英语枚举/数字round_id原先schema拒绝、addon_analysis缺失均写失败回归后修复。只按语义统一枚举，不放松真实成交核对。
5. 最后新10测试+旧8个纯会计测试，**18 passed，1.763s**；命令和源码哈希见JSON。图表用合成fixture渲染并目视检查，标题、日期、同轴及NO_PROMOTION标识正常。

## 参数与回测结果

- 新增策略参数：无，本工具仅消费已冻结addon配置。
- 修改/删除原策略参数：无。
- 新增/修改/删除真实回测结果：均无。合成单元测试权益和PnL不代表策略成绩。
- 真实期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数及胜率：待A/C完成且独立审查后填报。

## 调研判断与边界

复用冻结设计列出的vn.py组合引擎原理及源码、Backtrader下一bar订单执行和完成周期对齐原则；本子任务没有再次发明或更换撮合框架。判断：总仓FIFO无法证明“平掉的就是addon那一手”，必须保留真实owner独立账本并以全账户净PnL守恒约束。新的报告不能证明新信号具有预测力、历史mapping完全PIT、交易成本真实充分或生产具备资格。

- 开始过拟合判断：本工具不寻优；源策略仍在既有历史样本内提出，有过拟合风险。
- 开始继续价值：有，避免归属与末仓统计混淆，并将资本路径影响分离。
- 结束过拟合判断：本工具没有加入信号阈值或救参，不增加策略拟合；不能消除原研究样本风险。
- 结束继续价值：有，已可对一次冻结A/C的accepted真实账本进行可复算报告。工具和单测通过不等于策略通过。

## TODO

- root运行同源A/C并在每次回放后安排全新独立审查；本子任务不冒充独审。
- 若真实schema与测试不同，先复现失败后修正数据接口；不得修改策略参数改善成绩。
- 最后真实A/C报告、源数据审查、加仓时序/归属逻辑与历史边界审查仍由root完整交付。

## 2026-10-28 17:00 真实attempt001只读拒绝诊断

root运行的A/C金融进程exit0后，报告attempt001正确拒绝C，未生成`artifacts/stage032_comparison`。本人未重跑策略、未改报告源码、未改真实CSV。原失败日志保留。结论是**真实owner allocation错误，不是会计报告分组/排序错误**：

|真实成交|原约|日期|平仓前base库存|错误全归base平量|仍悬留addon|allocation CSV行|
|---|---|---|---:|---:|---|---|
|BACKTESTING.315|FG401.CZCE|2023-12-11|10|11|86:1、1手|354/358/359|
|BACKTESTING.424|SM505.CZCE|2025-02-13|26|27|111:1、1手|477/478/479/480|
|BACKTESTING.489|cu2509.SHFE|2025-09-03|2|3|124:1、1手|540/548/550|

逐笔按execution_clock排序扫描全表得到以上3处base overclose，均标`forced_margin_deleverage`。FG先有base开10与addon开1，后真实平11却全base，净仓虽为零但owner变base−1/addon+1。SM在423平1时已经分错：前一日addon有fixed-stop close_signal，但423平1归base，故真正归属错误早于424的库存溢出检测；不能仅补最后1手。cu加仓先有rollover close_signal，最后全仓平3仍全base。三组均未产生对应addon close_fill。

待平owner队列被后续强平路径覆盖是待adapter作者验证的根因假说；确定事实为源CSV已错，报告正确fail-closed。root与新的独立结果reviewer均已收到具体证据。应保留C attempt001为失败金融证据，修adapter回归后新attempt重跑；禁止修改历史归属或宽松报告来救结果。源数据和失败日志SHA256见同名JSON新增diagnostic字段。逻辑cohort来自父计划、并非真实底仓交易计数；主胜率仍由真实fill-derived native flat-to-flat定义，加仓数只认真实addon_id open allocation，pending另计。
