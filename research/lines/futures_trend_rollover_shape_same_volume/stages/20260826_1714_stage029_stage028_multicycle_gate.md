# Stage029 Stage028 五日延迟换月多周期冻结门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 冻结时间：`2026-08-26 17:14 CST`
- 完成时间：`2026-08-26 18:30 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy/.worktrees/fix-rollover-new-contract-history`
- 分支：`codex/stage028-rollover-delay-5d`
- 阶段性质：用户明确要求在 Stage028 全周期晋级门失败后补跑固定多周期诊断
- 是否重要突破：否；运行前没有新证据，且完整周期失败保持约束
- 是否触发 A/B：是；固定 A/B/C，A=正式Q、B=Stage027、C=Stage028

## 身份与假设

- A：活动正式 Q，必须由 `official_strategy_materials/CURRENT.json` 与稳定生产六身份实时解析。
- B：Stage027，只用新主力自身K线并立即换月。
- C：Stage028，B基础上唯一新增 `rollover_delay_trading_days=5`。
- 候选逻辑冻结提交：`20635f4cb55b20c8ae0c8641a2caa656f988a2b3`。
- 数据截止：`2026-08-25`；账户15万；正式AI池、产品池、成本与broker10口径不变。
- 假设：固定等待5个交易日可能降低立即换月的短期价格发现噪声，但延期持有旧合约也可能放大流动性、到期和路径风险。

## 固定窗口与输出

- 全周期1个，1年16个，2年14个，3年12个，共43个窗口、129个arm-window。
- 1/2/3年均按每年1月1日和6月1日独立冷启动；每窗重建引擎、15万资金、持仓和账户状态。
- 只用完整窗口投票；临近完整窗口若出现只观察、不投票。
- 固定五图：全周期、1年网格、2年网格、3年网格、多周期聚合。
- 每个arm-window完成后写带候选逻辑、数据库、正式manifest、窗口和arm身份的校验checkpoint；最终发布原子替换。

## 预声明门禁

- 完整周期：收益不低于左臂、回撤恶化不超过2pp、Sharpe不低于0.02、滑点不超过105%、账户生存、broker100失败数不增加。
- 各周期×combined/January/June：收益胜率至少50%、收益差中位不为负、DD非劣率至少80%、DD50失败数不增加、Sharpe非劣率至少80%、滑点不超过105%、全部生存、broker100失败数不增加。
- `A_vs_C` 与 `B_vs_C` 全部完整周期和多周期门同时通过，才允许进入正式评审；Stage028既有完整周期失败不能被局部窗口覆盖。

## 运行前反思

- 过拟合：否。规则、参数、截止日、起点、周期和门禁均在结果前冻结，不扫描2-10天、品种、方向、年份或失败窗口。
- 继续价值：有。Stage028只有14次真实D5执行，必须用不同起点检验优势是否集中于少数复利路径；但本阶段无权修改正式物料、master、生产、CTP或订单路径。

## 外部调研判断

