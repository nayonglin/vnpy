# Stage067 Reentry 微观盘口稳定性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 07:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：固定 Stage066 tick/orderbook 特征的稳定性审计；不是真实组合引擎，不生成交易规则
- 是否重要突破：否，属于研究分支反证与方向收束
- 是否触发A/B：否；`strategy_rule_created=false`、`true_engine_run=false`

## 外部调研与判断

- 参考资料：
  - hftbacktest 文档把 order book imbalance / order flow imbalance 定义为常用微观结构指标，并列出 static imbalance、VAMP、weighted depth 等可执行盘口派生特征。
  - hftbacktest GitHub 项目强调 tick、L2/L3 盘口、队列位置和延迟对高频回测的重要性，说明盘口字段若要交易化，必须落到执行可成交口径，而不是只看 OHLC。
  - Briola/Bartolucci/Aste 的 LOB forecasting 研究明确提醒：高预测指标不一定等于可交易信号，必须用实际交易可执行框架评估。
  - Cartea/Donnelly/Jaimungal 的 LOB volume imbalance 研究支持盘口不平衡能解释短期订单流和价格修正，但也强调 adverse selection、订单类型和样本外测试。
- 我的判断：盘口不平衡、spread、depth、OI delta 有短期解释力是成立的；但本线目标是“穿越周期、保护 C9 右尾、降低回撤且收益保留 80%+”，不能把 54 个 reentry 样本里最高相关的 OI delta 包装成规则。必须先做跨年、产品族、右尾保护、坏尾识别审计；审计不通过就应该停止该分支。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage067_reentry_microstructure_stability_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 无交易参数。
  - 固定审计 score 仅用于视觉/稳定性诊断，不作为交易规则：低 `open_interest_delta_target`、低 `median_spread_r`、低 `p90_spread_r`、高 `median_depth1_log`、高 `median_directional_book_imbalance`、高 `directional_mid_move_r`、高 `directional_last_move_r`。
  - 固定诊断 bucket：`headwind_low_score`、`mixed_mid_score`、`supportive_high_score`；不是可执行阈值，不进入 true engine。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据输入：Stage066 `54/54` 个 C9 reentry tick 微观盘口事件。
- 官方基准：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 账户规模：`150,000`
- 成本口径：本阶段不新增成交、不改变成本；官方基准沿用 Stage046/正式 C9 成本口径。
- 审计口径：
  - 全局 Spearman 与预声明方向是否一致。
  - leave-one-year：每次留出一个 reentry 年份，训练集只确定符号和中位数，检查留出年 favorable vs unfavorable 的均值 edge。
  - 产品族稳定性：按静态 product family 分组检查符号一致性。
  - 尾部门槛：必须同时保护 `OI201/lh2301/FG601` 右尾并识别 `jm2209/OI505` 坏尾。

## 结果

- 期末权益：官方基准 `39,176,437.60`；本阶段无新 C 版本期末权益。
- 总收益：官方基准 `26017.6251%`；本阶段无新 C 版本总收益。
- 最大回撤：官方基准 `-45.0827%`；本阶段无新 C 版本最大回撤。
- Sharpe：官方基准 `1.6339`。
- 总滑点：官方基准 `2,730,130`。
- 总交易次数：官方基准 `787`。
- 胜率：官方日胜率 `53.2560%`；closed-lot 胜率仍只作历史参考。
- 其他关键指标：
  - `event_count=54`
  - `microstructure_ready_count=54`
  - `product_count=16`
  - `product_family_count=10`
  - `year_count=9`
  - 决策：`stage067_reentry_microstructure_stability_failed_stop_rule_path`
  - 下一步：`stop_reentry_microstructure_rule_path_and_move_to_stage045_initial_entry_tick_coverage_audit`
  - 稳定 score 特征数：`0`
  - 审计门槛通过：`1/5`
  - 通过项只有 `supportive_bucket_net_positive=true`
  - 未通过项：`stable_score_feature_count_ge3=false`、`all_named_right_tail_watch_supportive=false`、`all_named_bad_tail_watch_headwind=false`、`headwind_bucket_net_negative=false`

### 固定 score bucket

| bucket | 事件数 | 净 reentry PnL | 正收益覆盖 | 负收益覆盖 | 右尾 watch | 坏尾 watch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `headwind_low_score` | 12 | `+691,355.00` | `20.9543%` | `13.9903%` | 1 | 0 |
| `mixed_mid_score` | 29 | `+1,463,216.80` | `59.2013%` | `66.5771%` | 2 | 2 |
| `supportive_high_score` | 13 | `+542,725.20` | `19.8444%` | `19.4325%` | 0 | 0 |

### 特征稳定性

- `open_interest_delta_target` 全局 Spearman `-0.3605`，方向符合“低 OI 扩张较优”，但 leave-one-year 正 edge 率只有 `57.1429%`、产品族符号一致率 `50.0000%`，不达稳定门槛。
- `median_directional_book_imbalance` 全局 Spearman `+0.1148`，leave-one-year 正 edge 率 `75.0000%`，但产品族符号一致率仅 `50.0000%`，不达稳定门槛。
- `median_depth1_log` 全局方向符合预期，但 leave-one-year 正 edge 率仅 `14.2857%`。
- `directional_mid_move_r`、`directional_last_move_r`、`median_spread_r`、`p90_spread_r` 的全局符号与第一性预期不一致或产品族不稳。

