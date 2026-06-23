# Stage182 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 05:08 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage182_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它是 Stage177 前置 lookback 的第二批数据扩展和 Stage179/180/181 刷新，不是收益/回撤策略突破，也不允许接入正式规则。

## 外部调研与判断

- TqSdk `get_tick_serial` 文档确认可以取得 tick serial，但 serial 长度与回放速度需要实测约束；本阶段继续采用小批量，并以实际 `observed_predecision_closed_bar_count` 验收，不假设 14 天请求天然完整。
- TqSdk `DataDownloader` 文档说明 `dur_sec=0` 是 tick 精度下载语义；本阶段仍使用现有 TqBacktest tick 回放链路，输出 raw/normalized/proof 三件套。
- vn.py `BarGenerator` 源码说明 tick -> 1m bar 聚合需要严格处理成交量/成交额增量；本阶段继续复用 Stage164/178 既有聚合 helper。
- 判断结论：当前最有价值的是扩大 point-in-time minute feature 的样本覆盖，不是把 priority、交易所、年份、产品或 high-quality 样本写成规则。Stage182 只做数据交付与泄漏闸门刷新。

## 本次改动

- 修改 `stage178_predecision_lookback_tick_aggregate_delivery_batch.py` 的少量硬编码标题/decision 为可复用常量，逻辑不变。
- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage182_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage182_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage182 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `4` 个扩到 `8` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE182_MAX_REQUESTS=4` 默认小批量。
  - `STAGE182_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE182_TICK_DATA_LENGTH=10000`。
  - `STAGE182_MIN_NORMALIZED_ROWS=61`。
  - `STAGE182_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage182 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`1,221,626`
- normalized rows：`13,468`
- positive-volume rows：`13,461`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`3,128`
- 最多观测 predecision closed bars：`3,470`
- target minimum bars：`61`
- selected right-tail windows：`4`
- selected low-resolution windows：`3`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | tick_fetch_status | raw_tick_rows | normalized_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0004_OI305_CZCE_20230310` | `OI305.CZCE` | `timeout` | `380,797` | `3,402` | `1` | `3,402` | `3` |
| `stage177_req_0010_jm2405_DCE_20240329` | `jm2405.DCE` | `extracted` | `304,270` | `3,471` | `1` | `3,470` | `3` |
| `stage177_req_0017_fu2503_SHFE_20241217` | `fu2503.SHFE` | `timeout` | `372,736` | `3,128` | `1` | `3,128` | `3` |
| `stage177_req_0006_SH405_CZCE_20240326` | `SH405.CZCE` | `extracted` | `163,823` | `3,467` | `1` | `3,466` | `3` |

说明：`timeout` 不是失败放行；它表示 tick 回放达到时间上限后停止，但已抽取到远超 `61` 根决策前闭合 bar 的可验收数据，并通过 proof/hash/schema 和后续 cutoff 过滤。后续仍保持小批量，不把 timeout 样本当作“完整 14 天覆盖”证明。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`8`
  - proof/hash/schema/identity ready：`8/8`
  - cutoff coverage pass：`8/8`
  - filtered request ready：`8`
  - direct file request ready：`3`
  - post-decision bars：`5`
  - 结论：仍必须禁止 direct normalized feature use，只能走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`8`
  - cutoff-filtered source ready：`8`
  - filtered source rows：`25,348`
  - positive-volume rows：`25,341`
  - post-decision removed：`5`
  - lineage pass：`8/8`
- Stage181：
  - feature audit rows：`8`
  - feature readiness rows：`80`
  - ready cells：`80/80`
  - cutoff guard：`8/8`
  - lineage pass：`8/8`
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

- Stage182 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage182 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 5 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 8 行 x 10 特征，全绿。
- Stage181 value heatmap 非空；`volume_participation_30m` 在 8 个样本上仍全为 `1.0`，应继续视为数据质量诊断候选，而不是可交易 alpha/risk 区分字段。

## 特征横截面概览

- `bar_return_1m`：min `-0.000311`，max `0.013514`
- `directional_efficiency_30m`：min `0.048544`，max `0.283582`
- `realized_volatility_30m`：min `0.000395`，max `0.002729`
- `volume_participation_30m`：min/max/mean 全为 `1.000000`
- `open_interest_delta_60m`：min `-22,709`，max `5,815`
- `closed_bar_count_coverage`：min `2,260`，max `3,470`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `4` 扩到 `8`，并完整跑通 Stage179/180/181；但距离 `219` 个 entry decision 还很远，当前仍只是数据/点时化地基，不足以支持规则候选。

## 后续规划

- Stage183 继续按 Stage177 manifest 小批量扩展 predecision lookback，优先保持 priority 和交易所轮转，不人为挑选产品/年份。
- 每批继续复跑 Stage179/180/181；只有覆盖显著扩大后，才定义 audit package -> formal feature table 的闸门。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
