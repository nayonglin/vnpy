# Stage193 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 08:34 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage193_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `TqBacktest`/`get_tick_serial` 文档显示历史 tick serial 回放可作为数据工程入口，但回测模式下行情推进和序列长度约束需要用实际落盘覆盖验收。
- TqSdk `DataDownloader` 文档显示批量下载可作为备选数据路径，但权限、完整性和状态仍需独立 proof；本阶段继续使用已验证能产出正成交量的 tick 聚合链路。
- pandas `rolling` 文档确认窗口端点会影响 rolling 特征；本阶段继续执行 `bar_end_ts <= decision_ts` 的点时化边界。
- vn.py `BarGenerator` 源码体现 tick 到 bar 聚合要处理 volume/turnover/open_interest，而不是只看价格；Stage193 沿用 Stage178/Stage164 的同一聚合纪律。
- 判断结论：Stage193 仍是数据底座扩展，不是规则设计。`maxDD` 与 `low_resolution` 只是 Stage177 覆盖义务，不能交易化。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage193_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage193_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage193 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `48` 个扩到 `52` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE193_MAX_REQUESTS=4` 默认小批量。
  - `STAGE193_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE193_TICK_DATA_LENGTH=10000`。
  - `STAGE193_MIN_NORMALIZED_ROWS=61`。
  - `STAGE193_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage193 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`873,011`
- normalized rows：`9,259`
- positive-volume rows：`9,259`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`1,610`
- 最多观测 predecision closed bars：`3,128`
- target minimum bars：`61`
- selected right-tail windows：`0`
- selected bottom-loss windows：`0`
- selected maxDD windows：`4`
- selected low-resolution windows：`2`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | exchange | tick_fetch_status | raw_tick_rows | normalized_rows | positive_volume_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0037_AP210_CZCE_20220825` | `AP210.CZCE` | `CZCE` | `extracted` | `207,422` | `2,261` | `2,261` | `1` | `2,260` | `3` |
| `stage177_req_0047_lh2301_DCE_20221209` | `lh2301.DCE` | `DCE` | `extracted` | `103,057` | `2,259` | `2,259` | `1` | `2,258` | `3` |
| `stage177_req_0050_fu2305_SHFE_20230131` | `fu2305.SHFE` | `SHFE` | `extracted` | `191,013` | `1,611` | `1,611` | `1` | `1,610` | `3` |
| `stage177_req_0051_fu2305_SHFE_20230214` | `fu2305.SHFE` | `SHFE` | `timeout` | `371,519` | `3,128` | `3,128` | `1` | `3,128` | `3` |

说明：`fu2305.SHFE` 2023-02-14 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`52`
  - proof/hash/schema/identity ready：`52/52`
  - cutoff coverage pass：`52/52`
  - filtered request ready：`52`
  - direct file request ready：`17`
  - post-decision bars：`35`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`52`
  - cutoff-filtered source ready：`52`
  - filtered source rows：`148,200`
  - positive-volume rows：`148,101`
  - post-decision removed：`35`
  - lineage pass：`52/52`
- Stage181：
  - feature audit rows：`52`
  - feature readiness rows：`520`
  - ready cells：`520/520`
  - cutoff guard：`52/52`
  - lineage pass：`52/52`
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

- Stage193 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage193 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `35` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `52 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`directional_efficiency_30m` 均值升至 `0.176548`、`closed_bar_count_coverage` 均值回到 `2,850.000000`，说明本批 maxDD/低分辨率覆盖继续扩展横截面，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.014597`，max `0.013514`，mean `0.000636`
- `range_ratio_1m`：min `0.000000`，max `0.002882`，mean `0.000567`
- `directional_efficiency_30m`：min `0.020408`，max `0.463415`，mean `0.176548`
- `realized_volatility_30m`：min `0.000156`，max `0.002780`，mean `0.000954`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `7.564231`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.995513`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.030076`
- `open_interest_delta_60m`：min `-64,294`，max `25,482`，mean `-4,133.326923`
- `turnover_vwap_gap_30m`：min `-0.011586`，max `0.012208`，mean `0.000728`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,850.000000`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；`maxDD`/`low_resolution` 只代表 Stage177 覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `48` 扩到 `52`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage194 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
