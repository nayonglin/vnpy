# Stage049 Stage037 与当前线上版蒙特卡洛路径复核

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-29 02:58 CST`
- 工作区/分支：`.worktrees/stage047-stage037-vs-live-fullperiod` / `codex/stage047-stage037-vs-live-fullperiod`
- 阶段性质：Stage047 冻结全周期结果的成对路径重采样压力测试
- 是否重要突破：否；Stage037 收益分布较强，但主路径质量门未全部通过
- 是否触发A/B：是；A 为当前线上生产版本，C 为冻结 Stage037

## 外部调研与判断

- 参考资料：AQR《A Century of Evidence on Trend-Following Investing》；Bailey 等《The Probability of Backtest Overfitting》；GitHub `arch` 与 `recombinator` 的 circular block bootstrap 实现。
- 我的判断：趋势策略日收益具有连续趋势、反转和亏损簇，IID 会破坏依赖结构，只能作为乐观下限；固定长度 circular block bootstrap 能保留块内顺序，但仍只是历史路径重排，不是未来收益预测或重新运行交易引擎。
- 资料：<https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing>；<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253>；<https://github.com/bashtage/arch>；<https://github.com/InvestmentSystems/recombinator>。

## 本次变更

- 新增脚本：`tools/stage049_stage037_vs_current_online_monte_carlo.py`。
- 新增测试：`tests/test_stage049_stage037_vs_current_online_monte_carlo.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增策略参数：无。
- 修改策略参数：无。
- 删除策略参数：无。
- 新增研究参数：`10,000` 路径/方法、`block=(1,20,60,120)`、主判断 `60/120` 日块、固定 seed `4903720260829`、A/C 共用同一重采样索引。
- 新增结果：每个方法 `10,000` 对，合计 `40,000` 对、`80,000` 条策略路径；三张图、逐路径结果、分位汇总、成对汇总和决策。
- 修改结果：Stage047 真引擎历史指标未改。首次生成后的核对发现源路径表历史 Sharpe 被按 `sqrt(252)` 重算，与真引擎相差约 `0.00035`，改为直接引用 Stage047 summary。独立 reviewer 随后发现首段负收益时初始 NAV=1 未被纳入 running peak，会轻微低估部分回撤概率；最终实现已修复并全量确定性重建。收益分布不变，回撤指标按正确口径小幅更新，失败结论不变。
- 删除结果：删除重新计算的历史 Sharpe 展示口径；删除未包含初始本金峰值的前两版模拟回撤结果，统一以最终 Stage049 产物为准。

## 回测/归因参数

- 数据区间：历史源路径 `2018-01-02 -> 2026-08-28`；对齐日收益 `2018-01-03 -> 2026-08-28`，共 `2,100` 条。
- 账户规模：历史真引擎 `150,000 CNY`；蒙特卡洛使用 rebased NAV，不改变账户或交易规则。
- 成本口径：日收益已经包含 Stage047 的手续费、滑点和真实组合路径成本；重采样不额外调整成本。
- 样本过滤：A/C 日期严格一一对齐；NAV 必须有限、严格大于0；收益必须有限且大于-100%。
- A：当前线上 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- C：冻结 `stage037_stage034_long_short_mirror_hard_block_v1`。
- 方法：成对 circular block bootstrap；同一次模拟的 A/C 共用索引，块内保持历史日收益顺序，尾部循环衔接。
- 运行：完整生成三次。第一次为初始实现；第二次只修历史 Sharpe 展示身份；独立 reviewer 发现初始本金回撤口径和 Stage048 decision 锁定两个 P1 后，第三次以同 seed 全量重建最终产物。没有策略参数变化，但前两版回撤结果已作废。

## 预声明门

- 主判断只看 `block_60` 与 `block_120`。
- 每个主方法分别要求：C 收益胜率 `>=55%`；C-A 收益差中位 `>=0`；C 最大回撤不劣于 A 超过2pp的比例 `>=80%`；C Sharpe 不劣于 A 超过0.05的比例 `>=80%`；C 的 p05 期末 NAV 不低于 A；C 的 DD50 概率不高于 A。
- 两个主方法必须全部通过才可称“蒙特卡洛支持稳定路径优势”；即便通过，也不能覆盖 Stage048 多周期硬失败或自动晋升。

## 历史真引擎源结果

### A 当前线上

- 期末权益：`14,665,615.10`
- 总收益：`9677.0767%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.461353`
- 总滑点：`1,743,270`
- 总交易次数：`847`
- 胜率：`52.6690%`（非零交易日）

### C Stage037

- 期末权益：`16,862,237.30`
- 总收益：`11141.4915%`
- 最大回撤：`-39.9147%`
- Sharpe：`1.539584`
- 总滑点：`1,671,655`
- 总交易次数：`734`
- 胜率：`53.1502%`（非零交易日）

## 蒙特卡洛结果

