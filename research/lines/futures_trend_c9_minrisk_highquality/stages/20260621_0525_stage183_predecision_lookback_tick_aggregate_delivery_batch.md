# Stage183 predecision lookback tick aggregate delivery batch

- 时间：2026-06-21 05:25 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage183_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 是否重要突破版本：否。它继续扩展 Stage177 前置 lookback 样本并刷新 Stage179/180/181，不是策略规则、收益或回撤突破。

## 外部调研与判断

- TqSdk `get_tick_serial` / 历史 tick 能力文档与 TqSdk 项目说明确认，tick 与 K 线历史数据可用于回放和数据工程，但 serial 长度、速度和 timeout 需要用实际覆盖验收，不能假设 14 天请求天然完整。
- pandas `rolling` 文档强调窗口端点由 `closed` / window boundary 决定；本线继续把 `bar_end_ts <= decision_ts` 作为唯一可见边界。
- IBM data leakage 与时间序列泄漏资料强调，预测时不可见的未来数据不能进入特征；本阶段继续由 Stage179 阻断 direct normalized feature use，并由 Stage180 物理裁剪 post-decision bar。
- 判断结论：当前还没到规则设计阶段。继续扩样本和点时化安全源，是比尝试分钟规则更本质、更不容易过拟合的推进方式。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage183_predecision_lookback_tick_aggregate_delivery_batch.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage183_predecision_lookback_tick_aggregate_delivery_batch/`
- 新增 Stage183 输出：summary、selected requests、request run status、delivery audit、window precheck、gate status、report、decision JSON 与 5 张图。
- 刷新 Stage179、Stage180、Stage181 当前输出，使已交付 predecision lookback 样本从 `8` 个扩到 `12` 个。

## 参数变化

- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE183_MAX_REQUESTS=4` 默认小批量。
  - `STAGE183_MAX_SECONDS_TICK=240` 单请求 tick 回放上限。
  - `STAGE183_TICK_DATA_LENGTH=10000`。
  - `STAGE183_MIN_NORMALIZED_ROWS=61`。
  - `STAGE183_MIN_POSITIVE_VOLUME_BARS=60`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## Stage183 交付结果

- 选中请求数：`4`
- 交付成功数：`4`
- 写入文件数：`12/12`
- raw tick rows：`880,655`
- normalized rows：`8,912`
- positive-volume rows：`8,900`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`1,130`
- 最多观测 predecision closed bars：`3,259`
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
| `stage177_req_0007_SM201_CZCE_20210901` | `SM201.CZCE` | `extracted` | `232,282` | `2,261` | `1` | `2,260` | `3` |
| `stage177_req_0012_lh2505_DCE_20250307` | `lh2505.DCE` | `extracted` | `143,956` | `2,261` | `1` | `2,260` | `3` |
| `stage177_req_0018_fu2509_SHFE_20250807` | `fu2509.SHFE` | `timeout` | `375,588` | `3,259` | `1` | `3,259` | `3` |
| `stage177_req_0001_AP201_CZCE_20211012` | `AP201.CZCE` | `extracted` | `128,829` | `1,131` | `1` | `1,130` | `3` |

说明：`fu2509` 的 `timeout` 不视为完整 14 天全量证明；它只说明在时间上限内抽取的数据已远超 `61` 根决策前闭合 bar，并且通过后续 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`12`
  - proof/hash/schema/identity ready：`12/12`
  - cutoff coverage pass：`12/12`
  - filtered request ready：`12`
  - direct file request ready：`4`
  - post-decision bars：`8`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`12`
  - cutoff-filtered source ready：`12`
  - filtered source rows：`34,257`
  - positive-volume rows：`34,238`
  - post-decision removed：`8`
  - lineage pass：`12/12`
- Stage181：
  - feature audit rows：`12`
  - feature readiness rows：`120`
  - ready cells：`120/120`
  - cutoff guard：`12/12`
  - lineage pass：`12/12`
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

- Stage183 资金路径图显示官方权益/回撤曲线未改变，底部只记录 selected/delivered/precheck/files，formal rows 仍为 `0`。
- Stage183 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `8` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `12 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`volume_participation_30m` 在 12 个样本上仍全为 `1.0`，继续只作数据质量诊断观察，不作为交易 alpha 或风险区分字段。

## 特征横截面概览

- `bar_return_1m`：min `-0.003467`，max `0.013514`
- `directional_efficiency_30m`：min `0.033175`，max `0.283582`
- `realized_volatility_30m`：min `0.000395`，max `0.002729`
- `volume_participation_30m`：min/max/mean 全为 `1.000000`
- `open_interest_delta_60m`：min `-22,709`，max `5,815`
- `closed_bar_count_coverage`：min `1,130`，max `3,470`

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有阈值搜索、没有品种/年份补丁，也没有根据收益结果筛选请求；Stage177 priority 只代表覆盖义务，不是交易条件。
- 是否还有价值继续做：是。已交付样本从 `8` 扩到 `12`，并完整刷新 Stage179/180/181；但距离 `219` 个 entry decision 仍很远，当前依然只是点时化分钟特征地基，不足以支持正式规则或 A/B。

## 后续规划

- Stage184 继续小批量扩展 Stage177 predecision lookback，保持 priority + 交易所轮转，不人工挑产品/年份。
- 每批继续复跑 Stage179/180/181，并持续生成资金曲线与视觉矩阵。
- 暂不触发 version A/B，不接 true engine，不把任何分钟特征写成正式进出场规则。
