# Stage184 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 05:49 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage184_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `get_tick_serial` / `DataDownloader` 文档确认 tick/K 线历史数据可用于回放和数据工程，但 serial 长度、速度和 timeout 必须用实际覆盖验收，不能假设 14 天请求天然完整。
- pandas `rolling` 文档强调窗口端点与边界定义会影响可见数据；本线继续把 `bar_end_ts <= decision_ts` 作为唯一特征可见边界。
- IBM data leakage 资料强调训练/预测时不可见的未来数据不能进入特征；本阶段继续由 Stage179 阻断 direct normalized feature use，并由 Stage180 物理裁剪 post-decision bar。
- vn.py `BarGenerator` 的 tick 聚合语义使用非负 tick 增量更新 volume/turnover；本阶段继续沿用 Stage178/Stage164 的相同聚合纪律。
- 判断结论：当前还没到规则设计阶段。继续扩样本、验收 proof/hash/schema/cutoff、扩大点时化安全源，比尝试分钟规则更本质，也更不容易过拟合。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage184_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage184_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage184 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `12` 个扩到 `16` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE184_MAX_REQUESTS=4` 默认小批量。
  - `STAGE184_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE184_TICK_DATA_LENGTH=10000`。
  - `STAGE184_MIN_NORMALIZED_ROWS=61`。
  - `STAGE184_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage184 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,237,676`
- normalized rows：`11,604`
- positive-volume rows：`11,594`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`2,260`
- 最多观测 predecision closed bars：`3,492`
- target minimum bars：`61`
- selected right-tail windows：`4`
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
| `stage177_req_0008_SM205_CZCE_20220303` | `SM205.CZCE` | `extracted` | `181,654` | `2,261` | `1` | `2,260` | `3` |
| `stage177_req_0011_jm2509_DCE_20250709` | `jm2509.DCE` | `timeout` | `373,823` | `3,192` | `1` | `3,192` | `3` |
| `stage177_req_0014_au2412_SHFE_20241017` | `au2412.SHFE` | `timeout` | `370,447` | `3,492` | `1` | `3,492` | `3` |
| `stage177_req_0005_OI309_CZCE_20230628` | `OI309.CZCE` | `extracted` | `311,752` | `2,659` | `1` | `2,658` | `3` |

说明：`jm2509` 与 `au2412` 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`16`
  - proof/hash/schema/identity ready：`16/16`
  - cutoff coverage pass：`16/16`
  - filtered request ready：`16`
  - direct file request ready：`6`
  - post-decision bars：`10`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`16`
  - cutoff-filtered source ready：`16`
  - filtered source rows：`45,859`
  - positive-volume rows：`45,830`
  - post-decision removed：`10`
  - lineage pass：`16/16`
- Stage181：
  - feature audit rows：`16`
  - feature readiness rows：`160`
  - ready cells：`160/160`
  - cutoff guard：`16/16`
  - lineage pass：`16/16`
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

- Stage184 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage184 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `10` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `16 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`volume_participation_30m` 已从此前全 `1.0` 扩展为 `0.966667-1.000000`，但仍主要是数据质量/流动性诊断，不作为交易 alpha 或风险区分字段。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`，mean `0.000974`
- `range_ratio_1m`：min `0.000000`，max `0.002718`，mean `0.000452`
- `directional_efficiency_30m`：min `0.033175`，max `0.308824`，mean `0.141072`
- `realized_volatility_30m`：min `0.000215`，max `0.002729`，mean `0.000947`
- `true_range_median_30m`：min `0.160000`，max `15.000000`，mean `5.260000`
- `volume_participation_30m`：min `0.966667`，max `1.000000`，mean `0.997917`
- `volume_zscore_60m`：min `-0.590071`，max `0.478178`，mean `0.031008`
- `open_interest_delta_60m`：min `-22,709`，max `5,815`，mean `-2,986.125000`
- `turnover_vwap_gap_30m`：min `-0.005875`，max `0.012208`，mean `0.000211`
- `closed_bar_count_coverage`：min `1,130`，max `3,492`，mean `2,866.187500`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `12` 扩到 `16`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage185 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
