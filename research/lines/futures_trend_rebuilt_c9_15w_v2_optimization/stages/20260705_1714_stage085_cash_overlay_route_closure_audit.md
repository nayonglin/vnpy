# Stage085 cash/account overlay route closure audit

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T17:14:37
- 阶段性质：Stage073-084 账户/现金/储备金路线只读收束审计
- 是否重要突破：否，路线收束；不晋级
- 是否触发A/B：否，本阶段不提出接入正式版候选

## 外部调研与判断

- 本轮外部调研结论沿用 Stage083/084：货基和基金回测需要显式处理 T+n、到账、限额、节假日和渠道约束；趋势系统的水下期更适合靠结构分散、波动率/资金治理和独立收益腿改善。
- 本阶段判断：现金收益可以改善账户体验，但不能当成 C9 交易 alpha；贴线通过的账户层 proxy 不应晋级。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage085_cash_overlay_route_closure_audit.py`
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。

## 结果

| route_bucket              | engine_level     |   candidate_count |   pass_count |   published_pass_count |   best_min_retention |   best_worst_drawdown |   best_max_days_below |   best_max_consecutive_below |
|:--------------------------|:-----------------|------------------:|-------------:|-----------------------:|---------------------:|----------------------:|----------------------:|-----------------------------:|
| drawdown_brake            | curve_proxy      |                 6 |            0 |                      0 |           nan        |              -36.307  |                   500 |                          387 |
| idle_reserve_yield        | cash_yield_proxy |                28 |           20 |                     15 |             0.504794 |              -52.3615 |                   389 |                          255 |
| idle_reserve_yield        | source_audit     |                 4 |            3 |                      0 |             0.501517 |              -52.7039 |                   485 |                          383 |
| reserve_internal_transfer | curve_proxy      |                18 |            0 |                      2 |             0.5      |              -35.9666 |                   465 |                          236 |
| reserve_internal_transfer | true_engine      |                 1 |            0 |                      0 |             0.177366 |              -46.8207 |                   522 |                          337 |
| separate_sleeve_proxy     | curve_proxy      |                 6 |            0 |                      0 |             0.5      |              -47.5888 |                   500 |                          387 |

## 通过但不晋级的行

| stage    | source_type                     | engine_level     | variant_label                                     |   min_return_retention_ratio |   worst_drawdown_pct |   max_days_below_initial |   max_consecutive_below_initial_days | published_pass   | computed_account_level_pass   | manual_verdict                                                   |
|:---------|:--------------------------------|:-----------------|:--------------------------------------------------|-----------------------------:|---------------------:|-------------------------:|-------------------------------------:|:-----------------|:------------------------------|:-----------------------------------------------------------------|
| Stage074 | buffer_topup_proxy              | curve_proxy      | Daily top-up to 15w                               |                     0.5      |             -53.1727 |                      472 |                                  291 | True             | False                         | not_promoted_after_true_engine: proxy passed but Stage075 failed |
| Stage074 | buffer_topup_proxy              | curve_proxy      | Month-end top-up to 15w                           |                     0.5      |             -53.0125 |                      465 |                                  236 | True             | False                         | not_promoted_after_true_engine: proxy passed but Stage075 failed |
| Stage077 | constant_cash_yield_proxy       | cash_yield_proxy | C9 15w + idle reserve yield 1%                    |                     0.500858 |             -52.8072 |                      494 |                                  383 |                  | True                          | not_promoted: constant yield proxy lacks accepted real source    |
| Stage077 | constant_cash_yield_proxy       | cash_yield_proxy | C9 15w + idle reserve yield 2%                    |                     0.501765 |             -52.7002 |                      485 |                                  383 |                  | True                          | not_promoted: constant yield proxy lacks accepted real source    |
| Stage077 | constant_cash_yield_proxy       | cash_yield_proxy | C9 15w + idle reserve yield 3%                    |                     0.502721 |             -52.5903 |                      479 |                                  288 |                  | True                          | not_promoted: constant yield proxy lacks accepted real source    |
| Stage077 | constant_cash_yield_proxy       | cash_yield_proxy | C9 15w + idle reserve yield 5%                    |                     0.504794 |             -52.3615 |                      389 |                                  255 |                  | True                          | not_promoted: constant yield proxy lacks accepted real source    |
| Stage078 | real_cash_yield_source_audit    | source_audit     | C9 15w + SHIBOR O/N benchmark                     |                     0.501414 |             -52.7405 |                      485 |                                  383 |                  | True                          | not_promoted: no accepted real cash source                       |
| Stage078 | real_cash_yield_source_audit    | source_audit     | C9 15w + Money fund 000009 actual income sample   |                     0.501517 |             -52.7039 |                      485 |                                  383 |                  | True                          | not_promoted: no accepted real cash source                       |
| Stage078 | real_cash_yield_source_audit    | source_audit     | C9 15w + CFETS deposit repo fixing FDR001 history |                     0.501416 |             -52.7406 |                      485 |                                  383 |                  | True                          | not_promoted: no accepted real cash source                       |
| Stage081 | fixed_money_fund_basket         | cash_yield_proxy | C9 15w + fixed 12 money fund basket               |                     0.501535 |             -52.7051 |                      485 |                                  383 |                  | True                          | not_promoted: weak account-level cash basket proxy               |
| Stage082 | conservative_money_fund_basket  | cash_yield_proxy | C9 15w + conservative fixed money fund basket     |                     0.50149  |             -52.7119 |                      485 |                                  383 | True             | True                          | not_promoted: conservative basket still aggregate/weak           |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | Stage082 base conservative                        |                     0.50149  |             -52.7119 |                      485 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | T+1 income delay                                  |                     0.501489 |             -52.7121 |                      485 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | T+2 income delay                                  |                     0.501489 |             -52.7122 |                      485 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | 25bp annual yield haircut                         |                     0.501259 |             -52.7393 |                      485 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | 50bp annual yield haircut                         |                     0.501031 |             -52.7665 |                      488 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | 100bp annual yield haircut                        |                     0.500587 |             -52.8201 |                      498 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | T+1 delay + 50bp haircut                          |                     0.501031 |             -52.7667 |                      489 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage083 | money_fund_friction_sensitivity | cash_yield_proxy | T+1 delay + 100bp haircut                         |                     0.500587 |             -52.8202 |                      498 |                                  383 | True             | True                          | not_promoted: friction pass only under light cost and edge thin  |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Stage082 base conservative                        |                     0.50149  |             -52.7119 |                      485 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Business-day T+1 delay                            |                     0.501489 |             -52.7121 |                      485 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Business-day T+2 delay                            |                     0.501486 |             -52.7126 |                      485 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Business T+1 + 100bp haircut negative allowed     |                     0.500587 |             -52.8202 |                      498 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Business T+1 + 100bp haircut floor0               |                     0.500616 |             -52.8167 |                      498 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |
| Stage084 | businessday_nonnegative_haircut | cash_yield_proxy | Business T+2 + 100bp haircut floor0               |                     0.500615 |             -52.817  |                      498 |                                  383 | True             | True                          | not_promoted: business-day/floor0 confirms weak account layer    |

## 结论

- 决策：`stage085_cash_account_overlay_closed_no_promotion_switch_to_structural_sleeve_or_true_exposure_attribution`。
- 汇总候选行：`63`；账户层通过行：`25`；真实引擎通过行：`0`。
- 关键判断：Stage074 proxy 的通过已经被 Stage075 true engine 否定；Stage077-084 是现金收益/货基储备账户层，不改变 C9 信号和持仓 alpha；Stage084 独立审查确认无统计 bug 但边际过线，不适合晋级。
- 下一步：停止现金/account overlay 救参；若仍关心实盘资金体验，单独做真实渠道申赎/流动性验收；若继续策略目标，应转向结构性独立收益腿或真实暴露归因。

## 独立 agent review

- 审查结论：Stage085 的“不晋级、关闭 cash/account overlay 路线”基本成立；置信度 `0.88`。
- 复算确认：`Stage073 6/0`、`Stage074 18/2`、`Stage075 1/0`、`Stage076 6/0`、`Stage077 5/4`、`Stage078 4/3`、`Stage081 1/1`、`Stage082 1/1`、`Stage083 11/8`、`Stage084 10/6`，合计候选 `63`、passing `25`、true engine passing `0`。
- 严重问题：无。
- 中等 caveat：Stage085 标题说汇总 Stage073-084，但候选 inventory 不含 Stage079/080；原因是 Stage079/080 是现金源状态/申购字段 gate，不是 variant_summary 候选表，不影响“无晋级”结论。
- 中等 caveat：`computed_account_level_pass` 对 `0.5` 未加浮点容忍，导致 Stage074 两个 proxy 主要靠 `published_pass=True` 进入 passing；总数正确，但后续可把 `pass_count` 命名为 `account_numeric_pass_count` 降低误读。
- 低级 caveat：`pass_count` 容易被误读成“策略通过”；这里只代表账户数值层通过，不是策略晋级。
- 独立结论：Stage074 proxy pass 已被 Stage075 true engine 否定；Stage077-084 的 pass 只是账户层/来源审计，不改变 C9 信号、持仓 alpha、整数手和保证金路径；Stage085 收束结论被证据支持。

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/滑点/交易次数/胜率：本阶段不新增回测，只汇总既有 Stage073-084 结果；详见 inventory 和各原 stage。

## 过拟合反思

- 运行前：否。只读汇总冻结结果，不新增阈值或按窗口救参。
- 运行后：否。结论是收束现金路线；继续换基金、篮子大小、补款频率或通过门槛才会过拟合。

## 继续价值反思

- 运行前：有。必须先把弱路线收束，避免继续在账户展示层消耗时间。
- 运行后：有，但方向切换。现金路线不值得继续作为策略晋级方向；结构性 sleeve/真实暴露归因仍值得做。

## 输出

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage085_cash_overlay_route_closure_audit/rebuilt_c9_v2_stage085_cash_overlay_route_closure_audit_report_stage085_cash_overlay_route_closure_audit_v1.md`
- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage085_cash_overlay_route_closure_audit/rebuilt_c9_v2_stage085_cash_overlay_route_closure_audit_candidate_inventory_stage085_cash_overlay_route_closure_audit_v1.csv`
- passing：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage085_cash_overlay_route_closure_audit/rebuilt_c9_v2_stage085_cash_overlay_route_closure_audit_passing_but_not_promoted_stage085_cash_overlay_route_closure_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage085_cash_overlay_route_closure_audit/rebuilt_c9_v2_stage085_cash_overlay_route_closure_audit_decision_stage085_cash_overlay_route_closure_audit_v1.json`
