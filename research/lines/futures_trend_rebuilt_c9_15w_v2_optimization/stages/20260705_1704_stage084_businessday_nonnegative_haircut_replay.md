# Stage084 business-day non-negative haircut replay

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:04:32
- 阶段性质：Stage083 审查后的基金工作日确认与非负 haircut 口径重算
- 是否重要突破：否，只是账户层弱候选口径收敛

## 外部调研与判断

- 天天基金帮助说明，每万份收益是货币基金每一万份单位当日收益，通常工作日晚公布；七日年化只代表过去七个自然日折算，不代表未来。
- 监管/基金资料显示，货币基金确认、快速赎回和普通赎回存在时效与额度约束，不能只看历史收益。
- GitHub 快速调研看到场外基金回测框架会建模 T+n 确认与到账，但未找到可直接复用到本仓库货基万份收益数据的专用实现。
- 本阶段判断：先用固定篮子做工作日确认和非负 haircut 口径收敛，不换基金、不扫篮子大小。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage084_businessday_nonnegative_haircut_replay.py`
- 新增参数：`business_delay_days in {0,1,2}`、`floor_daily_return_at_zero in {True,False}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

| version                                | variant_label                                 |   business_delay_days |   annual_haircut_bps | floor_daily_return_at_zero   |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |   days_below_improved_count |   max_consecutive_below_improved_count | passes_account_level_stage077_proxy_goal   |
|:---------------------------------------|:----------------------------------------------|----------------------:|---------------------:|:-----------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|----------------------------:|---------------------------------------:|:-------------------------------------------|
| official_c9_15w_reference              | Official C9 15w reference                     |                     0 |                    0 | True                         |            13 |               13 |         1.90107  |            126.199  |          3886.19 |                     1        |                        1        |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| stage082_base_conservative             | Stage082 base conservative                    |                     0 |                    0 | True                         |            13 |               13 |         1.1805   |             65.344  |          1948.89 |                     0.50149  |                        0.51526  |             -52.7119 |              -18.5753 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| business_tplus1_delay                  | Business-day T+1 delay                        |                     1 |                    0 | True                         |            13 |               13 |         1.17916  |             65.3412 |          1948.88 |                     0.501489 |                        0.515216 |             -52.7121 |              -18.5755 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| business_tplus2_delay                  | Business-day T+2 delay                        |                     2 |                    0 | True                         |            13 |               13 |         1.1779   |             65.3387 |          1948.87 |                     0.501486 |                        0.515167 |             -52.7126 |              -18.5758 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |
| business_tplus1_haircut100_neg_allowed | Business T+1 + 100bp haircut negative allowed |                     1 |                  100 | False                        |            13 |               13 |         0.958847 |             63.5366 |          1945.37 |                     0.500587 |                        0.503514 |             -52.8202 |              -18.7284 |                      498 |                          20 |                                  383 |                                      16 |                           6 |                                      4 | True                                       |
| business_tplus1_haircut150_neg_allowed | Business T+1 + 150bp haircut negative allowed |                     1 |                  150 | False                        |            13 |               13 |         0.849083 |             62.9145 |          1943.7  |                     0.446635 |                        0.499743 |             -52.8728 |              -18.8036 |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| business_tplus1_haircut200_neg_allowed | Business T+1 + 200bp haircut negative allowed |                     1 |                  200 | False                        |            13 |               13 |         0.739581 |             62.3496 |          1942.09 |                     0.389035 |                        0.494056 |             -52.9244 |              -18.8781 |                      501 |                          24 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| business_tplus1_haircut100_floor0      | Business T+1 + 100bp haircut floor0           |                     1 |                  100 | True                         |            13 |               13 |         0.97576  |             63.5863 |          1945.49 |                     0.500616 |                        0.504058 |             -52.8167 |              -18.7246 |                      498 |                          20 |                                  383 |                                      16 |                           6 |                                      4 | True                                       |
| business_tplus1_haircut150_floor0      | Business T+1 + 150bp haircut floor0           |                     1 |                  150 | True                         |            13 |               13 |         0.962701 |             63.247  |          1944.22 |                     0.50029  |                        0.501337 |             -52.8643 |              -18.7642 |                      500 |                          20 |                                  387 |                                      16 |                           1 |                                      0 | False                                      |
| business_tplus1_haircut200_floor0      | Business T+1 + 200bp haircut floor0           |                     1 |                  200 | True                         |            13 |               13 |         0.958651 |             63.1698 |          1943.52 |                     0.50011  |                        0.500676 |             -52.894  |              -18.7773 |                      500 |                          20 |                                  387 |                                      16 |                           1 |                                      0 | False                                      |
| business_tplus2_haircut100_floor0      | Business T+2 + 100bp haircut floor0           |                     2 |                  100 | True                         |            13 |               13 |         0.975716 |             63.5852 |          1945.48 |                     0.500615 |                        0.50402  |             -52.817  |              -18.7247 |                      498 |                          20 |                                  383 |                                      16 |                           6 |                                      4 | True                                       |

