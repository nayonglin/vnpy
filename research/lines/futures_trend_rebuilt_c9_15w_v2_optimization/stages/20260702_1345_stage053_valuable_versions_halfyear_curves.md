# Stage053 有价值版本逐半年净值曲线复算

- 记录时间：2026-07-02 13:45 CST
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- model_tag：`stage053_valuable_versions_halfyear_curves_v1`
- 是否重要突破版本：否，本阶段是只读汇总与绘图，不新增交易规则。
- 新增参数：无交易参数；新增比较集合 `valuable_versions + official C9/15w`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。
- 回测/曲线口径：逐半年起点；终点统一使用 `2026-06-30`；已存在的真引擎/代理曲线按原 stage 输出读取并重新计算 NAV、终点收益和回撤。

## 外部调研判断

- Managed futures / trend-following 资料支持用多起点、跨周期路径和右尾保留判断策略，不应只看单一起点。
- vectorbt 等矩阵化回测框架说明多版本/多起点曲线适合统一面板分析；本阶段仍沿用仓库既有回测曲线，不迁移框架。

## 过拟合与继续价值反思

- 开始是否过拟合：否。本阶段只汇总前面已冻结的版本，不按结果新增阈值、日期、品种、方向或资金比例。
- 结束是否过拟合：否。图表揭示差异但不据此调参；后续若只挑收益最好的起点救参会过拟合。
- 开始是否值得继续：有。用户需要把所有有价值版本放到同一逐半年口径对比，这是判断下一步路线的必要视图。
- 结束是否值得继续：有，但方向应转向能同时保留右尾和减少冷启动左尾的结构；单纯资金 ramp / sleeve / profit lock 已显示收益保留问题。

## 汇总结论

- 这次没有新增达成目标的版本；所有候选仍只是研究资产或诊断资产。
- 终点收益/净值曲线最值得继续看的仍是 `Stage010/013/014/022` 质量加风险链；它们多数起点能抬高收益，但仍不是严格任意一年以上正收益解法。
- `Stage008/017/036/074` 更偏防守或部署层，能改善部分左尾窗口，但收益保留或晚近起点表现明显受损。
- `Stage052 contract OI share proxy` 是上游旧 Stage052 逐合约 OI 加风险 proxy，不是 v2 当前 TqSdk jd 补数 Stage052。

## Version Summary

| version                          | source_type      |   start_count |   positive_start_count |   win_vs_official_count |   comparable_to_official_count |   min_total_return_pct |   median_total_return_pct |   worst_max_drawdown_pct |   min_final_nav_ratio_vs_official |
|:---------------------------------|:-----------------|--------------:|-----------------------:|------------------------:|-------------------------------:|-----------------------:|--------------------------:|-------------------------:|----------------------------------:|
| Official C9/15w Stage847         | true_engine      |            17 |                     17 |                       0 |                             17 |                 1.9011 |                   203.643 |                 -56.2069 |                            1      |
| Stage013 account-state pilot     | true_engine      |            17 |                     17 |                      14 |                             17 |                 1.9011 |                   238.369 |                 -43.794  |                            0.9075 |
| Stage008 risk-release gate       | true_engine      |            17 |                     17 |                      10 |                             17 |                 6.688  |                   228.359 |                 -42.8852 |                            0.3902 |
| Stage010 quality +25% proxy      | closed_lot_proxy |            17 |                     17 |                      17 |                             17 |                 3.3513 |                   286.72  |                 -41.2213 |                            1.0142 |
| Stage013 guarded quality proxy   | closed_lot_proxy |            17 |                     17 |                      16 |                             17 |                 0.1327 |                   297.728 |                 -40.5376 |                            0.9826 |
| Stage014 guarded floor integer   | integer_proxy    |            17 |                     17 |                      16 |                             17 |                 0.1544 |                   280.512 |                 -40.8929 |                            0.9829 |
| Stage014 guarded ceil integer    | integer_proxy    |            17 |                     17 |                      16 |                             17 |                 0.0677 |                   312.062 |                 -39.4718 |                            0.982  |
| Stage017 C9 60 + Stage372 40     | sleeve_proxy     |            11 |                     11 |                       0 |                             11 |                 9.301  |                   145.346 |                 -49.714  |                            0.7511 |
| Stage022 guarded xsmom proxy     | closed_lot_proxy |            17 |                     17 |                      16 |                             17 |                 0.1327 |                   275.905 |                 -40.5376 |                            0.9826 |
| Stage036 profit tranche 6x       | account_overlay  |            11 |                     11 |                       3 |                             11 |                32.3783 |                   179.444 |                 -55.1835 |                            0.5133 |
| Stage036 balanced tranche 10x    | account_overlay  |            11 |                     11 |                       3 |                             11 |                32.3783 |                   179.444 |                 -55.1835 |                            0.6625 |
| Stage052 contract OI share proxy | closed_lot_proxy |            17 |                     17 |                      17 |                             17 |                 3.143  |                   274.779 |                 -40.3699 |                            1.0122 |
| Stage070 AI top8 active<3 proxy  | closed_lot_proxy |            17 |                     17 |                      15 |                             17 |                 5.4611 |                   252.088 |                 -44.1402 |                            0.9163 |
| Stage074 cold-start ramp proxy   | account_overlay  |            17 |                     17 |                      11 |                             17 |                 0.694  |                   231.653 |                 -46.5554 |                            0.8793 |

