# Stage048 Stage037 与当前线上版本多周期复核

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-29 02:44 CST`
- 工作区/分支：`.worktrees/stage047-stage037-vs-live-fullperiod` / `codex/stage047-stage037-vs-live-fullperiod`
- 阶段性质：Stage047 通过后的固定多周期、独立冷启动稳健性复核
- 是否重要突破：否；Stage037 全周期占优，但多周期存在预声明硬失败
- 是否触发A/B：是；A 为当前线上生产版本，C 为冻结 Stage037

## 外部调研与判断

- 参考资料：AQR《A Century of Evidence on Trend-Following Investing》；Bailey 等《The Probability of Backtest Overfitting》及《The Deflated Sharpe Ratio》。
- 我的判断：趋势策略应在不同时间起点和市场状态下保持可接受的路径质量；回测后选参数会放大后验偏差。本阶段只扩展固定冷启动窗口，不改 Stage037 参数，也不根据失败窗口救参。

## 本次变更

- 新增脚本：`tools/stage048_stage037_vs_current_online_multicycle.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：仅研究窗口合同——`START_MONTHS=(1,6)`、`DURATIONS_YEARS=(1,2,3)`、完整窗口限定和预声明聚合门；这些不是策略参数。
- 修改参数：无；Stage037 的13项相对线上配置差异全部冻结。
- 删除参数：无。
- 新增结果：全周期 + 42 个1/2/3年完整独立冷启动窗口，A/C 共86个臂窗；五张固定图片、逐窗汇总、比较、聚合与决策。
- 修改结果：无；Stage047 全周期结果逐值复用并校验，不改写历史指标。
- 删除结果：无。

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-08-28`；全周期1个，1年16个、2年14个、3年12个完整窗口。
- 起点合同：每个1/2/3年周期均包含固定1月和6月起点；不纳入不完整终端窗口。
- 账户规模：每个窗口、每个臂均以 `150,000 CNY` 空仓独立启动，不继承前窗持仓或权益。
- 成本口径：A/C 使用同一品种手续费、滑点、保证金和风险乘数口径。
- A：当前线上 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，每窗直接运行生产 checkout 核心模块。
- C：`stage037_stage034_long_short_mirror_hard_block_v1`，冻结逻辑提交 `827764ed33f95e9aee6cc03b2b6703805a939ace`。
- 生产身份：production HEAD、本地 `origin/master` 和实时远端 master 均为 `09aa96a03fb91124be90bd69861be3f834ab6299`。
- 数据库：SHA256 `ee83eae2159afec2b745a5827f73aaf9da1e71d65af2c0a624496555c08b6ebe`，最新日线 `2026-08-28`。
- AI池：SHA256 `56b6a35419831809a27cf222a019e0a62c9dc34390fd996243ee26353a7004cf`，研究物料与生产物料逐项 parity 通过。
- 执行情况：Stage047 全周期复用并逐值验证；其余42窗×2臂均为独立真引擎，新生成 checkpoint `84`，复用 `0`。

## 预声明门

- 全周期：C收益不低于A；最大回撤恶化不超过2pp；Sharpe差不低于-0.02；滑点不超过A的105%；账户生存且broker100不劣于A。
- 各周期 combined/January/June：C收益胜率至少50%；收益差中位数非负；DD不劣2pp比例至少80%；Sharpe不劣0.05比例至少80%；聚合滑点不超过105%；账户生存且broker100不劣于A。
- 九个周期聚合门必须全部通过才支持下一正式评审；本阶段无论结果如何均不自动晋升或部署。

## 全周期结果

### A 当前线上

- 期末权益：`14,665,615.10`
- 总收益：`9677.0767%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.461353`
- 总滑点：`1,743,270`
- 总交易次数：`847`（成交记录口径）
- 胜率：`52.6690%`（非零交易日胜率）
- 其他关键指标：broker10峰值 `99.6724%`，超100%天数 `0`。

### C Stage037

- 期末权益：`16,862,237.30`
- 总收益：`11141.4915%`
- 最大回撤：`-39.9147%`
- Sharpe：`1.539584`
- 总滑点：`1,671,655`
- 总交易次数：`734`（成交记录口径）
- 胜率：`53.1502%`（非零交易日胜率）
- 其他关键指标：broker10峰值 `93.5807%`，超100%天数 `0`。

## 多周期结果

| 周期 | 起点 | 窗口 | C收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | C/A滑点比 | 门 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1年 | combined | 16 | 62.50% | +4.0267pp | 81.25% | 68.75% | 0.9151 | 失败 |
| 1年 | January | 8 | 62.50% | +4.0267pp | 75.00% | 75.00% | 0.8662 | 失败 |
| 1年 | June | 8 | 62.50% | +3.1500pp | 87.50% | 62.50% | 0.9686 | 失败 |
| 2年 | combined | 14 | 64.29% | +8.9947pp | 64.29% | 78.57% | 0.9619 | 失败 |
| 2年 | January | 7 | 57.14% | +4.7460pp | 71.43% | 71.43% | 0.8504 | 失败 |
| 2年 | June | 7 | 71.43% | +16.2169pp | 57.14% | 85.71% | 1.0812 | 失败 |
| 3年 | combined | 12 | 66.67% | +13.4533pp | 83.33% | 83.33% | 0.9549 | 通过 |
| 3年 | January | 6 | 83.33% | +13.4533pp | 83.33% | 100.00% | 0.8396 | 通过 |
| 3年 | June | 6 | 50.00% | +16.7944pp | 83.33% | 66.67% | 1.0785 | 失败 |

- 42个短周期窗口合计：C收益胜出 `27/42`；C正收益 `38/42`，A正收益 `37/42`；DD非劣 `32/42`；Sharpe非劣 `32/42`；总滑点比 `0.9532`。
- 最弱收益窗口：`roll_3y_2018_06`，C-A收益 `-343.3493pp`，但C回撤更浅约 `0.9141pp`，Sharpe差 `-0.0535`。
- 最弱回撤窗口：`roll_2y_2021_01`，C回撤恶化 `6.1012pp`，虽然收益多 `21.7867pp`。
- 关键硬失败：1年Sharpe非劣比例不足；2年DD非劣比例不足；2年June滑点比 `1.0812`；3年June Sharpe非劣率 `66.67%` 且滑点比 `1.0785`。

## 输出文件

- report：`artifacts/stage048_stage037_vs_live_multicycle/stage048_multicycle_report.md`
- summary：`artifacts/stage048_stage037_vs_live_multicycle/stage048_window_summary.csv`
- comparison：`artifacts/stage048_stage037_vs_live_multicycle/stage048_window_comparison.csv`
- aggregate：`artifacts/stage048_stage037_vs_live_multicycle/stage048_cycle_aggregate.csv`
- daily：`artifacts/stage048_stage037_vs_live_multicycle/stage048_equity_curves.csv`
- decision：`artifacts/stage048_stage037_vs_live_multicycle/stage048_decision.json`
- charts：`stage048_full_period_equity_ac.png`、`stage048_equity_curves_1y_ac.png`、`stage048_equity_curves_2y_ac.png`、`stage048_equity_curves_3y_ac.png`、`stage048_cycle_aggregate_ac.png`

## 结论

- 本阶段结论：Stage037 的收益改善不是只存在于全周期，1/2/3年收益胜率均高于50%，收益差中位数均为正；但路径质量不够稳定，九组聚合门仅3年combined和3年January通过，因此决策为 `stage037_multicycle_has_hard_fail_keep_research`。
- 是否进入下一步：不进入正式晋升或部署；只保留为研究候选和归因证据。
- 下一步：不围绕失败窗口扫描天数、ATR倍数、方向、年份或品种。若继续，应等待新样本或做不改变规则的forward shadow观察。

## 过拟合反思

- 运行前判断：本次固定规则、多起点验证本身不新增过拟合；Stage037历史形成过程仍有后验选择风险。
- 运行后判断：结论不变，Stage037仍有明显起点依赖，不能用漂亮全周期覆盖短周期失败。
- 原因：42窗中虽然27窗收益胜出，但回撤和Sharpe非劣只有32窗，且6月起点出现成本与Sharpe集中失败；按这些失败再调阈值会成为典型回测后救参。

## 继续价值反思

- 运行前判断：有价值；需要判断Stage037全周期优势是否依赖单一起点。
- 运行后判断：本次验证有价值，但当前路线没有继续调参价值。
- 原因：结果明确区分了“长期收益候选”和“可正式晋级的路径稳健候选”；Stage037属于前者，不属于后者。

## 安全边界

- 本次为隔离worktree内的离线研究；没有连接CTP，order/send/cancel API调用均为 `0`。
- 未修改正式物料、生产worktree、AI池、launchd、远端master或券商状态。

## 合入建议

- 是否更新本线 `LINE.md`：否；本阶段只提交唯一Stage048记录，统一合入时再整理。
- 是否更新 `research/registry.md`：否；研究线归属未变化。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是重要突破、正式候选或跨线里程碑。
