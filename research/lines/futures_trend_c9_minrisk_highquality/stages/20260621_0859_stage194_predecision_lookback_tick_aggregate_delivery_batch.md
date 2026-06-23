# Stage194 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 08:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `52` 扩到 `56`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk 回测/tick serial 适合继续作为历史 tick 数据工程入口，但必须用落盘文件、hash/schema/proof 和窗口 precheck 验收，不能凭下载状态判断完整性。
  - pandas rolling 的窗口端点语义要求继续坚持 `bar_end_ts <= decision_ts`，避免把决策后 bar 混入前置特征。
  - vn.py tick 聚合 bar 需要处理 volume、turnover、open_interest，不能只用价格路径构造分钟 K。
  - 因此 Stage194 仍只能作为数据地基扩容；`maxDD`、`low_resolution`、SHFE 连续样本和 timeout/extracted 状态都不能交易化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage194_predecision_lookback_tick_aggregate_delivery_batch.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE194_MAX_REQUESTS=4`
  - `STAGE194_MAX_SECONDS_TICK=240`
  - `STAGE194_TICK_DATA_LENGTH=10000`
  - `STAGE194_MIN_NORMALIZED_ROWS=61`
  - `STAGE194_MIN_POSITIVE_VOLUME_BARS=60`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage177 manifest 中剩余 predecision lookback 请求；本批为 `2023-02-17` 至 `2023-03-01` 的 4 个 SHFE 请求。
- 账户规模：沿用官方 C9/15w 路径审计，不改本金。
- 成本口径：沿用官方 C9/15w 路径审计，不新增成本模型。
- 样本过滤：按 Stage177 剩余最高 priority + 交易所轮转自动选择；未按 PnL、年份、品种、方向人工筛选。
- 策略/归因口径：只交付 raw/normalized/proof 三件套，并刷新 Stage179 点时化验证、Stage180 cutoff-filtered source、Stage181 只读特征审计；不写真正 feature table。

## Stage194 交付结果

- 决策：`stage194_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选中请求数：`4`
- 交付成功数：`4/4`
- 写入文件数：`12/12`
- raw tick rows：`1,485,598`
- normalized rows：`13,214`
- positive-volume rows：`13,214`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`3,125`
- 最多观测 predecision closed bars：`3,460`
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
| `stage177_req_0052_fu2305_SHFE_20230217` | `fu2305.SHFE` | `SHFE` | `timeout` | `376,745` | `3,171` | `3,171` | `1` | `3,171` | `3` |
| `stage177_req_0053_hc2305_SHFE_20230221` | `hc2305.SHFE` | `SHFE` | `timeout` | `374,110` | `3,457` | `3,457` | `1` | `3,457` | `3` |
| `stage177_req_0055_rb2305_SHFE_20230223` | `rb2305.SHFE` | `SHFE` | `timeout` | `372,751` | `3,125` | `3,125` | `1` | `3,125` | `3` |
| `stage177_req_0057_ru2305_SHFE_20230301` | `ru2305.SHFE` | `SHFE` | `extracted` | `361,992` | `3,461` | `3,461` | `1` | `3,460` | `3` |

说明：3 个 `timeout` 不视为完整 14 天全量证明；它们只说明时间上限内已抽取到远超 `61` 根决策前闭合 bar，且可接受与否继续交给 Stage179/180/181 的 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`56`
  - proof/hash/schema/identity ready：`56/56`
  - cutoff coverage pass：`56/56`
  - filtered request ready：`56`
  - direct file request ready：`20`
  - post-decision bars：`36`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`56`
  - cutoff-filtered source ready：`56`
  - filtered source rows：`161,413`
  - positive-volume rows：`161,314`
  - post-decision removed：`36`
  - lineage pass：`56/56`
- Stage181：
  - feature audit rows：`56`
  - feature readiness rows：`560`
  - ready cells：`560/560`
  - cutoff guard：`56/56`
  - lineage pass：`56/56`
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

- Stage194 资金路径图显示官方权益/回撤曲线未改变，formal rows 仍为 `0`。
- Stage194 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `36` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `56 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`open_interest_delta_60m` 上界扩展到 `47,119`，说明本批 SHFE/maxDD 覆盖继续扩展横截面，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.014597`，max `0.013514`，mean `0.000602`
- `range_ratio_1m`：min `0.000000`，max `0.002882`，mean `0.000580`
- `directional_efficiency_30m`：min `0.020408`，max `0.463415`，mean `0.179829`
- `realized_volatility_30m`：min `0.000156`，max `0.002780`，mean `0.000923`
- `true_range_median_30m`：min `0.160000`，max `30.000000`，mean `7.354286`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.995833`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.037099`
- `open_interest_delta_60m`：min `-64,294`，max `47,119`，mean `-3,058.017857`
- `turnover_vwap_gap_30m`：min `-0.011586`，max `0.012208`，mean `0.000642`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,882.375000`

## 结论

- 本阶段结论：Stage177 predecision lookback 地基从 `52` 个样本推进到 `56` 个样本，proof/hash/schema/cutoff/lineage 全部通过；但距离 `219` 个 entry decision 仍远。
- 是否进入下一步：是，继续数据地基扩容。
- 下一步：Stage195 继续小批量扩展 Stage177 delivery，并复跑 Stage179/180/181。样本覆盖显著扩大前继续禁止分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。运行前已限定为 Stage177 剩余请求的机械扩容，不使用 PnL 标签和策略阈值。
- 运行后判断：否。本阶段没有最终收益标签筛选、没有参数扫描、没有品种/年份补丁，也没有根据 2023 SHFE 样本形成规则。
- 原因：所有新增输出都是 raw/normalized/proof、cutoff source 和只读审计特征；`maxDD` 与 `low_resolution` 只是覆盖义务，不是交易条件。

## 继续价值反思

- 运行前判断：是。Stage193 后仅 `52/219`，不足以支撑普世分钟执行判断。
- 运行后判断：是。Stage194 后达到 `56/219`，数据合同继续通过，但覆盖率仍只有约四分之一。
- 原因：目标是降低回撤且保留 80%+ 收益，这要求先有足够跨年、跨品种、跨状态的点时化分钟地基；现在还不能进入规则设计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage194 摘要。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或路线切换。
- 是否追加根目录 `memory.md/back_log.md`：否。不是重要突破、路线废弃、正式候选或跨线合并。
