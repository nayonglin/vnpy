# Stage185 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 06:07 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage185_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `get_tick_serial` / `DataDownloader` 文档确认 tick/K 线历史数据可用于回放和数据工程，但 serial 长度、速度和 timeout 必须用实际覆盖验收，不能假设 14 天请求天然完整。
- pandas `rolling` 文档强调窗口端点与边界定义会影响可见数据；本线继续把 `bar_end_ts <= decision_ts` 作为唯一特征可见边界。
- IBM data leakage 资料强调训练/预测时不可见的未来数据不能进入特征；本阶段继续由 Stage179 阻断 direct normalized feature use，并由 Stage180 物理裁剪 post-decision bar。
- vn.py `BarGenerator` 的 tick 聚合语义使用非负 tick 增量更新 volume/turnover；本阶段继续沿用 Stage178/Stage164 的相同聚合纪律。
- 判断结论：当前仍不是规则设计阶段。Stage185 首次把本轮前置 lookback 扩展从纯右尾优先样本推进到 right-tail/bottom-loss/maxDD 混合覆盖，继续扩大点时化安全源，比尝试分钟规则更稳健。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage185_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage185_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage185 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `16` 个扩到 `20` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE185_MAX_REQUESTS=4` 默认小批量。
  - `STAGE185_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE185_TICK_DATA_LENGTH=10000`。
  - `STAGE185_MIN_NORMALIZED_ROWS=61`。
  - `STAGE185_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage185 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,173,731`
- normalized rows：`11,901`
- positive-volume rows：`11,901`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`2,260`
- 最多观测 predecision closed bars：`3,460`
- target minimum bars：`61`
- selected right-tail windows：`2`
- selected bottom-loss windows：`2`
- selected maxDD windows：`1`
- selected low-resolution windows：`0`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | tick_fetch_status | raw_tick_rows | normalized_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0002_AP505_CZCE_20250328` | `AP505.CZCE` | `extracted` | `217,552` | `2,261` | `1` | `2,260` | `3` |
| `stage177_req_0015_au2510_SHFE_20250902` | `au2510.SHFE` | `timeout` | `374,909` | `3,184` | `1` | `3,184` | `3` |
| `stage177_req_0021_OI205_CZCE_20220105` | `OI205.CZCE` | `extracted` | `333,783` | `2,995` | `1` | `2,994` | `3` |
| `stage177_req_0025_jm2301_DCE_20221130` | `jm2301.DCE` | `extracted` | `247,487` | `3,461` | `1` | `3,460` | `3` |

说明：`au2510` 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`20`
  - proof/hash/schema/identity ready：`20/20`
  - cutoff coverage pass：`20/20`
  - filtered request ready：`20`
  - direct file request ready：`7`
  - post-decision bars：`13`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`20`
  - cutoff-filtered source ready：`20`
  - filtered source rows：`57,757`
  - positive-volume rows：`57,728`
  - post-decision removed：`13`
  - lineage pass：`20/20`
- Stage181：
  - feature audit rows：`20`
  - feature readiness rows：`200`
  - ready cells：`200/200`
  - cutoff guard：`20/20`
  - lineage pass：`20/20`
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

- Stage185 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage185 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `13` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `20 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`volume_participation_30m` 仍集中在 `0.966667-1.000000`，继续只当数据质量诊断观察，不作为交易 alpha 或风险区分字段。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`，mean `0.000949`
- `range_ratio_1m`：min `0.000000`，max `0.002718`，mean `0.000524`
- `directional_efficiency_30m`：min `0.033175`，max `0.347518`，mean `0.149608`
- `realized_volatility_30m`：min `0.000156`，max `0.002729`，mean `0.000882`
- `true_range_median_30m`：min `0.160000`，max `15.000000`，mean `5.092000`
- `volume_participation_30m`：min `0.966667`，max `1.000000`，mean `0.998333`
- `volume_zscore_60m`：min `-0.590071`，max `0.478178`，mean `0.086242`
- `open_interest_delta_60m`：min `-22,709`，max `5,815`，mean `-2,930.200000`
- `turnover_vwap_gap_30m`：min `-0.005875`，max `0.012208`，mean `0.000175`
- `closed_bar_count_coverage`：min `1,130`，max `3,492`，mean `2,887.850000`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `16` 扩到 `20`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage186 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
