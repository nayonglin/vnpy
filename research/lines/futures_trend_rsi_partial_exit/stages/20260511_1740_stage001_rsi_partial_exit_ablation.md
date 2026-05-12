# Stage001 RSI分批止盈开关消融（Stage247）

- line_id：`futures_trend_rsi_partial_exit`
- 当前模式：`day`
- 记录时间：`2026-05-11 17:40`
- 工作区/分支：本机工作区（未做 git 约束）
- 阶段性质：A vs C 单变量消融
- 是否重要突破：否（首轮结论偏负面）
- 是否触发A/B：是（A=显式OFF，C=显式ON；不设B）

## 外部调研与判断

- 参考资料：
  - 快速浏览了若干“partial profit taking / scale-out”类文章与实践经验，主结论一致：分批止盈常用于降低回吐，但对趋势策略存在显著“截断右尾”的风险（大赢家贡献会被削弱）。
  - 本仓库 `QmtRollPortfolioStrategy` 的实现属于“极端 RSI 触发一次性减半”，且同一持仓只触发一次（`state.rsi_partial_exit_done`）。
- 我的判断：
  - 从第一性原理看，这类规则更可能提升资金曲线平滑度，但对“靠少数大趋势赚钱”的趋势系统，最常见副作用是降低长期复利。
  - 因为我们明确要求“能穿越周期”，所以判定标准应以多周期鲁棒性、弱周期存活与成本压力为主，不能只看最大回撤略微改善。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无（使用策略内既有参数）
- 修改参数：无（显式覆盖开关，仅做消融）
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-04-30`（与当前 `78-1` 口径一致）
- 账户规模：`500,000`
- 成本口径：使用策略内既有费率/滑点口径；并做滑点倍数压力 `x1/x2/x3/x5`
- 样本过滤：无
- 策略/归因口径：
  - 基准：`official_stage78_1_defensive_50w_no_sizing_cap`
  - 唯一变量：`enable_rsi_partial_exit` 显式开/关（阈值固定 `95`，比例固定 `0.5`）
  - 备注：由于 `run_backtest()` 的默认 setting 中存在 `enable_rsi_partial_exit=True` 的隐式默认，本实验用“显式开/关”确保对照口径不被污染。

## 结果

主回测（since_2020）：

- A（显式 OFF）：`rsi_partial_exit_off`
  - 期末权益：`29,302,880`
  - 总收益：`5760.576%`
  - 最大回撤：`-40.8215%`
  - Sharpe：`1.1520`
  - 总滑点：`2,190,590`
  - 总交易次数：`869`
  - 胜率：`41.8014%`
- C（显式 ON）：`rsi_partial_exit_on`
  - 期末权益：`25,542,885`
  - 总收益：`5008.577%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`

多周期要点（ON - OFF）：

- `since_2020/2021/2022/2023/2024`：ON 的收益显著低于 OFF；回撤略有改善但幅度不足以抵消收益损失。
- `since_2025`：ON 在收益上略优于 OFF（`+24.341%`），且最大回撤更低（约 `-26.32%` vs `-32.82%`）。
- `since_2026`：两者完全一致（该窗口内未产生可触发差异的情况，或触发不影响最终路径）。

滑点压力（x1/x2/x3/x5）：

- ON 相对 OFF：总滑点更低；在 `x2/x3` 下最大回撤更小；但在 `x1` 下长期收益劣势仍然明显。
- 在 `x5` 极端压力下，两者回撤接近（约 `-66%`），说明该规则不是尾部“结构性保护”。

## 输出文件

- report：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite_report_stage247_stage78_1_rsi_partial_exit_ablation_suite_v1.md`
- summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite_main_summary_stage247_stage78_1_rsi_partial_exit_ablation_suite_v1.csv`
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite_multiperiod_summary_stage247_stage78_1_rsi_partial_exit_ablation_suite_v1.csv`
- daily：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite_main_daily_stage247_stage78_1_rsi_partial_exit_ablation_suite_v1.csv`
- quality：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage247_stage78_1_rsi_partial_exit_ablation_suite_slippage_stress_stage247_stage78_1_rsi_partial_exit_ablation_suite_v1.csv`

## 结论

- 本阶段结论：
  - “RSI>95 减半”在全周期/多数起点上表现为：收益显著下降，回撤小幅改善。
  - 这更像典型的“截断右尾”，不符合趋势策略的穿越周期诉求，因此不建议合入 `78-1` 默认基准。
- 是否进入下一步：有条件继续（只做低自由度归因，不做阈值/比例调参）
- 下一步：
  - 做一次“触发频率与收益贡献归因”：统计 `long_rsi_partial_exit_half/short_rsi_partial_exit_half` 触发次数、触发后的持仓 PnL 贡献，验证是否确实在截断大赢家。
  - 如果确认为右尾被截断，则停止该方向，不再尝试通过调阈值“救版本”。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：只做单变量开关消融，阈值/比例固定，不根据结果迭代参数。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是（但只允许做归因，不允许调参）
- 原因：需要把“回撤略优但收益显著下降”的根因量化出来，形成可复用的决策结论，避免未来重复投入。

## 合入建议

- 是否更新本线 `LINE.md`：否（先写入 Stage001；等归因完成再更新本线状态）
- 是否更新 `research/registry.md`：否（并行规则：暂不频繁更新 registry，由合入者统一维护）
- 是否追加根目录 `memory.md/back_log.md`：否（首轮为负面结果，不属于重要突破/正式候选）

