# Stage036 利润兑现资金层生存线审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:43:13
- 阶段性质：当前重建 C9/15w 的账户外层只读审计；不是策略信号、不是 true engine、不是实盘执行改动
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考 Rob Carver/pysystemtrade 对 capital correction、趋势跟随分散化与收益路径治理的讨论，以及 time-series momentum/managed futures 研究。
- 我的判断：利润兑现/资金分层符合“保住已赚到的右尾”的账户管理直觉，但不能创造信号质量；如果亏损发生在首次锁定前，它没有保护能力。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage036_profit_lock_survival_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage036_profit_lock_survival_audit.py`
- 新增参数：`POLICIES=[{"variant": "profit_tranche_norm6x", "threshold_multiple": 6.0, "transfer_fraction": 0.7, "locked_fraction": 0.7, "reserve_fraction": 0.3, "note": "Stage232 3m/500k threshold normalized to 6x for 150k; aggressive profit lock."}, {"variant": "balanced_tranche_norm10x", "threshold_multiple": 10.0, "transfer_fraction": 0.5, "locked_fraction": 0.6, "reserve_fraction": 0.4, "note": "Stage232 5m/500k threshold normalized to 10x for 150k; balanced profit lock."}]`
- 修改参数：无正式策略参数修改
- 删除参数：无
- 新增图表：汇总图、绝对资金曲线图

## 结果

- C9 密集 >1 年负窗口数：`267708`
- C9 密集 >1 年最差收益：`-54.6931%`
- 最优非 C9 资金层：`profit_tranche_norm6x`
- 最优非 C9 密集 >1 年负窗口数：`245913`
- 最优非 C9 密集 >1 年最差收益：`-54.6931%`
- 最优非 C9 最小收益保留：`0.5008`
- 目标通过 variant 数：`0`
- 转出事件数：`121`
- 决策：`stage036_profit_lock_survival_not_goal_keep_readonly`
- 原因：预声明利润兑现资金层未能同时清零密集 >1 年负窗口并保留 C9 80% 收益。
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## 目标门汇总

| variant                  |   all_gt1y_window_count |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_window_count |   to_final_negative_count |   to_final_min_return_pct |   retention_80pct_pass_count |   retention_rows |   min_retention | objective_pass   |
|:-------------------------|------------------------:|--------------------------:|--------------------------:|------------------------:|--------------------------:|--------------------------:|-----------------------------:|-----------------:|----------------:|:-----------------|
| profit_tranche_norm6x    |                 3687503 |                    245913 |                  -54.6931 |                    7955 |                         0 |                    7.0855 |                            8 |               11 |          0.5008 | False            |
| balanced_tranche_norm10x |                 3687503 |                    252407 |                  -54.6931 |                    7955 |                         0 |                    9.4048 |                            9 |               11 |          0.6538 | False            |
| c9_100                   |                 3687503 |                    267708 |                  -54.6931 |                    7955 |                         0 |                   11.7997 |                           11 |               11 |          1      | False            |

## 多起点摘要

| stage    | line_id                                      | model_tag                              | variant                  | requested_start_month   | start_date   | end_date   |   trading_days |   start_equity |       end_equity |   total_return_pct |   max_drawdown_pct |   sharpe |   min_equity |   total_transferred |   ending_locked_equity |   ending_reserve_equity |
|:---------|:---------------------------------------------|:---------------------------------------|:-------------------------|:------------------------|:-------------|:-----------|---------------:|---------------:|-----------------:|-------------------:|-------------------:|---------:|-------------:|--------------------:|-----------------------:|------------------------:|
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2020-01                 | 2020-01-02   | 2026-06-30 |           1571 |         150000 |      3.96113e+06 |          2540.75   |           -40.2173 |   1.4847 |       141520 |         2.58994e+06 |            1.55396e+06 |             1.03597e+06 |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2020-07                 | 2020-07-01   | 2026-06-30 |           1454 |         150000 |      3.56053e+06 |          2273.69   |           -43.4613 |   1.4753 |       150000 |         2.18826e+06 |            1.31296e+06 |        875306           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2021-01                 | 2021-01-04   | 2026-06-30 |           1328 |         150000 |      2.32827e+06 |          1452.18   |           -54.318  |   1.293  |       150000 |    952711           |       571627           |        381085           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2021-07                 | 2021-07-01   | 2026-06-30 |           1210 |         150000 | 512050           |           241.367  |           -47.2779 |   0.8355 |       140165 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2022-01                 | 2022-01-04   | 2026-06-30 |           1085 |         150000 | 323799           |           115.866  |           -39.982  |   0.6772 |       105690 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2022-07                 | 2022-07-01   | 2026-06-30 |            968 |         150000 | 455464           |           203.643  |           -55.1835 |   0.929  |       129300 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2023-01                 | 2023-01-03   | 2026-06-30 |            843 |         150000 | 338069           |           125.38   |           -24.469  |   0.9137 |       114505 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2023-07                 | 2023-07-03   | 2026-06-30 |            725 |         150000 | 419165           |           179.444  |           -24.3785 |   1.1937 |       140110 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2024-01                 | 2024-01-02   | 2026-06-30 |            601 |         150000 | 339299           |           126.199  |           -22.5622 |   1.2246 |       146850 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2024-07                 | 2024-07-01   | 2026-06-30 |            484 |         150000 | 226853           |            51.2352 |           -23.3751 |   0.7898 |       137350 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | balanced_tranche_norm10x | 2025-01                 | 2025-01-02   | 2026-06-30 |            359 |         150000 | 198567           |            32.3783 |           -22.6508 |   0.7362 |       135050 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2020-01                 | 2020-01-02   | 2026-06-30 |           1571 |         150000 |      5.97928e+06 |          3886.19   |           -55.3701 |   1.3959 |       141520 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2020-07                 | 2020-07-01   | 2026-06-30 |           1454 |         150000 |      4.87135e+06 |          3147.57   |           -54.7368 |   1.4052 |       150000 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2021-01                 | 2021-01-04   | 2026-06-30 |           1328 |         150000 |      2.39524e+06 |          1496.83   |           -54.318  |   1.2859 |       150000 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2021-07                 | 2021-07-01   | 2026-06-30 |           1210 |         150000 | 512050           |           241.367  |           -47.2779 |   0.8355 |       140165 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2022-01                 | 2022-01-04   | 2026-06-30 |           1085 |         150000 | 323799           |           115.866  |           -39.982  |   0.6772 |       105690 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2022-07                 | 2022-07-01   | 2026-06-30 |            968 |         150000 | 455464           |           203.643  |           -55.1835 |   0.929  |       129300 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2023-01                 | 2023-01-03   | 2026-06-30 |            843 |         150000 | 338069           |           125.38   |           -24.469  |   0.9137 |       114505 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2023-07                 | 2023-07-03   | 2026-06-30 |            725 |         150000 | 419165           |           179.444  |           -24.3785 |   1.1937 |       140110 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2024-01                 | 2024-01-02   | 2026-06-30 |            601 |         150000 | 339299           |           126.199  |           -22.5622 |   1.2246 |       146850 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2024-07                 | 2024-07-01   | 2026-06-30 |            484 |         150000 | 226853           |            51.2352 |           -23.3751 |   0.7898 |       137350 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | c9_100                   | 2025-01                 | 2025-01-02   | 2026-06-30 |            359 |         150000 | 198567           |            32.3783 |           -22.6508 |   0.7362 |       135050 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2020-01                 | 2020-01-02   | 2026-06-30 |           1571 |         150000 |      3.06927e+06 |          1946.18   |           -28.6327 |   1.5608 |       141520 |         2.25873e+06 |            1.58111e+06 |        677620           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2020-07                 | 2020-07-01   | 2026-06-30 |           1454 |         150000 |      2.77093e+06 |          1747.29   |           -29.8403 |   1.5665 |       150000 |         1.95959e+06 |            1.37171e+06 |        587876           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2021-01                 | 2021-01-04   | 2026-06-30 |           1328 |         150000 |      1.88787e+06 |          1158.58   |           -47.6802 |   1.3178 |       150000 |         1.07421e+06 |       751948           |        322264           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2021-07                 | 2021-07-01   | 2026-06-30 |           1210 |         150000 | 512050           |           241.367  |           -47.2779 |   0.8355 |       140165 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2022-01                 | 2022-01-04   | 2026-06-30 |           1085 |         150000 | 323799           |           115.866  |           -39.982  |   0.6772 |       105690 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2022-07                 | 2022-07-01   | 2026-06-30 |            968 |         150000 | 455464           |           203.643  |           -55.1835 |   0.929  |       129300 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2023-01                 | 2023-01-03   | 2026-06-30 |            843 |         150000 | 338069           |           125.38   |           -24.469  |   0.9137 |       114505 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2023-07                 | 2023-07-03   | 2026-06-30 |            725 |         150000 | 419165           |           179.444  |           -24.3785 |   1.1937 |       140110 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2024-01                 | 2024-01-02   | 2026-06-30 |            601 |         150000 | 339299           |           126.199  |           -22.5622 |   1.2246 |       146850 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2024-07                 | 2024-07-01   | 2026-06-30 |            484 |         150000 | 226853           |            51.2352 |           -23.3751 |   0.7898 |       137350 |         0           |            0           |             0           |
| Stage036 | futures_trend_rebuilt_c9_15w_v2_optimization | stage036_profit_lock_survival_audit_v1 | profit_tranche_norm6x    | 2025-01                 | 2025-01-02   | 2026-06-30 |            359 |         150000 | 198567           |            32.3783 |           -22.6508 |   0.7362 |       135050 |         0           |            0           |             0           |

## 聚合窗口

| variant                  | source_start_month   | audit_scope                 |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:-------------------------|:---------------------|:----------------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| balanced_tranche_norm10x | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           844554 |            37482 |              4.2495 |         -39.5274 |          516.767  |                                 0 |
| balanced_tranche_norm10x | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |           9.4048 |          478.223  |                                 0 |
| balanced_tranche_norm10x | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           693472 |            40093 |              5.4655 |         -42.7107 |          324.664  |                                 0 |
| balanced_tranche_norm10x | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          10.4636 |          304.721  |                                 0 |
| balanced_tranche_norm10x | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           534237 |            54768 |              9.2984 |         -53.296  |          198.875  |                                 0 |
| balanced_tranche_norm10x | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          17.0226 |          245.51   |                                 0 |
| balanced_tranche_norm10x | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           391896 |            75977 |             16.2388 |         -46.7059 |           73.3605 |                                 0 |
| balanced_tranche_norm10x | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          12.3976 |          110.565  |                                 0 |
| balanced_tranche_norm10x | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           328424 |            26361 |              7.4301 |         -39.3228 |           84.9892 |                                 0 |
| balanced_tranche_norm10x | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          21.7747 |          118.811  |                                 0 |
| balanced_tranche_norm10x | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           246346 |            16850 |              6.4021 |         -54.6931 |           96.7695 |                                 0 |
| balanced_tranche_norm10x | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          22.6343 |          123.034  |                                 0 |
| balanced_tranche_norm10x | 2023-01              | all_trading_end_dates_gt_1y |         180432 |           179556 |              876 |              0.4855 |          -8.6906 |           97.1337 |                                 0 |
| balanced_tranche_norm10x | 2023-01              | start_to_2026_06_30_only    |            600 |              600 |                0 |              0      |          24.4069 |          104.464  |                                 0 |
| balanced_tranche_norm10x | 2023-07              | all_trading_end_dates_gt_1y |         116529 |           116529 |                0 |              0      |           4.9842 |           98.0054 |                                 0 |
| balanced_tranche_norm10x | 2023-07              | start_to_2026_06_30_only    |            482 |              482 |                0 |              0      |          18.9999 |           93.5041 |                                 0 |
| balanced_tranche_norm10x | 2024-01              | all_trading_end_dates_gt_1y |          64285 |            64285 |                0 |              0      |           0.8339 |           73.6446 |                                 0 |
| balanced_tranche_norm10x | 2024-01              | start_to_2026_06_30_only    |            358 |              358 |                0 |              0      |          20.8545 |           68.3196 |                                 0 |
| balanced_tranche_norm10x | 2024-07              | all_trading_end_dates_gt_1y |          29059 |            29059 |                0 |              0      |           4.94   |           55.471  |                                 0 |
| balanced_tranche_norm10x | 2024-07              | start_to_2026_06_30_only    |            241 |              241 |                0 |              0      |          21.5913 |           49.9826 |                                 0 |
| balanced_tranche_norm10x | 2025-01              | all_trading_end_dates_gt_1y |           6738 |             6738 |                0 |              0      |          11.7997 |           45.3421 |                                 0 |
| balanced_tranche_norm10x | 2025-01              | start_to_2026_06_30_only    |            116 |              116 |                0 |              0      |          11.7997 |           36.595  |                                 0 |
| c9_100                   | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           836553 |            45483 |              5.1566 |         -54.3794 |          659.851  |                                 0 |
| c9_100                   | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          17.9714 |          775.75   |                                 0 |
| c9_100                   | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           686178 |            47387 |              6.4598 |         -53.7574 |          402.715  |                                 0 |
| c9_100                   | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          18.1655 |          458.925  |                                 0 |
| c9_100                   | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           534229 |            54776 |              9.2998 |         -53.296  |          206.081  |                                 0 |
| c9_100                   | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          18.1519 |          255.599  |                                 0 |
| c9_100                   | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           391896 |            75976 |             16.2386 |         -46.7059 |           73.3605 |                                 0 |
| c9_100                   | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          12.3976 |          110.565  |                                 0 |
| c9_100                   | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           328424 |            26360 |              7.4299 |         -39.3228 |           84.9892 |                                 0 |
| c9_100                   | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          21.7747 |          118.811  |                                 0 |
| c9_100                   | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           246346 |            16850 |              6.4021 |         -54.6931 |           96.7695 |                                 0 |
| c9_100                   | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          22.6343 |          123.034  |                                 0 |
| c9_100                   | 2023-01              | all_trading_end_dates_gt_1y |         180432 |           179556 |              876 |              0.4855 |          -8.6906 |           97.1337 |                                 0 |
| c9_100                   | 2023-01              | start_to_2026_06_30_only    |            600 |              600 |                0 |              0      |          24.4069 |          104.464  |                                 0 |
| c9_100                   | 2023-07              | all_trading_end_dates_gt_1y |         116529 |           116529 |                0 |              0      |           4.9842 |           98.0054 |                                 0 |
| c9_100                   | 2023-07              | start_to_2026_06_30_only    |            482 |              482 |                0 |              0      |          18.9999 |           93.5041 |                                 0 |
| c9_100                   | 2024-01              | all_trading_end_dates_gt_1y |          64285 |            64285 |                0 |              0      |           0.8339 |           73.6446 |                                 0 |
| c9_100                   | 2024-01              | start_to_2026_06_30_only    |            358 |              358 |                0 |              0      |          20.8545 |           68.3196 |                                 0 |
| c9_100                   | 2024-07              | all_trading_end_dates_gt_1y |          29059 |            29059 |                0 |              0      |           4.94   |           55.471  |                                 0 |
| c9_100                   | 2024-07              | start_to_2026_06_30_only    |            241 |              241 |                0 |              0      |          21.5913 |           49.9826 |                                 0 |
| c9_100                   | 2025-01              | all_trading_end_dates_gt_1y |           6738 |             6738 |                0 |              0      |          11.7997 |           45.3421 |                                 0 |
| c9_100                   | 2025-01              | start_to_2026_06_30_only    |            116 |              116 |                0 |              0      |          11.7997 |           36.595  |                                 0 |
| profit_tranche_norm6x    | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           845642 |            36394 |              4.1261 |         -27.065  |          431.279  |                                 0 |
| profit_tranche_norm6x    | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |           7.0855 |          355.428  |                                 0 |
| profit_tranche_norm6x    | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           695162 |            38403 |              5.2351 |         -29.3235 |          266.536  |                                 0 |
| profit_tranche_norm6x    | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |           7.7373 |          221.328  |                                 0 |
| profit_tranche_norm6x    | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           537953 |            51052 |              8.6675 |         -46.7973 |          161.758  |                                 0 |
| profit_tranche_norm6x    | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          11.9537 |          177.08   |                                 0 |
| profit_tranche_norm6x    | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           391896 |            75977 |             16.2388 |         -46.7059 |           73.3605 |                                 0 |
| profit_tranche_norm6x    | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          12.3976 |          110.565  |                                 0 |
| profit_tranche_norm6x    | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           328424 |            26361 |              7.4301 |         -39.3228 |           84.9892 |                                 0 |
| profit_tranche_norm6x    | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          21.7747 |          118.811  |                                 0 |
| profit_tranche_norm6x    | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           246346 |            16850 |              6.4021 |         -54.6931 |           96.7695 |                                 0 |
| profit_tranche_norm6x    | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          22.6343 |          123.034  |                                 0 |
| profit_tranche_norm6x    | 2023-01              | all_trading_end_dates_gt_1y |         180432 |           179556 |              876 |              0.4855 |          -8.6906 |           97.1337 |                                 0 |
| profit_tranche_norm6x    | 2023-01              | start_to_2026_06_30_only    |            600 |              600 |                0 |              0      |          24.4069 |          104.464  |                                 0 |
| profit_tranche_norm6x    | 2023-07              | all_trading_end_dates_gt_1y |         116529 |           116529 |                0 |              0      |           4.9842 |           98.0054 |                                 0 |
| profit_tranche_norm6x    | 2023-07              | start_to_2026_06_30_only    |            482 |              482 |                0 |              0      |          18.9999 |           93.5041 |                                 0 |

## 80% 收益保留

| variant                  | requested_start_month   |   total_return_pct |   c9_total_return_pct |   return_retention_vs_c9 |   passes_80pct_retention |
|:-------------------------|:------------------------|-------------------:|----------------------:|-------------------------:|-------------------------:|
| balanced_tranche_norm10x | 2020-01                 |          2540.75   |             3886.19   |                   0.6538 |                        0 |
| balanced_tranche_norm10x | 2020-07                 |          2273.69   |             3147.57   |                   0.7224 |                        0 |
| balanced_tranche_norm10x | 2021-01                 |          1452.18   |             1496.83   |                   0.9702 |                        1 |
| balanced_tranche_norm10x | 2021-07                 |           241.367  |              241.367  |                   1      |                        1 |
| balanced_tranche_norm10x | 2022-01                 |           115.866  |              115.866  |                   1      |                        1 |
| balanced_tranche_norm10x | 2022-07                 |           203.643  |              203.643  |                   1      |                        1 |
| balanced_tranche_norm10x | 2023-01                 |           125.38   |              125.38   |                   1      |                        1 |
| balanced_tranche_norm10x | 2023-07                 |           179.444  |              179.444  |                   1      |                        1 |
| balanced_tranche_norm10x | 2024-01                 |           126.199  |              126.199  |                   1      |                        1 |
| balanced_tranche_norm10x | 2024-07                 |            51.2352 |               51.2352 |                   1      |                        1 |
| balanced_tranche_norm10x | 2025-01                 |            32.3783 |               32.3783 |                   1      |                        1 |
| c9_100                   | 2020-01                 |          3886.19   |             3886.19   |                   1      |                        1 |
| c9_100                   | 2020-07                 |          3147.57   |             3147.57   |                   1      |                        1 |
| c9_100                   | 2021-01                 |          1496.83   |             1496.83   |                   1      |                        1 |
| c9_100                   | 2021-07                 |           241.367  |              241.367  |                   1      |                        1 |
| c9_100                   | 2022-01                 |           115.866  |              115.866  |                   1      |                        1 |
| c9_100                   | 2022-07                 |           203.643  |              203.643  |                   1      |                        1 |
| c9_100                   | 2023-01                 |           125.38   |              125.38   |                   1      |                        1 |
| c9_100                   | 2023-07                 |           179.444  |              179.444  |                   1      |                        1 |
| c9_100                   | 2024-01                 |           126.199  |              126.199  |                   1      |                        1 |
| c9_100                   | 2024-07                 |            51.2352 |               51.2352 |                   1      |                        1 |
| c9_100                   | 2025-01                 |            32.3783 |               32.3783 |                   1      |                        1 |
| profit_tranche_norm6x    | 2020-01                 |          1946.18   |             3886.19   |                   0.5008 |                        0 |
| profit_tranche_norm6x    | 2020-07                 |          1747.29   |             3147.57   |                   0.5551 |                        0 |
| profit_tranche_norm6x    | 2021-01                 |          1158.58   |             1496.83   |                   0.774  |                        0 |
| profit_tranche_norm6x    | 2021-07                 |           241.367  |              241.367  |                   1      |                        1 |
| profit_tranche_norm6x    | 2022-01                 |           115.866  |              115.866  |                   1      |                        1 |
| profit_tranche_norm6x    | 2022-07                 |           203.643  |              203.643  |                   1      |                        1 |
| profit_tranche_norm6x    | 2023-01                 |           125.38   |              125.38   |                   1      |                        1 |
| profit_tranche_norm6x    | 2023-07                 |           179.444  |              179.444  |                   1      |                        1 |
| profit_tranche_norm6x    | 2024-01                 |           126.199  |              126.199  |                   1      |                        1 |
| profit_tranche_norm6x    | 2024-07                 |            51.2352 |               51.2352 |                   1      |                        1 |
| profit_tranche_norm6x    | 2025-01                 |            32.3783 |               32.3783 |                   1      |                        1 |

## 转出事件样例

| variant                  | requested_start_month   | date                |   base_account_equity |   production_equity |    locked_equity |   reserve_equity |   threshold_equity |   transfer_amount |   cumulative_transferred |
|:-------------------------|:------------------------|:--------------------|----------------------:|--------------------:|-----------------:|-----------------:|-------------------:|------------------:|-------------------------:|
| balanced_tranche_norm10x | 2020-01                 | 2021-09-30 00:00:00 |           1.66576e+06 |         1.58288e+06 |  49727.3         |  33151.6         |            1.5e+06 |         82878.9   |          82878.9         |
| balanced_tranche_norm10x | 2020-01                 | 2021-10-29 00:00:00 |           2.32153e+06 |         1.85301e+06 | 261534           | 174356           |            1.5e+06 |        353011     |         435890           |
| balanced_tranche_norm10x | 2020-01                 | 2021-11-30 00:00:00 |           1.92137e+06 |         1.5168e+06  | 271616           | 181078           |            1.5e+06 |         16804.3   |         452694           |
| balanced_tranche_norm10x | 2020-01                 | 2021-12-31 00:00:00 |           1.91348e+06 |         1.50529e+06 | 274789           | 183193           |            1.5e+06 |          5287.82  |         457982           |
| balanced_tranche_norm10x | 2020-01                 | 2022-03-31 00:00:00 |           2.4271e+06  |         1.70467e+06 | 397591           | 265061           |            1.5e+06 |        204671     |         662652           |
| balanced_tranche_norm10x | 2020-01                 | 2022-07-29 00:00:00 |           2.5602e+06  |         1.64908e+06 | 487037           | 324692           |            1.5e+06 |        149077     |         811729           |
| balanced_tranche_norm10x | 2020-01                 | 2022-08-31 00:00:00 |           2.41959e+06 |         1.52925e+06 | 504589           | 336393           |            1.5e+06 |         29253.4   |         840982           |
| balanced_tranche_norm10x | 2020-01                 | 2024-03-29 00:00:00 |           2.37436e+06 |         1.50033e+06 | 504789           | 336526           |            1.5e+06 |           333.342 |         841316           |
| balanced_tranche_norm10x | 2020-01                 | 2024-04-30 00:00:00 |           2.91469e+06 |         1.67088e+06 | 607318           | 404879           |            1.5e+06 |        170881     |              1.0122e+06  |
| balanced_tranche_norm10x | 2020-01                 | 2024-05-31 00:00:00 |           3.1936e+06  |         1.66538e+06 | 706549           | 471033           |            1.5e+06 |        165385     |              1.17758e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-06-28 00:00:00 |           3.59838e+06 |         1.68823e+06 | 819489           | 546326           |            1.5e+06 |        188234     |              1.36582e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-07-31 00:00:00 |           3.43448e+06 |         1.55567e+06 | 852891           | 568594           |            1.5e+06 |         55668.9   |              1.42148e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-08-30 00:00:00 |           3.56161e+06 |         1.55663e+06 | 886867           | 591245           |            1.5e+06 |         56626.6   |              1.47811e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-09-30 00:00:00 |           3.94908e+06 |         1.61299e+06 | 954659           | 636439           |            1.5e+06 |        112987     |              1.5911e+06  |
| balanced_tranche_norm10x | 2020-01                 | 2024-10-31 00:00:00 |           4.03312e+06 |         1.57366e+06 | 998852           | 665902           |            1.5e+06 |         73656.2   |              1.66475e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-11-29 00:00:00 |           4.13558e+06 |         1.55682e+06 |      1.03294e+06 | 688629           |            1.5e+06 |         56817.2   |              1.72157e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2024-12-31 00:00:00 |           4.22104e+06 |         1.54449e+06 |      1.05964e+06 | 706426           |            1.5e+06 |         44494.1   |              1.76607e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-06-30 00:00:00 |           4.15149e+06 |         1.50952e+06 |      1.06535e+06 | 710236           |            1.5e+06 |          9523.65  |              1.77559e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-07-31 00:00:00 |           5.92163e+06 |         1.82658e+06 |      1.2613e+06  | 840868           |            1.5e+06 |        326582     |              2.10217e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-08-29 00:00:00 |           5.70665e+06 |         1.63013e+06 |      1.33938e+06 | 892922           |            1.5e+06 |        130133     |              2.2323e+06  |
| balanced_tranche_norm10x | 2020-01                 | 2025-09-30 00:00:00 |           5.82545e+06 |         1.58203e+06 |      1.3886e+06  | 925736           |            1.5e+06 |         82034.6   |              2.31434e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-10-31 00:00:00 |           5.92877e+06 |         1.55505e+06 |      1.42163e+06 | 947754           |            1.5e+06 |         55046.8   |              2.36939e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-11-28 00:00:00 |           6.73231e+06 |         1.6329e+06  |      1.50137e+06 |      1.00092e+06 |            1.5e+06 |        132903     |              2.50229e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2025-12-31 00:00:00 |           6.60031e+06 |         1.55044e+06 |      1.53164e+06 |      1.02109e+06 |            1.5e+06 |         50443.4   |              2.55273e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2026-01-30 00:00:00 |           6.67643e+06 |         1.53416e+06 |      1.55214e+06 |      1.03476e+06 |            1.5e+06 |         34162.2   |              2.58689e+06 |
| balanced_tranche_norm10x | 2020-01                 | 2026-02-27 00:00:00 |           6.55423e+06 |         1.50304e+06 |      1.55396e+06 |      1.03597e+06 |            1.5e+06 |          3041.04  |              2.58994e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2021-10-29 00:00:00 |           2.0199e+06  |         1.75995e+06 | 155969           | 103980           |            1.5e+06 |        259949     |         259949           |
| balanced_tranche_norm10x | 2020-07                 | 2022-03-31 00:00:00 |           2.1031e+06  |         1.66622e+06 | 255703           | 170468           |            1.5e+06 |        166222     |         426171           |
| balanced_tranche_norm10x | 2020-07                 | 2022-07-29 00:00:00 |           2.21942e+06 |         1.62919e+06 | 333216           | 222144           |            1.5e+06 |        129189     |         555360           |
| balanced_tranche_norm10x | 2020-07                 | 2022-08-31 00:00:00 |           2.09962e+06 |         1.52062e+06 | 345591           | 230394           |            1.5e+06 |         20624.5   |         575985           |
| balanced_tranche_norm10x | 2020-07                 | 2024-04-30 00:00:00 |           2.46809e+06 |         1.64374e+06 | 431836           | 287891           |            1.5e+06 |        143742     |         719727           |
| balanced_tranche_norm10x | 2020-07                 | 2024-05-31 00:00:00 |           2.69887e+06 |         1.64872e+06 | 521068           | 347379           |            1.5e+06 |        148721     |         868447           |
| balanced_tranche_norm10x | 2020-07                 | 2024-06-28 00:00:00 |           3.03663e+06 |         1.67753e+06 | 627585           | 418390           |            1.5e+06 |        177528     |              1.04598e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2024-07-31 00:00:00 |           2.90103e+06 |         1.55131e+06 | 658371           | 438914           |            1.5e+06 |         51309.1   |              1.09728e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2024-08-30 00:00:00 |           3.00707e+06 |         1.55401e+06 | 690775           | 460516           |            1.5e+06 |         54006.7   |              1.15129e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2024-09-30 00:00:00 |           3.32402e+06 |         1.6089e+06  | 756115           | 504077           |            1.5e+06 |        108901     |              1.26019e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2024-10-31 00:00:00 |           3.38243e+06 |         1.56859e+06 | 797267           | 531511           |            1.5e+06 |         68586.2   |              1.32878e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2024-11-29 00:00:00 |           3.46879e+06 |         1.55432e+06 | 829857           | 553238           |            1.5e+06 |         54317.6   |              1.3831e+06  |
| balanced_tranche_norm10x | 2020-07                 | 2024-12-31 00:00:00 |           3.53868e+06 |         1.54282e+06 | 855548           | 570365           |            1.5e+06 |         42817.2   |              1.42591e+06 |
| balanced_tranche_norm10x | 2020-07                 | 2025-07-31 00:00:00 |           4.81236e+06 |         1.79906e+06 |      1.03498e+06 | 689990           |            1.5e+06 |        299061     |              1.72497e+06 |

## 最差窗口

| variant                  | source_start_month   | window_type   | start_date   | end_date   |   period_calendar_days |   period_trading_days |   return_pct |     start_equity |       end_equity |
|:-------------------------|:---------------------|:--------------|:-------------|:-----------|-----------------------:|----------------------:|-------------:|-----------------:|-----------------:|
| c9_100                   | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -54.6931 | 288510           | 130715           |
| profit_tranche_norm6x    | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -54.6931 | 288510           | 130715           |
| balanced_tranche_norm10x | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -54.6931 | 288510           | 130715           |
| c9_100                   | 2020-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -54.3794 |      3.22788e+06 |      1.47258e+06 |
| c9_100                   | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -54.3742 | 288510           | 131635           |
| profit_tranche_norm6x    | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -54.3742 | 288510           | 131635           |
| balanced_tranche_norm10x | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -54.3742 | 288510           | 131635           |
| c9_100                   | 2020-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -54.0621 |      3.22788e+06 |      1.48282e+06 |
| c9_100                   | 2020-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -53.7574 |      2.78902e+06 |      1.28972e+06 |
| c9_100                   | 2020-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -53.444  |      2.78902e+06 |      1.29846e+06 |
| balanced_tranche_norm10x | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -53.296  |      1.36258e+06 | 636379           |
| c9_100                   | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -53.296  |      1.36258e+06 | 636379           |
| profit_tranche_norm6x    | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -53.1888 | 288510           | 135055           |
| c9_100                   | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -53.1888 | 288510           | 135055           |
| balanced_tranche_norm10x | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -53.1888 | 288510           | 135055           |
| balanced_tranche_norm10x | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -53.0039 |      1.36258e+06 | 640359           |
| c9_100                   | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -53.0039 |      1.36258e+06 | 640359           |
| c9_100                   | 2020-01              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -52.5862 |      3.22788e+06 |      1.53046e+06 |
| c9_100                   | 2020-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -51.9725 |      2.78902e+06 |      1.3395e+06  |
| balanced_tranche_norm10x | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -51.6007 |      1.36258e+06 | 659479           |
| c9_100                   | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -51.6007 |      1.36258e+06 | 659479           |
| profit_tranche_norm6x    | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -46.7973 |      1.32101e+06 | 702815           |
| balanced_tranche_norm10x | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -46.7059 | 341745           | 182130           |
| profit_tranche_norm6x    | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -46.7059 | 341745           | 182130           |
| c9_100                   | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -46.7059 | 341745           | 182130           |
| c9_100                   | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-17 |                    368 |                   245 |     -46.5641 | 244620           | 130715           |
| balanced_tranche_norm10x | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-17 |                    368 |                   245 |     -46.5641 | 244620           | 130715           |
| profit_tranche_norm6x    | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-17 |                    368 |                   245 |     -46.5641 | 244620           | 130715           |
| profit_tranche_norm6x    | 2021-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -46.5449 |      1.32101e+06 | 706149           |
| balanced_tranche_norm10x | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -46.384  | 341745           | 183230           |
| profit_tranche_norm6x    | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -46.384  | 341745           | 183230           |
| c9_100                   | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -46.384  | 341745           | 183230           |
| balanced_tranche_norm10x | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-07-05 |                    617 |                   412 |     -46.2108 | 334965           | 180175           |
| profit_tranche_norm6x    | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-07-05 |                    617 |                   412 |     -46.2108 | 334965           | 180175           |
| c9_100                   | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-07-05 |                    617 |                   412 |     -46.2108 | 334965           | 180175           |
| c9_100                   | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-18 |                    369 |                   246 |     -46.188  | 244620           | 131635           |
| profit_tranche_norm6x    | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-18 |                    369 |                   246 |     -46.188  | 244620           | 131635           |
| balanced_tranche_norm10x | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-18 |                    369 |                   246 |     -46.188  | 244620           | 131635           |
| profit_tranche_norm6x    | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-07-06 |                    618 |                   413 |     -46.0705 | 334965           | 180645           |
| balanced_tranche_norm10x | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-07-06 |                    618 |                   413 |     -46.0705 | 334965           | 180645           |

## 过拟合反思

- 运行前判断：否。Stage036 只用旧 Stage232 资金分层思路按 15w 做倍数归一，不按具体坏窗口、品种、月份或方向扫参。
- 运行后判断：若继续微调阈值倍数、转出比例或锁定/备用比例以刚好修复某些窗口，就是过拟合；本阶段只评价预声明形状。

## 继续价值反思

- 运行前判断：有。当前没有新的 schema-ready PIT 数据时，账户外层是少数不改 AI/信号也能改善生存性的方向。
- 运行后判断：若未过目标门，继续扫资金层细参价值低；若过门，也必须先做真实现金账本和出入金约束，而不是改策略信号。

## 输出文件

- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_curves_stage036_profit_lock_survival_audit_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_summary_stage036_profit_lock_survival_audit_v1.csv`
- aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_goal_aggregate_stage036_profit_lock_survival_audit_v1.csv`
- to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_goal_to_final_windows_stage036_profit_lock_survival_audit_v1.csv`
- fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_goal_fixed_horizon_windows_stage036_profit_lock_survival_audit_v1.csv`
- worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_goal_worst_windows_stage036_profit_lock_survival_audit_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_retention_vs_c9_stage036_profit_lock_survival_audit_v1.csv`
- goal_table: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_goal_table_stage036_profit_lock_survival_audit_v1.csv`
- transfer_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_transfer_events_stage036_profit_lock_survival_audit_v1.csv`
- summary_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_summary_chart_stage036_profit_lock_survival_audit_v1.png`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_absolute_equity_curves_stage036_profit_lock_survival_audit_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_decision_stage036_profit_lock_survival_audit_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage036_profit_lock_survival_audit/rebuilt_c9_v2_stage036_profit_lock_survival_audit_report_stage036_profit_lock_survival_audit_v1.md`
