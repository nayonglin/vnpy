# Stage195 predecision lookback tick aggregate delivery batch

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 09:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage177 predecision lookback 数据地基小批量扩容；刷新 Stage179/180/181 审计链路。
- 是否重要突破：否。本阶段只把已交付样本从 `56` 扩到 `60`，不是策略收益/回撤突破。
- 是否触发A/B：否。没有策略候选、没有 true engine、没有正式配置变更。

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest` 官方文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html
  - TqSdk `TqApi/get_tick_serial` 官方文档：https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html
  - pandas `DataFrame.rolling` 官方文档：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html
  - vn.py `BarGenerator` 源码：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：
  - TqSdk 回测/tick serial 能继续作为历史 tick 抽取入口，但 tick 回放状态本身不是完整性证明，必须继续依赖 raw/normalized/proof、hash/schema 和窗口 precheck。
  - pandas rolling 的端点和时间列语义继续支持 `bar_end_ts <= decision_ts` 的点时化边界。
  - vn.py BarGenerator 说明 tick 聚合成分钟 bar 应同时关心价格、volume、turnover、open_interest；只看价格路径会低估数据合同风险。
  - 因此 Stage195 仍是数据地基扩容；`maxDD`、`low_resolution`、交易所/年份轮转、timeout/extracted 状态都不能变成交易条件。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage195_predecision_lookback_tick_aggregate_delivery_batch.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数。
- 新增执行参数：
  - `STAGE195_MAX_REQUESTS=4`
  - `STAGE195_MAX_SECONDS_TICK=240`
  - `STAGE195_TICK_DATA_LENGTH=10000`
  - `STAGE195_MIN_NORMALIZED_ROWS=61`
  - `STAGE195_MIN_POSITIVE_VOLUME_BARS=60`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage177 manifest 中剩余 predecision lookback 请求；本批为 `2020-01-10` 至 `2023-03-08` 的 4 个请求。
- 账户规模：沿用官方 C9/15w 路径审计，不改本金。
- 成本口径：沿用官方 C9/15w 路径审计，不新增成本模型。
- 样本过滤：按 Stage177 剩余最高 priority + 交易所轮转自动选择；未按 PnL、年份、品种、方向人工筛选。
- 策略/归因口径：只交付 raw/normalized/proof 三件套，并刷新 Stage179 点时化验证、Stage180 cutoff-filtered source、Stage181 只读特征审计；不写真正 feature table。

## Stage195 交付结果

- 决策：`stage195_predecision_lookback_tick_aggregate_delivery_written_refresh_stage179_180_181_no_rule`
- 选中请求数：`4`
- 交付成功数：`4/4`
- 写入文件数：`12/12`
- raw tick rows：`1,080,700`
- normalized rows：`13,137`
- positive-volume rows：`13,125`
- window precheck：`4/4`
- 最少观测 predecision closed bars：`2,994`
- 最多观测 predecision closed bars：`3,954`
- target minimum bars：`61`
- selected right-tail windows：`0`
- selected bottom-loss windows：`0`
- selected maxDD windows：`2`
- selected low-resolution windows：`3`
- feature table rows：`0`
- strategy rule created：`0`
- true engine run：`0`
- A/B triggered：`0`
- official config changed：`0`
- order API called：`0`

## 本批请求明细

| request_id | vt_symbol | exchange | tick_fetch_status | raw_tick_rows | normalized_rows | positive_volume_rows | precheck_pass | observed_predecision_closed_bars | files_written |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage177_req_0056_rb2305_SHFE_20230308` | `rb2305.SHFE` | `SHFE` | `timeout` | `366,288` | `3,071` | `3,071` | `1` | `3,071` | `3` |
| `stage177_req_0048_cu2303_SHFE_20230112` | `cu2303.SHFE` | `SHFE` | `extracted` | `288,503` | `3,955` | `3,944` | `1` | `3,954` | `3` |
| `stage177_req_0067_FG009_CZCE_20200519` | `FG009.CZCE` | `CZCE` | `extracted` | `293,887` | `3,116` | `3,116` | `1` | `3,115` | `3` |
| `stage177_req_0094_jm2005_DCE_20200110` | `jm2005.DCE` | `DCE` | `extracted` | `132,022` | `2,995` | `2,994` | `1` | `2,994` | `3` |

