# Stage078 TqSdk dur0 tick transform gate 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:43 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage077 后 R2 同源 tick/orderbook 数据闸门审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`。文档说明历史下载支持 tick 级别和任意 K 线周期，`dur_sec=0` 为 Tick，但数据下载器属于专业版/授权功能。
  - TqSdk 行情与历史数据文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`。文档说明 tick 序列可取得 bid/ask price 1、volume 等盘口/成交量字段。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`。`TickData` 包含 last trade、orderbook snapshot 和 intraday statistics；`BarData` 是 OHLCV 周期数据。
  - vn.py `utility.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`。`BarGenerator.update_tick` 是从 tick 生成分钟 bar 的标准路径，使用 last_price、累计 volume/turnover 变化等字段。
- 我的判断：
  - TqSdk `dur_sec=0` 是当前最直接的同 vendor tick 出口；但同 vendor 不等于同 transform。
  - 只有在 tick/orderbook 能重建 Stage449/raw 60s price proxy 的 initial-open anchor exact 后，才允许继续研究 spread/depth/imbalance/真实 OHLCV。
  - 现有本地 tick 文件即使能 exact，也只能说明局部 TCA/文件存在，不能越过 transform gate。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage078_tqsdk_dur0_tick_transform_gate_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 新增只读下载闸门环境变量 `STAGE078_ALLOW_TQSDK_DOWNLOAD`，默认 `0`，本阶段未下载。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage074/077 全量 `324` 个 initial opens 与 Stage045 官方资金曲线，覆盖 `2018-2026`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定读取 Stage074 source decision audit、Stage077 summary、Stage045 official curve。
  - manifest 选择规则为每年按时间排序取前 `4` 个 `timestamp_ready=1` initial opens，总计 `28` 个；不按收益、回撤、品种、方向或交易所筛选。
  - 扫描本线 outputs 下现有 `*tick*.csv`，只用 `candidate_{index}` 文件名 token 做 initial-entry 锚点匹配。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓、减仓、恢复风险或退出规则。
  - 不跑 true engine。
  - 不下载数据、不连接 CTP、不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage078_tq_dur0_route_environment_ready_but_transform_unverified_no_rule`
  - next_step：`manual_opt_in_download_small_dur0_manifest_then_rebuild_stage449_transform_before_any_rule`
  - TqSdk import / version：`1 / 3.9.4`
  - DataDownloader import：`1`
  - datafeed username/password present：`1 / 1`
  - download allowed by env / attempted：`0 / 0`
  - initial opens：`324`
  - timestamp-ready：`219`
  - fallback no-proxy：`105`
  - full existing Tq proxy ready/exact/mismatch：`60 / 46 / 14`
  - local tick named csv/schema files/schema rows：`149 / 120 / 57,765`
  - manifest size：`28`
  - manifest local tick match/schema/exact：`6 / 6 / 6`
  - manifest Stage074 Tq ready/exact/mismatch：`6 / 6 / 0`
  - same-source transform verified：`0`
  - rule candidate allowed：`0`
  - download plan rows：`28`

## 视觉观察

- official path gate chart：官方资金曲线与回撤曲线保持不变；红色 manifest 锚点只是数据 gate 采样点，不是交易信号。第三栏显示 `timestamp_ready_non_manifest` 承载主要右尾，manifest 本身贡献偏小且偏负，进一步说明不能把数据可得性或 manifest 选择交易化。
- readiness atlas：TqSdk import、DataDownloader import、datafeed 凭据、manifest、部分本地 tick schema 均为 `1`；但 `download opt-in=0`、`same transform verified=0`、`rule candidate allowed=0`。真正阻塞点仍是 transform 复现，而不是 Python 环境。
- manifest coverage chart：`2020` 的 `4/4` 与 `2021` 的 `2/4` 有本地 candidate-token tick match；`2022-2026` smoke manifest 全部为 `0`。现有 tick 资产明显不能支撑跨周期 initial-entry 微观规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_report_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_summary_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.csv`
- manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_manifest_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.csv`
- download plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_download_plan_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.csv`
- local tick catalog：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_local_tick_catalog_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_official_path_tq_gate_chart_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.png`
- readiness atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_readiness_gate_atlas_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.png`
- manifest coverage chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage078_tqsdk_dur0_tick_transform_gate_audit/qmt_roll_stage078_c9_minrisk_tqsdk_dur0_tick_transform_gate_audit_manifest_coverage_chart_stage078_tqsdk_dur0_tick_transform_gate_audit_v1.png`

## 结论

- 本阶段结论：`stage078_tq_dur0_route_environment_ready_but_transform_unverified_no_rule`
- 是否进入下一步：是，但仍然不能写交易规则。
- 下一步：
  - 第一优先：显式 opt-in 后只下载 Stage078 `28` 行 small dur0 tick manifest，优先验证 `2022-2026` 的空覆盖点。
  - 第二优先：把 dur0 tick 按固定 BarGenerator/Stage449 transform 候选聚合回 60s open，复验 initial-open anchor exact；只有 exact 且跨年覆盖后，才允许进入微观结构只读稳定性审计。
  - 第三优先：若 dur0 tick 仍不能重建 Stage449/raw open，只能把 Tq tick 作为 TCA；策略研究转向授权 vendor/raw exchange tick/quote/depth 或真正外生、入场前可见、覆盖完整的数据源。
  - 明确禁止：不得把 local tick match、tick exact、Tq ready/exact、manifest year coverage、download availability、source class、产品、年份或方向写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段目标是数据闸门，不按收益筛样本，不新增交易条件。
- 运行后判断：否，并且进一步降低过拟合风险。
- 原因：
  - manifest 只按年份和时间顺序固定抽样，不看 PnL、回撤、品种、方向。
  - gate 判定只看 import、授权、文件 schema、跨年覆盖和 transform verified；所有交易权限仍为 `0`。
  - 6 个本地 exact tick 样本被明确降级为局部证据，不能代表跨周期规则。

## 继续价值反思

- 运行前判断：有价值。Stage077 已把 R2 压实到同源 tick/orderbook transform，Stage078 需要确认本地环境和最小下载 manifest。
- 运行后判断：有价值，但价值仍在数据工程，不在策略规则。
- 原因：
  - 环境与凭据已经可行，下一步不再是“能不能用 TqSdk”，而是小样本下载和 transform 复验。
  - 现有本地 tick 只覆盖 `2020/2021` 一小段，直接解释了为什么不能继续在本地 tick 上写跨周期规则。
  - 如果 small manifest 下载后仍无法重建 Stage449/raw open，R2 可以明确关闭或降级为 TCA，避免继续在伪分钟结构上过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage078 状态、视觉结论和下一步 download/transform gate。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据闸门审计。
