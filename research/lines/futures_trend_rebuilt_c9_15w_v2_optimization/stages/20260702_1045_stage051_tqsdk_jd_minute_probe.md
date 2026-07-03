# Stage051 TqSdk jd 分钟线小窗口探针

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:45:09
- 阶段性质：数据源可行性探针；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方参考文档、TqSdk GitHub README、managed futures 研究、PBO 文献。
- 我的判断：当前目标不能靠继续扫可见字段小参数推进；若要复建 Stage208 级真承载，优先确认 TqSdk 是否能补 Stage050 的 jd 分钟缺口。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage051_tqsdk_jd_minute_probe.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe.py`
- 新增参数：`STAGE051_ENABLE_NETWORK_PROBE`、`STAGE051_MAX_SYMBOLS`、`STAGE051_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage051_tqsdk_jd_minute_probe_success_ready_for_limited_gap_download`
- readiness：`ready_for_tqsdk_backtest_probe`
- probe_plan_rows：`1`
- probe_success_contract_count：`1`
- minute_gap_download_ready：`True`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`jd_contract_daily_margin_history`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Readiness

| stage    | readiness                      | module_ready   | credentials_ready   | probe_plan_ready   | network_probe_enabled   |   probe_plan_rows |
|:---------|:-------------------------------|:---------------|:--------------------|:-------------------|:------------------------|------------------:|
| Stage051 | ready_for_tqsdk_backtest_probe | True           | True                | True               | True                    |                 1 |

## Probe Plan

| contract_vt   | product_vt_symbol   | tq_symbol   | request_start_date   | request_end_date   | probe_start_datetime   | probe_end_datetime   |   observed_price_rows | priority                 |
|:--------------|:--------------------|:------------|:---------------------|:-------------------|:-----------------------|:---------------------|----------------------:|:-------------------------|
| jd2604.DCE    | jd.DCE              | DCE.jd2604  | 2026-02-12           | 2026-03-04         | 2026-02-12 21:00:00    | 2026-02-13 09:10:00  |                     9 | P0_jd_true_carry_blocker |

## Probe Status

| contract_vt   | tq_symbol   | probe_start_datetime   | probe_end_datetime   | status    |   rows | first_bar_datetime   | last_bar_datetime   |   elapsed_seconds | raw_path                                                                                                                                                                            | message   |
|:--------------|:------------|:-----------------------|:---------------------|:----------|-------:|:---------------------|:--------------------|------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------|
| jd2604.DCE    | DCE.jd2604  | 2026-02-12 21:00:00    | 2026-02-13 09:10:00  | extracted |     11 | 2026-02-13 09:00:00  | 2026-02-13 09:10:00 |              4.51 | /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/raw_tqsdk_probe/DCE/jd2604_minute_probe.csv |           |

## 过拟合反思

- 运行前判断：否。本阶段只验证缺失数据源能否补齐，不根据收益调参。
- 运行后判断：否。即使分钟探针成功，也只是解除数据层阻塞；仍不创建交易规则。

## 继续价值反思

- 运行前判断：有。Stage050 已把 jd 分钟线列为 Stage208 真承载 P0 阻塞，探针能决定是否进入下载批次。
- 运行后判断：有。若探针成功，下一步补完整 41 个 jd 合约分钟线；若失败，继续转 vendor 或同源回放，避免本地救参。

## 输出文件

- probe_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe_probe_plan_stage051_tqsdk_jd_minute_probe_v1.csv`
- probe_status：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe_probe_status_stage051_tqsdk_jd_minute_probe_v1.csv`
- probe_bars：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe_probe_bars_stage051_tqsdk_jd_minute_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe_decision_stage051_tqsdk_jd_minute_probe_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage051_tqsdk_jd_minute_probe/rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe_report_stage051_tqsdk_jd_minute_probe_v1.md`
