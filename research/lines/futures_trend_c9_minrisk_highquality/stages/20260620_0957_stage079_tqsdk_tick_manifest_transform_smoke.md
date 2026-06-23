# Stage079 TqSdk tick manifest transform smoke

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage078 后显式 opt-in 的 TqSdk dur0 tick 小 manifest 下载与 transform smoke，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`。文档说明历史下载支持 tick 级别和任意 K 线周期，`dur_sec=0` 为 Tick，但数据下载能力受专业版/授权约束。
  - TqSdk 行情与历史数据文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`。文档说明可用 `get_tick_serial` 取得 tick 序列，包含 `last_price`、`bid_price1`、`ask_price1`、`volume`、`open_interest` 等字段。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`。`TickData` 是 last trade、orderbook snapshot 与日内统计，`BarData` 是周期 OHLCV。
  - vn.py `utility.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`。`BarGenerator.update_tick` 是 tick 到分钟 bar 的标准聚合路径。
- 我的判断：
  - Stage079 只能回答“是否能拿到 Tq tick，以及首个简单 transform 是否能重建官方/raw/Stage449 open”，不能回答“能不能交易”。
  - 下载成功不是数据同源性的证明；只有跨年稳定复现 Stage449/raw open，才允许继续研究盘口、价差、深度和成交流。
  - 如果为了 exact 人为挑 tick index、bid/ask 侧或合约/年份特例，就是在数据 transform 层过拟合，比策略参数过拟合更危险。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage079_tqsdk_tick_manifest_transform_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE079_ENABLE_TQSDK`：默认 `0`；本次显式设为 `1` 才允许请求 TqSdk 历史 tick。
  - `STAGE079_MAX_EVENTS`：可选限制 manifest 行数，本次未限制，跑满 `28` 行。
  - `STAGE079_MAX_SECONDS_PER_EVENT`：单事件等待上限，本次为 `25` 秒。
  - `STAGE079_TICK_DATA_LENGTH`：tick serial 长度，本次为 `12000`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage078 fixed manifest，每年按时间排序取前 `4` 个 `timestamp_ready=1` initial-open，覆盖 `2020-2026` 共 `28` 行；官方资金曲线继承 Stage045/C9 15w。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 不按收益、回撤、品种、方向、交易所筛选。
  - 固定下载/读取 Stage078 manifest 中的 `28` 个 anchor window。
  - 每个事件取 `authority_anchor_time - 30s` 到 `+90s` 的 tick，target minute 为 anchor 所在分钟。
