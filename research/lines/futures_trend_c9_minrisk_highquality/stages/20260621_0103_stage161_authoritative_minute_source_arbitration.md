# Stage161 权威分钟数据源仲裁

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 01:03`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage152 授权分钟包替代源只读仲裁
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - TqSdk 历史/行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html`
  - Nasdaq Data Link Chinese Futures Data：`https://data.nasdaq.com/databases/DY8`
- 我的判断：TqSdk 这类 SDK 技术上可以提供分钟 K、volume、open_interest 或通过回测通路补目标窗口；本地也确实存在其他线的 Stage861 分钟明细。但这些都不能直接绕过 Stage152/153。能不能用于当前线，核心不是“有没有 CSV”，而是是否具备授权来源、raw/normalized/proof 三件套、当前线 lineage、窗口覆盖、无 fixture/proxy 标记，并通过 Stage153 proof/schema/hash/window coverage。没有这些，直接拿 Stage861 或其他线 TqSdk 产物做规则，会把来源偏差和选择偏差包装成 alpha。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage161_authoritative_minute_source_arbitration.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增 source arbitration、local artifact audit、migration requirements、gate status。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage160 官方路径资金曲线作视觉跟踪；本阶段不运行新回测。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage160 官方路径总滑点口径。
- 样本过滤：无新增过滤；只读当前线 Stage151/160/033/107/114 与其他线 Stage859/861/445/446 摘要，不读取其他线大分钟明细做交易判断。
- 策略/归因口径：data source arbitration；不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage161_source_arbitration_no_alternate_substitute_wait_authorized_package_no_rule`
  - `source_count=8`
  - `alternate_source_count=7`
  - `current_data_ready_source_count=4`
  - `stage153_substitute_allowed_count=0`
  - `strategy_rule_allowed_count=0`
  - `eligible_line_scope_source_count=0`
  - `migration_requirement_count=10`
  - `migration_requirement_pass_count=0/10`
  - `local_artifact_count=12`
  - `other_line_artifact_count=7`
  - `tqsdk_module_installed=1`
  - `akshare_module_installed=1`
  - `rqdatac_module_installed=1`
  - `tushare_module_installed=1`
  - `current_package_promotion_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `objective_completion_proven=0`
  - `max_broker10_margin_to_equity_pct=111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_report_stage161_authoritative_minute_source_arbitration_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_summary_stage161_authoritative_minute_source_arbitration_v1.csv`
- source arbitration：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_source_arbitration_stage161_authoritative_minute_source_arbitration_v1.csv`
- local artifact audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_local_artifact_audit_stage161_authoritative_minute_source_arbitration_v1.csv`
- migration requirements：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_migration_requirements_stage161_authoritative_minute_source_arbitration_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_gate_status_stage161_authoritative_minute_source_arbitration_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage161_authoritative_minute_source_arbitration/qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_decision_stage161_authoritative_minute_source_arbitration_v1.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：5 张 PNG 视觉产物均非空：
  - `qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_official_path_source_status_stage161_authoritative_minute_source_arbitration_v1.png`
  - `qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_source_eligibility_matrix_stage161_authoritative_minute_source_arbitration_v1.png`
  - `qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_source_score_bar_stage161_authoritative_minute_source_arbitration_v1.png`
  - `qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_local_artifact_size_coverage_stage161_authoritative_minute_source_arbitration_v1.png`
  - `qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration_gate_status_matrix_stage161_authoritative_minute_source_arbitration_v1.png`

## 视觉分析

- 官方路径资金曲线仍只是基线视觉跟踪；Stage161 没有改变交易路径。
- source eligibility matrix 显示所有源在 `authorized_proof_ready`、`coverage_ready_for_stage152`、`lineage_ready` 上失败，因此 `stage153_substitute_allowed=0`。
- source score bar 显示 TqSdk 与 Stage861 有数据/工具价值，但硬阻断是 current-line proof 和 lineage，不是技术库缺失。
- local artifact size 图显示最大本地分钟明细是其他线 Stage861 `276.89MB / 1,482,591 rows`，但 `line_scope_compatible=0`，不能当当前线候选证据。
- gate matrix 显示安全闸门通过：`stage153_substitute_allowed_count=0`、`strategy_rule_allowed_count=0`、`no_true_engine=1`、`no_order_or_ctp=1`；数据闸门仍失败：`migration_requirement_pass_count=0/10`。

## 结论

- 本阶段结论：当前没有任何本地/TqSdk/其他线分钟源可以直接替代 Stage152 授权包进入 Stage153。TqSdk 可以作为潜在数据源，但必须先生成当前线的 raw/normalized/proof 三件套并通过 Stage153；Stage861 只能作为历史视觉上下文，不能复制成当前线交易证据。
- 是否进入下一步：可以，但下一步不能再做纯 no-data 面板。
- 下一步：如果继续推进，应尝试一个最小的 proofed conversion smoke：选 Stage152 的 1 个 request，用 TqSdk/已授权源生成 raw、normalized parquet、proof JSON 到 `incoming/stage152_authoritative_minute_ohlcv/...`，然后跑 Stage160/153 验证；如果不能生成真实 proof，就应停等授权数据。

## 过拟合反思

- 运行前判断：否。Stage161 只仲裁数据源资格，不用收益结果拟合规则。
- 运行后判断：否。没有使用品种、年份、胜负样本或资金曲线形态生成交易条件，也没有运行 true engine。
- 原因：所有输出都是数据源合同层的 hard gate，不是 alpha 选择。

## 继续价值反思

- 运行前判断：有。Stage160 后如果不核查 TqSdk/Stage861，就可能误以为“本地有分钟 CSV，所以可以继续策略”。
- 运行后判断：仍有价值，但已经到达边界。Stage161 明确了替代源必须 proofed conversion，不能直接绕过 Stage153。
- 原因：目标的核心是无过拟合地找高质量分钟信号；没有授权且可回溯的分钟数据，后续策略实验无法证明有效。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage161 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃。
