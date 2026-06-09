# Stage404 正式版 Stage372 关闭 AI 选品消融

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-07 14:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式实盘默认 Stage372 的 no-AI 消融回测
- 是否重要突破：否，属于关键反证；明确不应关闭正式版 AI 选品
- 是否触发A/B：否；C 分支明显劣化，不进入正式候选或 A/B

## 外部调研与判断

- 参考资料：
  - NBER `Backtesting Strategies Based on Multiple Signals` 指出多信号/多配置选择容易产生严重过拟合与多重检验偏差。
  - `Trend-following trading strategies in commodity futures: A re-examination` 在 48 年、28 个商品市场样本中强调趋势跟随要看跨市场组合与数据挖掘/交易成本稳健性。
  - SSRN `Trend Following, Risk Parity and Momentum in Commodity Futures` 支持商品期货趋势跟随与 long-short 组合的风险调整收益价值，但核心在趋势规则和组合层风险，而不是盲目扩机会。
  - GitHub `quantiacs/strategy-futures-trend-following` 是一个公开 futures trend-following 模板，更多是工程/教学参考，没有发现可直接复制到本策略的 AI 选品替代逻辑。
- 我的判断：外部资料不支持“关掉选品、扩大交易次数自然更好”。AI 选品若是点时化、低自由度、长期审计通过的 eligibility gate，它更像组合机会质量过滤器；但如果后续继续调 AI 池名单、年份或品种小补丁，则会转向过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage691_official_stage372_no_ai.py`
- 修改脚本：无正式脚本修改；仅新增 wrapper
- 删除脚本：无
- 新增参数：`enable_ai_product_pool_filter=False`、`ai_product_pool_eligibility_path=""`、`ai_product_pool_strategy=""`
- 修改参数：C 分支仅关闭 AI product pool filter；保留当前正式 Stage372/20万 `official_live_stage372_20w_recovery_sleeve` 的品种池、入场、空头、恢复仓、强制减仓、`force95->80`、`product_cap_ratio=0.25`、`max_concurrent_positions=4`、`risk_multiplier=0.8`
- 删除参数：无；正式配置文件未改

## 回测/归因参数

- 数据区间：Stage372/Stage526 既有全周期回测口径，约 `2019-10-15` 至 `2026-04`
- 账户规模：`200,000`
- 成本口径：正常成本，并做 `2x/3x` 滑点成本压力
- 样本过滤：A 为当前正式 AI 选品；C 为同正式池但禁用 AI product pool filter
- 策略/归因口径：真实引擎 A/C 对照、年度归因、产品归因、强制减仓归因、成本压力、资金曲线/回撤/资金占用图

## 结果

- A 正式版期末权益：`8,728,285`
- A 正式版总收益：`4264.1425%`
- A 正式版最大回撤：`-38.6713%`
- A 正式版 Sharpe：`1.6279`
- A 正式版总滑点：`506,220`
- A 正式版总交易次数：`633`
- A 正式版胜率：`52.2586%`
- C 关闭 AI 期末权益：`827,790`
- C 关闭 AI 总收益：`313.8950%`
- C 关闭 AI 最大回撤：`-44.7176%`
- C 关闭 AI Sharpe：`0.8283`
- C 关闭 AI 总滑点：`140,660`
- C 关闭 AI 总交易次数：`853`
- C 关闭 AI 胜率：`51.5538%`
- 其他关键指标：
  - C 相对 A 期末权益少 `7,900,495`，总收益少 `3950.2475pp`，最大回撤恶化 `6.0463pp`，Sharpe 少 `0.7996`
  - C 交易多 `220` 笔，但收益保留仅 `7.3613%`
  - C broker10 最大资金占用/权益 `66.8560%`，低于 A 的 `79.6015%`；p95 `47.3523%`，低于 A 的 `55.0005%`
  - C 强制减仓 `10` 次 `203` 手，多于 A 的 `6` 次但减仓手数少于 A 的 `299` 手；C 最大观察占用 `127.7215%`
  - C 2x 成本 DD `-47.8060%`，3x 成本 DD `-51.1479%`，均明显弱于 A 的 `-40.6555%/-42.7649%`
  - 年度：C 在 `2022` 为 `-33,035/-6.0146%`，`2026` 截至样本末为 `-28,260/-3.3012%`；A 各年均为正
  - 产品差分：C 相对 A 最大损失集中在 `jm -3,011,640`、`oi -1,194,090`、`fu -1,023,280`、`lh -733,680`、`si -588,300`、`au -529,580`、`ru -438,750`、`rb -425,910`、`lc -422,700`。少数改善如 `ma +475,740`、`sa +241,080`、`ap +227,140` 不足以抵消核心右尾损失。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_report_stage691_official_stage372_no_ai_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_summary_stage691_official_stage372_no_ai_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_trade_usage_stage691_official_stage372_no_ai_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_daily_stage691_official_stage372_no_ai_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_decision_stage691_official_stage372_no_ai_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage691_official_stage372_no_ai_chart_stage691_official_stage372_no_ai_v1.png`

## 结论

- 本阶段结论：`official_stage372_no_ai_rejected_keep_ai_filter`。正式版不能关闭 AI 选品。
- 是否进入下一步：不进入关 AI 方向的下一步。
- 下一步：保留正式 AI 选品；若继续研究 AI，只能做点时化 selector 资格审计、样本外稳定性、以及“AI 池内/池外候选的只读机会质量归因”，不能按年份、品种或小阈值救 no-AI。

## 过拟合反思

- 运行前判断：否。本阶段是消融实验，固定正式版，仅关闭一个模块，用来检验 AI 选品贡献。
- 运行后判断：否，但结论提醒不要过拟合。no-AI 明显失败，反而说明当前 AI gate 不是随意装饰；如果为了救 no-AI 继续挑年份、品种或参数，就是高概率过拟合。
- 原因：C 交易增加但净值路径、年度稳定性、成本压力和核心产品右尾全部劣化；这是结构性机会质量下降，不是单个窗口偶然。

## 继续价值反思

- 运行前判断：有价值，因为它直接回答“正式版是否依赖 AI 选品”。
- 运行后判断：关 AI 方向没有继续推广价值；AI 选品审计仍有价值。
- 原因：C 收益保留只有 `7.3613%`，且 DD40 失败；继续救 no-AI 只会把研究拉向历史拟合。更有价值的是保护当前点时化 AI gate，同时做透明的资格/归因审计，避免它未来漂移或被人为调参污染。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage404 当前状态
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：是，作为正式版关键反证追加
