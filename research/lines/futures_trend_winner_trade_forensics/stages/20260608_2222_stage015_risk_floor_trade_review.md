# Stage015 正式版 0.1 风险交易逐笔复盘

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:22 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读逐笔法证复盘
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - https://crosstrade.io/learn/performance-metrics/r-multiple
  - https://www.tradingheroes.com/mfe-mae-explained/
  - https://github.com/quantopian/zipline/issues/189
  - https://github.com/braverock/quantstrat
- 我的判断：逐笔复盘不能只按现金盈亏判断，应使用 R-multiple 统一不同品种、不同手数和不同风险预算下的收益质量，同时用 MFE/MAE、退出效率、持仓天数和入场上下文判断是否真的出现可事前利用的大右尾。GitHub/开源侧也普遍把 per-trade stats、MAE/MFE 和组合交易记录作为交易系统复盘基础，但没有可直接复制成“0.1 风险豁免规则”的现成代码或证据。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage732_risk_floor_trade_review.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage719 当前正式 Stage372/20万 closed lots，全周期 `2020-01-03` 至 `2026-04-30` 附近。
- 账户规模：正式版参考 `200,000`。
- 成本口径：沿用 Stage719 已成交 closed lots，不重新估算滑点。
- 样本过滤：`risk_multiplier<=0.100001` 或 `risk_multiplier_bucket=risk_floor_01` 的实际成交 closed lots。
- 策略/归因口径：只读复盘正式版实际成交，不读取候选表作为成交替代；大赢家定义沿用 Stage719 预声明 `r_multiple >= 3.890766623752712`，并额外标注 MFE 达到该阈值但最终回吐的交易。

## 结果

- 期末权益：不适用，本阶段不是权益回测；正式版参考仍为 `8,728,285`
- 总收益：不适用；正式版参考仍为 `4264.1425%`
- 最大回撤：不适用；正式版参考仍为 `-38.6713%`
- Sharpe：不适用；正式版参考仍为 `1.6279`
- 总滑点：不适用；正式版参考仍为 `506,220`
- 总交易次数：正式版 raw trades 参考 `633`；本阶段 0.1 风险 closed lots `51`
- 胜率：0.1 风险 closed lots 最终盈利 `10/51=19.6078%`
- 其他关键指标：
  - 实现大赢家 `1/51`，即 `SM505.CZCE` 空单，`2025-03-14` 入场、`2025-03-27` 退出，最终 `+47,560`、`+4.3158R`、MFE `7.0000R`、MAE `1.8421R`。
  - MFE 达到大赢家阈值的交易 `2/51`：上述 `SM505.CZCE` 真大赢家，以及 `SM409.CZCE` 多单，后者 MFE `6.2387R` 但最终 `-0.9415R`，属于大 MFE 回吐，不是已实现大赢家。
  - 0.1 档实际总盈亏 `-380,665`，R 总和 `-40.2123R`。
  - 若仅按风险倍率线性估算恢复到 1.0 风险，总盈亏约 `-3,806,650`；盈利交易少赚约 `1,434,510`，亏损交易少亏约 `4,860,495`，0.1 档相对线性 1.0 的净保护约 `3,425,985`。
  - 按分类：`realized_big_winner=1`、`ordinary_winner_ge_1r=5`、`small_winner=4`、`big_mfe_gave_back=1`、`failed_after_1r_mfe=10`、`loss_or_no_right_tail=30`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_report_stage732_risk_floor_trade_review_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_summary_stage732_risk_floor_trade_review_v1.csv`
- orders：不适用
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_risk_floor_lots_stage732_risk_floor_trade_review_v1.csv`
- 其他：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_big_winners_stage732_risk_floor_trade_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_year_summary_stage732_risk_floor_trade_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage732_risk_floor_trade_review_decision_stage732_risk_floor_trade_review_v1.json`

## 结论

- 本阶段结论：正式版被缩小到 0.1 风险的 51 笔实际成交里，真正被压小的已实现大赢家只有 1 笔；另有 1 笔盘中达到大赢家级 MFE 但最终回吐为亏损。0.1 档整体不是大面积错杀右尾，而是以牺牲少量右尾为代价，显著压住了连败后的一批负期望/高回吐交易。
- 是否进入下一步：不进入策略 A/B，不作为豁免特征。
- 下一步：若继续寻找高质量机会豁免，应转向外生、事前、可 walk-forward 的特征或 forward watch；不要从这 51 笔里围绕唯一 `SM505` 空单或 `SM409` 回吐多单倒推规则。

## 过拟合反思

- 运行前判断：不是过拟合，本阶段只做正式成交只读复盘，不新增交易规则。
- 运行后判断：复盘本身不是过拟合；但如果把唯一真大赢家或单一大 MFE 回吐交易的事后共同点提炼成豁免条件，就会变成高风险过拟合。
- 原因：样本只有 `51` 笔，真大赢家只有 `1` 笔，且收益集中在单一年份/单一局部状态；当前证据更支持防守阈值有效，而不是支持新增豁免。

## 继续价值反思

- 运行前判断：有价值，因为用户需要确认 0.1 风险是否漏掉大量大赢家。
- 运行后判断：本次复盘问题已经回答；继续在同一 51 笔上找规则价值低，但总目标仍有价值。
- 原因：结果显示 0.1 档主要是防守有效，下一步若继续只能换信息源或做预声明 forward watch；继续从这批样本里扫条件只会提高过拟合风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为当前正式版 0.1 风险机制的重要归因结论。