## 结论

- 决策：`stage084_businessday_floor0_confirms_cash_basket_weak_not_promotion`。
- 通过 variant 数：`6`。
- 回测指标说明：本阶段是账户层现金收益摩擦敏感性，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 独立 agent review：严重问题 `0`；中等问题 `2`；低级问题 `2`；置信度 `0.89`。
  - 确认未改 C9 交易路径、未换基金篮子/容量，Stage082 基线在 Stage084 中逐行复现，账户权益最大差约 `9.31e-10`。
  - 统计口径未发现 bug：非 official 账户恒等式 `account_equity = c9_equity + reserve_equity` 最大误差约 `9.31e-10`，`13` 个起点、`11` 个版本无重复。
  - 中等 caveat：`BDay` 是周一到周五近似，不是中国基金交易日历；当前逐半年起点没有跨春节/国庆等长假，不改变本轮“不晋级”结论，但若扩展到任意日起点必须换 `CustomBusinessDay`/中国交易日历。
  - 中等 caveat：`business_tplus1_haircut100_floor0` 只是贴线通过，最小 retention `0.500616`，水下天数 `498` 只比 official `500` 少 `2` 天；150/200bp floor0 虽 retention 略高于 `0.5`，但水下/连续水下不再过关。
  - 低级 caveat：Stage084 没有继承 Stage082 的 per-start 可购性审计输出；`floor0` 是现实非负货基收益口径，真正压力口径是 negative allowed。
  - 独立结论：`stage084_businessday_floor0_confirms_cash_basket_weak_not_promotion` 被输出支持，不应晋级；下一步不应换基金、换篮子大小或调门槛。
- 运行前过拟合反思：否。只修正 Stage083 的确认日和 haircut 口径，不按结果调基金或资金比例。
- 运行后过拟合反思：若继续为了守住 `50%` 换基金、换篮子大小或改通过门槛，就是过拟合；应把它视为账户层弱候选。
- 继续价值：有限。若结果仍贴近 `50%`，下一步只做真实渠道验收；若明显失效，现金篮子降级。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage084_businessday_nonnegative_haircut_replay/rebuilt_c9_v2_stage084_businessday_nonnegative_haircut_replay_report_stage084_businessday_nonnegative_haircut_replay_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage084_businessday_nonnegative_haircut_replay/rebuilt_c9_v2_stage084_businessday_nonnegative_haircut_replay_decision_stage084_businessday_nonnegative_haircut_replay_v1.json`
- variant_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage084_businessday_nonnegative_haircut_replay/rebuilt_c9_v2_stage084_businessday_nonnegative_haircut_replay_variant_summary_stage084_businessday_nonnegative_haircut_replay_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage084_businessday_nonnegative_haircut_replay/rebuilt_c9_v2_stage084_businessday_nonnegative_haircut_replay_retention_vs_official_c9_stage084_businessday_nonnegative_haircut_replay_v1.csv`