- 策略/归因口径：
  - 使用 TqSdk `TqBacktest + get_tick_serial` 拉取 dur0 tick，落盘到本线 `raw_tick/`。
  - 用 target minute 第一笔 `last_price` 重建 open，并与 official/raw/Stage449 anchor open exact 比较。
  - 不改变官方交易，不写真引擎，不新增开仓、减仓、恢复风险或退出规则，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage079_small_manifest_transform_mixed_no_rule`
  - next_step：`inspect_mismatch_by_year_then_either_fix_transform_or_downgrade_tq_tick_to_tca`
  - TqSdk import / version：`1 / 3.9.4`
  - enable_tqsdk / download_attempted：`1 / 1`
  - manifest size / year count：`28 / 7`
  - download success / failed-or-empty：`28 / 0`
  - target tick ready：`28 / 28`
  - rebuilt open exact official/raw/Stage449：`8 / 28`
  - same-source transform verified：`8 / 28`
  - transform verified year count：`6 / 7`
  - rule candidate allowed：`0 / 28`
  - any last/bid/ask exact official：`24 / 28`
  - official inside any spread：`24 / 28`
  - 年度 exact 分布：`2020=2/4`，`2021=0/4`，`2022=1/4`，`2023=1/4`，`2024=1/4`，`2025=2/4`，`2026=1/4`
  - raw tick 文件：`28` 个，`5066` 行含表头。

## 视觉观察

- official path transform chart：官方 C9/15w 资金曲线和回撤曲线保持不变；Stage079 只是数据 transform gate。绿色 verified 与橙色 tick-ready-not-verified 都散布在官方长期路径上，不能按颜色当收益/风险信号。
- year matrix chart：每年 `4/4` 都已 extracted/target-ready，但 exact 只有 `8/28`，其中 `2021` 为 `0/4`。这说明阻塞已从“拿不到 tick”推进到“transform 语义未闭环”。
- tick transform atlas：已验证样本中，official/raw/Stage449 open 线与 target minute 第一笔 last 近似对齐；但 audit 表显示 mismatch 样本里 `24/28` 至少在 minute 内某处 last/bid/ask 能碰到 official，`24/28` official 落入某处 spread。这提示 Tq tick 源不是完全错源，但 Stage449/raw open 可能不是简单“target minute 第一笔 last_price”。不能据此挑某个 tick index 或盘口侧直接规则化。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_report_stage079_tqsdk_tick_manifest_transform_smoke_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_summary_stage079_tqsdk_tick_manifest_transform_smoke_v1.csv`
- download status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_download_status_stage079_tqsdk_tick_manifest_transform_smoke_v1.csv`
- transform audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_transform_audit_stage079_tqsdk_tick_manifest_transform_smoke_v1.csv`
- year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_year_transform_matrix_stage079_tqsdk_tick_manifest_transform_smoke_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_decision_stage079_tqsdk_tick_manifest_transform_smoke_v1.json`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_official_path_transform_chart_stage079_tqsdk_tick_manifest_transform_smoke_v1.png`
- year matrix chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_year_transform_matrix_chart_stage079_tqsdk_tick_manifest_transform_smoke_v1.png`
- tick atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_tick_transform_atlas_stage079_tqsdk_tick_manifest_transform_smoke_v1.png`
- raw tick dir：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage079_tqsdk_tick_manifest_transform_smoke/raw_tick/`

## 结论

- 本阶段结论：`stage079_small_manifest_transform_mixed_no_rule`
- 是否进入下一步：是，但仍然只能做数据 transform 归因，不能写交易规则。
- 下一步：
  - 第一优先：对 `20` 个 mismatch 逐行检查 official/raw/Stage449 open 在 tick minute 内的 first/last/bid/ask/time-index 位置，判断是否存在统一、可解释、非参数化的 transform 规则。
  - 第二优先：如果统一 transform 不存在，Tq dur0 tick 降级为 TCA/成交质量观察源，不能作为同源 initial-entry 微观规则数据源。
  - 第三优先：若继续 R2，只能换授权 vendor/raw exchange tick/quote/depth，或找到 Stage449/raw 生成端的真实 tick/orderbook transform；否则策略研究转向真正外生、入场前可见、覆盖完整的数据源。
  - 明确禁止：不得把 download success、target tick ready、exact/mismatch、any bid/ask exact、inside spread、年度覆盖、产品、交易所、方向或 manifest 事件写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段只做固定 manifest 的数据下载与 transform gate，不看收益筛样本，不新增交易条件。
- 运行后判断：否，但后续存在 transform 过拟合风险，必须压住。
- 原因：
  - manifest 固定来自 Stage078，每年按时间顺序取样，未按 PnL、回撤、品种、方向筛选。
  - `8/28` exact 明确不足，结论是 mixed/no-rule，而不是从 mismatch 中挑局部规则。
  - 后续若为了 exact 去挑 tick index、bid/ask 侧或个别交易所口径，就会把数据误差拟合成策略 alpha，必须禁止。

## 继续价值反思

- 运行前判断：有价值。Stage078 已确认环境和凭据，必须实际下载小 manifest 才能判断 R2 是否还有路。
- 运行后判断：有价值，但价值收窄为数据 transform 归因，不是策略 alpha。
- 原因：
  - 下载 `28/28` 成功，说明 TqSdk 历史 tick 通路可用，数据阻塞已前移。
  - transform 只有 `8/28` exact，说明当前“第一笔 last_price”无法解释官方/raw/Stage449 open，直接交易化会污染研究。
  - `24/28` official 在 minute 内触达 last/bid/ask 或落入 spread，仍值得做一次统一 transform 根因检查；如果不能统一解释，应果断降级 Tq tick。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage079 状态、视觉结论和下一步 mismatch 归因边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据闸门审计。
