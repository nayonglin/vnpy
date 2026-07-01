# Stage156 当前重建版三臂年度基准

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：延续 Stage154/155，把历史有价值结构落到当前重建版三臂基准：Stage372 legacy recovery sleeve、Stage819/C4 broker10 cap、Stage847/C9 0.5R stop/retry once。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮按用户此前“不要搜索”的约束不做外网/GitHub搜索；只用本仓 Stage653/660/830/847/901 现有回测引擎。
- 我的判断：这不是新策略，而是当前 15万账户下的结构定位。目标是判断 C9 相对旧正式 Stage372 和上游 C4 的边际来自收益增强还是风险改善。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage156_current_rebuild_three_arm_annual_baseline.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 三臂：`stage372_legacy_recovery_sleeve_15w_current_ai`、`stage819_c4_broker10_cap_15w_current_ai`、`stage847_c9_stop_retry_15w_current_ai`
  - 统一资金：`150,000`
  - 统一 AI 池：当前 Stage182 combined eligibility 文件
  - 年度起点：`2018-01` 到 `2026-01`
  - 统一终点：`2026-06-30`
- 修改参数：无策略参数扫描；仅将三臂资金和 AI source 统一到当前重建版口径
- 删除参数：无

## 运行中发现的工程依赖

- 初版脚本在构造 Stage819/C4 profile 时失败：`Stage660._official_spec` 会回查 `OFFICIAL_LIVE_PROFILE_NAME`，而当前 live 已经是 C9 名称 `stage847_c9_15w_stage819_05r_stop_retry_live`，Stage660 找不到旧 Stage372 profile。
- 修复方式：参考 Stage901 的做法，只在构造 Stage819/C4 与 C9 profile 时临时把 Stage660 全局 state 切回 legacy Stage372，再立即恢复。
- 判断：这不是交易逻辑 bug，也不是 C9 实盘入口 bug；Stage901 已经有相同保护。但它说明后续 healthcheck 应覆盖 profile/capital/AI path/minute source，避免研究脚本或新入口误用当前 live 名称导致候选构造失败。

## 回测口径

- 三臂全部使用当前 Stage182 AI 池：
  - `qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 三臂全部使用 `150,000` fresh capital。
- Stage372 臂：Stage653 force95->80 + Stage372 recovery sleeve 参数。
- C4 臂：Stage819 + C2 entry-day 1R stop + broker10 cap。
- C9 臂：C4 + entry-day `0.5R` stop/retry once。
- 不连接 CTP，不读取账户，不调用订单 API。

## 结果

### Aggregate

| arm | 样本 | 正收益 | 收益最低/中位/最高 | 最差回撤 | 回撤中位 | Sharpe中位 | peak broker10 | DD30/DD40/DD50 | broker100 | 交易数 | 关键事件 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| `stage372_legacy_recovery_sleeve_15w_current_ai` | `9` | `7` | `-8.1200% / 19.5933% / 1547.6967%` | `-46.8263%` | `-31.4252%` | `0.4215` | `89.5033%` | `5 / 4 / 0` | `0` | `3,160` | forced events `23` |
| `stage819_c4_broker10_cap_15w_current_ai` | `9` | `9` | `0.1155% / 119.9371% / 8509.7715%` | `-56.2883%` | `-39.9596%` | `1.0300` | `95.0527%` | `5 / 4 / 4` | `0` | `3,329` | broker10 cap events `165` |
| `stage847_c9_stop_retry_15w_current_ai` | `9` | `9` | `1.9011% / 126.1993% / 9084.6458%` | `-56.2069%` | `-39.9820%` | `1.2246` | `96.6295%` | `5 / 4 / 4` | `0` | `3,531` | stop/retry events `171`，broker10 cap events `175` |

### 配对结论

- C9 收益胜出 Stage372：`9/9`
- C9 收益胜出 C4：`8/9`
- C9 回撤胜出 Stage372：`2/9`
- C9 回撤胜出 C4：`4/9`
- C9 对 C4 的边际：
  - 收益中位更高：`126.1993%` vs `119.9371%`
  - Sharpe 中位更高：`1.2246` vs `1.0300`
  - 回撤中位基本不改善：`-39.9820%` vs `-39.9596%`
  - peak broker10 略高：`96.6295%` vs `95.0527%`
  - 交易更多：`3,531` vs `3,329`

### 年度关键点

- 早期大右尾来自 C4/C9，不来自 Stage372 15万口径：
  - `2018-01`：Stage372 `1547.6967%`，C4 `3955.7052%`，C9 `8471.4361%`
  - `2019-01`：Stage372 `1547.6967%`，C4 `8509.7715%`，C9 `9084.6458%`
  - `2020-01`：Stage372 `1294.8367%`，C4 `3141.2297%`，C9 `3886.1873%`
- 风险尾也来自 C4/C9 进攻结构：
  - `2018-01` C9 回撤比 Stage372 深 `10.9176pp`
  - `2019-01` C9 回撤比 Stage372 深 `10.4952pp`
  - `2020-01` C9 回撤比 Stage372 深 `12.7309pp`
- 近期窗口：
  - `2025-01`：C4 收益 `34.4721%` 略高于 C9 `32.3783%`，C9 回撤略深
  - `2026-01`：C9 `1.9011%`，C4 `0.1155%`，Stage372 `-5.3467%`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_summary_stage156_current_rebuild_three_arm_annual_baseline_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_aggregate_stage156_current_rebuild_three_arm_annual_baseline_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_comparison_stage156_current_rebuild_three_arm_annual_baseline_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_curves_stage156_current_rebuild_three_arm_annual_baseline_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_decision_stage156_current_rebuild_three_arm_annual_baseline_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage156_current_rebuild_three_arm_annual_baseline_report_stage156_current_rebuild_three_arm_annual_baseline_v1.md`

## 结论

- C9 是当前重建版最强收益/Sharpe 三臂，但不是低风险替代。
- C4/C9 继承 Stage819 进攻结构后，明显提升收益与 Sharpe，但把 DD50 尾部带回来；Stage372 15万口径收益弱、正收益起点少，但 DD50 为 `0`。
- C9 stop/retry 对 C4 的收益边际为正，但回撤边际不稳定；它更像右尾参与增强，而不是风险治理。
- 继续优化当前版本时，应保留 AI 和 C9 骨架，但方向必须转向：
  1. C9 vs C4 的 stop/retry 事件归因：哪些 `171` 个事件贡献收益，哪些扩大回撤；
  2. C4/C9 相对 Stage372 的风险尾归因：早期 `2018-2021` DD50 尾部从哪些产品/方向/压力簇来；
  3. 工程 healthcheck：profile/capital/AI path/minute source/no-order-api manifest。
- 不应继续扫 `R倍数`、`重试次数`、`AI topN`、年份或品种黑名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：三臂、资金、AI 池、起点和终点全部预先固定；本阶段只做结构对照，不提出任何按结果挑选窗口或调参的规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：三臂基准明确了当前优化边界：C9 值得保留，但风险尾没有解决。继续价值在事件归因和账户/持仓层风险治理，不在参数扫描。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等 C9 stop/retry 事件归因或三臂风险尾归因补完后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是基准与归因前置，不是正式候选变更。
