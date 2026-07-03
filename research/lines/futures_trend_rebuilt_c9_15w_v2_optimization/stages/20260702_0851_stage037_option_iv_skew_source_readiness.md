# Stage037 期权 IV/skew 数据源 readiness 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:51:46
- 阶段性质：只读数据源能力/覆盖/小探针审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 期权基础和 DataDownloader 文档、AKShare 期权数据文档、Ricequant options greeks 文档、商品期权 implied skew/IV 与商品收益相关论文、CME CVOL skew 文章。
- 我的判断：期权 IV/skew 是比当前 OI/分钟线更不同的信息层，可能服务于“AI 选品/高质量信号确认”；但必须先有 2018-2026 连续 PIT 期权链，不能把计算函数或单日接口当成特征。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage037_option_iv_skew_source_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage037_option_iv_skew_source_readiness.py`
- 新增参数：`STAGE037_ENABLE_NETWORK_PROBE=1`、`STAGE037_PROBE_TIMEOUT_SECONDS=18`、`STAGE037_MAX_PROBES=4`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage037_option_iv_skew_sources_not_rule_ready_data_contract_required`
- best_next_direction：`build_or_import_pit_option_chain_history_before_signal`
- source_count：`5`
- schema_ready_source_count：`0`
- immediate_strategy_candidate_count：`0`
- target_product_count：`14`
- target_products_with_listed_option：`12`
- target_products_without_listed_option：`2`
- AKShare successful probes：`3/4`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Source readiness

| source_id                     | source_status                                    |   priority_score | rule_candidate_allowed   | blocking_reasons                                                                                          | recommended_next_action                                       |
|:------------------------------|:-------------------------------------------------|-----------------:|:-------------------------|:----------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------|
| tqsdk_tafunc                  | compute_only_no_pit_history                      |               40 | False                    | no_historical_chain,incomplete_target_product_coverage                                                    | acquire_historical_option_chain_before_iv_skew_signal         |
| tqsdk_data_downloader         | permission_unverified_history_downloader_no_rule |               50 | False                    | incomplete_target_product_coverage,no_continuous_2018_2026_history,history_download_permission_unverified | verify_historical_download_permission_on_small_option_chain   |
| akshare_exchange_option_daily | partial_public_endpoint_probe_no_rule            |               60 | False                    | no_verified_pit_timestamp,incomplete_target_product_coverage,no_continuous_2018_2026_history              | build_full_pit_history_schema_hash_and_coverage_before_signal |
| rqdatac_options               | credential_missing_no_probe                      |               45 | False                    | incomplete_target_product_coverage,no_continuous_2018_2026_history,credentials_missing                    | configure_datafeed_credentials_before_history_probe           |
| vnpy_optionmaster             | missing_dependency                               |                5 | False                    | module_not_available,incomplete_target_product_coverage                                                   | install_or_enable_dependency_before_probe                     |

## Target coverage

| target_product   | option_symbol_name   | has_listed_option   | coverage_blocking_reason                                      |
|:-----------------|:---------------------|:--------------------|:--------------------------------------------------------------|
| SA.CZCE          | 纯碱期权             | True                |                                                               |
| si.GFEX          | 工业硅               | True                |                                                               |
| FG.CZCE          | 玻璃期权             | True                |                                                               |
| MA.CZCE          | 甲醇期权             | True                |                                                               |
| OI.CZCE          | 菜籽油期权           | True                |                                                               |
| jm.DCE           | 焦煤期权             | True                |                                                               |
| AP.CZCE          | 苹果期权             | True                |                                                               |
| rb.SHFE          | 螺纹钢期权           | True                |                                                               |
| fu.SHFE          | 燃料油期权           | True                |                                                               |
| SM.CZCE          | 锰硅期权             | True                |                                                               |
| ru.SHFE          | 橡胶期权             | True                |                                                               |
| SH.CZCE          | 烧碱期权             | True                |                                                               |
| lh.DCE           |                      | False               | no_listed_commodity_option_or_not_verified_for_target_product |
| jd.DCE           |                      | False               | no_listed_commodity_option_or_not_verified_for_target_product |

## Probe results

