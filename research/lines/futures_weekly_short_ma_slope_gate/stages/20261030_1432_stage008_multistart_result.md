# Stage008 去掉多头过滤：23独立起点至同截止验证

- line_id=futures_weekly_short_ma_slope_gate；模式day；记录2026-10-30T14:32:20.703716+08:00；工作区/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian；是否重要突破：否，固定研究验证，不自动晋级。
- 结论：MIXED_OR_FAIL_NO_RESCUE_TUNING / NO_PROMOTION。独审PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0，无未解决失败。财务/来源通过不等于策略稳健或生产资格。
- 用户明确范围：2015—2025每年1月1日和6月1日、另2026年1月1日至2026-10-29，共23独立窗口/46臂窗；年中按仓库6月1日定义。原始A与仅空头底20%C各15万元空仓起跑，42次新引擎+4份已审精确复用。复用窗口是2015 A/C及2020 A/C，其源回放时间逐窗保留，未冒称新跑。
- 本轮不是默认固定1/2/3年周期，也不是当前正式A多周期晋级：用户指定所有起点到相同截止，原19历史研究对照。更短2026Jan观察只展示、不投票；22个>=1年窗口参与投票（January11、June11）。窗口相互重叠，是独立财务状态，不是统计独立样本或新OOS。
- 冻结金融源HEAD：6706e27c8c71207b64286267c33a546d1d9a9bce；freeze SHA：f285ede86164f43c906b498da3138bff7c479d783be96ec1a62ffc6907e6c992；最新完整交易日2026-10-29，未使用未完成10/30日线。
- 本次规则/运行入口变更冻结时间：2026-10-30T13:43:45.449786+08:00；交付中文记录时间：2026-10-30T14:32:20.703716+08:00，两者与各terminal的真实回放执行时间分别保留。

## 本次变更、参数与执行

- 删除：从本轮候选去掉Stage007多头顶部20%过滤/新高例外wrapper，直接复用Stage005/006仅空头原类；原Stage007代码和负结果不删除。多空新增均线斜率门均关闭，多头无新增价格门。
- 新增：23请求起点、独立进程队列、源绑定checkpoint、46独审收据与逐窗中文记录、23配对表/6cohort行/五图及最终交付。修改参数仅起点；原品种/风险/成本/退出/20%阈值不变。旧回测结果修改/删除：无。
- C：P=信号日close，L/H为同真实合约同physical epoch、date<=signal_date全部已有有效日线极值；P<=L+0.2(H-L)不新开空，flat range拒开、缺源失败。A此门关闭但部分旧源保留would诊断。多头、换月、退出、原MA信号和全部父级资金风控保持。
- 原19池、动态底仓、不加仓、150000初资，原滑点、手续费0、静态margin×1.65，21周ready/41storage；AI/MACD/半R/C2/RSI退出/short_case2关闭。无现金流转移，各窗口不承接其他账户权益或仓位；预热只更新指标。
- 先验收全2015复用A/C，再跑2015June A/C canary并独审，批准后才批量其余；经济负收益/DD40/deployable失败不会停止或重试，只有数据/代码/完整性失败才停止派发。所有未满批结果只算checkpoint，不是最终报告。
- 每次回放真实起止分钟、参数、结果与source hash见[stage008_windows](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/stages/stage008_windows)的46记录；运行队列/完成时间在[registry.json](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/stage008_multistart/registry.json)和各terminal。

## 全周期与成熟cohort

| 指标 | A无价格门 | C仅空头底20% |
|---|---:|---:|
| 2015首个交易日 | 2015-01-05 | 2015-01-05 |
| 期末权益 | 3,661,110.00 | 3,180,475.00 |
| 总收益 | 2,340.740000% | 2,020.316667% |
| 最大回撤 | -56.312173% | -53.107123% |
| Sharpe | 0.890090 | 0.865356 |
| 总滑点 | 255,980.00 | 221,670.00 |
| 成交笔数 | 725 | 618 |
| 完整周期胜率 | 44.382022% | 42.763158% |
| 平均盈利/平均亏损绝对额 | 46,183.86/25,890.91 | 62,816.92/29,858.87 |
| 平均盈亏比 | 1.783786 | 2.103795 |
| Profit Factor | 1.430651 | 1.590077 |

成熟窗三门：C权益严格更高、DD不更差、Sharpe不更低，权益相同不通过；CSV浮点只按已声明容差判序列化微扰，不放行实质漂移。

