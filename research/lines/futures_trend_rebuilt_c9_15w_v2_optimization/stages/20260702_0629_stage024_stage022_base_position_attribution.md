# Stage024 Stage022 base residual 持仓归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T06:31:33
- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只定位剩余亏损持仓路径，不生成可上线规则

## 外部调研与判断

- 参考：pyfolio drawdown period 分析、position-level performance attribution、Rob Carver/系统化期货分散与风险暴露管理思路。
- 我的判断：Stage023 已确认 Stage022 delta 整体在减亏；继续推进前必须把 base residual 拆到持仓层，避免把趋势系统正常回撤误改成单品种/单日期黑名单。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage024_stage022_base_position_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage024_stage022_base_position_attribution.py`
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入窗口：Stage023 focus windows。
- 输入持仓：Stage006 已保存 Stage013 base positions。
- 口径：窗口内 `(start_date, end_date]` 活跃持仓的 holding/trading/cost/net PnL；按起点日是否已有仓分桶。
- 校验：窗口持仓净 PnL 必须对齐 Stage023 `base_net_pnl_in_window`。

## 结果

- focus windows：`12`
- focus position net pnl：`-1132935.0000`
- focus position holding pnl：`-1129785.0000`
- focus position trading pnl：`29845.0000`
- focus position cost：`32995.0000`
- existing bucket net pnl：`-373020.0000`
- opened/traded bucket net pnl：`-759915.0000`
- top loss driver：`hc.SHFE short existing_at_window_start net=-169740.0000`
- max base net pnl abs diff：`0.00000000`
- 决策：`stage024_base_residual_opened_positions_dominate_need_pit_entry_signal`

## Source Bucket 汇总

| source_bucket                       |   affected_window_count |   holding_pnl |   trading_pnl |   commission |   slippage |   cost |   net_pnl |   trade_count |   net_loss_share_pct |
|:------------------------------------|------------------------:|--------------:|--------------:|-------------:|-----------:|-------:|----------:|--------------:|---------------------:|
| opened_or_traded_after_window_start |                      12 |       -798495 |         69745 |            0 |      31165 |  31165 |   -759915 |           701 |              67.0749 |
| existing_at_window_start            |                      12 |       -331290 |        -39900 |            0 |       1830 |   1830 |   -373020 |            36 |              32.9251 |

## Product Direction 汇总

| product   | direction   | source_bucket                       |   affected_window_count |   holding_pnl |   trading_pnl |   commission |   slippage |   cost |   net_pnl |   active_days |   contract_count |   trade_count |   worst_window_return_pct |   max_abs_end_pos |   net_loss_share_pct |
|:----------|:------------|:------------------------------------|------------------------:|--------------:|--------------:|-------------:|-----------:|-------:|----------:|--------------:|-----------------:|--------------:|--------------------------:|------------------:|---------------------:|
| hc.SHFE   | short       | existing_at_window_start            |                       9 |       -161460 |         -7590 |            0 |        690 |    690 |   -169740 |            36 |                9 |             9 |                  -40.5376 |                 9 |            14.2982   |
| sp.SHFE   | long        | opened_or_traded_after_window_start |                      12 |       -109200 |        -31200 |            0 |       3120 |   3120 |   -143520 |            36 |               12 |            24 |                  -40.5376 |                10 |            12.0896   |
| fu.SHFE   | long        | opened_or_traded_after_window_start |                      12 |        -75260 |        -51560 |            0 |       3190 |   3190 |   -130010 |           584 |               33 |           151 |                  -40.5376 |                11 |            10.9515   |
| rb.SHFE   | short       | existing_at_window_start            |                       9 |       -116160 |          3840 |            0 |        480 |    480 |   -112800 |            36 |                9 |             9 |                  -40.5376 |                 9 |             9.50183  |
| SM.CZCE   | short       | opened_or_traded_after_window_start |                      12 |       -176130 |         75810 |            0 |       2460 |   2460 |   -102780 |            72 |               24 |            48 |                  -40.5376 |                13 |             8.65778  |
| rb.SHFE   | long        | opened_or_traded_after_window_start |                      12 |        -18660 |        -68940 |            0 |       2760 |   2760 |    -90360 |           180 |               12 |            72 |                  -40.5376 |                12 |             7.61157  |
| SA.CZCE   | long        | opened_or_traded_after_window_start |                      12 |        -22100 |        -63740 |            0 |       3940 |   3940 |    -89780 |            71 |               22 |            41 |                  -40.5376 |                11 |             7.56271  |
| fu.SHFE   | short       | existing_at_window_start            |                       9 |        -47250 |          5400 |            0 |        150 |    150 |    -42000 |            18 |                9 |             9 |                  -40.5376 |                 3 |             3.53791  |
| SM.CZCE   | long        | opened_or_traded_after_window_start |                       8 |        -27660 |         -8650 |            0 |        970 |    970 |    -37280 |            86 |               13 |            24 |                  -40.4856 |                 7 |             3.14032  |
| lh.DCE    | short       | opened_or_traded_after_window_start |                       6 |        -72480 |         41760 |            0 |       1920 |   1920 |    -32640 |            48 |                6 |            24 |                  -40.5376 |                 1 |             2.74947  |
| cu.SHFE   | short       | opened_or_traded_after_window_start |                       6 |        -17400 |        -11400 |            0 |        600 |    600 |    -29400 |            12 |                6 |            12 |                  -40.5376 |                 1 |             2.47654  |
| jm.DCE    | long        | opened_or_traded_after_window_start |                       6 |        -17640 |         -9360 |            0 |       1440 |   1440 |    -28440 |            42 |               12 |            24 |                  -40.5376 |                 1 |             2.39567  |
| si.GFEX   | long        | opened_or_traded_after_window_start |                       3 |        -19350 |         -6300 |            0 |        900 |    900 |    -26550 |            12 |                3 |             6 |                  -35.7299 |                 6 |             2.23647  |
| jm.DCE    | short       | existing_at_window_start            |                       3 |         -1800 |        -21780 |            0 |        180 |    180 |    -23760 |             6 |                3 |             3 |                  -35.7299 |                 1 |             2.00145  |
| cu.SHFE   | long        | opened_or_traded_after_window_start |                       6 |        -13800 |         -4200 |            0 |       1800 |   1800 |    -19800 |           120 |               18 |            36 |                  -40.5376 |                 1 |             1.66787  |
| MA.CZCE   | short       | opened_or_traded_after_window_start |                       3 |         -7650 |        -10320 |            0 |        360 |    360 |    -18330 |            24 |                3 |            12 |                  -31.5663 |                 5 |             1.54405  |
| fu.SHFE   | long        | existing_at_window_start            |                       3 |        -19200 |          1650 |            0 |        150 |    150 |    -17700 |             6 |                3 |             3 |                  -31.5663 |                 5 |             1.49098  |
| au.SHFE   | long        | opened_or_traded_after_window_start |                       6 |          2640 |        -19800 |            0 |        240 |    240 |    -17400 |            12 |                6 |            12 |                  -40.5376 |                 1 |             1.46571  |
| cu.SHFE   | flat        | opened_or_traded_after_window_start |                       6 |             0 |        -14700 |            0 |        600 |    600 |    -15300 |             6 |                6 |            12 |                  -40.5376 |                 0 |             1.28881  |
| AP.CZCE   | long        | opened_or_traded_after_window_start |                      12 |        -12930 |          2280 |            0 |       1080 |   1080 |    -11730 |            72 |               15 |            30 |                  -40.5376 |                 6 |             0.988089 |

## Source 汇总

| source_start_month   |   window_count |   worst_return_pct |   position_net_pnl |   position_holding_pnl |   position_trading_pnl |   position_cost |   max_base_net_pnl_abs_diff |   active_position_rows |   active_contract_count |
|:---------------------|---------------:|-------------------:|-------------------:|-----------------------:|-----------------------:|----------------:|----------------------------:|-----------------------:|------------------------:|
| 2022-07              |              3 |           -40.5376 |            -378580 |                -401615 |                  32160 |            9125 |                 1.45519e-11 |                    480 |                      71 |
| 2021-07              |              3 |           -35.7299 |            -423125 |                -420280 |                  11205 |           14050 |                 0           |                    722 |                     105 |
| 2022-01              |              6 |           -33.7953 |            -331230 |                -307890 |                 -13520 |            9820 |                 0           |                    905 |                     108 |

## 过拟合反思

- 运行前判断：否。本阶段只做已冻结 Stage022 focus 窗口的持仓归因，不根据结果改产品、方向、日期或阈值。
- 运行后判断：否。结果可以提示下一步信号形状，但不能把 top loss driver 直接做黑名单；那会过拟合。

## 继续价值反思

- 运行前判断：有价值。若 base residual 仍集中在窗口后新增仓，下一步才值得继续找 PIT 入场确认或账户外层；若只是已有趋势仓正常回撤，则不该强行优化。
- 运行后判断：有价值。剩余 base 亏损主要来自窗口后新增/交易仓，下一步应围绕新增仓的 PIT 入场状态、账户状态或外生确认继续找结构信号。

## 输出文件

- window_position_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_window_position_detail_stage024_stage022_base_position_attribution_v1.csv.gz`
- window_validation：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_window_validation_stage024_stage022_base_position_attribution_v1.csv`
- product_direction_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_product_direction_summary_stage024_stage022_base_position_attribution_v1.csv`
- source_bucket_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_source_bucket_summary_stage024_stage022_base_position_attribution_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_source_summary_stage024_stage022_base_position_attribution_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_loss_driver_chart_stage024_stage022_base_position_attribution_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_decision_stage024_stage022_base_position_attribution_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage024_stage022_base_position_attribution/rebuilt_c9_v2_stage024_stage022_base_position_attribution_report_stage024_stage022_base_position_attribution_v1.md`