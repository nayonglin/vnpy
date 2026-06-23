# Stage188 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 06:58 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage188_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `get_tick_serial` / `DataDownloader` 文档确认 tick/K 线历史数据可用于回放和数据工程，但 serial 长度、速度和 timeout 必须用实际覆盖验收，不能假设 14 天请求天然完整。
- pandas `rolling` 文档强调窗口端点与边界定义会影响可见数据；本线继续把 `bar_end_ts <= decision_ts` 作为唯一特征可见边界。
- IBM data leakage 资料强调训练/预测时不可见的未来数据不能进入特征；本阶段继续由 Stage179 阻断 direct normalized feature use，并由 Stage180 物理裁剪 post-decision bar。
- vn.py `BarGenerator` 的 tick 聚合语义使用非负 tick 增量更新 volume/turnover；本阶段继续沿用 Stage178/Stage164 的相同聚合纪律。
- 判断结论：当前仍不是规则设计阶段。Stage188 继续补 bottom-loss 与 low-resolution 相关 predecision lookback，扩大负尾覆盖；任何分钟特征都只能作为审计值，不能交易化。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage188_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage188_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage188 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `28` 个扩到 `32` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE188_MAX_REQUESTS=4` 默认小批量。
  - `STAGE188_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE188_TICK_DATA_LENGTH=10000`。
  - `STAGE188_MIN_NORMALIZED_ROWS=61`。
  - `STAGE188_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage188 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,428,990`
- normalized rows：`13,057`
- positive-volume rows：`13,028`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`3,002`
- 最多观测 predecision closed bars：`3,489`
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

| request_id | vt_symbol | tick_fetch_status | raw_tick_rows | normalized_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0023_SH607_CZCE_20260430` | `SH607.CZCE` | `extracted` | `320,173` | `3,490` | `1` | `3,489` | `3` |
| `stage177_req_0026_jm2601_DCE_20251028` | `jm2601.DCE` | `timeout` | `379,897` | `3,207` | `1` | `3,207` | `3` |
| `stage177_req_0033_ru2409_SHFE_20240611` | `ru2409.SHFE` | `extracted` | `354,422` | `3,003` | `1` | `3,002` | `3` |
| `stage177_req_0034_ru2601_SHFE_20251203` | `ru2601.SHFE` | `timeout` | `374,498` | `3,357` | `1` | `3,357` | `3` |

说明：`jm2601` 与 `ru2601` 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`32`
  - proof/hash/schema/identity ready：`32/32`
  - cutoff coverage pass：`32/32`
  - filtered request ready：`32`
  - direct file request ready：`10`
  - post-decision bars：`22`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`32`
  - cutoff-filtered source ready：`32`
  - filtered source rows：`89,527`
  - positive-volume rows：`89,451`
  - post-decision removed：`22`
  - lineage pass：`32/32`
- Stage181：
  - feature audit rows：`32`
  - feature readiness rows：`320`
  - ready cells：`320/320`
  - cutoff guard：`32/32`
  - lineage pass：`32/32`
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

- Stage188 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage188 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `22` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `32 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`true_range_median_30m` 上界扩展到 `30.000000`、`volume_participation_30m` 下界扩展到 `0.866667`，说明 bottom-loss/低分辨率覆盖进入后横截面继续变宽，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`，mean `0.000690`
- `range_ratio_1m`：min `0.000000`，max `0.002718`，mean `0.000453`
- `directional_efficiency_30m`：min `0.033175`，max `0.454545`，mean `0.148545`
- `realized_volatility_30m`：min `0.000156`，max `0.002729`，mean `0.000880`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `6.401250`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.992708`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.052957`
- `open_interest_delta_60m`：min `-33,047`，max `5,815`，mean `-3,109.500000`
- `turnover_vwap_gap_30m`：min `-0.005875`，max `0.012208`，mean `0.000573`
- `closed_bar_count_coverage`：min `1,130`，max `3,492`，mean `2,797.718750`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `28` 扩到 `32`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage189 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