| cohort | 完整窗口 | 收益胜/平/负 | DD严格胜 | Sharpe严格胜 | 三门全过 | A/C负收益窗 | C生存失败窗 | C配置占用失败窗 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 年初 | 11 | 3/0/8 | 6 | 3 | 3 | 0/1 | 0 | 7 |
| 年中6月1日 | 11 | 4/0/7 | 3 | 4 | 2 | 0/1 | 0 | 7 |
| 合并 | 22 | 7/0/15 | 9 | 7 | 5 | 0/2 | 0 | 14 |

不同窗口长度不能直接平均总收益当预期收益。聚合只作配对计数、cohort分层、中位/最差DD/Sharpe和生存/占用描述；不以单一赢家覆盖失败窗口。

## 23配对完整表

以下每格A/C顺序；*仅2026年初不足1年观察、不投票。三门标记为展示事实，不会把观察窗计入成熟胜率。

| 请求起点 | 期末权益A/C | 总收益A/C | 最大回撤A/C | SharpeA/C | 三门 |
|---|---:|---:|---:|---:|---|
| 2015-01-01 | 3,661,110/3,180,475 | 2,340.74%/2,020.32% | -56.31%/-53.11% | 0.890/0.865 | 未通过 |
| 2015-06-01 | 3,992,085/3,730,325 | 2,561.39%/2,386.88% | -58.85%/-57.25% | 0.928/0.912 | 未通过 |
| 2016-01-01 | 968,940/3,730,425 | 545.96%/2,386.95% | -61.51%/-57.24% | 0.647/0.941 | 通过 |
| 2016-06-01 | 351,720/189,590 | 134.48%/26.39% | -71.57%/-76.87% | 0.417/0.259 | 未通过 |
| 2017-01-01 | 1,351,195/588,825 | 800.80%/292.55% | -66.17%/-71.41% | 0.766/0.565 | 未通过 |
| 2017-06-01 | 358,830/190,170 | 139.22%/26.78% | -66.73%/-76.34% | 0.444/0.268 | 未通过 |
| 2018-01-01 | 397,935/223,520 | 165.29%/49.01% | -66.42%/-68.10% | 0.494/0.318 | 未通过 |
| 2018-06-01 | 1,351,185/589,025 | 800.79%/292.68% | -68.27%/-68.53% | 0.842/0.618 | 未通过 |
| 2019-01-01 | 1,220,470/916,685 | 713.65%/511.12% | -59.80%/-64.94% | 0.855/0.769 | 未通过 |
| 2019-06-01 | 1,351,275/1,677,170 | 800.85%/1,018.11% | -51.28%/-49.61% | 0.907/0.981 | 通过 |
| 2020-01-01 | 1,304,010/2,435,920 | 769.34%/1,523.95% | -55.04%/-44.45% | 0.966/1.162 | 通过 |
| 2020-06-01 | 2,768,045/3,023,255 | 1,745.36%/1,915.50% | -41.93%/-45.71% | 1.264/1.288 | 未通过 |
| 2021-01-01 | 776,660/730,040 | 417.77%/386.69% | -53.59%/-54.75% | 0.906/0.856 | 未通过 |
| 2021-06-01 | 1,253,750/587,350 | 735.83%/291.57% | -38.21%/-55.42% | 1.165/0.821 | 未通过 |
| 2022-01-01 | 371,275/664,720 | 147.52%/343.15% | -50.35%/-45.51% | 0.663/0.975 | 通过 |
| 2022-06-01 | 771,905/829,635 | 414.60%/453.09% | -39.48%/-43.25% | 1.106/1.116 | 未通过 |
| 2023-01-01 | 1,049,885/619,080 | 599.92%/312.72% | -41.46%/-39.57% | 1.404/1.070 | 未通过 |
| 2023-06-01 | 719,050/833,205 | 379.37%/455.47% | -44.92%/-37.19% | 1.319/1.389 | 通过 |
| 2024-01-01 | 714,415/192,760 | 376.28%/28.51% | -40.22%/-43.79% | 1.402/0.432 | 未通过 |
| 2024-06-01 | 260,330/157,965 | 73.55%/5.31% | -48.36%/-51.11% | 0.771/0.257 | 未通过 |
| 2025-01-01 | 180,635/118,495 | 20.42%/-21.00% | -50.38%/-48.19% | 0.463/-0.123 | 未通过 |
| 2025-06-01 | 186,380/109,480 | 24.25%/-27.01% | -40.22%/-40.58% | 0.590/-0.294 | 未通过 |
| 2026-01-01* | 366,760/172,380 | 144.51%/14.92% | -31.24%/-36.16% | 2.787/0.610 | 未通过 |

