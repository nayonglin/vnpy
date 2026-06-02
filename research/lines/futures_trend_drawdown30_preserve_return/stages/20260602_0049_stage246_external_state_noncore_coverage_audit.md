# Stage246 外生状态非核心覆盖审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 00:49 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据覆盖/可执行性审计；不做收益回测，不生成交易候选。
- 是否重要突破：否，但明确阻断了“直接拿现有外生缓存做非核心选品”的路径。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AKShare futures data / futures spot basis 文档与 GitHub。
  - Tushare 期货持仓/会员持仓接口文档。
  - AQR 趋势跟踪长期证据与多市场分散研究。
  - Rob Carver `pysystemtrade` 中的分散期货、风险预算与相关性控制实践。
- 我的判断：降低单笔风险、扩大品种池、避免高相关风险，是趋势策略更低过拟合的结构方向；但“选对品种”不能靠事后收益筛选，必须有点时化、可实盘获取、能覆盖非核心产品的外生状态。现有缓存若对非核心/Oracle6 覆盖为零，直接接选择器会把数据缺口误当成信号。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage546_external_state_noncore_coverage_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 审计对象：Stage543 非核心扩池样本与 Stage241 Oracle6 上限产品。
  - 路线：`member_rank_existing`、`supply_basis_warehouse_existing`、`term_structure_existing`。
  - 实时源探针日期：`20260417`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage543/Stage241 评估样本；本阶段只审计覆盖，不回放交易收益。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：Stage543 非核心产品 `38` 个；Oracle6 产品 `6` 个。
- 策略/归因口径：只检查现有外生缓存和固定日期实时源探针，不调任何选择器收益参数。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`existing_external_state_unusable_for_noncore_selection_basis_partial_backfill_needed`
  - 现有缓存覆盖：
    - `member_rank_existing`：非核心产品覆盖 `0/38`，row coverage `0%`，Oracle6 coverage `0%`
    - `supply_basis_warehouse_existing`：非核心产品覆盖 `0/38`，row coverage `0%`，Oracle6 coverage `0%`
    - `term_structure_existing`：非核心产品覆盖 `0/38`，row coverage `0%`，Oracle6 coverage `0%`
  - Oracle6 实时探针：
    - `basis` 返回 `4/6`：`al.SHFE`、`c.DCE`、`v.DCE`、`y.DCE`
    - `basis` 缺口 `2/6`：`ao.SHFE`、`lu.INE`
    - `member_rank` 返回 `0/6`，错误类型为 `BadZipFile`
    - `warehouse` 可用 `0/6`，SHFE/DCE 多为 `JSONDecodeError`，`lu.INE` 当前探针路径不支持
  - 图表视觉复盘：现有外生路线覆盖柱完全为零；Oracle6 热力图只在 basis 列有 4 个绿色单元，member/warehouse 全红；blocker 图显示会员和仓单缺口是全覆盖问题。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_report_stage546_external_state_noncore_coverage_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_route_summary_stage546_external_state_noncore_coverage_audit_v1.csv`
- coverage：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_coverage_by_product_stage546_external_state_noncore_coverage_audit_v1.csv`
- live probe：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_live_probe_stage546_external_state_noncore_coverage_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_decision_stage546_external_state_noncore_coverage_audit_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage546_external_state_noncore_coverage_audit_chart_stage546_external_state_noncore_coverage_audit_v1.png`

## 结论

- 本阶段结论：现有外生状态缓存不能用于非核心扩池选品；它对 Stage543 非核心样本和 Oracle6 都是零覆盖。AKShare 基差源有局部可行性，但需要专门回补；会员、仓单、舆情都不能直接进入 live 选择器。
- 是否进入下一步：进入“专门非核心基差回补和固定选择器诊断”，不进入交易候选。
- 下一步：先做月度基差快照与固定选择器检验；不在现有缓存上跑收益选择器，也不调会员/仓单/舆情因子窗口。

## 过拟合反思

- 运行前判断：不是过拟合。它是数据可用性审计，不看策略收益，不优化参数。
- 运行后判断：不是过拟合，反而降低了过拟合风险。
- 原因：本阶段拒绝把覆盖为零的缓存当成信号，避免用缺失模式拟合历史结果。

## 继续价值反思

- 运行前判断：有价值，因为 Stage245 已经证明价格/账本类状态不足，必须检查外生状态是否可用。
- 运行后判断：仍有价值，但价值集中在 basis 局部补齐和数据工程，不在现有缓存。
- 原因：basis 对 `AL/C/V/Y` 有样例返回，说明至少存在局部可验证路线；会员、仓单、舆情当前不具备直接回测资格。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
