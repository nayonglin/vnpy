# Stage189 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 07:20 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage189_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk API 文档显示 `get_tick_serial` 的序列长度和回放更新机制适合作为 tick 到分钟聚合的数据工程入口，但实际覆盖质量必须由落盘后的 proof/schema/hash/cutoff 验收决定。
- TqSdk `DataDownloader` 文档显示历史下载能力适合批量数据，但权限与运行状态需要独立验证；本线继续沿用已能产出正成交量的 tick 回放聚合路径。
- pandas `rolling` 文档提醒窗口边界会影响特征值；本线继续坚持 `bar_end_ts <= decision_ts`，避免把入场决策后的分钟 K 线混入特征。
- vn.py `BarGenerator` 源码体现 tick 聚合需要处理成交量/成交额增量，不能只看价格；Stage189 继续沿 Stage178/Stage164 的同一聚合纪律。
- 判断结论：当前仍不是规则设计阶段。Stage189 只补 Stage177 剩余 predecision lookback 样本，扩大 bottom-loss/低分辨率覆盖；分钟特征只能作为点时化审计值，不能交易化。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage189_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage189_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage189 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `32` 个扩到 `36` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE189_MAX_REQUESTS=4` 默认小批量。
  - `STAGE189_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE189_TICK_DATA_LENGTH=10000`。
  - `STAGE189_MIN_NORMALIZED_ROWS=61`。
  - `STAGE189_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage189 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,164,821`
- normalized rows：`13,107`
- positive-volume rows：`13,085`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`1,267`
- 最多观测 predecision closed bars：`4,670`
- target minimum bars：`61`
- selected right-tail windows：`0`
- selected bottom-loss windows：`4`
- selected maxDD windows：`0`
- selected low-resolution windows：`1`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | tick_fetch_status | raw_tick_rows | normalized_rows | positive_volume_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0035_ru2605_SHFE_20260127` | `ru2605.SHFE` | `timeout` | `371,639` | `3,206` | `3,206` | `1` | `3,206` | `3` |
| `stage177_req_0036_ru2605_SHFE_20260225` | `ru2605.SHFE` | `extracted` | `145,060` | `1,268` | `1,268` | `1` | `1,267` | `3` |
| `stage177_req_0029_cu2307_SHFE_20230621` | `cu2307.SHFE` | `extracted` | `361,704` | `4,671` | `4,664` | `1` | `4,670` | `3` |
| `stage177_req_0030_cu2502_SHFE_20250103` | `cu2502.SHFE` | `extracted` | `286,418` | `3,962` | `3,947` | `1` | `3,961` | `3` |

说明：`ru2605.SHFE` 2026-01-27 请求的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`36`
  - proof/hash/schema/identity ready：`36/36`
  - cutoff coverage pass：`36/36`
  - filtered request ready：`36`
  - direct file request ready：`11`
  - post-decision bars：`25`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`36`
  - cutoff-filtered source ready：`36`
  - filtered source rows：`102,631`
  - positive-volume rows：`102,533`
  - post-decision removed：`25`
  - lineage pass：`36/36`
- Stage181：
  - feature audit rows：`36`
  - feature readiness rows：`360`
  - ready cells：`360/360`
  - cutoff guard：`36/36`
  - lineage pass：`36/36`
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

- Stage189 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage189 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `25` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `36 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`directional_efficiency_30m` 上界扩展到 `0.463415`、`closed_bar_count_coverage` 上界扩展到 `4,670`，说明本批铜和橡胶样本继续拉宽入场前横截面，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`，mean `0.000627`
- `range_ratio_1m`：min `0.000000`，max `0.002718`，mean `0.000448`
- `directional_efficiency_30m`：min `0.033175`，max `0.463415`，mean `0.167597`
- `realized_volatility_30m`：min `0.000156`，max `0.002729`，mean `0.000825`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `7.773333`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.993519`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.029611`
- `open_interest_delta_60m`：min `-33,047`，max `5,815`，mean `-2,856.305556`
- `turnover_vwap_gap_30m`：min `-0.005875`，max `0.012208`，mean `0.000583`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,850.861111`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `32` 扩到 `36`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage190 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