| probe_id                    | function_name    | kwargs                                           | probe_scope                                   | status   |   rows |   column_count | columns                                                                                                                      | error_type      | error_message                             | head_json                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|:----------------------------|:-----------------|:-------------------------------------------------|:----------------------------------------------|:---------|-------:|---------------:|:-----------------------------------------------------------------------------------------------------------------------------|:----------------|:------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| akshare_dce_option_hist_m   | option_hist_dce  | {"symbol": "豆粕期权", "trade_date": "20240603"} | DCE commodity option daily chain price/OI     | error    |      0 |              0 |                                                                                                                              | JSONDecodeError | Expecting value: line 1 column 1 (char 0) | []                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| akshare_czce_option_hist_ma | option_hist_czce | {"symbol": "甲醇期权", "trade_date": "20240603"} | CZCE commodity option daily chain price/OI    | ok       |    220 |             16 | 合约代码,昨结算,今开盘,最高价,最低价,今收盘,今结算,涨跌1,涨跌2,成交量(手),持仓量,增减量,成交额(万元),DELTA,隐含波动率,行权量 |                 |                                           | [{"合约代码": "MA407C2050", "昨结算": "605.0", "今开盘": "0.0", "最高价": "0.0", "最低价": "0.0", "今收盘": "0.0", "今结算": "543.0", "涨跌1": "-62.0", "涨跌2": "-62.0", "成交量(手)": "0.0", "持仓量": "0.0", "增减量": "0.0", "成交额(万元)": "0.0", "DELTA": "1.0", "隐含波动率": "27.93", "行权量": "0.0"}, {"合约代码": "MA407C2075", "昨结算": "580.0", "今开盘": "0.0", "最高价": "0.0", "最低价": "0.0", "今收盘": "0.0", "今结算": "518.0", "涨跌1": "-62.0", "涨跌2": "-62.0", "成交量(手)": "0.0", "持仓量": "0.0", "增减量": "0.0", "成交额(万元)": "0.0", "DELTA": "1.0", "隐含波动率": "27.44", "行权量": "0.0"}] |
| akshare_shfe_option_vol_cu  | option_vol_shfe  | {"symbol": "铜期权", "trade_date": "20250418"}   | SHFE official option implied volatility table | ok       |     12 |              7 | 合约系列,成交量,持仓量,持仓量变化,成交额,行权量,隐含波动率                                                                   |                 |                                           | [{"合约系列": "cu2505", "成交量": "94812", "持仓量": "75036", "持仓量变化": "-1626", "成交额": "12057.48", "行权量": "423", "隐含波动率": "0.210198"}, {"合约系列": "cu2506", "成交量": "11613", "持仓量": "31132", "持仓量变化": "694", "成交额": "3638.59", "行权量": "0", "隐含波动率": "0.21719"}]                                                                                                                                                                                                                                                                                                                           |
| akshare_gfex_option_vol_si  | option_vol_gfex  | {"symbol": "工业硅", "trade_date": "20230724"}   | GFEX official option implied volatility table | ok       |      7 |              2 | 合约系列,隐含波动率                                                                                                          |                 |                                           | [{"合约系列": "si2309", "隐含波动率": "31.744937"}, {"合约系列": "si2310", "隐含波动率": "27.111583"}]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

## 过拟合反思

- 运行前判断：否。Stage037 只审计期权 IV/skew 数据源能力和覆盖，不回测收益、不选择阈值、不新增交易规则。
- 运行后判断：否。即使 public endpoint 探针成功，也保持 data-first；若用单日接口成功直接写 IV/skew 规则才是过拟合。

## 继续价值反思

- 运行前判断：有。Stage036 后资金层细调价值低，期权 IV/skew 是少数真正不同信息层，值得先验证数据合同。
- 运行后判断：有，但下一步价值取决于是否能导入连续 PIT 期权链；如果拿不到历史链，就不能沿这条路线做信号优化。

## 输出文件

- source_readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_source_readiness_stage037_option_iv_skew_source_readiness_v1.csv`
- target_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_target_product_option_coverage_stage037_option_iv_skew_source_readiness_v1.csv`
- akshare_functions：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_akshare_option_functions_stage037_option_iv_skew_source_readiness_v1.csv`
- probes：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_probe_results_stage037_option_iv_skew_source_readiness_v1.csv`
- data_contract：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_data_contract_stage037_option_iv_skew_source_readiness_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_decision_stage037_option_iv_skew_source_readiness_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage037_option_iv_skew_source_readiness/rebuilt_c9_v2_stage037_option_iv_skew_source_readiness_report_stage037_option_iv_skew_source_readiness_v1.md`
