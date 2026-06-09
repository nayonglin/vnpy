# Stage430 正式版 0.1 连败档高质量机会只读审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 16:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因 / 策略回测前置闸门
- 是否重要突破：否，关键负结论
- 是否触发A/B：否，样本与 walk-forward 闸门未通过

## 外部调研与判断

- 参考资料：
  - López de Prado 的 meta-labeling / triple-barrier 思路：先有主信号，再用独立标签判断是否值得下注或放大仓位。
  - `Neyt/How-To-Backtest-Correctly` GitHub 项目：强调避免回看未来收益直接训练入场，适合作为方法边界参考。
  - Rob Carver / trend following position sizing 相关资料：趋势系统可以用信号强度、波动、组合风险状态调仓，但必须做跨期验证。
- 我的判断：用户提出“高质量机会不受 0.1 限制”方向在第一性原理上成立，但必须先证明 0.1 档候选里存在可事前识别、跨年份稳定的高质量子集。不能用红框结果倒推规则，也不能用真实最终交易 PnL 做标签；本阶段只用入场后固定 20/40 个交易日的路径标签做只读前置审计。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage716_official_throttle_quality_readonly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `FAVORABLE_R=2.0`
  - `ADVERSE_R=1.0`
  - `HORIZONS=(20,40)`
  - `MIN_TRAIN_ROWS=30`
  - `MIN_TEST_ROWS=8`
  - `EMBARGO_DAYS=40`
  - `SHRINKAGE_ROWS=20.0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage696 正式版 entry candidates，覆盖 `2020-01` 至 `2026-04` 候选；路径标签读取本地 TQSDK 日线 `2010-2026_04`。
- 账户规模：`200,000` 正式版口径；本阶段不重跑账户回测。
- 成本口径：不适用，只读候选路径标注。
- 样本过滤：
  - 基准：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - 0.1 基础档：`streak_entry_structure_risk_recovery_base_multiplier<=0.1` 或 `loss_streak>=3`
  - 可行动样本：通过初筛、AI 池允许、状态为已开仓或 `sizing_zero_volume`
- 策略/归因口径：
  - 不改正式配置、不连接 CTP、不调用下单。
  - 对候选入场后 20/40 个交易日 high/low 标注 MFE/MAE，保守判断先到 `+2R` 还是 `-1R`；同日同时触发按不利先到。
  - 只用当时已知粗桶特征做年份 walk-forward：方向、signal、AI rank、RSI 方向确认、同向相关、账户回撤、已持仓、风险预算、止损距离等。

## 结果

- 期末权益：不适用（只读归因）
- 总收益：不适用（只读归因）
- 最大回撤：不适用（只读归因）
- Sharpe：不适用（只读归因）
- 总滑点：不适用（只读归因）
- 总交易次数：不适用（只读归因）
- 胜率：不适用（只读归因）
- 其他关键指标：
  - 正式版候选总数 `1,082`，其中基础 0.1 档且通过初筛 `321`。
  - 基础 0.1 档通过初筛后，`opened=64`、`sizing_zero_volume=38`、`ai_blocked=69`、`short_rejected=117`。
  - 真正可行动 0.1 样本 `86`，其中 `opened=64`、`sizing_zero_volume=22`，可标注 H40 样本 `73`。
  - 可行动样本 H40 `+2R` 先到率 `30.14%`，平均 `MFE-MAE=9.9391R`，但右尾分布极不均匀。
  - Walk-forward 实际只剩 `20` 条测试样本、`2` 个测试年份（2024/2025），不满足 `sample_rows>=120` 和 `walkforward_years>=4`。
  - high 桶在 2024 与 low 桶 `+2R` 先到率同为 `33.33%`，但 path score 显著低于 low；2025 high 先到率高 `25pp`，但 path score 仍低于 low。
  - high 桶捕获 big winner 比例 `28.57%`，低于 high 样本占比 `35.00%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_report_stage716_official_throttle_quality_readonly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_scope_summary_stage716_official_throttle_quality_readonly_v1.csv`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_labeled_candidates_stage716_official_throttle_quality_readonly_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_walkforward_stage716_official_throttle_quality_readonly_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_feature_quality_stage716_official_throttle_quality_readonly_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_bucket_summary_stage716_official_throttle_quality_readonly_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage716_official_throttle_quality_readonly_bucket_chart_stage716_official_throttle_quality_readonly_v1.png`

## 结论

- 本阶段结论：`throttled_quality_selector_not_promoted`。当前证据不足以把“高质量机会绕过 0.1”推进到策略回测，更不能接正式版。
- 是否进入下一步：不进入同形态策略回测。
- 下一步：如果继续，应换成更上游的账户级 selector 训练目标重对齐，或 forward/paper 预声明观察；不要基于 2025 红框倒推特征，也不要继续在主账户连败 `0.1` 上做局部补丁。

## 过拟合反思

- 运行前判断：否。本阶段是只读前置闸门，且使用路径标签、时间切分和 embargo，目的就是避免用红框结果倒推规则。
- 运行后判断：若现在继续做策略接入，会过拟合。
- 原因：可行动样本只有 `86`，可标注 `73`，walk-forward 仅 `20` 条测试样本和 `2` 个年份；high 桶没有稳定压过 low 桶，big winner 捕获也不足。继续按这些粗桶做 bypass 规则，本质会变成拟合少数历史右尾。

## 继续价值反思

- 运行前判断：有价值。它直接回答“能否识别高质量机会并绕过 0.1”。
- 运行后判断：当前形态无继续价值，但问题方向仍有价值。
- 原因：被 0.1 压住的可行动集合不是稳定高质量集合；真正值得继续的是账户级 selector 或独立正期望风险槽，而不是在主账户连败机制上继续救援。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：是，作为当前连败风控研究边界更新
