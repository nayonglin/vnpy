# Stage417 Stage407 局部最后亏损相关性连败风控反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 13:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读连败来源审计 + 固定单点回测反证
- 是否重要突破：否，关键负结论
- 是否触发A/B：是，风控候选可能影响正式版，按 A/D/B/C 对照

## 外部调研与判断

- 参考资料：
  - AQR `Trend Following`：趋势跟踪收益来自多市场长期趋势暴露和严格风险控制，不能因单一近期窗口重塑规则。
  - Man Group `Trend Following: Optimal Market Mix`：扩市场有价值，但核心在组合层机会集，不应破坏原有核心右尾。
  - Concretum trend-following position sizing discussion：仓位管理会显著改变收益/回撤形状，简单放大右尾也会同步放大反转损失。
- 我的判断：连续亏损后直接把所有品种降到 `0.1` 过于粗；但把它局部化，也必须证明不会放大正式版 2022 类坏路径。本阶段候选用一个低自由度原则验证：只有当前品种+方向最近也亏损，才认为全局三连败与当前机会相关；否则不把当前机会压到 `0.1`。这不是按鸡蛋、红框或年份定制，但如果正式版被伤害，必须直接否决。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage703_stage407_loss_streak_source_audit.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage704_stage407_local_last_loss_relevance.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LOCAL_RELEVANCE_LOOKBACK_DAYS=252`
  - D/C 候选启用 `enable_failure_memory_micro_sizing=True` 仅用于记录同品种同方向 outcome history
  - `failure_memory_micro_sizing_min_consecutive_failures=999`
  - `failure_memory_micro_sizing_multiplier=1.0`
- 修改参数：
  - `streak_risk_multipliers` 仍为 `1.0,1.0,1.0,0.1`
  - 运行期 monkey patch：当 `loss_streak>=3` 且原始 multiplier 为 `0.1` 时，只有当前 `product+direction` 最近一笔本地交易为亏损，才保留 `0.1`；否则返回 `1.0`
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用当前 Stage372/Stage407 全周期，红框窗口 `2025-04-16` 至 `2025-07-25`
- 账户规模：`200,000`
- 成本口径：正常成本，并输出 2x/3x 成本压力
- 样本过滤：无未来数据；AI eligibility 沿用 Stage407 点时月度池
- 策略/归因口径：
  - Stage416：只读读取 Stage702 的 `trade_usage`、`entry_risk`、`entry_candidates`，FIFO 近似还原亏损来源，不跑新回测
  - A：正式 Stage372/20w `maxpos4` 原版
  - D：正式版 + 局部最后亏损相关性规则
  - B：Stage407 原正式 AI 池 + `jd.DCE` 参与 AI rerank top9 + `maxpos5`
  - C：B + 局部最后亏损相关性规则

## 结果

- Stage416 只读审计：
  - Stage407 红框中 `loss_streak>=3` 的已开仓行 `4` 个
  - FIFO 近似显示 `same_product_tail_rate=0.0`，`same_direction_tail_rate=0.25`
  - 审计提示：红框三连败主要是跨品种全局状态污染，但 trade_usage 与策略内部 layer 顺序在 `2025-07-04/07/08` 附近存在近似误差，因此只作为机制选择线索，不作为绩效证据
- A 正式版：
  - 期末权益：`8,728,285`
  - 总收益：`4264.1425%`
  - 最大回撤：`-38.6713%`
  - Sharpe：`1.6279`
  - 总滑点：`506,220`
  - 总交易次数：`633`
  - 胜率：`52.2586%`
- D 正式版局部相关性：
  - 期末权益：`2,110,610`
  - 总收益：`955.3050%`
  - 最大回撤：`-50.5109%`
  - Sharpe：`1.0892`
  - 总滑点：`222,430`
  - 总交易次数：`661`
  - 胜率：`51.2389%`
  - 相对 A：期末权益少 `6,617,675`，收益少 `3308.8375pp`，回撤恶化 `11.8396pp`
- B Stage407 原版：
  - 期末权益：`3,284,935`
  - 总收益：`1542.4675%`
  - 最大回撤：`-33.2821%`
  - Sharpe：`1.3858`
  - 总滑点：`298,030`
  - 总交易次数：`688`
  - 胜率：`51.7181%`
- C Stage407 局部相关性：
  - 期末权益：`3,143,580`
  - 总收益：`1471.7900%`
  - 最大回撤：`-37.5193%`
  - Sharpe：`1.3043`
  - 总滑点：`279,940`
  - 总交易次数：`695`
  - 胜率：`52.1586%`
  - 相对 B：期末权益少 `141,355`，收益少 `70.6775pp`，回撤恶化 `4.2372pp`
- 红框窗口：
  - A：`+5,605,230`
  - D：`+1,303,100`
  - B：`+90,830`
  - C：`+1,427,140`
  - C 相对 B 修复 `+1,336,310`，但仍比 A 少 `4,178,090`
- 红框产品归因：
  - C 相对 B：`jm +846,450`、`si +338,100`、`fg +61,380`、`ma +58,080`
  - 这说明局部相关性规则确实能让红框多拿回部分右尾仓位
- 全周期产品归因：
  - C 相对 B 改善：`jm +423,240`、`fu +253,460`、`sa +196,480`
  - C 相对 B 恶化：`oi -334,790`、`sh -252,060`、`rb -190,010`、`ru -160,150`、`lh -136,160`
  - D 正式版也大幅损失 `jm/oi/fu/lh/lc/si/au` 等正式右尾，证明规则不是可推广防守
- 入场风险：
  - B 红框已开仓中位 `target_risk_amount=12,912.50`，中位 `selected_volume=17`
  - C 红框已开仓中位 `target_risk_amount=60,525.14`，中位 `selected_volume=52.5`
  - 仓位确实恢复，但全周期代价过高

## 输出文件

- Stage416 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage703_stage407_loss_streak_source_audit_report_stage703_stage407_loss_streak_source_audit_v1.md`
- Stage416 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage703_stage407_loss_streak_source_audit_decision_stage703_stage407_loss_streak_source_audit_v1.json`
- Stage417 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage704_stage407_local_last_loss_relevance_report_stage704_stage407_local_last_loss_relevance_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage704_stage407_local_last_loss_relevance_summary_stage704_stage407_local_last_loss_relevance_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage704_stage407_local_last_loss_relevance_daily_stage704_stage407_local_last_loss_relevance_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage704_stage407_local_last_loss_relevance_entry_risk_stage704_stage407_local_last_loss_relevance_v1.csv`
- equity_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage704_stage407_local_last_loss_relevance_equity_only_stage704_stage407_local_last_loss_relevance_v1.png`

## 结论

- 本阶段结论：`stage407_local_last_loss_relevance_not_promoted`。
- 是否进入下一步：不进入，不接正式版，不做 A/B。
- 下一步：
  - 停止“全局连败机制局部化”这一类救援，包括本地冷却、本地最后亏损相关性、连败小数下限、0手补仓。
  - 保留正式版当前 `1,1,1,0.1 + recovery_sleeve`，因为它虽然粗糙，但在正式池坏路径上确实承担防守。
  - 若目标是避免新增品种导致原核心开不出仓位，应转向独立风险槽 / 非挤占式 sleeve / 账户级 selector 重训，而不是继续改主账户连败规则。

## 过拟合反思

- 运行前判断：否。候选来自 Stage416 的机制审计和第一性原理，不按具体品种黑名单、年份、红框调参。
- 运行后判断：继续沿本地相关性、lookback、last-loss、same-direction 等细节调参会过拟合。
- 原因：它能修红框，但正式版全周期从 `8,728,285` 被打到 `2,110,610`，Stage407 也更差；这是规则结构本身的问题，不是参数没调好。

## 继续价值反思

- 运行前判断：有价值。它是对“全局0.1是否可以低自由度局部化”的必要反证。
- 运行后判断：这条局部化路线无继续价值；目标本身仍有价值，但应换承载结构。
- 原因：连续多次验证显示，任何让主账户三连败后更容易恢复仓位的规则，都会在正式版或全周期坏路径里放大亏损；真正的问题是共享风险池和AI扩池挤占，而不是单独一个 `0.1` 数字。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为后续禁区和路线转向依据。