## Min Return Top

| version                         | source_type      |   start_count |   min_total_return_pct |   median_total_return_pct |   worst_max_drawdown_pct |
|:--------------------------------|:-----------------|--------------:|-----------------------:|--------------------------:|-------------------------:|
| Stage036 profit tranche 6x      | account_overlay  |            11 |                32.3783 |                   179.444 |                 -55.1835 |
| Stage036 balanced tranche 10x   | account_overlay  |            11 |                32.3783 |                   179.444 |                 -55.1835 |
| Stage017 C9 60 + Stage372 40    | sleeve_proxy     |            11 |                 9.301  |                   145.346 |                 -49.714  |
| Stage008 risk-release gate      | true_engine      |            17 |                 6.688  |                   228.359 |                 -42.8852 |
| Stage070 AI top8 active<3 proxy | closed_lot_proxy |            17 |                 5.4611 |                   252.088 |                 -44.1402 |
| Stage010 quality +25% proxy     | closed_lot_proxy |            17 |                 3.3513 |                   286.72  |                 -41.2213 |

## Drawdown Top

| version                          | source_type      |   start_count |   min_total_return_pct |   median_total_return_pct |   worst_max_drawdown_pct |
|:---------------------------------|:-----------------|--------------:|-----------------------:|--------------------------:|-------------------------:|
| Stage014 guarded ceil integer    | integer_proxy    |            17 |                 0.0677 |                   312.062 |                 -39.4718 |
| Stage052 contract OI share proxy | closed_lot_proxy |            17 |                 3.143  |                   274.779 |                 -40.3699 |
| Stage013 guarded quality proxy   | closed_lot_proxy |            17 |                 0.1327 |                   297.728 |                 -40.5376 |
| Stage022 guarded xsmom proxy     | closed_lot_proxy |            17 |                 0.1327 |                   275.905 |                 -40.5376 |
| Stage014 guarded floor integer   | integer_proxy    |            17 |                 0.1544 |                   280.512 |                 -40.8929 |
| Stage010 quality +25% proxy      | closed_lot_proxy |            17 |                 3.3513 |                   286.72  |                 -41.2213 |

## 输出

- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_halfyear_curves_stage053_valuable_versions_halfyear_curves_v1.csv.gz`
- per_start_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_halfyear_per_start_summary_stage053_valuable_versions_halfyear_curves_v1.csv`
- version_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_halfyear_version_summary_stage053_valuable_versions_halfyear_curves_v1.csv`
- nav_curves_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_halfyear_nav_curves_stage053_valuable_versions_halfyear_curves_v1.png`
- final_return_heatmap: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_final_return_heatmap_stage053_valuable_versions_halfyear_curves_v1.png`
- vs_official_ratio_heatmap: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage053_valuable_versions_halfyear_curves/rebuilt_c9_v2_stage053_vs_official_ratio_heatmap_stage053_valuable_versions_halfyear_curves_v1.png`
