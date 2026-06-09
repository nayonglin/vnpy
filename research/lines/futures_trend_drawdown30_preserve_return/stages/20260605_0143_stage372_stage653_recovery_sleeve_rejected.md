# Stage372 Stage653 受限恢复仓 sleeve 多周期反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-05 01:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 部署风控层实验；固定当前官方实盘版本 Stage653/20万，测试“风险倍率0.1触底时，只对结构恢复信号启用1手恢复仓”的机制。
- 是否重要突破：否，但属于重要正向线索。相比 Stage371 粗暴最少1手，Stage372 明显更稳，但仍未通过正式替换闸门。
- 是否触发A/B：是。A=`official_live_stage653_20w_force95_to80`；C=`Stage653 + recovery sleeve`。B standalone 不单独设立，因为这是部署/风险层补丁，不是独立 alpha。

## 外部调研与判断

- 参考资料：
  - CME Group `Margin: Know What's Needed`：期货保证金是开仓/持仓履约保证金，保证金要求会随市场波动和清算规则变化。
  - CME Group `Position and Risk Management`：手数应基于账户规模、风险情景和资金承受力，不应只按券商允许的最大保证金来决定。
  - 本地策略已有 `streak_entry_structure_recovery_signals=long_case1a,short_case1a`，说明仓库内已经有“结构恢复信号”的低自由度语义。
- 我的判断：
  - “0.1 风险倍率导致0手”是小资金和期货最小合约粒度的真实结构问题。
  - 但修复不能是全局最少1手；更合理的是只在组合空仓、结构恢复信号、相关不拥挤、单手保证金可承受时开一个受限恢复仓。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage662_stage653_recovery_sleeve_multiperiod.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数/规则：
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,short_case1a`
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `RECOVERY_BROKER_MARGIN_MULTIPLIER=1.65`
  - `RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY=0.20`
  - `RECOVERY_COOLDOWN_CALENDAR_DAYS=20`
  - 恢复仓强制 `selected_volume=1`，只在 `streak_entry_structure_risk_recovery_applied=1` 且基础风险倍率 `<=0.1` 时生效。
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
- 策略/归因口径：当前官方实盘 Stage653/20万 `stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4` + 受限恢复仓。

## 结果

- 全周期 C：
  - 期末权益：`8,728,285`
  - 总收益：`4264.1425%`
  - 最大回撤：`-38.6713%`
  - Sharpe：`1.6279`
  - 总滑点：`506,220`
  - 总交易次数：`633`
  - 胜率：`52.2586%`
  - broker10 保证金峰值：`79.6015%`
  - 强制减仓：`6` 次 / `299` 手
- 关键多周期：
  - `since_2021`：`4,642,610 / 2221.3050% / -38.1656% / Sharpe 1.5636`，相对原版 `-49.1004%` 修复并通过 DD40。
  - `since_2022`：`467,710 / 133.8550% / -28.0550% / Sharpe 0.8895`，修复原版 `-19.6200%`，但弱于 Stage371 粗暴最少1手的 `437.2350%`。
  - `phase_2022_2023`：`200,595 / 0.2975% / -28.0550% / Sharpe 0.1053`，从原版 `-32.2300%` 修到小幅正收益。
  - `ytd_2026_latest_ai`：`222,440 / 11.2200% / -16.3027% / Sharpe 1.0240`，明显强于原版 `201,140 / 0.5700% / -14.5394%`，但回撤深 `1.7633pp`。
- 成本压力：
  - 全周期 2x：`8,222,065 / 4011.0325% / -40.6555% / Sharpe 1.5544`，硬失败。
  - 全周期 3x：`7,715,845 / 3757.9225% / -42.7649% / Sharpe 1.4816`，硬失败。
  - `since_2021` 2x：`4,380,010 / 2090.0050% / -39.7934%`，通过 DD40；3x 为 `-41.4937%`，失败。
  - `since_2022` 1x/2x/3x 最大回撤分别为 `-28.0550%/-28.6200%/-29.2300%`，均通过。
- A/C 对照：
  - 全周期收益从 `5107.5350%` 降到 `4264.1425%`，少 `843.3925pp`；回撤浅 `0.2017pp`；交易从 `655` 降到 `633`；滑点从 `597,710` 降到 `506,220`；broker10 峰值从 `83.3212%` 降到 `79.6015%`。
  - `since_2021` 收益提升 `245.7625pp`，回撤改善 `10.9348pp`。
  - `since_2022` 收益提升 `153.4750pp`，回撤改善 `6.1600pp`。
  - `since_2023` 和 `since_2024` 收益明显低于原版，分别少 `107.4575pp` 和 `121.9525pp`。
  - 最新 YTD 收益提升 `10.6500pp`，回撤变深 `1.7633pp`，仍在预声明容忍线内。
- 滚动窗口：
  - 63日 p05：`-12.5900%`
  - 126日 p05：`-7.5638%`
  - 252日 p05：`8.2030%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_report_stage662_stage653_recovery_sleeve_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_summary_stage662_stage653_recovery_sleeve_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_comparison_stage662_stage653_recovery_sleeve_multiperiod_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_cost_stress_stage662_stage653_recovery_sleeve_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_chart_stage662_stage653_recovery_sleeve_multiperiod_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_decision_stage662_stage653_recovery_sleeve_multiperiod_v1.json`

## 结论

- 本阶段结论：`stage653_recovery_sleeve_candidate_rejected`。
- 是否进入下一步：不进入正式线上替换；但比 Stage371 更接近可用，保留为受限恢复仓方向的主证据。
- 下一步：
  - 不继续扫 `0.2/0.3` 保证金线、`10/20/30` 冷却天数或 `0.5/0.8/1.0` 恢复倍率。
  - 若继续推进，应先做归因：全周期 2x 成本失败是恢复仓造成，还是原 Stage653 长回撤成本压力继承；不要用恢复仓小数去救系统性成本失败。
  - 当前实盘默认仍维持原版 `official_live_stage653_20w_force95_to80`；实盘动作继续以每日影子盘、fresh read-only、dry-run、人工确认和 TCA 为先。

## 过拟合反思

- 运行前判断：不是典型过拟合。候选规则来自期货最小合约粒度和已有结构恢复信号，不是为了单窗调参。
- 运行后判断：继续调恢复仓阈值会进入过拟合。Stage372 已显著改善 2021/2022/YTD，但没有过全周期 2x 成本；失败只差 `0.6555pp`，此时最容易开始小数救援，应停止。
- 原因：Stage372 的价值在机制形状，而不是某个具体冷却天数或保证金线。正式推广必须靠更高层成本/TCA治理，而非恢复仓细调。

## 继续价值反思

- 运行前判断：有价值。它针对 Stage371 暴露的“粗暴至少1手误伤过大”做机制化收窄。
- 运行后判断：有价值，但不是继续调参价值，而是归因价值。
- 原因：它把 Stage371 的粗暴参与改成结构恢复仓后，修复 `since_2021/since_2022/YTD`，说明方向不假；但全周期 2x 成本仍失败，说明正式版本还缺成本执行层证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage372 反证。
- 是否更新 `research/registry.md`：是，最新关键阶段切到 Stage372，但官方默认仍不变。
- 是否追加根目录 `memory.md/back_log.md`：是，属于当前实盘候选的重要负向决策和后续研究边界。
