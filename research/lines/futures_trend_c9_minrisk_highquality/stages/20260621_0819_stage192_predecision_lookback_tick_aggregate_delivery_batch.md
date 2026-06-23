# Stage192 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 08:19 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage192_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `TqBacktest`/`get_tick_serial` 文档显示历史 tick serial 回放可作为数据工程入口，但回测模式下行情推进和序列长度约束需要用实际落盘覆盖验收。
- TqSdk `DataDownloader` 文档显示批量下载可作为备选数据路径，但权限、完整性和状态仍需独立 proof；本阶段继续使用已验证能产出正成交量的 tick 聚合链路。
- pandas `rolling` 文档确认窗口端点会影响 rolling 特征；本阶段继续执行 `bar_end_ts <= decision_ts` 的点时化边界。
- vn.py `BarGenerator` 源码体现 tick 到 bar 聚合要处理 volume/turnover/open_interest，而不是只看价格；Stage192 沿用 Stage178/Stage164 的同一聚合纪律。
- 判断结论：Stage192 仍是数据底座扩展，不是规则设计。`maxDD` 与 `low_resolution` 只是 Stage177 覆盖义务，不能交易化。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage192_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage192_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage192 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `44` 个扩到 `48` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE192_MAX_REQUESTS=4` 默认小批量。
  - `STAGE192_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE192_TICK_DATA_LENGTH=10000`。
  - `STAGE192_MIN_NORMALIZED_ROWS=61`。
  - `STAGE192_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage192 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,196,767`
- normalized rows：`11,422`
- positive-volume rows：`11,421`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`2,260`
- 最多观测 predecision closed bars：`3,171`
- target minimum bars：`61`
- selected right-tail windows：`0`
- selected bottom-loss windows：`0`
- selected maxDD windows：`4`
- selected low-resolution windows：`1`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | exchange | tick_fetch_status | raw_tick_rows | normalized_rows | positive_volume_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0040_MA305_CZCE_20230104` | `MA305.CZCE` | `CZCE` | `extracted` | `354,404` | `2,995` | `2,995` | `1` | `2,994` | `3` |
| `stage177_req_0046_lh2301_DCE_20221123` | `lh2301.DCE` | `DCE` | `extracted` | `110,365` | `2,261` | `2,260` | `1` | `2,260` | `3` |
| `stage177_req_0054_rb2305_SHFE_20230112` | `rb2305.SHFE` | `SHFE` | `extracted` | `356,711` | `2,995` | `2,995` | `1` | `2,994` | `3` |
| `stage177_req_0041_MA305_CZCE_20230118` | `MA305.CZCE` | `CZCE` | `timeout` | `375,287` | `3,171` | `3,171` | `1` | `3,171` | `3` |

说明：`MA305.CZCE` 2023-01-18 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`48`
  - proof/hash/schema/identity ready：`48/48`
  - cutoff coverage pass：`48/48`
  - filtered request ready：`48`
  - direct file request ready：`16`
  - post-decision bars：`32`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`48`
  - cutoff-filtered source ready：`48`
  - filtered source rows：`138,944`
  - positive-volume rows：`138,845`
  - post-decision removed：`32`
  - lineage pass：`48/48`
- Stage181：
  - feature audit rows：`48`
  - feature readiness rows：`480`
  - ready cells：`480/480`
  - cutoff guard：`48/48`
  - lineage pass：`48/48`
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

- Stage192 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage192 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `32` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `48 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`bar_return_1m` 下界扩展到 `-0.014597`、`open_interest_delta_60m` 扩展为 `-64,294` 到 `25,482`，说明 maxDD 覆盖继续拉宽入场前横截面，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.014597`，max `0.013514`，mean `0.000492`
- `range_ratio_1m`：min `0.000000`，max `0.002882`，mean `0.000561`
- `directional_efficiency_30m`：min `0.020408`，max `0.463415`，mean `0.170269`
- `realized_volatility_30m`：min `0.000156`，max `0.002780`，mean `0.000928`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `7.382083`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.995139`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.026807`
- `open_interest_delta_60m`：min `-64,294`，max `25,482`，mean `-4,183.604167`
- `turnover_vwap_gap_30m`：min `-0.011586`，max `0.012208`，mean `0.000675`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,894.666667`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；`maxDD`/`low_resolution` 只代表 Stage177 覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `44` 扩到 `48`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage193 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
