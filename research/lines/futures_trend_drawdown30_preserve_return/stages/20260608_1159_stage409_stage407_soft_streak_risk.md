# Stage409 Stage407 软连败风控消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 12:01 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/B/C/D 机制消融与反证
- 是否重要突破：否，属于关键负结果
- 是否触发A/B：是，风险机制可能影响正式版，已按 `skills/version-ab-experiment/SKILL.md` 执行

## 外部调研与判断

- 参考资料：
  - Man Group, `A Trend Following Deep Dive: The Optimal Market Mix for a Trend Follower`, https://www.man.com/insights/trend-following-optimal-market-mix
  - AQR, `Trend Following`, https://www.aqr.com/insights/trend-following
  - AQR, `Understanding Managed Futures`, https://www.aqr.com/Insights/Research/White-Papers/Understanding-Managed-Futures
- 我的判断：趋势跟踪的通用原则是保留多市场、多方向趋势暴露，并用系统化仓位/波动/回撤控制风险；资料支持风险管理，但不支持针对一个品种或一个红框窗口做特殊补丁。本次候选把连败风险从硬 cliff `1,1,1,0.1` 改为简单阶梯 `1,1,0.5,0.25`，属于低自由度机制验证，不是围绕鸡蛋调参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage696_stage407_soft_streak_risk.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`SOFT_STREAK_MULTIPLIERS=1.0,1.0,0.5,0.25`
- 修改参数：仅运行期 overrides 修改 `streak_risk_multipliers`
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage372 当前完整回测区间，`2020-01-02` 至当前仓库回测终点
- 账户规模：`200,000`
- 成本口径：当前 Stage372 正式成本、交易所费用、滑点与 broker10 保证金代理
- 样本过滤：2020-2021 因 full-market AI 预测未覆盖，沿用正式 AI 快照且不放行鸡蛋；2022 后按受限小池 AI 重排
- 策略/归因口径：
  - A：当前正式 Stage372/20w，正式 AI，`maxpos4`，连败倍率 `1,1,1,0.1`
  - D：当前正式 Stage372/20w，仅把连败倍率改为 `1,1,0.5,0.25`
  - B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，连败倍率 `1,1,1,0.1`
  - C：B 仅把连败倍率改为 `1,1,0.5,0.25`

## 结果

- A 正式硬阶梯：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次 `299` 手
- D 正式软阶梯：
  - 期末权益 `2,331,545`
  - 总收益 `1065.7725%`
  - 最大回撤 `-42.1647%`
  - Sharpe `1.2139`
  - 总滑点 `187,960`
  - 总交易次数 `578`
  - 胜率 `51.6192%`
  - broker10 峰值 `86.4547%`
  - 强制减仓 `4` 次 `99` 手
- B Stage407 硬阶梯：
  - 期末权益 `3,284,935`
  - 总收益 `1542.4675%`
  - 最大回撤 `-33.2821%`
  - Sharpe `1.3858`
  - 总滑点 `298,030`
  - 总交易次数 `688`
  - 胜率 `51.7181%`
  - broker10 峰值 `82.6211%`
  - 强制减仓 `14` 次 `361` 手
- C Stage407 软阶梯：
  - 期末权益 `1,744,020`
  - 总收益 `772.0100%`
  - 最大回撤 `-38.3848%`
  - Sharpe `1.1524`
  - 总滑点 `147,550`
  - 总交易次数 `629`
  - 胜率 `51.5534%`
  - broker10 峰值 `83.4905%`
  - 强制减仓 `8` 次 `192` 手
- 红框窗口 `2025-04-16` 至 `2025-07-25`：
  - A：`+5,605,230`
  - D：`+1,500,420`
  - B：`+90,830`
  - C：`+872,380`
  - C 相对 B 多 `+781,550`，说明 0.1 风险档确实是红框增长缺失的一部分；但 C 相对 A 仍少 `-4,732,850`，说明问题没有被真正修复。
- 红框窗口 C 相对 B 的主要改善：
  - `jm +342,210`
  - `lc +203,440`
  - `si +102,900`
  - `ma +74,800`
- 全周期 C 相对 B 的主要恶化：
  - `oi -558,300`
  - `ru -321,800`
  - `jm -277,470`
  - `lh -268,800`
  - `rb -226,010`
- 入场风险诊断：
  - B 红框已开仓 entries：`loss_streak>=3` 为 `4/6`，中位 `target_risk_amount=12,912.50`，中位 `selected_volume=17`
  - C 红框已开仓 entries：`loss_streak>=3` 为 `0/7`，中位 `target_risk_amount=40,824.17`，中位 `selected_volume=36`
  - C 全周期已开仓 entries 的总 selected volume 从 B 的 `8,837` 降到 `4,404`，说明软阶梯不是单纯“把 0.1 提到 0.25”，它在 `loss_streak=2` 先降到 `0.5`，压低更早的权益底座和后续仓位。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_report_stage696_stage407_soft_streak_risk_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_summary_stage696_stage407_soft_streak_risk_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_daily_stage696_stage407_soft_streak_risk_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_positions_stage696_stage407_soft_streak_risk_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_entry_candidates_stage696_stage407_soft_streak_risk_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_entry_risk_stage696_stage407_soft_streak_risk_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage696_stage407_soft_streak_risk_equity_only_stage696_stage407_soft_streak_risk_v1.png`

## 结论

- 本阶段结论：`stage407_soft_streak_not_promoted`。红框增长消失确实有“连败后 0.1 风险档导致仓位太小”的成分，但把连败倍率平滑成 `1,1,0.5,0.25` 不是解法。它对红框窗口有修复，却在更早阶段过早降风险，压低权益底座，最终全周期收益、回撤、Sharpe 全面弱于 Stage407 硬阶梯，也明显弱于当前正式版。
- 是否进入下一步：不沿这条 `1,1,0.5,0.25` 继续调参。
- 下一步：若继续研究连败机制，只能做结构性替代，而不是扫 `0.2/0.3/0.4/0.5` 小数；优先考虑“不在第二次亏损提前砍半，只在三连败后用不低于一手可开仓的风险下限/恢复仓结构”或回到独立 sleeve / 非挤占式风险槽。

## 过拟合反思

- 运行前判断：否，候选只有一个预声明固定阶梯，不按鸡蛋、年份、月份或红框窗口做过滤。
- 运行后判断：继续救会转为过拟合。
- 原因：结果已经说明简单阶梯不是稳定机制；若继续围绕 `0.2/0.25/0.3/0.5` 调小数，就是用历史路径寻找刚好不过早砍仓、又刚好保住红框右尾的形状。

## 继续价值反思

- 运行前判断：有价值，因为 Stage408 已证明红框窗口仓位被 0.1 风险档压成约一成。
- 运行后判断：连败机制本身仍有价值，但本形态无继续价值。
- 原因：本次证明“0.1 cliff 会造成机会缺失”与“简单平滑阶梯能解决”是两个命题；前者成立，后者失败。下一步必须重新定义机制，而不是救这个阶梯。

## 合入建议

- 是否更新本线 `LINE.md`：是，加入 Stage409 负结果。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为后续连败机制研究的停止经验。
