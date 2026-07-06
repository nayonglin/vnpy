# Stage083 money fund friction sensitivity

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:55:32
- 阶段性质：Stage082 固定货币基金篮子的真实渠道摩擦敏感性
- 是否重要突破：否，验证账户层弱候选的摩擦承受力

## 外部调研与判断

- 天天基金帮助说明，每万份收益是货币基金每一万份单位当日收益，通常工作日晚公布；七日年化只代表过去七个自然日折算，不代表未来。
- 易方达 000009 快速赎回协议显示，快速赎回有单只货基单日限额、收益停止和暂停服务等约束。
- 东方财富转载的监管文件显示，T+0 快速赎回提现单只货基单销售渠道单日上限不高于 `1万元`，普通赎回不受该快速额度限制。
- 本阶段判断：现金篮子不能只看历史收益，必须在确认延迟和收益 haircut 后仍保留目标边际；否则降级。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage083_money_fund_friction_sensitivity.py`
- 新增参数：`delay_days in {0,1,2}`、`annual_haircut_bps in {0,25,50,100,150,200}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

| version                    | variant_label              |   delay_days |   annual_haircut_bps |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |   days_below_improved_count |   max_consecutive_below_improved_count | passes_account_level_stage077_proxy_goal   |
|:---------------------------|:---------------------------|-------------:|---------------------:|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|----------------------------:|---------------------------------------:|:-------------------------------------------|
| official_c9_15w_reference  | Official C9 15w reference  |            0 |                    0 |            13 |               13 |         1.90107  |            126.199  |          3886.19 |                     1        |                        1        |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| stage082_base_conservative | Stage082 base conservative |            0 |                    0 |            13 |               13 |         1.1805   |             65.344  |          1948.89 |                     0.50149  |                        0.51526  |             -52.7119 |              -18.5753 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| tplus1_delay               | T+1 income delay           |            1 |                    0 |            13 |               13 |         1.17916  |             65.3412 |          1948.88 |                     0.501489 |                        0.515216 |             -52.7121 |              -18.5755 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| tplus2_delay               | T+2 income delay           |            2 |                    0 |            13 |               13 |         1.1779   |             65.3387 |          1948.88 |                     0.501489 |                        0.515167 |             -52.7122 |              -18.5758 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| haircut_25bp               | 25bp annual yield haircut  |            0 |                   25 |            13 |               13 |         1.125    |             64.8865 |          1947.99 |                     0.501259 |                        0.512457 |             -52.7393 |              -18.6138 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| haircut_50bp               | 50bp annual yield haircut  |            0 |                   50 |            13 |               13 |         1.06957  |             64.433  |          1947.1  |                     0.501031 |                        0.50989  |             -52.7665 |              -18.6521 |                      488 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| haircut_100bp              | 100bp annual yield haircut |            0 |                  100 |            13 |               13 |         0.95892  |             63.5379 |          1945.38 |                     0.500587 |                        0.503523 |             -52.8201 |              -18.7282 |                      498 |                          20 |                                  383 |                                      16 |                           6 |                                      4 | True                                       |
| haircut_150bp              | 150bp annual yield haircut |            0 |                  150 |            13 |               13 |         0.84853  |             62.9151 |          1943.71 |                     0.446344 |                        0.499748 |             -52.8728 |              -18.8035 |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| haircut_200bp              | 200bp annual yield haircut |            0 |                  200 |            13 |               13 |         0.738404 |             62.3496 |          1942.09 |                     0.388416 |                        0.494057 |             -52.9244 |              -18.8781 |                      501 |                          24 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| tplus1_haircut_50bp        | T+1 delay + 50bp haircut   |            1 |                   50 |            13 |               13 |         1.06887  |             64.4311 |          1947.1  |                     0.501031 |                        0.509883 |             -52.7667 |              -18.6523 |                      489 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| tplus1_haircut_100bp       | T+1 delay + 100bp haircut  |            1 |                  100 |            13 |               13 |         0.958847 |             63.5366 |          1945.37 |                     0.500587 |                        0.503514 |             -52.8202 |              -18.7284 |                      498 |                          20 |                                  383 |                                      16 |                           6 |                                      4 | True                                       |
| tplus1_haircut_150bp       | T+1 delay + 150bp haircut  |            1 |                  150 |            13 |               13 |         0.849083 |             62.9145 |          1943.7  |                     0.446635 |                        0.499743 |             -52.8728 |              -18.8036 |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |

## 结论

- 决策：`stage083_light_friction_survives_but_edge_thin_not_promotion`。
- 通过 variant 数：`8`。
- 回测指标说明：本阶段是账户层现金收益摩擦敏感性，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 独立 agent 审查结论：严重问题为无，置信度 `0.82`；Stage083 未换基金、未调篮子大小、未改 C9 交易路径，Stage083 base 与 Stage082 base 仅浮点误差，所有 variant 的 C9 路径 `max_abs_diff=0`。中等问题是 `delay_days` 用自然日而非基金工作日，`annual_haircut_bps` 允许负 carry 因而更像压力测试，且通过仍是账户层聚合 proxy、不是每个起点都改善。建议 Stage084 只读重算工作日确认口径，并增加 haircut 后日收益不低于 `0` 的现实口径对照。
- 运行前过拟合反思：否。只对真实渠道摩擦做固定压力测试，不换基金、不调篮子。
- 运行后过拟合反思：若因为某个 haircut 失败而换基金、换数量或改口径，就是过拟合；应把失败视为账户层弱候选的鲁棒性不足。
- 继续价值：有但只限口径收敛；下一步只做工作日确认与非负 haircut 口径重算，不换基金、不扫篮子大小，不进入正式。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage083_money_fund_friction_sensitivity/rebuilt_c9_v2_stage083_money_fund_friction_sensitivity_report_stage083_money_fund_friction_sensitivity_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage083_money_fund_friction_sensitivity/rebuilt_c9_v2_stage083_money_fund_friction_sensitivity_decision_stage083_money_fund_friction_sensitivity_v1.json`
- variant_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage083_money_fund_friction_sensitivity/rebuilt_c9_v2_stage083_money_fund_friction_sensitivity_variant_summary_stage083_money_fund_friction_sensitivity_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage083_money_fund_friction_sensitivity/rebuilt_c9_v2_stage083_money_fund_friction_sensitivity_retention_vs_official_c9_stage083_money_fund_friction_sensitivity_v1.csv`
