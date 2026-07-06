# Stage079 cash source status gate

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:20:33
- 阶段性质：现金收益源当前状态/限额只读验收
- 是否重要突破：否，000009 状态仍需交易渠道确认

## 外部调研与判断

- 货币基金可以作为账户层现金收益源候选，但必须通过当前可申购、可赎回、额度足够、历史收益可重放和真实账户可买的验收。
- 本阶段不把单一基金历史收益当 alpha，不改 C9，不连接 CTP，不触发订单。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage079_cash_source_status_gate.py`
- 新增参数：`TARGET_FUND_CODE=000009`、`RESERVE_CAPITAL=150000.0`、`MIN_CURRENT_7D_YIELD_PCT=1.0`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Status Sources

| source_id                            | asof_hint   | purchase_status_raw   | redeem_status_raw   | open_purchase_flag   | open_redeem_flag   | limit_large_flag   |   limit_amount_yuan |   current_7d_yield_pct | fee_raw   | source_confidence   | source_url                                       |
|:-------------------------------------|:------------|:----------------------|:--------------------|:---------------------|:-------------------|:-------------------|--------------------:|-----------------------:|:----------|:--------------------|:-------------------------------------------------|
| akshare_fund_money_fund_daily_em     | 2026-07-03  | 购买                  |                     | True                 |                    | False              |                 nan |                  0.864 | 0费率     | medium              | https://fund.eastmoney.com/HBJJ_pjsyl.html       |
| akshare_fund_money_fund_info_em_tail | 2026-07-04  | 暂停申购              | 开放赎回            | False                | True               | False              |                 nan |                  0.863 |           | medium_low          | https://fundf10.eastmoney.com/jjjz_000009.html   |
| eastmoney_fundf10                    | 2026-07-05  | 开放申购              | 开放赎回            | True                 | True               | False              |                 nan |                nan     | 0.00%     | medium_high         | https://fundf10.eastmoney.com/000009.html        |
| eastmoney_jjgg                       | 2026-07-05  | 开放申购              | 开放赎回            | True                 | True               | False              |                 nan |                nan     | 0.00%     | medium_high         | https://fundf10.eastmoney.com/jjgg_000009_5.html |
| efunds_official                      | 2026-07-05  | 购买入口可见          |                     | True                 |                    | False              |                 nan |                nan     | 0.00%     | medium              | https://www.efunds.com.cn/fund/000009.shtml      |

## 当前候选池

- 初筛候选数：`340`
- 条件：成立早于 `2020-01-01`、0费率、当前可购、最新 7日年化不低于 `1%`。
- 样例：

|   fund_code | fund_name           | inception_date   |   latest_7d_yield_pct | fee_raw   | purchase_raw   | latest_yield_column   |
|------------:|:--------------------|:-----------------|----------------------:|:----------|:---------------|:----------------------|
|      260102 | 景顺货币A           | 2003-10-24       |                 1.01  | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      290001 | 泰信天天收益货币A   | 2004-02-10       |                 2.087 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      202301 | 南方现金增利货币A   | 2004-03-05       |                 1.101 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      180009 | 银华货币B           | 2005-01-31       |                 1.124 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      110006 | 易方达货币A         | 2005-02-02       |                 1.052 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      070008 | 嘉实货币A           | 2005-03-18       |                 1.002 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      240007 | 华宝现金宝货币B     | 2005-03-31       |                 1.073 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      288101 | 华夏货币A           | 2005-04-20       |                 1.07  | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      270004 | 广发货币A           | 2005-05-20       |                 1.051 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      091005 | 大成货币B           | 2005-06-03       |                 1.204 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      163802 | 中银货币A           | 2005-06-07       |                 1.094 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      020007 | 国泰货币A           | 2005-06-21       |                 1.051 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      162206 | 宏利货币A           | 2005-11-10       |                 1.122 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      080011 | 长盛货币A           | 2005-12-12       |                 1.056 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519588 | 交银货币A           | 2006-01-20       |                 1.069 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519518 | 汇添富货币A         | 2006-03-23       |                 1.057 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      530002 | 建信货币A           | 2006-04-25       |                 1.106 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      340005 | 兴全货币A           | 2006-04-27       |                 1.069 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519508 | 万家货币A           | 2006-05-24       |                 1.076 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      310338 | 申万菱信收益宝货币A | 2006-07-07       |                 1.025 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      110016 | 易方达货币B         | 2006-07-18       |                 1.294 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519506 | 海富通货币B         | 2006-08-01       |                 1.046 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      400005 | 东方金账簿货币A     | 2006-08-02       |                 1.281 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      100028 | 富国天时货币B       | 2006-11-29       |                 1.168 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519517 | 汇添富货币B         | 2007-05-22       |                 1.3   | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      519589 | 交银货币B           | 2007-06-22       |                 1.311 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      270014 | 广发货币B           | 2009-04-20       |                 1.294 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      460106 | 华泰柏瑞货币B       | 2009-05-06       |                 1.098 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      213909 | 宝盈货币B           | 2009-08-05       |                 1.118 | 0费率     | 购买           | 2026-07-03-7日年化%   |
|      217014 | 招商现金增值货币B   | 2009-12-01       |                 1.02  | 0费率     | 购买           | 2026-07-03-7日年化%   |

## 结论

- 决策：`stage079_cash_source_status_conflict_needs_channel_confirmation`。
- 回测指标：本阶段不回测，不新增订单，因此无期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。
- 运行前过拟合反思：否。验收当前状态和限额是 Stage078 的必要外部状态确认，不按历史坏窗口挑收益率。
- 运行后过拟合反思：否。状态源冲突时不直接 accepted；后续若按当前最高收益率挑单只基金，就是过拟合/选择偏差。
- 继续价值：有。下一步应固定非收益排序的候选篮子或确认真实交易渠道，再做历史收益回放。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage079_cash_source_status_gate/rebuilt_c9_v2_stage079_cash_source_status_gate_report_stage079_cash_source_status_gate_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage079_cash_source_status_gate/rebuilt_c9_v2_stage079_cash_source_status_gate_decision_stage079_cash_source_status_gate_v1.json`
- status_sources：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage079_cash_source_status_gate/rebuilt_c9_v2_stage079_cash_source_status_gate_status_sources_stage079_cash_source_status_gate_v1.csv`
- candidate_pool：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage079_cash_source_status_gate/rebuilt_c9_v2_stage079_cash_source_status_gate_current_money_fund_candidate_pool_stage079_cash_source_status_gate_v1.csv`
