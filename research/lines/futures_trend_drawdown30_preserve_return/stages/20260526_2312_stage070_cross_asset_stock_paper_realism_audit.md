# Stage070 跨资产股票paper真实性复核

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 23:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage069 候选真实性复核；路线降级
- 是否重要突破：否，重要反证
- 是否触发A/B：是。Stage069 可能接近正式候选，本阶段按 A/B 隔离原则只做真实性复核，不改 78-1、C3 或股票 paper 策略规则。

## 外部调研与判断

- 参考资料：
  - AQR managed futures / trend following 资料支持跨资产低相关分散对趋势策略回撤有先验价值。
  - Harvey/Liu、Lopez de Prado 等关于金融回测多重检验和回测过拟合的研究提醒：净值层好看不足以证明可实盘，必须审计成交、资金颗粒度、容量和 OOS。
- 我的判断：
  - Stage069 的方向有经济含义：用低相关股票震荡 paper 净值平滑 C3。
  - 但当前目标是 50万 Stage78-1/C3 口径；若 5% 股票腿只有 2.5万，A股 100股整手和最低佣金会让真实组合严重偏离 1000万 paper 权重账本。
  - 因此本阶段只做真实性审计，不做权重救援，不扫 `4%/6%/7%`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage370_cross_asset_stock_paper_realism_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 股票整手压力账户：`25,000/50,000/100,000/250,000/300,000/1,000,000` 元
  - A股整手：`100` 股
  - 最低佣金压力：`5` 元
  - 组合口径：`95%C3 + 5%股票腿`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：公共样本 `2020-01-02` 至 `2026-04-27`
- 账户规模：当前目标口径为 50万；真实 5% 股票腿等价 `25,000` 元股票袖珍账户。
- 成本口径：股票腿复算加入 100股整手约束和 5元最低佣金压力。
- 样本过滤：读取 Stage369 C3 日曲线、股票 paper 日账本、v3 ex-ante ADV 和 fallback audit；不改 C3/股票规则。
- 策略/归因口径：
  - `A_c3_100`
  - `cash_control_c3_95_cash_05`
  - `combo_c3_95_stock_lot_25000_05`
  - `combo_c3_95_stock_lot_300000_05`

## 结果

- 账面 paper 组合：总收益 `5078.5193%`，最大回撤 `-29.5080%`。
- 真实 2.5万股票整手组合：总收益 `4905.6132%`，最大回撤 `-29.7400%`，C3收益保留 `84.0238%`。
- 同权重现金对照：总收益 `4908.2096%`，最大回撤 `-29.7155%`。
- 2.5万股票腿目标买不到一手比例：`96.7957%`。
- 2.5万股票腿最新目标日实际持仓数：`1`。
- `30万` 股票整手账户组合：总收益 `5047.2844%`，最大回撤 `-29.5659%`，C3收益保留 `86.4504%`，优于同权重现金；但它需要独立/更大股票资金，不是当前 50万内 5% 股票腿。
- 决策：`fail_true_50w_split_stock_leg_not_realistically_portable`。

## 检查点

- `paper_ledger_quality_fail_zero`：通过，股票 paper 质量检查失败项 `0`。
- `v3_exante_fill_ratio_above_99pct`：通过，ex-ante ADV 成交填充率 `0.9972600173601659`。
- `fallback_audit_pass`：通过，fallback audit 通过率 `1.0`。
- `fallback_not_current_turnover`：通过，fallback 不等同当日成交额。
- `true_25k_lot_rounding_tolerable`：失败，目标买不到一手比例 `96.80%`。
- `true_25k_latest_diversification_tolerable`：失败，最新实际持仓数 `1`，低于分散要求。
- `true_25k_combo_drawdown30`：通过，最大回撤 `-29.7400%`。
- `true_25k_combo_return_retention80`：通过，C3收益保留 `84.0238%`。
- `true_25k_combo_beats_cash`：失败，收益和回撤均略差于同权重现金。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_report_stage370_cross_asset_stock_paper_realism_audit_v1.md`
- account_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_account_summary_stage370_cross_asset_stock_paper_realism_audit_v1.csv`
- combo_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_combo_summary_stage370_cross_asset_stock_paper_realism_audit_v1.csv`
- account_daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_account_daily_stage370_cross_asset_stock_paper_realism_audit_v1.csv`
- checkpoints：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_checkpoints_stage370_cross_asset_stock_paper_realism_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage370_cross_asset_stock_paper_realism_audit_decision_stage370_cross_asset_stock_paper_realism_audit_v1.json`

## 结论

- 本阶段结论：Stage069 的净值层线索不能直接升级为当前 50万正式候选。
- 核心原因：50万账户内 5% 股票腿只有 2.5万，受 100股整手和最低佣金影响，无法复刻 1000万股票 paper 的分散组合；真实 2.5万股票腿组合还略差于同权重现金稀释。
- 是否进入下一步：当前 `95%C3+5%股票paper` 在 50万内 5% 股票腿口径不进入下一步。
- 下一步：
  - 若继续跨资产路线，只能研究两个方向：一是独立股票账户资金约 `30万+` 的组合层方案；二是寻找小资金可承载的 ETF、指数、期权、期货化或其他低相关工具。
  - 不继续扫股票权重小数，不调股票 paper 内部参数。

## 过拟合反思

- 运行前判断：不是过拟合。Stage069 是粗权重、低相关先验下的候选，本阶段只验证真实性。
- 运行后判断：不是过拟合。结果暴露了承载失败，没有继续调参救结果。
- 原因：本阶段没有新增可搜索参数；失败来自资金颗粒度和整手交易约束，而不是收益排序。

## 继续价值反思

- 运行前判断：有价值。Stage069 是当时最接近目标的候选，必须确认是否可执行。
- 运行后判断：跨资产思路仍有价值，但当前 2.5万股票腿路线继续价值低。
- 原因：多资产低相关仍可能帮助平滑曲线；但必须换成当前资金能真实承载的工具，否则只是纸面净值拼接。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage069 在 50万内 5% 股票腿口径下被反证。
- 是否更新 `research/registry.md`：是，当前线最新阶段改为 Stage070。
- 是否追加根目录 `memory.md/back_log.md`：是，作为候选降级和后续禁区。