- [vn.py 官方回测引擎](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)以独立 `BacktestingEngine` 承载策略和账户状态，支持本阶段每窗 fresh engine 纪律。
- [CME 换月说明](https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll)强调主力流动性迁移和到期过程；固定5日是可证伪研究假设，不是通用最优换月日。
- [walk-forward 方法](https://onlinelibrary.wiley.com/doi/abs/10.1002/9781119196969.ch11)能观察状态依赖，但并不能自动消除过拟合；结果后仍禁止挑选有利起点。

## 本次变更

- 新增脚本：`tools/stage029_stage028_multicycle_abc.py`。
- 新增测试：`tests/test_stage029_stage028_multicycle_runner.py`。
- 修改脚本：无策略逻辑修改；2年图片在数值发布后仅按同一曲线 CSV 做标题布局重绘。
- 删除脚本：无。
- 新增参数：无策略参数；验证窗口固定为全周期、1/2/3年，每年1月和6月起点。
- 修改参数：无；候选 C 仍仅为 `rollover_delay_trading_days=5`。
- 删除参数：无。

## 回测参数与运行凭据

- 数据区间：全周期 `2018-01-01 -> 2026-08-25`；滚动窗口均为完整1/2/3年。
- 账户规模：每个窗口独立 `150,000` 元、空仓冷启动。
- 成本口径：正式成本、滑点、保证金与 broker10 压力口径不变。
- 样本过滤：1年16窗、2年14窗、3年12窗；每档同时包含1月与6月起点，没有近完整观察窗混入投票。
- 真引擎运行：本阶段首次完整运行新算 `126` 个滚动 arm-window，全周期3臂复用并严格校验 Stage028；共 `43` 窗、`129` 个逻辑 arm-window。
- 检查点：首次完整运行 `generated=126/reused=0`。图片格式校验时，绘图源码被纳入过宽运行哈希，误触发第二轮；完成3个新哈希检查点并在第4个中止，未进入最终发布。恢复冻结运行合同后，最终发布逐个校验并复用原始126个检查点，没有再计算策略数值。
- 正式身份：策略 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，ruleset `stage021_q_rollover_volume_atr_v1`，material `m0015_20260825T205121+0800_c097d7836dd4`，manifest `495f37eaa9802ba5b8042d15ca599d62d72ab607f595d4b1492a5904981c38d0`。
- 数据库 SHA256：`d7375edac99e182ba3524abfbed92abb035e101d05744cb801ec5c7b5dbd47f5`。

## 全周期结果

| Arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 胜率 | broker10峰值 | 超100%天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式Q | 14,989,515.10 | 9893.0101% | -44.9033% | 1.468555 | 1,741,690 | 846 | 52.6728% | 99.6724% | 0 |
| B Stage027 | 13,868,439.90 | 9145.6266% | -47.9843% | 1.418929 | 1,685,830 | 834 | 52.6274% | 87.7838% | 0 |
| C Stage028 +5TD | 15,889,543.30 | 10493.0289% | -46.4506% | 1.437784 | 1,654,705 | 810 | 52.8229% | 100.3426% | 1 |

- C-A：期末权益 `+900,028.20`、收益 `+600.0188pp`、回撤恶化 `1.5473pp`、Sharpe `-0.030771`、滑点 `-86,985`、交易 `-36`。收益和回撤门通过，但 Sharpe 非劣门及 broker100 失败数门失败。
- C-B：期末权益 `+2,021,103.40`、收益 `+1347.4023pp`、回撤改善 `1.5337pp`、Sharpe `+0.018855`、滑点 `-31,125`、交易 `-24`。broker100 失败数仍从0增至1，完整周期门失败。

## 1/2/3年多周期聚合

| 对照 | 周期 | 起点 | 窗口 | 收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 | 门禁 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A_vs_C | 1年 | combined | 16 | 68.75% | +1.5283pp | 93.75% | 81.25% | 1.0016 | 通过 |
| A_vs_C | 1年 | January | 8 | 62.50% | +3.7100pp | 87.50% | 75.00% | 0.9762 | 失败 |
| A_vs_C | 1年 | June | 8 | 75.00% | +0.4283pp | 100.00% | 87.50% | 1.0293 | 通过 |
| A_vs_C | 2年 | combined | 14 | 50.00% | +1.5617pp | 64.29% | 78.57% | 1.0229 | 失败 |
| A_vs_C | 2年 | January | 7 | 42.86% | -1.6600pp | 42.86% | 85.71% | 0.9664 | 失败 |
| A_vs_C | 2年 | June | 7 | 57.14% | +4.7833pp | 85.71% | 71.43% | 1.0833 | 失败 |
| A_vs_C | 3年 | combined | 12 | 66.67% | +20.9333pp | 83.33% | 66.67% | 0.9708 | 失败 |
| A_vs_C | 3年 | January | 6 | 66.67% | +34.0701pp | 66.67% | 66.67% | 0.9414 | 失败 |
| A_vs_C | 3年 | June | 6 | 66.67% | +17.3350pp | 100.00% | 66.67% | 1.0024 | 失败 |
| B_vs_C | 1年 | combined | 16 | 68.75% | +0.1600pp | 93.75% | 93.75% | 0.9782 | 通过 |
| B_vs_C | 1年 | January | 8 | 75.00% | +2.4717pp | 100.00% | 100.00% | 0.9938 | 通过 |
| B_vs_C | 1年 | June | 8 | 62.50% | +0.0000pp | 87.50% | 87.50% | 0.9625 | 通过 |
| B_vs_C | 2年 | combined | 14 | 50.00% | +0.6794pp | 92.86% | 78.57% | 0.9587 | 失败 |
| B_vs_C | 2年 | January | 7 | 57.14% | +5.7065pp | 85.71% | 85.71% | 0.9693 | 失败 |
| B_vs_C | 2年 | June | 7 | 42.86% | -0.4413pp | 100.00% | 71.43% | 0.9488 | 失败 |
| B_vs_C | 3年 | combined | 12 | 66.67% | +23.6550pp | 75.00% | 66.67% | 0.9215 | 失败 |
| B_vs_C | 3年 | January | 6 | 66.67% | +25.4051pp | 66.67% | 66.67% | 0.9425 | 失败 |
| B_vs_C | 3年 | June | 6 | 66.67% | +16.0500pp | 83.33% | 66.67% | 0.9013 | 失败 |

## 尾部与失败窗口

- A_vs_C 最差收益：`roll_3y_2019_01=-597.3072pp`；B_vs_C 同窗为 `-496.6379pp`。
- 最大回撤恶化：`roll_2y_2022_01` 与 `roll_3y_2022_01` 均为 `10.7620pp`，相对 A/B 都失败。
- A_vs_C 最差 Sharpe：`roll_1y_2018_06=-0.659919`；B_vs_C 最差 Sharpe：`roll_2y_2019_06=-0.236624`。
- A_vs_C 最高聚合成本窗口：`roll_3y_2020_06` 滑点比 `1.3311`；B_vs_C 最高为 `roll_3y_2022_01=1.1884`。
- 所有滚动 C 窗口账户均生存；但3年聚合相对 A/B 都新增1个 broker100 失败，且2/3年多组 DD50、回撤或 Sharpe 门失败。

## 输出文件

- report：`artifacts/stage029/stage029_multicycle_report.md`
- summary：`artifacts/stage029/stage029_window_summary.csv`
- comparison：`artifacts/stage029/stage029_window_comparison.csv`
- aggregate：`artifacts/stage029/stage029_cycle_aggregate.csv`
- daily/equity：`artifacts/stage029/stage029_equity_curves.csv`
- decision：`artifacts/stage029/stage029_decision.json`
- 图片：`stage029_full_period_equity_abc.png`、`stage029_equity_curves_1y_abc.png`、`stage029_equity_curves_2y_abc.png`、`stage029_equity_curves_3y_abc.png`、`stage029_cycle_aggregate_abc.png`。
- orders：无独立订单导出；本阶段未连接订单通路。
- quality：`43`窗、`129`臂窗、`64,497`行资金曲线、所有关键数值有限、五图目视通过；Stage027/028/029 联合回归 `24 passed`，独立 reviewer 最终 `P0/P1/P2=0/0/0`。

## 工具硬化与独立评审

- reviewer 初审确认 Stage029 数值、全周期 Stage028 复用、comparison/aggregate、五图和最终 `not promotable` 决策可信，但发现 runner 三个 fail-closed 缺口：只哈希预期数据库却不核对 vn.py 实际绑定、严重截断窗口仍可复用、重复交易日仍可复用。
- 修复后 Stage029 无条件拒绝 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`，同时核对当前 worktree 的 `TRADER_DIR/TEMP_DIR` 和 SQLite 实际数据库路径，并把实际路径写入新 checkpoint 合同。
- checkpoint 与最终发布双层要求：实际起止距请求边界不超过7日、curve首尾与summary一致、同一 arm-window 日期唯一。错误数据库override、严重截断、首尾错位和重复日期反例均 fail closed；现有129行summary/64,497行curve通过严格合同，真实边界差为0-3日且重复三元组为0。
- 更严格合同使修复前旧 checkpoint 全部安全失效；`checkpoint_reused=126` 只归属于修复前冻结格式恢复运行。既有最终CSV/PNG已经独立复算聚合并通过新时序校验，所以本轮没有为工具门禁修复重跑126个滚动臂窗。
- 报告生成器补齐正式 `source_commit`、最弱收益/回撤/Sharpe/成本/生存、五图、结果与中文stage链接、review/tests、安全边界及过拟合/继续价值，并按固定多周期顺序重生磁盘报告。
- 最终 reviewer：`P0=0/P1=0/P2=0`，允许提交；无正式物料、master、生产、CTP或订单变化。

## 结论

- 决策：`confirm_stage028_not_promotable_after_multicycle`。
- Stage028 的收益优势不是虚构：相对正式 A，1/2/3年 combined 收益胜率为 `68.75%/50.00%/66.67%`；但这不等于“稳健更优”。1月/6月分组方向不一致，2/3年回撤与 Sharpe 门广泛失败，全周期又有 Sharpe 和 broker100 硬失败。
- 是否进入下一步：否；不晋级、不继续围绕2-10天扫描，不修改正式物料、远端master、稳定生产、CTP或订单路径。
- 下一步：仅保留 Stage028 状态机工程经验和失败证据；若再研究换月时机，必须引入外生、可解释的新信息，而不是继续救固定天数。

## 过拟合反思

- 运行前：否。窗口、起点、周期、三臂和门禁均在结果前冻结，没有扫描天数、品种、方向、年份或失败窗口。
- 运行后：否，针对本次验证过程本身；没有按结果调参或挑窗口。不过 Stage028 表现存在明显起点和状态依赖，若因为全周期收益更高而忽略 Sharpe、broker100 与尾部窗口，或者继续扫描2-10天，就会变成高风险过拟合。

## 继续价值反思

- 运行前：是。14次D5执行样本不足以支持正式决策，多周期是必要证伪。
- 运行后：否，不值得围绕固定等待天数继续优化。它有局部收益与状态机工程价值，但不具备穿越周期的正式晋级证据。

## 安全与合入建议

- order/send/cancel API：`0/0/0`；`ctp_connected=false`。
- 正式物料、远端 master `09aa96a03fb91124be90bd69861be3f834ab6299`、稳定生产均未改变。
- 更新本线 `LINE.md`：是，记录 Stage028/029 收束结论。
- 更新 `research/registry.md`：否，line_id、owner和状态类别未发生跨线变化。
- 追加根目录 `back_log.md`：是，作为重要负向多周期里程碑。
- 更新根目录 `memory.md`：否，本阶段没有正式策略政策或身份变更。
