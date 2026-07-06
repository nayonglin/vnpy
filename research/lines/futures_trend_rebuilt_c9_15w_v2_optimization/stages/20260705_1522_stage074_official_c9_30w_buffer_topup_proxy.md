# Stage074 official C9 30w buffer top-up proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T15:22:46
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新目标下的正式 C9 30w 缓冲资金治理代理
- 是否重要突破：候选突破；代理通过新目标，但尚非真实引擎
- 是否触发A/B：是；候选可能接入正式资金治理，当前为 A/C 前置代理

## 外部调研与判断

- CPPI/TIPP、capital correction 和趋势跟随风险资料共同提示：资金缓冲可以降低账户体验压力，但降风险规则容易牺牲趋势右尾和拉长水下。
- 本阶段改用用户新目标：收益率保留 `50%`，同时减少水下时间和最大回撤。
- 我的判断：不要继续扫回撤阈值；先测试固定资金结构 `30w=15w交易袖+15w储备`，再决定是否真实引擎。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage074_official_c9_30w_buffer_topup_proxy.py`
- 修改脚本：无正式入口修改
- 删除脚本：无
- 新增参数：`daily_topup_to_15w`、`monthend_topup_to_15w`、`cppi_floor_150k/200k/225k` 代理形状；新通过门槛 `min_return_retention_ratio>=0.5`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage053 正式 C9 曲线，逐半年起点 `2018-01` 到 `2026-01`，统一终点 `2026-06-30`；重点样本 `2020-01` 到 `2026-01`。
- 账户规模：正式对照 `150,000`；缓冲候选 `300,000=150,000 交易袖 + 150,000 储备`。
- 成本口径：沿用正式 C9 曲线成本；代理不新增交易成本。
- 样本过滤：无。
- 策略/归因口径：曲线级代理；补款为内部资金搬运，分母固定 30w。

## 结果

| sample           | version                   | variant_label             |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days | passes_new_goal_vs_official   |
|:-----------------|:--------------------------|:--------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|:------------------------------|
| starts_2020_2026 | official_c9_15w_reference | Official C9 15w reference |            13 |               13 |         1.90107  |            126.199  |          3886.19 |                     1        |                        1        |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 | False                         |
| starts_2020_2026 | idle_30w_reserve_view     | 30w idle reserve view     |            13 |               13 |         0.950533 |             63.0997 |          1943.09 |                     0.5      |                        0.5      |             -52.9113 |              -18.7861 |                      500 |                          20 |                                  387 | False                         |
| starts_2020_2026 | daily_topup_to_15w        | Daily top-up to 15w       |            13 |               13 |         1.12097  |             86.0557 |          2059.65 |                     0.5      |                        0.536329 |             -53.1727 |              -19.3562 |                      472 |                          20 |                                  291 | True                          |
| starts_2020_2026 | monthend_topup_to_15w     | Month-end top-up to 15w   |            13 |               13 |         1.09133  |             86.8277 |          1986.29 |                     0.5      |                        0.536037 |             -53.0125 |              -18.7861 |                      465 |                          20 |                                  236 | True                          |
| starts_2020_2026 | cppi_floor_150k           | CPPI floor 150k           |            13 |               13 |         0.76027  |             63.0686 |          1943.02 |                     0.399917 |                        0.49831  |             -52.915  |              -18.8122 |                      540 |                          21 |                                  430 | False                         |
| starts_2020_2026 | cppi_floor_200k           | CPPI floor 200k           |            13 |               13 |         0.659852 |             63.0526 |          1942.98 |                     0.347096 |                        0.497422 |             -52.9168 |              -18.826  |                      553 |                          21 |                                  432 | False                         |
| starts_2020_2026 | cppi_floor_225k           | CPPI floor 225k           |            13 |               13 |         0.556081 |             63.0362 |          1942.93 |                     0.29251  |                        0.496494 |             -52.9188 |              -18.078  |                      559 |                          22 |                                  435 | False                         |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage074_official_c9_30w_buffer_topup_proxy/rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy_report_stage074_official_c9_30w_buffer_topup_proxy_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage074_official_c9_30w_buffer_topup_proxy/rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy_per_start_summary_stage074_official_c9_30w_buffer_topup_proxy_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage074_official_c9_30w_buffer_topup_proxy/rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy_curves_stage074_official_c9_30w_buffer_topup_proxy_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage074_official_c9_30w_buffer_topup_proxy/rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy_retention_vs_official_stage074_official_c9_30w_buffer_topup_proxy_v1.csv`

## 结论

- 本阶段结论：`stage074_monthend_topup_proxy_passes_new_50pct_retention_goal_needs_true_engine`。
- 是否进入下一步：是，进入真实引擎 A/C 验证；但当前代理本身不能上线。
- 下一步：实现正式 C9 的月末储备补回真实引擎，复跑 2020-2026 逐半年起点，确认 AI 池、开仓、保证金和整数手真实路径。

## 过拟合反思

- 运行前判断：否。新目标来自真实资金约束，资金结构固定为 `15w+15w`，不是按某个窗口调金额。
- 运行后判断：基本否。虽然同时看了 daily/monthend/CPPI 对照，但晋级的是低频月末规则，不继续扫补款日期、比例或 CPPI floor。
- 原因：继续调具体阈值和补款频率会过拟合；真实引擎验证才是下一步。

## 继续价值反思

- 运行前判断：有。旧 80% 收益目标下很多资金治理会被错杀；新 50% 目标更符合实际缓冲资金。
- 运行后判断：有。月末补款代理同时满足收益保留、回撤和水下时间三项，值得进入真实引擎。
- 原因：它不是简单降风险，而是用已存在储备维持交易袖参与恢复段，机制上可能缩短水下。

## 合入建议

- 是否更新本线 `LINE.md`：真实引擎通过后再更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：真实引擎通过或失败后再追加。
