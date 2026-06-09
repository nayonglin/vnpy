# Stage429 当前正式版 MA20 初始止损手数计算多起点反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 16:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前正式 Stage372/20万风控候选 A/C 多起点验证
- 是否重要突破：否，但形成“MA20 sizing 可降回撤、但砍掉正式右尾”的重要边界
- 是否触发A/B：是，已读取并遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - TradeAlgo `Futures Risk Management: Position Sizing, Stop`：期货仓位应由账户风险预算和止损距离共同决定，而不是只看保证金或主观信心。
  - Concretum Group `Position Sizing in Trend-Following`：趋势系统的仓位管理会显著改变收益/回撤形态，不能把 sizing 视为中性细节。
  - NexusFi `Automated Position Management in Futures Trading`：ATR/波动止损距离常用于反推合约手数，并需要同时受保证金和最大仓位限制。
  - GitHub/公开趋势跟踪资料：公开实现普遍把 position sizing、stop distance 和 portfolio heat 视为核心风险模块。
- 我的判断：
  - MA20 初始止损手数计算是低自由度、可解释的通用风险计量，不是按鸡蛋、红框或年份做补丁。
  - 但 Stage398/399 的线索来自另一个 `50万 + no AI + no loss streak` 分支，不能直接推广到当前正式 Stage372；本阶段必须用当前正式版多起点验证。
  - 本次只测 `MA20` 固定窗口，不扫 `10/15/30/40`，也不关闭 prev2day，不改 AI、不改品种池、不改连败倍率。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage715_official_ma20_initial_stop_multiperiod.py`
- 修改脚本：无正式策略修改；新增 wrapper 内按 candidate 分支运行期 monkeypatch `_entry_stop_price`
- 删除脚本：无
- 新增参数：
  - `MA_STOP_WINDOW=20`
  - `CANDIDATE_VARIANT=stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_ma20_initial_stop_stage715`
- 修改参数：
  - C 分支初始止损手数计算：当 MA20 位于有效趋势侧时，用 MA20 作为初始止损距离；否则回落到官方 `_entry_stop_price`
  - `streak_risk_multipliers` 保持 `1.0,1.0,1.0,0.1`
  - AI 池、品种池、recovery sleeve、退出逻辑、prev2day 均保持不变
- 删除参数：无
- 正式配置：未修改
- CTP/下单：未连接 CTP，未调用 order API
- 工程修正：首次运行发现 wrapper 把 MA20 monkeypatch 套在 A/C 两个分支上，导致 A/C 完全一致；该无效输出已废弃。已修正为只在 candidate 分支临时启用 MA20，并重跑覆盖输出。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本、`2x`、`3x` 滑点压力
- 样本过滤：当前正式 Stage372/20万 AI 池与品种池，不新增品种
- 策略/归因口径：
  - A：当前正式 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：A + `MA20` 初始止损手数计算，其他不变
- 多起点窗口：full、`since_2021` 至 `since_2026`、`phase_2020_2021`、`phase_2022_2023`、`phase_2024_2025`、`phase_2026_latest`

## 结果

### 全周期

- A 正式版：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次，`299` 手
- C MA20 初始止损：
  - 期末权益 `2,272,145`
  - 总收益 `1036.0725%`
  - 最大回撤 `-26.2102%`
  - Sharpe `1.4375`
  - 总滑点 `126,430`
  - 总交易次数 `572`
  - 胜率 `53.1953%`
  - broker10 峰值 `70.2109%`
  - 强制减仓 `1` 次，`5` 手
  - 收益保留 `24.2973%`

### 成本压力

- A `2x/3x` 成本 DD：`-40.6555%/-42.7649%`
- C `2x/3x` 成本 DD：`-27.2605%/-28.3662%`
- C 在成本压力和保证金上明显更稳，但这是以大幅牺牲右尾收益为代价。

### 多起点

- C 明显改善：
  - `since_2023`：A `70.2100%/-24.5662%/Sharpe0.7818`，C `101.8400%/-16.6001%/Sharpe1.0701`
  - `since_2024`：A `33.3550%/-29.4347%/Sharpe0.5945`，C `102.8075%/-15.4226%/Sharpe1.3949`
  - `since_2025`：A `17.9975%/-17.6662%/Sharpe0.6589`，C `84.7775%/-16.3218%/Sharpe1.7170`
  - `phase_2022_2023`：A `0.2975%/-28.0550%/Sharpe0.1053`，C `13.7450%/-20.0892%/Sharpe0.4183`
  - `phase_2024_2025`：A `33.2675%/-29.4347%/Sharpe0.6398`，C `106.3750%/-15.4226%/Sharpe1.5386`
- C 明显恶化：
  - `since_2021`：A `2221.3050%/-38.1656%/Sharpe1.5636`，C `343.3650%/-26.8760%/Sharpe1.2093`
  - `phase_2020_2021`：A `441.4650%/-24.2699%/Sharpe2.1114`，C `185.0750%/-26.2102%/Sharpe1.7110`
  - `since_2026/phase_2026_latest`：A `1.1450%/-16.3027%/Sharpe0.2783`，C `-3.6975%/-15.1948%/Sharpe-0.3843`

### 闸门

- hard fail：
  - `full_return_retention_ge80`：C 收益保留仅 `24.2973%`
  - `start_years_min_retention_ge70`：`since_2026` 为负收益，相对 A 退化
- watch：
  - `full_sharpe_not_lower`
  - `phase_min_retention_ge65`
- pass：
  - `full_dd30_pass`
  - `full_broker10_100_pass`
  - `cost2_full_dd40_pass`
  - `start_years_dd_not_worse_by_3pp`
  - `start_years_dd40_all_pass`
  - `phase_dd40_all_pass`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_report_stage715_official_ma20_initial_stop_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_summary_stage715_official_ma20_initial_stop_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_comparison_stage715_official_ma20_initial_stop_multiperiod_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_cost_stress_stage715_official_ma20_initial_stop_multiperiod_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_curves_stage715_official_ma20_initial_stop_multiperiod_v1.csv`
