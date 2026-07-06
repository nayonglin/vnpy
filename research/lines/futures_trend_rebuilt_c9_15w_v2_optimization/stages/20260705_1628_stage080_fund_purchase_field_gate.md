# Stage080 fund purchase field gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:28:07
- 阶段性质：公开销售平台申赎/限额字段验收
- 是否重要突破：否，公开平台通过但仍需用户真实交易渠道确认

## 外部调研与判断

- `fund_purchase_em` 是东方财富/天天基金“基金申购状态”字段，比 Stage079 的网页文本和历史净值状态更适合做当前申赎/限额验收。
- 但公开销售平台字段仍不是用户真实账户可买证明，不能直接接入实盘默认路径。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage080_fund_purchase_field_gate.py`
- 新增参数：`RESERVE_CAPITAL=150000.0`、目标基金 `000009`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Target

|   fund_code | fund_name_purchase   | fund_type       | purchase_status   | redeem_status   |   purchase_min_yuan |   daily_limit_yuan |   fee_pct | public_platform_purchase_field_eligible   |
|------------:|:---------------------|:----------------|:------------------|:----------------|--------------------:|-------------------:|----------:|:------------------------------------------|
|      000009 | 易方达天天理财货币A  | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 | True                                      |

## 结果

- Stage079 初筛候选数：`340`
- 成功 join `fund_purchase_em`：`340`
- 公开平台字段通过候选数：`236`
- 非收益排序篮子样例：按成立日期、基金代码排序取前 `12` 只，不按收益率排序。

|   fund_code | fund_name         | inception_date   |   latest_7d_yield_pct | purchase_status   | redeem_status   |   purchase_min_yuan |   daily_limit_yuan |   fee_pct |
|------------:|:------------------|:-----------------|----------------------:|:------------------|:----------------|--------------------:|-------------------:|----------:|
|      260102 | 景顺货币A         | 2003-10-24       |                 1.01  | 限大额            | 开放赎回        |                  10 |              5e+06 |         0 |
|      202301 | 南方现金增利货币A | 2004-03-05       |                 1.101 | 限大额            | 开放赎回        |                  10 |              2e+06 |         0 |
|      180009 | 银华货币B         | 2005-01-31       |                 1.124 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      110006 | 易方达货币A       | 2005-02-02       |                 1.052 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      070008 | 嘉实货币A         | 2005-03-18       |                 1.002 | 限大额            | 开放赎回        |                  10 |              5e+06 |         0 |
|      288101 | 华夏货币A         | 2005-04-20       |                 1.07  | 限大额            | 开放赎回        |                  10 |              5e+06 |         0 |
|      270004 | 广发货币A         | 2005-05-20       |                 1.051 | 限大额            | 开放赎回        |                  10 |              1e+07 |         0 |
|      091005 | 大成货币B         | 2005-06-03       |                 1.204 | 限大额            | 开放赎回        |                  10 |              5e+07 |         0 |
|      163802 | 中银货币A         | 2005-06-07       |                 1.094 | 限大额            | 开放赎回        |                  10 |              2e+07 |         0 |
|      020007 | 国泰货币A         | 2005-06-21       |                 1.051 | 限大额            | 开放赎回        |                  10 |              1e+06 |         0 |
|      162206 | 宏利货币A         | 2005-11-10       |                 1.122 | 限大额            | 开放赎回        |                  10 |              2e+06 |         0 |
|      519588 | 交银货币A         | 2006-01-20       |                 1.069 | 限大额            | 开放赎回        |                  10 |              5e+06 |         0 |

## 结论

- 决策：`stage080_target_purchase_fields_confirmed_public_platform`。
- 回测指标：本阶段不回测，不新增订单，因此无期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。
- 运行前过拟合反思：否。补申赎/限额字段是可实现性验收，不按历史收益挑选。
- 运行后过拟合反思：否。公开平台通过仍不直接上线，下一步若做历史回放也应使用非收益排序或固定规则篮子。
- 继续价值：有。下一步可对固定篮子做历史每万份收益回放，或先让用户确认真实交易渠道。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage080_fund_purchase_field_gate/rebuilt_c9_v2_stage080_fund_purchase_field_gate_report_stage080_fund_purchase_field_gate_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage080_fund_purchase_field_gate/rebuilt_c9_v2_stage080_fund_purchase_field_gate_decision_stage080_fund_purchase_field_gate_v1.json`
- target_gate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage080_fund_purchase_field_gate/rebuilt_c9_v2_stage080_fund_purchase_field_gate_target_purchase_gate_stage080_fund_purchase_field_gate_v1.csv`
- candidate_gate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage080_fund_purchase_field_gate/rebuilt_c9_v2_stage080_fund_purchase_field_gate_candidate_purchase_gate_stage080_fund_purchase_field_gate_v1.csv`