| 方法 | 策略 | p05期末NAV | 中位期末NAV | p05最大回撤 | 中位最大回撤 | DD40概率 | DD50概率 | DD60概率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| block60 | A线上 | 10.3656 | 91.2720 | -56.3139% | -40.9176% | 54.93% | 15.15% | 2.52% |
| block60 | C Stage037 | 11.2783 | 105.3343 | -57.2643% | -40.7878% | 53.76% | 15.89% | 2.77% |
| block120 | A线上 | 9.0246 | 91.5872 | -54.8899% | -40.8686% | 54.78% | 12.92% | 1.75% |
| block120 | C Stage037 | 10.1609 | 104.7264 | -51.8936% | -39.9147% | 44.84% | 7.85% | 0.59% |

| 方法 | C收益胜率 | C-A收益差中位 | DD非劣2pp率 | C-A回撤差中位 | Sharpe非劣0.05率 | 全门 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| iid | 63.32% | +823.4327pp | 82.60% | +2.6775pp | 86.03% | 通过 |
| block20 | 63.50% | +712.0172pp | 77.65% | +1.5626pp | 88.78% | 失败 |
| block60 | 64.93% | +762.0607pp | 66.47% | -0.1425pp | 90.47% | 失败 |
| block120 | 65.73% | +714.9546pp | 69.52% | +0.6709pp | 92.41% | 失败 |

- Stage037 的收益优势有明显统计宽度：主块收益胜率 `64.93%/65.73%`，中位期末 NAV 高于线上约 `14.06/13.14`。
- 但不是稳定支配：仍有 `35.07%/34.27%` 的主块路径收益低于线上；p05 的 C-A 期末 NAV 差为 `-81.64/-77.83`。
- 关键失败是回撤路径：DD非劣2pp率只有 `66.47%/69.52%`；block60 下 Stage037 的 DD50 概率反而为 `15.89%`，略高于线上 `15.15%`。
- block120 的边际风险表现较好，但单独一个块长通过部分指标不能覆盖 block60 和成对回撤门失败。

## 输出文件

- report：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_monte_carlo_report.md`
- summary：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_monte_carlo_summary.csv`
- paired summary：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_paired_summary.csv`
- simulations：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_simulations.csv`
- paired simulations：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_paired_simulations.csv`
- source stats：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_source_path_stats.csv`
- decision：`artifacts/stage049_stage037_vs_live_monte_carlo/stage049_decision.json`
- charts：`stage049_nav_fan_ac.png`、`stage049_drawdown_probability_ac.png`、`stage049_paired_advantage_ac.png`

## 结论

- 本阶段结论：决策为 `stage049_mc_does_not_support_stable_stage037_path_advantage_keep_research`。Stage037 的收益分布优于线上版，但在较长相关块下，成对回撤优势不稳定；它仍是高收益研究候选，不是稳定压过线上版的路径风险候选。
- 是否进入下一步：不进入正式晋升或部署；Stage048 多周期硬失败继续有效。
- 下一步：不扫 block 长度、ATR、天数、方向、品种或阈值救参；若继续，只做冻结规则 forward shadow 或等待新样本。

## 过拟合反思

- 运行前判断：本次不是新增过拟合；方法、块长、路径数、seed 和门槛在看结果前冻结，策略参数不变。
- 运行后判断：本次检验本身仍不是过拟合，但 Stage037 作为历史多轮筛选版本保留后验选择风险。
- 原因：蒙特卡洛只重排既有日收益；若根据 block60 的失败再调整过滤阈值或只报告 block120，就会成为典型的结果后选择。

## 继续价值反思

- 运行前判断：有价值；多周期只能观察真实起点，蒙特卡洛可检查盈亏块顺序变化后的路径脆弱性。
- 运行后判断：本次验证有价值，但继续扫描没有价值。
- 原因：结果清楚地区分了“收益分布更强”和“回撤稳定支配”——Stage037 只满足前者。

## 安全边界

- 离线读取冻结 Stage047 产物；没有运行新策略回测、没有连接 CTP。
- order/send/cancel API 调用均为 `0`。
- 未修改正式物料、生产 worktree、AI池、launchd、远端 master 或券商状态。

## 独立评审与验证

- 独立 reviewer 最终结论：`PASS`，`P0/P1/P2/P3=0/0/0/0`。
- reviewer 独立复算 `80,000` 条策略路径和 `40,000` 对路径；summary 最大差 `5.82e-11`、paired summary 最大差 `3.64e-12`，配对 delta 最大数值误差 `1.86e-9`。
- Stage047/048/049 扩大谱系测试 `43 passed`；主代理本地相关回归 `13 passed`；`py_compile` 与 `git diff --check` 通过。
- reviewer 确认 A/C 共用索引、块内递增、模N循环、初始NAV回撤峰值、Stage048 decision SHA及 hard-fail 绑定均正确；无 CTP/order 调用。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线继续只写唯一 Stage049 文件，统一合入时再整理。
- 是否更新 `research/registry.md`：否；研究线归属未变化。
- 是否追加根目录 `memory.md/back_log.md`：否；不是重要突破、正式候选或跨线里程碑。
