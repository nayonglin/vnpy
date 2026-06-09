# Stage410 Stage407 连败风险下限 0.25 反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 12:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：连败风控结构归因 / 单点 A/B 反证
- 是否重要突破：否，关键负结果
- 是否触发A/B：否，未达到可接入正式版标准

## 外部调研与判断

- 参考资料：
  - Man Group：Trend following market mix，强调趋势跟踪收益来自多市场分散与右尾捕捉，扩市场不能破坏原有右尾暴露。
  - AQR：Trend Following 与 Understanding Managed Futures，趋势跟踪应通过风险预算、分散与多空趋势暴露实现稳健性，而不是针对单个历史窗口调小数。
- 我的判断：Stage408 已证明鸡蛋参与 AI 重排后红框增长缺失，Stage409 又证明 `1,1,0.5,0.25` 虽修复部分窗口但全周期更差。本阶段只测试一个更低自由度结构：保留 0/1/2 连败风险不变，只把 3 连败及以上的 `0.1` 底线抬到 `0.25`，验证能否在不提前砍仓的情况下恢复右尾参与权。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage697_stage407_loss_streak_floor025.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`LOSS_STREAK_FLOOR_MULTIPLIERS=1.0,1.0,1.0,0.25`
- 修改参数：运行期 `streak_risk_multipliers 1.0,1.0,1.0,0.1 -> 1.0,1.0,1.0,0.25`
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage407/Stage696 口径，`2020-01-01` 至仓库当前期货数据末端。
- 账户规模：`200,000`
- 成本口径：正常滑点成本，并输出 2x/3x 成本压力。
- 样本过滤：不重新训练、不改正式 AI 训练过程；Stage407 口径为原正式 AI 池 + `jd.DCE` 参与 AI 重排 `top9`，`maxpos5`。
- 策略/归因口径：
  - A：当前正式 Stage372/20w `maxpos4`，连败倍率 `1,1,1,0.1`。
  - D：A 仅把三连败后风险底线改为 `0.25`。
  - B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，连败倍率 `1,1,1,0.1`。
  - C：B 仅把三连败后风险底线改为 `0.25`。

## 结果

- A 正式版原 0.1：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`，broker10 峰值 `79.6015%`，强制减仓 `6` 次 `299` 手，`deployable_pass=1`。
- D 正式版 0.25：期末权益 `4,885,530`，总收益 `2342.7650%`，最大回撤 `-53.5171%`，Sharpe `1.4018`，总滑点 `384,400`，总交易次数 `634`，胜率 `52.5135%`，broker10 峰值 `85.8969%`，强制减仓 `6` 次 `356` 手，`deployable_pass=0`。
- B Stage407 原 0.1：期末权益 `3,284,935`，总收益 `1542.4675%`，最大回撤 `-33.2821%`，Sharpe `1.3858`，总滑点 `298,030`，总交易次数 `688`，胜率 `51.7181%`，broker10 峰值 `82.6211%`，强制减仓 `14` 次 `361` 手，`deployable_pass=1`。
- C Stage407 0.25：期末权益 `2,156,795`，总收益 `978.3975%`，最大回撤 `-34.1547%`，Sharpe `1.2355`，总滑点 `229,960`，总交易次数 `678`，胜率 `51.3315%`，broker10 峰值 `72.4280%`，强制减仓 `11` 次 `233` 手，`deployable_pass=1`。
- 红框窗口 `2025-04-16` 至 `2025-07-25`：A 增长 `+5,605,230`，D 增长 `+3,450,060`，B 只增长 `+90,830`，C 增长 `+402,880`。C 相对 B 只多 `+312,050`，仍比 A 少 `5,202,350`。
- Stage407 入场风险：B 红框已开仓中位 `target_risk_amount=12,912.50`、中位 `selected_volume=17`；C 升至 `23,655.56` 和 `30.5`，但红框打开笔数仍为 `6`，全周期 selected volume 从 B 的 `8,837` 降到 C 的 `7,012`。
- 品种归因：C 相对 B 改善集中在 `jd +87,370`、`sa +52,180`、`fu +33,990`、`si +19,475`、`ap +19,120`；但恶化集中在 `jm -291,390`、`oi -258,320`、`ru -248,950`、`lh -206,080`、`rb -123,770`、`au -80,520`、`lc -51,200`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_report_stage697_stage407_loss_streak_floor025_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_summary_stage697_stage407_loss_streak_floor025_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_daily_stage697_stage407_loss_streak_floor025_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_positions_stage697_stage407_loss_streak_floor025_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_equity_only_stage697_stage407_loss_streak_floor025_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage697_stage407_loss_streak_floor025_decision_stage697_stage407_loss_streak_floor025_v1.json`

## 结论

- 本阶段结论：`stage407_loss_streak_floor025_not_promoted`。把三连败后风险底线从 `0.1` 抬到 `0.25` 能局部修复红框窗口的一部分仓位，但不能恢复 Stage407 的全周期收益，更不能接近正式版；对正式版直接套用还会把最大回撤打到 `-53.5171%`，属于明显伤害。
- 是否进入下一步：本形态不进入下一步。
- 下一步：如果继续解决“风险预算太小导致算不出一手”，应测试更窄的结构：只在 `selected_volume=0` 且保证金/单笔上限允许时给最小可参与仓，而不是把所有三连败后的非零仓位统一放大；同时保留正式版作为硬对照，若正式版被伤害则拒绝。

## 过拟合反思

- 运行前判断：否。只测试一个预声明低自由度结构，不按鸡蛋、年份或红框窗口做过滤。
- 运行后判断：继续沿 `0.15/0.2/0.3/0.4` 扫连败下限会过拟合。
- 原因：结果显示问题不是单个下限小数，而是共享账户路径和核心右尾被 AI 重排挤占后的复利断裂；粗暴抬高三连败风险会扩大坏路径，并伤害正式版。

## 继续价值反思

- 运行前判断：有价值。Stage408/409 已经显示 `0.1` 风险档会让红框行情参与不足，需要验证是否能用更保守的结构修复。
- 运行后判断：连败机制仍有研究价值，但本形态无继续价值。
- 原因：0.25 下限只局部修复红框，未恢复全周期；下一步必须从“只补 0 手”或“独立 sleeve/非挤占式风险槽”这类更精确机制入手。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage410 为负结果。
- 是否更新 `research/registry.md`：否，本次不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：是，登记长期反证与回测摘要。
