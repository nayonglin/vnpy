# Stage107 合约月份 OI patched root 覆盖复审

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 16:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据工程 / 临时 patched root / 覆盖复审，不写真引擎
- 是否重要突破：否；这是 Stage106 之后的严格复审，结论是“覆盖修复但仍不能规则化”
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：沿用 Stage106 对 TqSdk 官方 `DataDownloader`、`get_kline_serial(86400)`、`TqBacktest` 与 TqSdk GitHub 的调研。
- 我的判断：
  - Stage106 证明 missing target contract 的 raw OI 可以隔离回放，但 Stage104 的 panel-ready 还要求同日同品种至少两个活跃合约可比较。
  - 临时 patched root 必须复用 Stage104 的原审计逻辑，不能只用 Stage106 gap rows 的 source date 覆盖率代替完整面板审计。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage107_contract_month_oi_patched_root_reaudit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE107_FORCE_REBUILD`，默认 `1`，每次重建临时 patched root。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage102 timestamp-ready 子集 `219` 笔；patched root 使用原主日线根 symlink + Stage106 `21` 个 overlay CSV。
- 账户规模：沿用官方路径背景，`150,000` 初始账户口径。
- 成本口径：不新增回测，沿用官方背景指标；总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；全量复审 Stage104 `219` 笔 timestamp-ready orders。
- 策略/归因口径：只读覆盖复审；主数据根未改，交易规则未创建。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `primary_daily_root_mutated=0`
  - `primary_symlink_count=4044`
  - `stage106_raw_file_count=21`
  - `overlay_target_file_count=21`
  - `overlay_provenance_complete_count=21`
  - `timestamp_ready_order_count=219`
  - `strict_panel_ready_count=216/219=98.6301%`
  - `adjusted_panel_ready_count=218/219=99.5434%`
  - `target_contract_found_active_count=219`
  - `target_contract_missing_count=0`
  - `source_age_le7_count=217`
  - `calendar_holiday_adjacent_accept_count=2`
  - `source_age_le7_or_calendar_adjacent_count=219`
  - `right_tail_adjusted_ready_count=18/18`
  - `bottom_loss_adjusted_ready_count=17/18`
  - 可比较 rank：`rank1=208`、`rank2=9`、`rank3plus=1`
  - `single_contract_panel_count=1`
  - `adjusted_product_year_hard_gap_cell_count=1`
  - `promotion_gate_pass_count=4/8`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage107_contract_month_oi_patched_root_reaudit/qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_report_stage107_contract_month_oi_patched_root_reaudit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage107_contract_month_oi_patched_root_reaudit/qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_summary_stage107_contract_month_oi_patched_root_reaudit_v1.csv`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage107_contract_month_oi_patched_root_reaudit/qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_features_stage107_contract_month_oi_patched_root_reaudit_v1.csv`
- overlay manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage107_contract_month_oi_patched_root_reaudit/qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_overlay_manifest_stage107_contract_month_oi_patched_root_reaudit_v1.csv`
- 临时 patched root：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage107_contract_month_oi_patched_root_reaudit/patched_tqsdk_daily_2010_2026_04_overlay/`
- 视觉图：
  - official path adjusted coverage：`qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_official_path_adjusted_coverage_stage107_contract_month_oi_patched_root_reaudit_v1.png`
  - product-year heatmap：`qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_product_year_adjusted_heatmap_stage107_contract_month_oi_patched_root_reaudit_v1.png`
  - rank/share：`qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_rank_share_recomputed_stage107_contract_month_oi_patched_root_reaudit_v1.png`
  - gate：`qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_promotion_gate_stage107_contract_month_oi_patched_root_reaudit_v1.png`

## 结论

- 本阶段结论：`stage107_patched_root_contract_coverage_fixed_single_contract_panel_blocks_rule`。Stage106 raw overlay 修复了 target contract 缺文件问题，`219/219` target contract 都能找到；但 `SH607.CZCE 2026-04-30` 是 `single_contract_panel`，同日只有一个活跃 SH 合约，无法计算主次合约 OI 迁移，且该样本是 bottom-loss `-1,440,000`。
- 是否进入下一步：不进入 OI rank/share true engine 或 A/B。
- 下一步：合约月 OI 迁移路线只能保留为数据资产和只读解释；如果继续策略目标，应换信息源或先做 `single_contract_panel` root-cause/上市初期自然状态审计，确认是否要把“不可比较新合约期”作为 no-feature fallback，而不是交易规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；并发现一个防过拟合边界。
- 原因：本阶段没有按收益调参，而是复用 Stage104 固定 panel-ready 口径复审全量 `219` 笔。新发现的 `single_contract_panel` 正好是大亏样本，如果为了让 OI 路线过 gate 而把它排除或单独处理，就会变成近端 bottom-loss 补丁化过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：有价值但 OI 迁移路线暂不值得继续规则化。
- 原因：Stage107 把阻塞点从“缺 raw 数据”推进到“部分品种上市/活跃初期没有可比较合约”，这是有价值的边界；但该边界不是收益信号，继续围绕 rank/share 做规则会偏离“能穿越周期”的原则。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage107 阻断结论。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不改正式候选，不触发跨线总账。
