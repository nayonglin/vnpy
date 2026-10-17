# Stage005 零账户潜在初始信号及首日分钟需求结果

- line_id：`futures_trend_triple_screen`；当前模式：day。
- 记录时间：2026-10-17 23:37 CST；实际唯一指标流枚举：23:34:00—23:34:29 CST。
- 工作区：`/Users/mac/Desktop/fian`；分支：`codex/ai-training-data-expansion`；记录时HEAD：`68dd572a9`。
- 阶段性质：数据需求生成，非金融回测、非策略优化、非生产资格认证；是否重要突破：否。
- 是否触发新A/B：否。本阶段为已冻结C0研究的数据准备，未启动新账户attempt。
- 当前独立复核状态：**pending**；已通知独立reviewer，不提前声称本阶段复核通过。

## 调研与判断

沿用Stage001的[Elder原始结构](https://6e6fa188-f273-4932-86c0-66af721f16a8.usrfiles.com/ugd/6e6fa1_60651ebd50ca4ea0bd0421f83dce9e74.pdf)、[LEAN指标实现](https://github.com/QuantConnect/Lean/blob/master/Indicators/MovingAverageConvergenceDivergence.cs)及[Backtrader多周期对齐](https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/)调研，并核对[次bar开盘成交说明](https://www.backtrader.com/blog/posts/2017-05-01-cheat-on-open/cheat-on-open/)。本阶段的实际语义以本仓库已接受C9源码为准，不实现另一份近似指标，也不把外部经典方法当作盈利证据。

我的判断：Stage004全部理论session上界混有大量持仓carry诊断，不适合作为直接下载清单。先在不读取PnL、不运行空仓账户的条件下枚举原策略可能产生的初始信号，可以把数据需求缩到有意义的机会事件；它仍不等于实际成交集合或完整账户路径覆盖。

开始过拟合判断：**否，未新增按收益选参**；原策略、AI与既有历史选择偏差仍保留。开始继续价值：**有**，先查真实机会对应缺口可以减少无效金融重跑。

## 本次变更与固定来源

- 新增：`tools/stage005_potential_signal_demand.py`及`test_stage005_potential_signal_demand.py`；本stage结果记录。
- 修改/删除正式策略、AI名单、风险、成本、资金与指标参数：均无。
- 新增金融参数：无；新增数据需求定义严格沿23:26冻结协议，不挑收益最佳事件。
- 新增、修改、删除回测结果：均无。本阶段金融attempt=0，策略初始化=0、账户engine=0、发单/撤单=0、训练=0、下载=0、源数据写入=0。

以`QmtRollPortfolioStrategy.__new__`取得只含方法的对象，原样赋予A0 `actual_strategy_settings`，不调用任何策略`__init__`、`on_bars`、账户planner或手数/保证金函数。指标入口直接复用原`_build_history_df`、`_generate_signal`和原`ArrayManager(41)`，没有重新实现EMA/RSI/信号公式。

原加载起点2019-06-01，本机首真实日线2019-06-03；交易起点2020-01-01、截止2026-10-14，实际warmup_days=90、AM=41。806个metadata真实合约按真实日线全局日期并集连续更新，不只喂当日主力，不补carry，不在2020清空AM。全局共1786个batch；每batch先更新所有真实bar的AM，再按当日主力映射查询目标真实bar和信号。目标缺真实bar或未暖机不产生flat信号。

全局engine日期与完整mapping日期用途分开：前者决定信号订单的下一撮合交易日；后者提供原session helper的交易日归属。订单保持信号日指定的真实合约，不换成生效日新主力；末日无下一批次记pending。C0周门仅派生标签：ready反向/零斜率拦截，unknown回退原始信号。

冻结依据包括协议、实际settings、DB、mapping、原策略/ArrayManager源码、周表、Stage004覆盖cache、其输入绑定和有限独立审查receipt。所有本阶段读取并记录的输入在执行前后SHA一致。原DB SHA为`273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`，周表SHA为`d8bae99069a24195975aac62fd47a1cfbdf5f024f15861a6772e424faf6c5f8e`；全部清单见输出`input_manifest.json`。

## 结果

| 口径 | 潜在初始信号事件 | 去重可生效首日session | 完整session | 缺口session | 缺失分钟 |
|---|---:|---:|---:|---:|---:|
| 原始alpha机会全部保留 | 900 | 899 | 416 | 483 | 156,831 |
| C0固定周门许可子集 | 701 | 700 | 322 | 378 | 124,772 |

原始事件中143个周状态未知，按原合同回退基线而不是隐性拒绝。末日有1个pending事件，不伪造下一交易日、成交或需求session。900→701只是周许可后的机会集变化，不是两臂实际成交数，更不是胜率或收益变化。

A0 `entry_candidates.csv`仅读取`date/product_vt_symbol/contract_vt_symbol/signal`四个身份字段，**886/886个已知初始候选全部命中，遗漏0**。没有读取候选胜负、资金、PnL或C0截断收益；该子集哨兵是必要条件，不足以独立证明所有未来路径都已覆盖。

覆盖计数直接复用Stage004冻结的逐合约/交易日session表，没有再次扫描249万分钟；每个本阶段需求key都成功join，且原session helper的expected_count逐key一致。所继承的是冻结数据的时戳覆盖计算，以及Stage004语义和8个session的有限独立抽核，不冒称整表价格/完整性已重新独立认证。7912个本机来源候选只用于缺口关联，文件路径和旧manifest声明不代表该来源已验收；本阶段未读取其payload或引入新源。

期末权益：N/A；总收益：N/A；最大回撤：N/A；Sharpe：N/A；总滑点：N/A；总交易次数：N/A；胜率：N/A。没有新的账户曲线可据此判断C0收益或回撤。

## 验证与产物

8项focused tests已先RED后GREEN：AM41边界与非主力历史、目标真实bar缺失不得carry、旧合约及下一global batch、未来追加不改既有已生效事件、周unknown回退、重复键拒绝、周五夜盘归周一与缺覆盖join拒绝、复用原方法且未策略初始化。

唯一一次真实指标流枚举29秒完成；没有因信号数量重跑、调整起点或选择参数。此前测试夹具中“下一日新主力”未纳入合成metadata的错误已在真实枚举前修正，原信号实现与正式参数未改。

- 主摘要：`outputs/stage005_potential_signal_demand/summary.json`。
- 原始/C0事件：`potential_initial_events.csv`、`c0_potential_initial_events.csv`。
- 需求/缺口：`initial_session_demand.csv`、`initial_session_gaps.csv`。
- 年度与品种：`year_coverage.csv`、`product_year_coverage.csv`。
- 本机候选路径：`gap_local_candidate_paths.csv`；仅索引，不构成数据接受证明。
- 来源与哨兵：`input_manifest.json`、`known_A0_subset_check.json`、`global_engine_calendar.csv`。
- runtime：`.py311/bin/python`，复用冻结numpy2.4.4/pandas2.3.3及仓库原ArrayManager/信号源码；具体路径与指纹在summary/manifest。

## 边界与下一步

本阶段只准确枚举固定纯信号接口的**潜在初始事件上界**，不是实际成交集合，不授权C0_attempt3。即使全部初始session补齐，也不能声称全账户路径已齐。

实际A0 settings中`enable_add_position=False`和`enable_donchian_add_position=False`，因此后续普通加仓路径在该固定配置下关闭；但换月重开仍是OPEN，也可能读取完整入场日分钟；普通CLOSE仍要求canonical首分钟anchor。下一步应先冻结不漏换月重开及可能普通退出anchor的需求闭包，再对必要本机来源逐session验收，不通过逐gap账户失败不断驱动补数。

当前本阶段独立review仍pending，后续由root登记其结论；本stage不改LINE、registry或旧工具。

结束过拟合判断：**否，未以收益或期望信号数改参数**；固定历史本身的既有选择风险继续存在。结束继续价值：**有**，准确初始机会把C0候选首日需求收敛为700个session，下一步价值在路径闭包和必要数据验收，而非重新跑账户或扫三重滤网参数。

## 独立复核补记（2026-10-17 23:54 CST）

`first_screen_independent`已完成有限独立复核，P0=0、P1=0；receipt SHA为`3e53c74994ef0e5bee58c1a2c18ae0e7475b72254ee9793fa5057f26f7733b4e`。复用原C9和研究wrapper的12个纯方法为同一函数对象、6份继承源码与A0一致；独立抽核6个正信号、2个无信号和1个暖机窗口，共329条SQL日线、6份周状态、5个session join。没有重复全指标流或金融回测。

额外确认17个跨主力切换事件仍保持信号日旧合约。两次C0失败session都不在本次“立即下一批次初始信号”集合，原失败证据未保留order offset，不能据此断言失败来自首次开仓或换月。该结果只接受本阶段初始需求语义和有限哨兵，不代表全路径已齐，也不批准C0_attempt3。原pending文字保留为记录当时状态；当前复核结论以本补记为准。
