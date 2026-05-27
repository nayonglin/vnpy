# Stage060 C3品种与行业组账本删减诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 19:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：账本反事实诊断；路线反证
- 是否重要突破：否，属于重要反证
- 是否触发A/B：否。本阶段没有生成可交易候选，只用于判断“删品种/删行业组”是否值得进入真实引擎。

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen 的趋势跟踪长期研究显示，趋势跟踪的长期稳健性来自跨市场、跨环境的分散与低相关收益，而不是事后删除单一亏损品种。
  - Man AHL 公开材料也强调趋势研究中的多市场配置、分散、波动控制和系统性风险控制。
- 我的判断：
  - C3 的 2021 最大回撤确实集中在黑色建材链，但直接删掉回撤窗口亏损品种很容易把单窗口噪声当成结构规律。
  - 为降低过拟合，本阶段只允许两类诊断：单品种 leave-one 只能作为归因；预声明行业组若全样本通过，才有资格进入真实引擎复验。
  - 账本反事实不是完整真实引擎，不能直接当成策略结果；它只能回答“是否值得继续做真实引擎候选”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage360_c3_product_group_ledger_ablation.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 预声明行业组：黑色建材链、能化工业链、农产品软商品、金属贵金属。
  - 单品种 leave-one 全量枚举。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30。
- 账户规模：50万，保持 Stage78-1/C3 当前研究口径。
- 成本口径：沿用 C3 当前真实引擎默认成本/滑点口径；账本反事实继承真实交易账本的成交与滑点。
- 样本过滤：不修改 C3 入场、AI池、品种池、供需强逆风规则和风险簇压力规则。
- 策略/归因口径：
  - 先跑 C3 原始真实引擎，生成逐品种日度损益账本。
  - 反事实移除某个品种或预声明行业组的账本贡献，重算权益曲线。
  - 本阶段只使用全样本账本反事实，不把账本中途切片当作独立冷启动回测；多周期必须另跑真实引擎。

## 结果

- C3基准期末权益：`30,925,650`
- C3基准总收益：`6085.1300%`
- C3基准最大回撤：`-31.0767%`
- C3基准Sharpe：`1.3663`
- C3基准总滑点：`1,556,750`
- C3基准总交易次数：`757`
- C3基准胜率：`45.3826%`
- 其他关键指标：
  - 决策：`leave_one_product_only_diagnostic_do_not_blacklist`
  - 预声明行业组通过数量：`0`
  - 单品种 leave-one 通过数量：`1`
  - 唯一通过的单品种账本反事实：移除 `SM.CZCE`，总收益 `6113.7600%`，最大回撤 `-29.8693%`，收益保留 `100.4705%`。
  - 移除黑色建材链：总收益 `3304.3760%`，最大回撤 `-59.3208%`，收益保留 `54.3025%`。
  - 移除能化工业链：总收益 `5155.7100%`，最大回撤 `-35.4819%`，收益保留 `84.7264%`。
  - 移除农产品软商品：总收益 `5400.4390%`，最大回撤 `-34.0297%`，收益保留 `88.7481%`。
  - 移除金属贵金属：总收益 `4394.8650%`，最大回撤 `-31.5981%`，收益保留 `72.2230%`。
  - 2021最大回撤窗口亏损较大的品种：`hc.SHFE -151,140`、`FG.CZCE -107,020`、`SM.CZCE -94,330`、`rb.SHFE -74,340`、`SA.CZCE -67,380`、`jm.DCE -56,730`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_report_stage360_c3_product_group_ledger_ablation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_summary_stage360_c3_product_group_ledger_ablation_v1.csv`
- frontier：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_frontier_stage360_c3_product_group_ledger_ablation_v1.csv`
- product_daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_product_daily_stage360_c3_product_group_ledger_ablation_v1.csv`
- product_dd：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_product_dd_stage360_c3_product_group_ledger_ablation_v1.csv`
- product_full：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_product_full_stage360_c3_product_group_ledger_ablation_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage360_c3_product_group_ledger_ablation_decision_stage360_c3_product_group_ledger_ablation_v1.json`

## 结论

- 本阶段结论：不应把 `SM.CZCE` 单品种 leave-one 结果升级为黑名单或正式候选；预声明行业组没有任何一个通过，说明“删行业组/删黑色链”不是当前回撤30以内保收益的可推广路线。
- 是否进入下一步：本路线不进入真实引擎 A/B。
- 下一步：停止单品种黑名单和行业组删减路线；继续寻找真正低相关收益源、新承载结构，或回到 Stage055 的正常成本外部现金部署边界。

## 过拟合反思

- 运行前判断：本阶段本身不是过拟合，因为预先声明行业组，且单品种 leave-one 只作为归因，不作为候选。
- 运行后判断：若把 `SM.CZCE` 的通过结果直接做成黑名单，就是过拟合；它只有单样本账本反事实证据，没有多周期真实引擎和经济解释支持。
- 原因：最大回撤窗口确实集中在少数品种，但趋势策略长期收益依赖跨市场分散。删除单品种容易拟合历史亏损点，同时破坏未来分散。

## 继续价值反思

- 运行前判断：有价值。它能确认是否存在低自由度、可解释的行业组风险源。
- 运行后判断：删品种/删行业组路线继续价值低；总研究线仍有价值。
- 原因：预声明组全部失败，唯一过线是单品种后验结果，不足以成为稳健策略。后续应避免在品种黑名单上耗时。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为单品种/行业组删减路线的废弃记录。