说明：`rb2305.SHFE` 2023-03-08 的 `timeout` 不视为完整 14 天全量证明；它只说明时间上限内已抽取到远超 `61` 根决策前闭合 bar，且可接受与否继续交给 Stage179/180/181 的 proof/hash/schema/cutoff 验证。

## Stage179/180/181 刷新结果

- Stage179：
  - present triplet：`60`
  - proof/hash/schema/identity ready：`60/60`
  - cutoff coverage pass：`60/60`
  - filtered request ready：`60`
  - direct file request ready：`21`
  - post-decision bars：`39`
  - 结论：direct normalized 文件仍不可直接进 feature builder，必须走 Stage180 cutoff-filtered source。
- Stage180：
  - filtered source written：`60`
  - cutoff-filtered source ready：`60`
  - filtered source rows：`174,547`
  - positive-volume rows：`174,436`
  - post-decision removed：`39`
  - lineage pass：`60/60`
- Stage181：
  - feature audit rows：`60`
  - feature readiness rows：`600`
  - ready cells：`600/600`
  - cutoff guard：`60/60`
  - lineage pass：`60/60`
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

- Stage195 资金路径图显示官方权益/回撤曲线未改变，formal rows 仍为 `0`。
- Stage195 predecision window precheck 图显示 4 个新增窗口均远高于 `61` 根，coverage precheck 全绿。
- Stage180 post-decision tail removed 图显示 `39` 根未来 bar 已从安全源中物理剔除。
- Stage181 readiness matrix 扩展为 `60 x 10` 特征，全绿。
- Stage181 value heatmap 非空；`true_range_median_30m` 上界扩展到 `40`，说明本批跨 2020/2023、CZCE/DCE/SHFE 的覆盖继续扩展横截面，但仍不得交易化。
- 20 张关键 PNG 已做非空像素检查，全部非空。

## 特征横截面概览

- `bar_return_1m`：min `-0.014597`，max `0.013514`，mean `0.000580`
- `range_ratio_1m`：min `0.000000`，max `0.002882`，mean `0.000595`
- `directional_efficiency_30m`：min `0.020408`，max `0.463415`，mean `0.177316`
- `realized_volatility_30m`：min `0.000156`，max `0.002780`，mean `0.000895`
- `true_range_median_30m`：min `0.160000`，max `40.000000`，mean `7.605667`
- `volume_participation_30m`：min `0.866667`，max `1.000000`，mean `0.996111`
- `volume_zscore_60m`：min `-0.590071`，max `0.506303`，mean `0.033346`
- `open_interest_delta_60m`：min `-64,294`，max `47,119`，mean `-2,728.250000`
- `turnover_vwap_gap_30m`：min `-0.011586`，max `0.012208`，mean `0.000618`
- `closed_bar_count_coverage`：min `1,130`，max `4,670`，mean `2,909.116667`

## 结论

- 本阶段结论：Stage177 predecision lookback 地基从 `56` 个样本推进到 `60` 个样本，proof/hash/schema/cutoff/lineage 全部通过；但距离 `219` 个 entry decision 仍远。
- 是否进入下一步：是，继续数据地基扩容。
- 下一步：Stage196 继续小批量扩展 Stage177 delivery，并复跑 Stage179/180/181。样本覆盖显著扩大前继续禁止分钟规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。运行前已限定为 Stage177 剩余请求的机械扩容，不使用 PnL 标签和策略阈值。
- 运行后判断：否。本阶段没有最终收益标签筛选、没有参数扫描、没有品种/年份补丁，也没有根据 2020/2023 或某个交易所形成规则。
- 原因：所有新增输出都是 raw/normalized/proof、cutoff source 和只读审计特征；`maxDD` 与 `low_resolution` 只是覆盖义务，不是交易条件。

## 继续价值反思

- 运行前判断：是。Stage194 后仅 `56/219`，不足以支撑普世分钟执行判断。
- 运行后判断：是。Stage195 后达到 `60/219`，数据合同继续通过，但覆盖率仍不足三分之一。
- 原因：目标是降低回撤且保留 80%+ 收益，这要求先有足够跨年、跨品种、跨交易所、跨状态的点时化分钟地基；现在还不能进入规则设计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage195 摘要。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或路线切换。
- 是否追加根目录 `memory.md/back_log.md`：否。不是重要突破、路线废弃、正式候选或跨线合并。