## C最弱或压力最高的成熟窗口

| 指标 | 起点→同截止 | 数值 |
|---|---|---:|
| total_return_pct | 2025-06-01 | -27.013333 |
| max_dd_pct | 2016-06-01 | -76.869079 |
| sharpe | 2025-06-01 | -0.294105 |
| total_slippage | 2015-06-01 | 244,910.000000 |
| actual_margin_to_equity_max_pct | 2021-01-01 | 108.715150 |

保证金字段只代表静态交易所保证金×1.65/权益，legacy broker10为×1.1，不得称实际历史券商保证金或生产可承载。未平净盯市保留在权益，已平/未平桥和胜率/均盈亏/平均盈亏比/Profit Factor见逐窗记录及summary；不能只删某臂未平来救比较，也不能将共享资本路径差叫过滤器独立alpha。

## 五图、验收与来源

1. [01_full_2015_nav_drawdown.png](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart_reviewed/01_full_2015_nav_drawdown.png)
2. [02_january_starts_nav.png](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart_reviewed/02_january_starts_nav.png)
3. [03_june_starts_nav.png](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart_reviewed/03_june_starts_nav.png)
4. [04_start_to_cutoff_heatmaps.png](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart_reviewed/04_start_to_cutoff_heatmaps.png)
5. [05_cohort_summary_weakest.png](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart_reviewed/05_cohort_summary_weakest.png)

- 表格与decision：[summary.csv](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/summary.csv)、[paired.csv](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/paired.csv)、[cohort_summary.csv](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/cohort_summary.csv)、[weakest_windows.csv](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/weakest_windows.csv)、[decision.json](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/decision.json)；原报告[report.md](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/artifacts/stage008_multistart/report.md)。
- 独审[stage008_independent_final.json](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/stages/stage008_independent_final.json)、46独审收据[stage008_independent_receipts](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/stages/stage008_independent_receipts)；已审图收据[stage008_reviewed_visual_receipt.json](/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/stages/stage008_reviewed_visual_receipt.json)绑定最终独审SHA 8a744d0b4f99f6536eb76a7cb8d4eb14f2f26041a8082c4e4e64c6dfd942c9b4。原pending图和comparison不修改。
- 全46状态validated、23配对、46财务cache及来源/输入/输出SHA、实际start/初资/零库存、同窗参数、长门/MA关闭、C短门、逐笔/逐日/库存/成本/末值、所有曲线点已验收。根最后再次全源哈希验证，manifest最后发布作为commit标记。
- 本批新金融回放42，复用4；报告/验收自身不调用金融引擎。行情下载、CTP/订单API、生产访问为0。旧Stage001—007、LINE/registry根总账、44品种及正式物料不修改。

## 调研、反思与TODO

- 参考官方订单时序https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/ 和区间位置实现https://github.com/mementum/backtrader/blob/master/backtrader/indicators/stochastic.py 。固定同约因果范围与next-open，不引入示例默认窗口或额外平滑。
- 运行前过拟合判断：有。20%规则是在已看历史内提出，23起点相互重叠，不能伪称新样本外；固定清单不扫参数降低进一步选择。
- 运行后过拟合判断：有。即便多数窗口获胜也不消除样本内选择，不挑年份/方向/品种或邻近阈值救失败。继续价值：否，不继续沿本规则调参或谋求晋级；本轮固定验证本身有价值且已完成。若另做研究，应先固定归因合同或等待新样本外数据，不挑年份、扫阈值救结果。
- 数据与置信度限制：缓存不是完整上市首日起历史/PIT真值，原已知无交易/结构缺口与暖机不足保留；零手续费、静态规格/保证金、日K next-open与无真实盘口/容量/涨跌停执行资格。独审会计一致不等于数据绝对全准或可上线。
- TODO：冻结46窗口及原始输入/账本/收据/图与哈希，向用户报告全23表与成熟cohort结果。后续研究须另固定合同，本轮不自动加窗、调参或晋级。
