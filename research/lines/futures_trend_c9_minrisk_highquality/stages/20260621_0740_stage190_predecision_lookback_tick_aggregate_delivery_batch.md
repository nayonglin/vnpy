# Stage190 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 07:40 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage190_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `TqApi` 文档显示 `get_tick_serial` 是官方支持的 tick serial 入口，`TqBacktest` 会推进历史行情；因此 tick 回放可以作为分钟 OHLCV 数据工程路径，但不能替代 proof/schema/hash/cutoff 验收。
- TqSdk `DataDownloader` 文档显示历史批量下载是另一条数据路径，但权限和运行结果需要单独验证；本线继续使用已在 Stage164 以后证明能产生正成交量的 tick 聚合链路。
- pandas `rolling` 文档再次提醒窗口端点会直接影响特征值；本阶段继续只允许 `bar_end_ts <= decision_ts` 的决策前闭合 K 线进入 Stage181 审计。
- vn.py `BarGenerator` 源码体现 tick 到 bar 的 volume/turnover 增量处理不是简单价格采样；Stage190 继续沿用 Stage178/Stage164 的聚合纪律。
- 判断结论：Stage190 仍是数据底座扩展，不是规则设计。`maxDD` 和 `low_resolution` 只是 Stage177 覆盖义务，不能被解释为交易筛选条件。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage190_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage190_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage190 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `36` 个扩到 `40` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE190_MAX_REQUESTS=4` 默认小批量。
  - `STAGE190_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE190_TICK_DATA_LENGTH=10000`。
  - `STAGE190_MIN_NORMALIZED_ROWS=61`。
  - `STAGE190_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage190 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,340,381`
- normalized rows：`12,666`
- positive-volume rows：`12,666`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`2,994`
- 最多观测 predecision closed bars：`3,460`
- target minimum bars：`61`
- selected right-tail windows：`0`
- selected bottom-loss windows：`0`
- selected maxDD windows：`4`
- selected low-resolution windows：`4`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | exchange | tick_fetch_status | raw_tick_rows | normalized_rows | positive_volume_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0039_MA209_CZCE_20220613` | `MA209.CZCE` | `CZCE` | `extracted` | `357,549` | `2,995` | `2,995` | `1` | `2,994` | `3` |
| `stage177_req_0044_jm2301_DCE_20220829` | `jm2301.DCE` | `DCE` | `extracted` | `248,416` | `3,461` | `3,461` | `1` | `3,460` | `3` |
| `stage177_req_0049_fu2209_SHFE_20220622` | `fu2209.SHFE` | `SHFE` | `timeout` | `366,801` | `3,093` | `3,093` | `1` | `3,093` | `3` |
| `stage177_req_0042_SA209_CZCE_20220707` | `SA209.CZCE` | `CZCE` | `timeout` | `367,615` | `3,117` | `3,117` | `1` | `3,117` | `3` |

说明：`fu2209.SHFE` 与 `SA209.CZCE` 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`40`
  - proof/hash/schema/identity ready：`40/40`
  - cutoff coverage pass：`40/40`
  - filtered request ready：`40`
  - direct file request ready：`13`
  - post-decision bars：`27`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`40`
  - cutoff-filtered source ready：`40`
  - filtered source rows：`115,295`
  - positive-volume rows：`115,197`
  - post-decision removed：`27`
  - lineage pass：`40/40`
- Stage181：
  - feature audit rows：`40`
  - feature readiness rows：`400`
  - ready cells：`400/400`
  - cutoff guard：`40/40`
  - lineage pass：`40/40`
  - formal feature table rows：`0`
  - strategy feature usable：`0`

## 官方路径指标

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉检查

- Stage190 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage190 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `27` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `40 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`range_ratio_1m` 上界扩展到 `0.002882`、`directional_efficiency_30m` 下界扩展到 `0.020408`，说明 maxDD/低分辨率覆盖进入后横截面继续变宽，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`，mean `0.000607`
- `range_ratio_1m`：min `0.000000`，max `0.002882`，mean `0.000585`
- `directional_efficiency_30m`：min `0.020408`，max `0.463415`，mean `0.163489`
- `realized_volatility_30m`：min `0.000156`，max `0.002729`，mean `0.000877`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `7.446000`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.994167`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.017361`
- `open_interest_delta_60m`：min `-33,047`，max `5,815`，mean `-3,838.375000`
- `turnover_vwap_gap_30m`：min `-0.005875`，max `0.012208`，mean `0.000828`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,882.375000`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；`maxDD`/`low_resolution` 只代表 Stage177 覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `36` 扩到 `40`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage191 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
