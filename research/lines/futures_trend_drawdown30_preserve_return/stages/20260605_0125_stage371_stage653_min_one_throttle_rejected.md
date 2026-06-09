# Stage371 Stage653 最少1手降风险修复反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-05 01:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 部署风控层反证；固定当前官方实盘版本 Stage653/20万，只测试“风险倍率降到0.1后若风险预算算出0手，保证金和过滤允许时至少开1手”的可执行性补丁。
- 是否重要突破：否。它修复了 2022 冷启动开不了仓的问题，但没有通过正式替换闸门。
- 是否触发A/B：是。A=`official_live_stage653_20w_force95_to80`；C=`Stage653 + min-one throttle`。B standalone 不单独设立，因为本次是风险/执行层补丁，不是独立 alpha。

## 外部调研与判断

- 参考资料：
  - CME Group, `Margin: Know What's Needed`，说明期货保证金只是开仓/持仓所需履约保证金，且会随市场波动和清算规则变化。
  - CME Group, `Position and Risk Management`，强调头寸数量应基于账户规模和风险情景，不应只按券商允许的最大保证金来决定。
- 我的判断：
  - 期货天然存在“最小 1 手”的合约粒度，20万小资金账户中，风险预算被压到 0.1 后算出 0 手，确实会导致策略永远无法从低权益/低倍率状态恢复。
  - 但“至少 1 手”不能无条件启用；它只能在信号过滤、保证金、单笔上限、风险簇上限都允许时作为执行粒度修复，否则会把防守风控变成硬加仓。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage661_stage653_min_one_throttle_multiperiod.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数/规则：
  - 仅在 `entry_context == "flat_entry"` 时生效。
  - 当 `risk_multiplier <= 0.1` 且 `contracts_by_risk <= 0` 导致 `selected_volume <= 0` 时，如果 `limited_balance >= margin_per_contract`、`contracts_by_margin >= 1`、`contracts_by_single_trade_cap >= 1`、`risk_cluster_max_volume >= 1`，则强制最少 `1` 手。
- 修改参数：无正式配置修改；`qmt_roll_official_live_config.py` 未变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - 历史全周期：2020-01-02 至 2026-04-30。
  - 多起点：2021/2022/2023/2024/2025/2026 起点。
  - 分阶段：2020-2021、2022-2023、2024-2025、2021核心回撤窗口。
  - 最新 AI 池 YTD：2026-01-05 至 2026-06-04。
- 账户规模：20万 fresh capital。
- 成本口径：1x/2x/3x 滑点压力。
- 样本过滤：不重新训练、不调参、不连接 CTP、不调用下单。
- 策略/归因口径：当前官方实盘 Stage653/20万 `stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4` + 最少1手补丁。

## 结果

- 全周期 C：
  - 期末权益：`7,832,610`
  - 总收益：`3816.3050%`
  - 最大回撤：`-38.2236%`
  - Sharpe：`1.5426`
  - 总滑点：`475,960`
  - 总交易次数：`676`
  - 胜率：`52.5913%`
  - broker10 保证金峰值：`82.2830%`
  - 强制减仓：`8` 次 / `368` 手
- 关键多周期：
  - `since_2021`：`3,629,950 / 1714.9750% / -44.3682% / Sharpe 1.3961`，仍硬失败。
  - `since_2022`：`1,074,470 / 437.2350% / -34.4630% / Sharpe 1.1701`，修复原版 `-19.6200%` 的冷启动亏损问题。
  - `since_2023`：`984,625 / 392.3125% / -30.4052% / Sharpe 1.4229`，收益提高但回撤较原版明显变深。
  - `phase_2022_2023`：`291,170 / 45.5850% / -34.4630% / Sharpe 0.7022`，修复原版 `-32.2300%`。
  - `ytd_2026_latest_ai_min_one`：`194,270 / -2.8650% / -20.6148% / Sharpe 0.0599`，弱于原版 Stage659 `201,140 / 0.5700% / -14.5394%`。
- 成本压力：
  - 全周期 2x 成本：`3578.3250% / -40.4913%`，硬失败。
  - 全周期 3x 成本：`3340.3450% / -42.9186%`，硬失败且 broker10 峰值触及 `100.9012%`。
  - `since_2021` 2x/3x：`-47.1832% / -50.1634%`，仍不满足 DD40。
- A/C 对照：
  - 全周期收益从 `5107.5350%` 降到 `3816.3050%`，少 `1291.2300pp`；最大回撤略改善 `0.6495pp`。
  - `since_2022` 从 `-19.6200%` 提升到 `437.2350%`，但交易从 `112` 增至 `373`，滑点从 `6,260` 增至 `58,520`，保证金峰值从 `53.8481%` 升至 `70.8426%`。
  - `since_2023` 回撤从 `-17.3480%` 恶化至 `-30.4052%`。
  - `weak_2021_drawdown` 收益略好，但回撤从 `-18.9108%` 恶化至 `-25.5999%`。
- 检查项：
  - 通过：全周期正常成本 DD40、broker10 不穿100、2022起点转正。
  - 失败：全周期 2x 成本 DD40、2021起点 DD40。
  - 观察：63日任意启动 p05 为 `-18.5428%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_report_stage661_stage653_min_one_throttle_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_summary_stage661_stage653_min_one_throttle_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_comparison_stage661_stage653_min_one_throttle_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_cost_stress_stage661_stage653_min_one_throttle_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_chart_stage661_stage653_min_one_throttle_multiperiod_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage661_stage653_min_one_throttle_multiperiod_decision_stage661_stage653_min_one_throttle_multiperiod_v1.json`

## 结论

- 本阶段结论：`stage653_min_one_throttle_candidate_rejected`。
- 是否进入下一步：不进入正式线上替换。可以保留为“小资金冷启动粒度问题”的证据和后续改良方向。
- 下一步：
  - 不把最少1手直接接入 `official_live_stage653_20w_force95_to80`。
  - 若继续修复冷启动，应改为更窄的条件，例如只在恢复型信号、低保证金合约、低账户回撤压力、低频触发下允许最少1手；但必须先定义机制，不能围绕 2022 单窗调参。
  - 当前实盘侧仍优先执行脚本复核、真实 TCA、保证金口径和每日 Stage659 影子盘。

## 过拟合反思

- 运行前判断：不是典型过拟合。原因是“0.1 风险倍率导致 0 手、策略无法恢复”是 20万小账户与期货最小合约粒度之间的结构问题。
- 运行后判断：若直接推广会形成路径过拟合。它主要救了 2022/2023 冷启动，但显著恶化 2023、2024 和最新 YTD 的回撤/近端表现，且 2x 成本和 2021 起点仍失败。
- 原因：最少1手提升了低权益状态下的参与率，也放大了低质量震荡期的交易和成本；它修复的是“开不了仓”，不是“什么时候该恢复开仓”。

## 继续价值反思

- 运行前判断：有价值。用户指出的问题直接影响实盘小资金能否恢复交易。
- 运行后判断：有研究价值，但当前实现不值得继续作为候选推进。
- 原因：它给出清晰证据：冷启动失败不是 alpha 完全失效，而是 sizing 粒度和防守闸门共同造成；但粗暴最少1手会带来新的回撤和成本问题。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage371 反证。
- 是否更新 `research/registry.md`：是，当前官方版本仍维持 Stage653 原版，Stage371 不替换。
- 是否追加根目录 `memory.md/back_log.md`：是，属于当前实盘候选的重要负向决策。