### 右尾/坏尾门槛

- 右尾保护失败：
  - `FG601.CZCE` reentry PnL `+950,000`，score `4/7`，bucket `mixed_mid_score`。
  - `OI201.CZCE` reentry PnL `+907,500`，score `2/7`，bucket `headwind_low_score`。
  - `lh2301.DCE` reentry PnL `+867,200`，score `3/7`，bucket `mixed_mid_score`。
- 坏尾识别失败：
  - `jm2209.DCE` reentry PnL `-310,980`，score `3/7`，bucket `mixed_mid_score`。
  - `OI505.CZCE` reentry PnL `-172,500`，score `4/7`，bucket `mixed_mid_score`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_report_stage067_reentry_microstructure_stability_audit_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_decision_stage067_reentry_microstructure_stability_audit_v1.json`
- events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_events_stage067_reentry_microstructure_stability_audit_v1.csv`
- feature stability：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_feature_stability_stage067_reentry_microstructure_stability_audit_v1.csv`
- leave-one-year：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_leave_one_year_stage067_reentry_microstructure_stability_audit_v1.csv`
- family summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_family_summary_stage067_reentry_microstructure_stability_audit_v1.csv`
- score bucket：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_score_bucket_summary_stage067_reentry_microstructure_stability_audit_v1.csv`
- 官方路径与 score 资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_official_path_score_chart_stage067_reentry_microstructure_stability_audit_v1.png`
- 特征稳定性图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_feature_stability_chart_stage067_reentry_microstructure_stability_audit_v1.png`
- 右尾/坏尾散点：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_tail_protection_scatter_stage067_reentry_microstructure_stability_audit_v1.png`
- 产品族/年份热力图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_year_family_heatmap_stage067_reentry_microstructure_stability_audit_v1.png`
- tail 微观结构 atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage067_reentry_microstructure_stability_audit/qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit_tail_microstructure_atlas_stage067_reentry_microstructure_stability_audit_v1.png`

## 视觉结论

- 官方路径 score 图：得分桶没有形成单调资金贡献。`headwind_low_score` 反而净盈利 `+691,355`，且包含 `OI201` 大右尾；`supportive_high_score` 没有覆盖命名大右尾。
- 稳定性图：没有任何 score 特征同时满足全局方向、leave-one-year 和产品族一致性；`open_interest_delta_target` 是最强单变量，但分段稳定性不够。
- 右尾/坏尾散点：大赢家和大亏在 score、OI delta、方向盘口不平衡上明显重叠，`jm2209/OI505` 没有落入低分坏尾区。
- 产品族/年份热力图：贡献集中在少数 family-year cell，例如 grains_oilseeds/livestock/black_ferrous 的个别年份；样本稀疏，不支持穿越周期规则。
- tail atlas：`OI201/lh2301/FG601` 与 `jm2209/OI505` 的 target-minute mid move、spread/depth、方向 book imbalance 都不是可分离形态；部分大赢家甚至出现方向 mid move 负值或方向 book imbalance 负值。

## 结论

- 本阶段结论：`stage067_reentry_microstructure_stability_failed_stop_rule_path`。
- 是否进入下一步：进入，但不是继续 reentry 盘口规则化；转向 Stage045 `timestamp_ready=1` initial entry 的同口径 tick/盘口覆盖审计。
- 不进入事项：
  - 不写真引擎。
  - 不触发 A/B。
  - 不接正式候选。
  - 不继续扫 `open_interest_delta_target`、spread、depth、imbalance、mid/last move、score bucket、产品、年份、方向或产品族。

## 过拟合反思

- 运行前判断：否。
- 原因：Stage067 只使用 Stage066 已固定特征和预声明稳定性门槛，没有按结果选择阈值，也没有把最高相关单变量直接写成规则。
- 运行后判断：否。
- 原因：审计结果虽然显示 `open_interest_delta_target` 最强，但我没有继续围绕它救参；相反按预声明门槛关闭 reentry 盘口规则化分支。拒绝把局部相关性包装成策略，是本阶段最重要的反过拟合动作。

## 继续价值反思

- 运行前判断：有价值。
- 原因：Stage066 已把 tick 覆盖补到 `54/54`，必须用全覆盖样本确认盘口 route 是否值得继续。
- 运行后判断：reentry 盘口规则化本身暂时没有继续价值；总体目标仍有继续价值。
- 原因：当前 evidence 已证明重入当刻盘口字段无法同时保护 C9 右尾并识别坏尾。继续在该小样本上扫阈值只会过拟合。更有价值的下一步是把同口径盘口审计前移到 initial entry 的 timestamp-ready 子集，或换真正外生、入场前可见、覆盖完整的信息源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage067 反证和停止 reentry 盘口规则化边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、跨线合入或重要路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线分支关闭，不是收益/回撤突破或正式候选。
