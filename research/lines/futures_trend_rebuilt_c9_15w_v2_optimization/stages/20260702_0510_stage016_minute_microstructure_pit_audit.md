# Stage016 Prior-minute Microstructure PIT Audit

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T05:13:01
- 阶段性质：当前重建 C9 入场前分钟结构只读审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；只有稳定候选进入真实路径 proxy 后才讨论

## 外部调研与判断

- 参考资料：managed futures/trend following 研究、pysystemtrade 资金/仓位回测文档、Concretum fast-alpha tactical overlay、intraday trend following/whipsaw 过滤讨论。
- 我的判断：分钟级信息更适合作为执行质量或 sizing overlay，不能替代日线趋势主逻辑；所以本阶段只看入场前已知的前一交易日分钟结构，不使用入场日后验确认。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage016_minute_microstructure_pit_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage016_minute_microstructure_pit_audit.py`
- 新增参数：`MAX_PRIOR_CALENDAR_DAYS=10`、`MIN_CONDITION_COUNT=80`、`MIN_CONDITION_YEARS=4`、`MIN_MEAN_PNL_LIFT=1.25`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- 输入事件数：`2867`
- 前一交易日分钟特征覆盖率：`25.0436%`
- 稳定候选数：`0`
- 最优条件：`prior_return_positive`
- 最优条件事件数：`459`
- 最优条件 mean PnL lift：`0.7655`
- 最优条件正贡献年数/覆盖年数：`3/7`
- 决策：`stage016_prior_minute_microstructure_no_stable_candidate_keep_readonly`
- 原因：入场前一交易日分钟结构没有形成跨年稳定、均值提升、坏路径不恶化的候选。

## 覆盖率

| metric                      |       value |
|:----------------------------|------------:|
| stage009_event_rows         |   2867      |
| stage009_unique_vt_symbols  |    192      |
| minute_bar_rows_filtered    | 660538      |
| minute_daily_feature_rows   |   2276      |
| prior_minute_available_rows |    718      |
| prior_minute_available_pct  |     25.0436 |

## 条件摘要

| condition_id                    | description                                                                     |   event_count |   event_pct |         total_pnl |   pnl_share_pct |   mean_pnl |   mean_pnl_lift |   win_rate_pct |   big_winner_rate_pct |   bad_path_rate_pct |   bad_path_delta_pp |   year_count |   positive_years | candidate_eligible   |
|:--------------------------------|:--------------------------------------------------------------------------------|--------------:|------------:|------------------:|----------------:|-----------:|----------------:|---------------:|----------------------:|--------------------:|--------------------:|-------------:|-----------------:|:---------------------|
| prior_return_positive           | Prior available trading day moved with signal direction.                        |           459 |     16.0098 |       7.75439e+06 |         12.255  |   16894.1  |          0.7655 |        28.5403 |               10.2397 |             40.7407 |              4.0473 |            7 |                3 | False                |
| prior_oi_up_and_return_positive | Prior day had OI up and signal-direction price return positive.                 |           309 |     10.7778 |       4.4649e+06  |          7.0563 |   14449.5  |          0.6547 |        27.5081 |                8.7379 |             39.1586 |              2.4652 |            7 |                2 | False                |
| prior_signal_side_close         | Prior close was in signal-side third of intraday range.                         |           307 |     10.7081 |       4.3476e+06  |          6.8709 |   14161.6  |          0.6417 |        28.9902 |               10.0977 |             35.5049 |             -1.1885 |            7 |                2 | False                |
| prior_high_noise                | Prior day had high minute path noise.                                           |           691 |     24.1018 |       7.37875e+06 |         11.6613 |   10678.4  |          0.4838 |        26.6281 |                6.8017 |             37.0478 |              0.3543 |            7 |                4 | False                |
| prior_return_negative           | Prior available trading day moved against signal direction.                     |           216 |      7.534  | -361523           |         -0.5713 |   -1673.72 |         -0.0758 |        24.537  |                0      |             31.9444 |             -4.749  |            7 |                4 | False                |
| prior_adverse_high_noise        | Prior day was adverse by return and high path noise.                            |           216 |      7.534  | -361523           |         -0.5713 |   -1673.72 |         -0.0758 |        24.537  |                0      |             31.9444 |             -4.749  |            7 |                4 | False                |
| prior_against_side_close        | Prior close was in against-side third of intraday range.                        |           159 |      5.5459 | -898798           |         -1.4205 |   -5652.82 |         -0.2561 |        11.9497 |                0      |             28.3019 |             -8.3915 |            5 |                1 | False                |
| prior_high_efficiency           | Prior day had high directional efficiency.                                      |             8 |      0.279  | -317840           |         -0.5023 |  -39730    |         -1.8002 |         0      |                0      |              0      |            -36.6934 |            1 |                0 | False                |
| prior_favorable_directional     | Prior day was signal-directional with signal-side close and non-low efficiency. |             0 |      0      |       0           |          0      |            |                 |                |                       |                     |                     |            0 |                0 | False                |
| prior_adverse_directional       | Prior day was adverse-directional by return and close location.                 |             0 |      0      |       0           |          0      |            |                 |                |                       |                     |                     |            0 |                0 | False                |

## 年度摘要

| condition_id                    |   entry_year |   event_count |         total_pnl |   mean_pnl |   bad_path_rate_pct |
|:--------------------------------|-------------:|--------------:|------------------:|-----------:|--------------------:|
| prior_return_positive           |         2020 |            89 | -350091           |  -3933.61  |             39.3258 |
| prior_return_positive           |         2021 |            91 |       4.91644e+06 |  54026.8   |             15.3846 |
| prior_return_positive           |         2022 |            52 |      -3.66406e+06 | -70462.6   |             69.2308 |
| prior_return_positive           |         2023 |            46 |       1.41443e+06 |  30748.5   |             73.913  |
| prior_return_positive           |         2024 |           120 |       7.72588e+06 |  64382.4   |             32.5    |
| prior_return_positive           |         2025 |            44 |      -2.27482e+06 | -51700.6   |             65.9091 |
| prior_return_positive           |         2026 |            17 |  -13392           |   -787.765 |              0      |
| prior_return_negative           |         2020 |            33 |   39647           |   1201.42  |              0      |
| prior_return_negative           |         2021 |            46 | -319690           |  -6949.78  |             17.3913 |
| prior_return_negative           |         2022 |            18 |       1.55357e+06 |  86309.4   |             50      |
| prior_return_negative           |         2023 |            18 |    2250           |    125     |             50      |
| prior_return_negative           |         2024 |            13 | -413400           | -31800     |              0      |
| prior_return_negative           |         2025 |            54 |      -1.35962e+06 | -25178.1   |             48.1481 |
| prior_return_negative           |         2026 |            34 |  135720           |   3991.76  |             50      |
| prior_signal_side_close         |         2020 |            55 | -224830           |  -4087.82  |             52.7273 |
| prior_signal_side_close         |         2021 |            60 | -586738           |  -9778.97  |             23.3333 |
| prior_signal_side_close         |         2022 |            43 |      -3.24756e+06 | -75524.6   |             62.7907 |
| prior_signal_side_close         |         2023 |            23 |       2.21827e+06 |  96446.5   |             47.8261 |
| prior_signal_side_close         |         2024 |            81 |       6.68208e+06 |  82494.8   |             16.0494 |
| prior_signal_side_close         |         2025 |            28 | -480225           | -17150.9   |             53.5714 |
| prior_signal_side_close         |         2026 |            17 |  -13392           |   -787.765 |              0      |
| prior_against_side_close        |         2020 |            34 |   60552           |   1780.94  |              0      |
| prior_against_side_close        |         2021 |            38 |  -46670           |  -1228.16  |              0      |
| prior_against_side_close        |         2024 |            26 | -828340           | -31859.2   |             46.1538 |
| prior_against_side_close        |         2025 |            44 |  -29620           |   -673.182 |             36.3636 |
| prior_against_side_close        |         2026 |            17 |  -54720           |  -3218.82  |            100      |
| prior_high_efficiency           |         2024 |             8 | -317840           | -39730     |              0      |
| prior_high_noise                |         2020 |           122 | -310444           |  -2544.62  |             28.6885 |
| prior_high_noise                |         2021 |           137 |       4.59675e+06 |  33552.9   |             16.0584 |
| prior_high_noise                |         2022 |            70 |      -2.11049e+06 | -30149.8   |             64.2857 |
| prior_high_noise                |         2023 |            64 |       1.41668e+06 |  22135.6   |             67.1875 |
| prior_high_noise                |         2024 |           133 |       7.31248e+06 |  54981.1   |             29.3233 |
| prior_high_noise                |         2025 |           114 |      -3.64856e+06 | -32004.9   |             48.2456 |
| prior_high_noise                |         2026 |            51 |  122328           |   2398.59  |             33.3333 |
| prior_oi_up_and_return_positive |         2020 |            52 | -342241           |  -6581.56  |             44.2308 |
| prior_oi_up_and_return_positive |         2021 |            45 | -477188           | -10604.2   |             15.5556 |
| prior_oi_up_and_return_positive |         2022 |            43 |      -2.98852e+06 | -69500.4   |             62.7907 |
| prior_oi_up_and_return_positive |         2023 |            23 |       2.21827e+06 |  96446.5   |             47.8261 |
| prior_oi_up_and_return_positive |         2024 |           100 |       8.04279e+06 |  80427.9   |             39      |
| prior_oi_up_and_return_positive |         2025 |            29 |      -1.97482e+06 | -68097.4   |             48.2759 |

## 过拟合反思

- 运行前判断：否。假设来自外部 fast-alpha/whipsaw 研究和已有分钟数据可用性；本阶段只预声明少量形态，不按失败窗口调参。
- 运行后判断：若本阶段没有候选后继续调 close-location/efficiency/noise 阈值，就是过拟合；应停止或换信息源。

## 继续价值反思

- 运行前判断：有价值。当前 AI 字段二级模型失败后，入场前分钟结构是新的 PIT 信息源，值得一次只读审计。
- 运行后判断：有限。继续围绕前一日分钟阈值调参大概率过拟合；若继续，应转更结构化的账户外层或新增外生特征。

## 输出文件

- features: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_features_stage016_minute_microstructure_pit_audit_v1.csv.gz`
- condition_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_condition_summary_stage016_minute_microstructure_pit_audit_v1.csv`
- year_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_year_summary_stage016_minute_microstructure_pit_audit_v1.csv`
- coverage: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_coverage_stage016_minute_microstructure_pit_audit_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_condition_chart_stage016_minute_microstructure_pit_audit_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_decision_stage016_minute_microstructure_pit_audit_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage016_minute_microstructure_pit_audit/rebuilt_c9_v2_stage016_minute_microstructure_pit_audit_report_stage016_minute_microstructure_pit_audit_v1.md`
