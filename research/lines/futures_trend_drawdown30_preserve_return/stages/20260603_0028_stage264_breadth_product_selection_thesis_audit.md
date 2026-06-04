# Stage264 低单笔风险扩池/选对品种结构审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 00:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读结构审计；整合 Stage241/253/257/258/263 证据，评估“减少单笔风险、扩大品种池、避免高相关、选对品种”是否值得继续。
- 是否重要突破：否，但属于重要边界结论。
- 是否触发A/B：否。本阶段不形成新策略候选，不接入正式版本。

## 外部调研与判断

- 参考资料：
  - AQR Managed Futures / Trend Following 资料：成熟趋势跟随通常依赖跨市场、多品种的分散机会与风险预算。
  - `pysystemtrade` / Rob Carver 框架：多期货系统强调 instrument diversification、相关性估计、组合权重和风险目标，而不是简单增加品种。
- 我的判断：
  - 用户提出的方向在第一性原理上成立：趋势收益稀疏，降低单笔风险并扩大低相关机会集，理论上能提高“每年抓到一部分趋势”的概率。
  - 但扩池本身不是 alpha。若没有能在交易前识别“哪个品种当时有趋势土壤”的 selector，宽池会把大量震荡和尾部亏损也放进来。
  - 本阶段只做证据整合和闸门定义，不扫 `risk/cap/corr/maxpos` 小数，不把 hindsight top6 当成实盘白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage563_breadth_pool_product_selection_thesis_audit.py`
- 修改脚本：
  - 无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - 结构闸门：年度机会存在、低相关材料性候选、宽池收益材料性、宽池路径不劣化、简单 selector 胜出、forward selector 数据资格、hindsight top6 不可直接部署。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage241/257 既有结果，覆盖 `2020-2026`。
- 账户规模：Stage526 核心 `50万`；宽池/卫星 sleeve `11.5万`；组合口径 `61.5万`。
- 成本口径：读取 Stage257 正常成本结果；不新增滑点回测。
- 样本过滤：
  - 非核心商品单品种机会图：Stage241 `38` 个非核心产品。
  - 宽池真实捕获：Stage257 三个粗档。
  - selector 资格：Stage258/263 forward ledger 质量闸门。
- 策略/归因口径：
  - 不重跑交易引擎，不修改入场/出场/AI池/产品池。
  - 只读取已有真实下一窗口回测、单品种机会图和 forward 数据资格结果。

## 结果

- 决策：`breadth_thesis_valid_selector_not_ready_no_promotion`
- 结构闸门：`2/7` 通过。
- 通过项：
  - 年度机会存在：非核心 hindsight top6 在 `7/7` 年为正，且每年至少有 `3` 个正贡献品种。
  - 低相关材料性候选存在：Stage241 找到 `6` 个材料性非核心候选，平均 `abs(Stage526日PnL相关)=0.0461`。
- 失败项：
  - 全非核心宽池真实捕获不够：卫星 PnL 仅 `9,395`，收益 `8.1696%`，低于 `50,000 / 30%` 材料性闸门。
  - 全非核心宽池路径劣化：组合最大回撤 `-36.3714%`，差于 Stage526 `-36.2670%`；Ulcer `14.4902`，差于 Stage526 `14.4691`。
  - 简单 selector 不成立：Stage543 best `diagnostic_pass=0`；上一年为正宽池 sleeve PnL `-18,245`。
  - forward selector 数据不够：当前质量样本 `2/20` runs、`2/20` dates，真实 sentiment/news ledger `0/1`，readiness `5/9`。
  - hindsight top6 不可直接部署：Stage256 卫星 PnL `54,005`，但使用历史赢家/Oracle风格上限，必须先有 point-in-time selector。

### 关键数表

| 版本/证据 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率/说明 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage526 | 23,369,505 | 3699.9195% | -36.2670% | 1.6385 | 1,342,190 | 905 | 非零日胜率 53.6330% |
| Stage256 fixed top6 | 23,423,510 | 3708.7008% | -36.0729% | 1.6433 | 1,346,430 | 1,109 | 卫星PnL 54,005；不可直接部署 |
| 全非核心宽池 r020 | 23,378,900 | 3701.4472% | -36.3714% | 1.6374 | 1,349,620 | 1,354 | 卫星PnL 9,395；路径劣化 |
| 上年为正宽池 r020 | 23,351,260 | 3696.9528% | -36.4055% | 1.6355 | 1,343,690 | 997 | 卫星PnL -18,245 |
| 上年为正宽池 r015 | 23,354,530 | 3697.4846% | -36.4126% | 1.6361 | 1,343,630 | 1,011 | 卫星PnL -14,975 |

### 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_chart_stage563_breadth_pool_product_selection_thesis_audit_v1.png`
- 左上图：年度机会确实存在，但集中在少数产品；2023/2025 全非核心单品种合计为负，hindsight top6 仍为正。
- 右上图：Stage256 fixed top6 有可见卫星贡献；全宽池贡献很小，上年为正宽池为负。
- 左下图：`lu.INE/v.DCE/al.SHFE/y.DCE/c.DCE/ao.SHFE` 确实是低相关材料性候选。
- 右下图：全宽池里 `lu.INE` 等赢家被 `zn.SHFE/PF.CZCE/fb.DCE/eb.DCE/cs.DCE` 等尾部亏损抵消。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_report_stage563_breadth_pool_product_selection_thesis_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_decision_stage563_breadth_pool_product_selection_thesis_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_chart_stage563_breadth_pool_product_selection_thesis_audit_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_summary_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_gates_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
- annual opportunity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_annual_opportunity_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
- material products：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_material_products_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
- width capture：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_width_capture_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
- product/family contribution：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_product_contribution_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_family_contribution_stage563_breadth_pool_product_selection_thesis_audit_v1.csv`

## 结论

- 本阶段结论：方向成立，但当前不能晋级交易版本。
- 是否进入下一步：进入数据工程/forward selector 路线，不进入宽池参数优化。
- 下一步：
  - 继续累计 point-in-time 外生状态样本，达到 `20` 个合格 runs / `20` 个合格 dates，并补至少 `1` 条真实 sentiment/news ledger。
  - 未来只做一次固定预测力审计：basis/inventory/member/sentiment 是否能提升未来 `63/126` 日品种趋势收益排序。
  - 停止继续扫全宽池 `risk/cap/corr/maxpos` 小数；宽池只能作为风险壳，不能当 alpha。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只整合已有证据和预定义闸门，不修改交易规则，不用未来收益生成交易白名单。
  - 对 hindsight top6 明确标记为不可部署上限，避免把“选对品种”的愿望误写成实盘规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：总方向有价值，但不能继续做宽池参数救援。
- 原因：
  - 机会和低相关候选都存在，说明“选对品种”不是空方向。
  - 宽池实际捕获弱、简单历史 selector 失败，说明真正瓶颈是事前 selector 数据资格；继续扫宽池壳会偏离本质。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段明确改变“低单笔风险扩池”后续边界。
