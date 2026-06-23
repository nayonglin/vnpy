# Stage027 供需/库存/仓单外生状态只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 22:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：点时化外生供需状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Gorton / Hayashi / Rouwenhorst, The Fundamentals of Commodity Futures Returns, NBER：`https://www.nber.org/system/files/working_papers/w13249/w13249.pdf`
  - Hong / Yogo, What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices, NBER：`https://www.nber.org/system/files/working_papers/w16712/w16712.pdf`
  - AKShare futures 文档，注册仓单、基差、库存接口说明：`https://akshare.akfamily.xyz/_sources/data/futures/futures.md.txt`
  - fushare GitHub，国内商品期货注册仓单、基差、会员持仓等公开数据路径：`https://github.com/LowinLi/fushare`
  - heamabc/Machine-Learning-on-Futures，Wind 商品期货 inventory / warehouse receipt 特征示例：`https://github.com/heamabc/Machine-Learning-on-Futures`
- 我的判断：
  - 库存、仓单、基差和持仓变化有第一性经济基础，优先级高于从亏损 closed-lot 反推的内部标签。
  - 但仓单有季节性、交割日和交易所覆盖噪声，不能用单一阈值直接当坏信号。
  - Stage359 已证明旧正式线上的“供需逆风硬过滤”会严重砍收益并恶化回撤，所以本阶段只做 C9 入场前点时化绑定和视觉归因，不写交易规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage027_supply_demand_inventory_forensics.py`
- 修改脚本：
  - 无
- 删除脚本：
  - 无
- 新增参数：
  - 只读归因绑定：`MAX_SIGNAL_AGE_DAYS=7`
  - 只读粗分桶：`score >= 0.35` 为 `supply_supportive`，`score <= -0.35` 为 `supply_headwind`，其余为 `supply_neutral`
  - closed-lot 产品键规范化：用 `vt_symbol` 推导 `AP.CZCE/rb.SHFE` 等点时化绑定键，避免旧 `product` 字段无交易所导致覆盖低估
- 修改参数：
  - 无交易参数修改
- 删除参数：
  - 无

## 回测/归因参数

- 数据区间：
  - 官方 C9/15w closed-lot：`2018-01-15` 至 `2026-06-08`
  - 外生供需信号：Stage358 `2020-2022` + Stage316 `2023-2026`
- 账户规模：官方 C9/15w，`150,000`
- 成本口径：沿用官方 C9/15w closed-lot 与官方曲线；本阶段不新增成交和成本模拟
- 样本过滤：
  - official closed lots 全部保留，`399` 笔
  - 供需缺失单独归为 `supply_missing`，不删除
  - 仓单/基差信号按交易日 `20:00` 可见，只允许向后影响下一交易日及之后
- 策略/归因口径：
  - 按 `product + direction` 和 `prev_state_date` 日终向前 `merge_asof`，最大滞后 `7` 个自然日
  - 不使用未来信号，不用最终盈亏标签构造规则
  - 只读归因，不是真实交易引擎

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：
  - 官方交易胜率沿用 Stage011 口径：`53.2560%`
  - 本阶段 closed-lot 胜率：`36.0902%`
- 其他关键指标：
  - 外生信号行数：`51,524`
  - official closed lots：`399`
  - supply ready：`309`，覆盖率 `77.4436%`
  - `supply_headwind`：`83` 笔、`16` 产品、`7` 年，净 PnL `9,561,268.00`，正收益覆盖 `21.5268%`，负收益绝对覆盖 `20.3308%`
  - `supply_neutral`：`203` 笔、`19` 产品、`7` 年，净 PnL `36,307,101.20`，正收益覆盖 `74.6828%`
  - `supply_supportive`：`23` 笔、`11` 产品、`6` 年，净 PnL `-2,356,900.00`，正收益覆盖仅 `0.7610%`
  - `high_conf_headwind`：`28` 笔、`8` 产品、`6` 年，净 PnL `5,407,737.90`，不是坏信号集合

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_report_stage027_supply_demand_inventory_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_decision_stage027_supply_demand_inventory_forensics_v1.json`
- orders：无，本阶段不下单、不生成订单
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_daily_active_share_stage027_supply_demand_inventory_forensics_v1.csv`
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_features_stage027_supply_demand_inventory_forensics_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_bucket_summary_stage027_supply_demand_inventory_forensics_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_bucket_year_heatmap_stage027_supply_demand_inventory_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_path_supply_state_chart_stage027_supply_demand_inventory_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_cohort_contribution_chart_stage027_supply_demand_inventory_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_supply_score_scatter_stage027_supply_demand_inventory_forensics_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage027_supply_demand_inventory_forensics/qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_product_supply_heatmap_stage027_supply_demand_inventory_forensics_v1.png`

## 视觉结论

- path chart：`supply_headwind` active share 在 `2022` 深回撤前后没有稳定领先；在 `2021/2024/2025` 权益上台阶时也频繁出现。
- contribution chart：`supply_headwind` 橙线自 `2021` 后整体上行，最终净赚 `956万`，不能当作削仓闸门。
- bucket-year heatmap：`supply_headwind` 仅 `2022` 为负，`2021/2024/2025/2026` 均为正；`supply_supportive` 反而在 `2022/2024/2025/2026` 为负，关系不单调。
- scatter：盈亏点在 `external_quality_score` 与 `confidence` 空间中混杂，没有干净边界。
- product heatmap：结果仍受 `jm.DCE/OI.CZCE/au.SHFE/lh.DCE/SH.CZCE` 等产品块主导，不能做产品/交易所补丁。

## 结论

- 本阶段结论：`stage027_supply_demand_no_candidate_nonmonotonic_or_right_tail_dominant`
- 是否进入下一步：不进入交易候选，不触发 A/B，不写 true engine。
- 下一步：
  - 停止当前 AKShare 基差+仓单粗供需质量分阈值分支；不扫 `0.25/0.35/0.50`、组件权重、最大滞后、产品、方向、年份或交易所。
  - 若继续外生路线，只能换更细、更点时化的官方仓单源覆盖审计、会员持仓排名结构、或 forward watch；否则暂停历史 closed-lot 内反推，避免把右尾产品块切成规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续围绕本结果扫阈值会变成过拟合。
- 原因：
  - 本阶段规则来自外部库存/仓单/基差理论和公开日级数据，只用入场前可见信息，未按亏损年份、品种、方向或具体交易调参。
  - 运行后已经看到 headwind/supportive 与盈亏关系非单调；若为了救结果再改分数阈值、组件权重或产品/年份，会直接违背穿越周期目标。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前粗供需质量分分支没有继续交易化价值；更细外生数据路线仍有有限研究价值。
- 原因：
  - 有价值部分在于覆盖率提高到 `77.4436%`，证明点时化库存/仓单/基差可以绑定到 C9 closed lots。
  - 没有交易化价值部分在于 headwind 并非坏信号，supportive 也非好信号，视觉上无法领先深回撤。
  - 若继续，只能研究更直接的官方仓单源、会员持仓结构或 forward watch；不能继续从本阶段粗分数里挤阈值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage027 结论和停止边界。
- 是否更新 `research/registry.md`：否，非重要突破、非路线废弃、非正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要合入摘要。
