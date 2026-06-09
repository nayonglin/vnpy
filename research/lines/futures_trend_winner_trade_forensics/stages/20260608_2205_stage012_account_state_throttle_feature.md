# Stage012 账户状态特征审计：0.1 档高质量机会豁免

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 22:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读特征审计，不做策略权益回放，不改正式版
- 是否重要突破：否，是负结论边界收束
- 是否触发A/B：否；无特征通过预声明可靠性门槛，不进入 A/C

## 外部调研与判断

- 参考资料：
  - `https://github.com/topics/triple-barrier-labeling`
  - `https://github.com/jo-cho/meta_labeling_simplified`
  - `https://finlab.finance/docs/en/tools/us_sp500_regime_filter/`
  - `https://www.grahamcapital.com/wp-content/uploads/2024/04/Trend-Following-Primer_January-2022.pdf`
- 我的判断：
  - meta-labeling / triple-barrier 的思想适合本问题：先有主策略信号，再用入场前可见特征判断该信号是否值得放大或过滤。
  - 账户状态过滤在趋势系统里是合理方向，但账户特征非常容易变成年份/路径代理，所以本阶段额外加入 `dominant_year_share<=45%`，避免把某一年行情误认为普适特征。
  - 如果账户状态特征不能在固定桶、跨年、跨品种、足够样本下同时提升 good rate 并压低 bad rate，就不能作为三连败后 `0.1` 风险档的豁免。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage730_account_state_throttle_feature.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无正式策略参数；审计内固定可靠性门槛为 rows `>=30`、years `>=4`、products `>=6`、dominant product share `<=35%`、dominant year share `<=45%`、good lift `>=10pp`、bad rate `<=60%`、good years `>=4`、positive-score years `>=4`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage723 enriched 的基础 `0.1` 档 H40 可标注候选，账户路径来自 Stage719 当前正式 Stage372/20万持仓净值路径
- 账户规模：不适用；只读特征审计
- 成本口径：不适用；不跑策略权益，不产生交易成本曲线
- 样本过滤：Stage723 enriched 的基础 `0.1` 档 H40 可标注可行动候选 `73` 条
- 策略/归因口径：
  - 从 Stage719 positions 聚合日度账户 equity，计算入场前可见的 `20/60` 日账户收益、MA200 gap、drawdown age、rolling volatility。
  - 同时使用候选快照中的 `portfolio_drawdown_pct`、`total_margin_in_use_before`、`free_capital`、`active_positions_before`、`loss_streak`。
  - 固定审计账户回撤、账户收益、账户恢复/下跌阶段、保证金/自由资金、持仓状态、连败深度，以及 `账户状态 + Stage723 directional_edge60` 一个交互桶。
  - 不使用品种名、年份、红框窗口作为规则特征。

## 结果

- 期末权益：不适用（只读特征审计）
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：baseline H40 `+2R` 先到率 `30.1370%`
- 其他关键指标：
  - H40 `-1R` 先到 bad rate：`68.4932%`
  - baseline path score：`9.9391R`
  - median account drawdown：`20.4889%`
  - max account drawdown：`31.6791%`
  - median loss streak：`5`
  - median margin usage：`0.1604%`
  - initial gate candidate count：`0`
  - decision：`no_account_state_reliable_exemption_feature_found`
  - top watch 1：`account_free_capital=free_ok_60_85`，rows `5`，good rate `80.0000%`，失败原因包括 `rows<30`、`years<4`、`products<6`、`dominant_year_share>45%`
  - top watch 2：`account_state_plus_edge=edge_in_falling_account`，rows `19`，good rate `57.8947%`，good lift `+27.7578pp`，bad rate `42.1053%`，失败原因 `rows<30`
  - 达到 `30` 条以上的较强账户桶：`ret20_60_both_down/falling_dd` rows `43`，good rate `34.8837%`，good lift `+4.7467pp`，bad rate `62.7907%`，且 `dominant_year_share>45%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_report_stage730_account_state_throttle_feature_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_decision_stage730_account_state_throttle_feature_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_enriched_candidates_stage730_account_state_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_feature_metrics_stage730_account_state_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_year_detail_stage730_account_state_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage730_account_state_throttle_feature_chart_stage730_account_state_throttle_feature_v1.png`

## 结论

- 本阶段结论：没有找到可接入正式版或进入 A/C 回测的账户状态型高质量豁免特征。账户态可以解释一部分路径，但在当前 `73` 条样本里，强信号样本太少；大样本桶又 good lift 不够、bad rate 偏高或年份集中。
- 是否进入下一步：本形状不进入策略回测，不接正式版。
- 下一步：停止围绕账户 DD、MA200、ret20/ret60、margin/free capital、loss streak 深度继续扫阈值。若继续寻找豁免，只能转真正独立外生数据或 forward watch；如果继续模型化，需要预声明 purged walk-forward/meta-labeling，而不能在 `73` 条历史样本上继续选桶。

## 过拟合反思

- 运行前判断：不是过拟合。原因是账户状态是趋势系统通用风控变量，且本阶段固定桶、增加年份集中度闸门，不用红框/品种/年份定制。
- 运行后判断：继续把 watch 特征交易化会过拟合。原因是最强可解释 watch `edge_in_falling_account` 只有 `19` 条样本；达到 `43` 条的 `falling_dd` good lift 只有 `+4.7467pp`，bad rate 仍 `62.7907%`。
- 原因：账户状态本身更像防守/路径上下文，不足以单独识别“应该恢复正常开仓”的右尾机会。

## 继续价值反思

- 运行前判断：有价值。原因是前面内部字段、外生日线、市场广度和 sleeve bypass 均失败，账户状态是仍有第一性原理的上游方向。
- 运行后判断：本账户状态桶形状没有继续价值；总目标仍有价值但证据越来越指向“历史样本内特征不足”。
- 原因：当前可见账户状态没有提供可靠豁免特征，继续在同一批 `73` 条样本里找阈值，会提高样本内拟合概率而不是提高普适性。后续要么接受三连败 `0.1` 是当前稳健防守，要么转 forward watch / 新外生数据。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage012 负结论。
- 是否更新 `research/registry.md`：是，当前法证线最新阶段更新为 Stage012。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要负结论和未来边界。