- annual/monthly：已输出
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_checks_stage715_official_ma20_initial_stop_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_chart_stage715_official_ma20_initial_stop_multiperiod_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage715_official_ma20_initial_stop_multiperiod_decision_stage715_official_ma20_initial_stop_multiperiod_v1.json`

## 结论

- 本阶段结论：`official_ma20_initial_stop_not_promoted`
- 是否进入下一步：不进入正式版，不继续扫 MA 窗口。
- 核心判断：
  - MA20 初始止损手数计算确实能把当前正式版全周期最大回撤压到 `-26.2102%`，且 2x/3x 成本压力明显更稳。
  - 但它把全周期收益从 `4264.1425%` 打到 `1036.0725%`，收益保留只有 `24.2973%`，主要砍掉 `2020-2021` 的复利底座和早期右尾。
  - 2023-2025 后段改善明显，说明“更宽风险距离”对某些震荡/成本压力阶段有用；但它不是穿越周期的正式替代。
  - 这不是解决“连败 0.1 经常开不出仓”的主路径，因为它更像整体降杠杆/降换手壳，而不是保留右尾参与权。
- 下一步：
  - 不扫 `MA10/15/30/40`，不按年份/品种补丁救 MA20。
  - 保留“宽风险距离/波动距离可作为风控组件”的思想，但不能单独替代正式版。
  - 当前目标继续转向更上游的账户级 selector、forward watch，或真正独立且事前有正期望的风险槽；正式主账户继续保持 Stage372/20万 `1,1,1,0.1 + recovery_sleeve`。

## 过拟合反思

- 运行前判断：不是典型过拟合，但有迁移风险。
- 原因：MA20 是通用风险计量，不按红框/鸡蛋/年份调参；但它来自 Stage398/399 的另一个分支，必须防止把那条分支的好结果直接搬到正式版。
- 运行后判断：不应继续救；继续扫 MA 窗口会过拟合。
- 原因：结果呈现明确的时期选择性：2023-2025 好，2020-2021 和 2026 冷启动弱。若继续调窗口或加条件，本质是在历史路径里找折中点。

## 继续价值反思

- 运行前判断：有价值。
- 原因：这是从第一性原理检验“手数风险距离”是否比继续改连败小数更合理。
- 运行后判断：本版本无继续价值；总目标仍有价值。
- 原因：它证明了风控不能只追求低 DD，必须保留趋势右尾；MA20 sizing 单独使用过于防守。目标应继续，但方向应从单一 stop-distance 替换转向“什么时候允许恢复右尾参与权”的更上游选择器。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage429 负结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为正式风控候选反证和后续禁区。
