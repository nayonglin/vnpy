# Stage076 C9 plus Stage372 reserve sleeve proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T15:51:45
- 阶段性质：30w 缓冲资金独立低相关 sleeve curve-level proxy
- 是否重要突破：否，代理未满足新目标

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage076_c9_plus_stage372_reserve_sleeve_proxy.py`
- 新增参数：`SLEEVE_CAPITALS=(0.0, 30000.0, 60000.0, 90000.0, 120000.0, 150000.0)`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

| version                            | variant_label                        |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |
|:-----------------------------------|:-------------------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|
| official_c9_15w_reference          | Official C9 15w reference            |            11 |               11 |         32.3783  |            179.443  |          3886.19 |                     1        |                        1        |             -55.3701 |              -39.982  |                      500 |                          20 |                                  387 |                                      17 |
| c9_15w_plus_stage372_sleeve_000000 | C9 15w + Stage372 reserve sleeve 0w  |            11 |               11 |         16.1891  |             89.7217 |          1943.09 |                     0.5      |                        0.5      |             -52.9113 |              -21.7104 |                      500 |                          20 |                                  387 |                                      17 |
| c9_15w_plus_stage372_sleeve_030000 | C9 15w + Stage372 reserve sleeve 3w  |            11 |               11 |         13.6576  |             99.1417 |          2083.72 |                     0.421815 |                        0.548759 |             -51.6311 |              -22.4155 |                      538 |                          29 |                                  426 |                                      25 |
| c9_15w_plus_stage372_sleeve_060000 | C9 15w + Stage372 reserve sleeve 6w  |            11 |               11 |         11.1261  |            108.562  |          2224.35 |                     0.34363  |                        0.597517 |             -50.437  |              -23.3058 |                      552 |                          44 |                                  426 |                                      24 |
| c9_15w_plus_stage372_sleeve_090000 | C9 15w + Stage372 reserve sleeve 9w  |            11 |               11 |          8.59463 |            117.982  |          2364.97 |                     0.265445 |                        0.646276 |             -49.3698 |              -24.2662 |                      554 |                          27 |                                  429 |                                      13 |
| c9_15w_plus_stage372_sleeve_120000 | C9 15w + Stage372 reserve sleeve 12w |            11 |               11 |          6.06313 |            127.402  |          2505.6  |                     0.187259 |                        0.695035 |             -48.4512 |              -25.639  |                      557 |                          23 |                                  557 |                                      12 |
| c9_15w_plus_stage372_sleeve_150000 | C9 15w + Stage372 reserve sleeve 15w |            11 |               11 |          3.53163 |            136.822  |          2646.23 |                     0.109074 |                        0.743793 |             -47.5888 |              -28.5162 |                      557 |                          16 |                                  557 |                                      12 |

## 结论

- 决策：`stage076_proxy_no_promotion_candidate`。
- 运行前过拟合反思：否。独立袖是结构分散，不按坏窗口调参。
- 运行后过拟合反思：若失败后扫 sleeve 金额小数、按月份开关 Stage372 或按坏窗口切换，就是过拟合。
- 继续价值：只有代理通过时才进入真实组合引擎；否则停止这条固定 Stage372 袖方向。
