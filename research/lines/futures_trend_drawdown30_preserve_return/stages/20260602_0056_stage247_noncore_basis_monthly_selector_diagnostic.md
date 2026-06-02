# Stage247 非核心月度基差选品诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 00:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：点时化数据补齐 + 固定选择器诊断；不生成交易版本。
- 是否重要突破：否；这是一次有效反证，明确 basis 不能单独作为动态 sleeve 选品核心。
- 是否触发A/B：否。没有达到可接入正式版本的晋级线。

## 外部调研与判断

- 参考资料：
  - AKShare `futures_spot_price` 基差数据源。
  - 商品期货 basis/term structure 与趋势收益相关研究。
  - AQR 多市场趋势跟踪证据。
  - `pysystemtrade` 风险预算、品种分散和相关性控制实践。
- 我的判断：基差有经济含义，可能解释某些商品趋势的“现货紧张/库存压力/期限结构”状态；但它不是天然 alpha。若基差选择器不能在 purged quarterly 样本里捕获 Oracle6 至少一半收益、且短窗口正收益率不够，就只能降级为解释/监控层。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 原始基差快照：Stage543 既有 `50` 个评估月，非核心产品 `38` 个。
  - 固定选择器：`basis_alignment_family_cap1`、`basis_pressure_family_cap1`、`basis_change_alignment_family_cap1`、`basis_blend_family_cap1`、`basis_blend_fill_stage544`。
  - 固定 family cap：每族最多 `1` 个产品。
  - 固定晋级线：Top6 相对全非核心未来60日均值 edge `>=500` 元/产品，Oracle6 捕获 `>=50%`，60日正窗口率 `>=55%`，Oracle6 平均召回 `>=2`，平均 basis 选中产品数 `>=4`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage543 既有月度评估日期，覆盖 `2022-01` 到 `2026-02` 附近样本。
- 账户规模：不适用；本阶段是选择器诊断，不形成组合账户回放。
- 成本口径：沿用 Stage541/543 的单产品真实下一窗口结果作为未来收益标签；本阶段不新增交易成本假设。
- 样本过滤：非核心产品 `38` 个；quarterly-purged 样本 `17` 个月。
- 策略/归因口径：只使用评估月当时可取的 basis 快照和固定公式，不看结果调权重。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`basis_monthly_selector_not_ready_coverage_and_predictive_power_short`
  - 通过项：`0`
  - basis 覆盖：非核心 `28/38` 有基差；Oracle6 `4/6` 有基差，Oracle6 平均覆盖率 `65.3333%`
  - 最好季度去重模式：`basis_alignment_family_cap1`
    - 未来60日均值：`151.3235`
    - 未来120日均值：`-23.9216`
    - 全非核心未来60日均值：`11.4087`
    - 相对全非核心 edge：`139.9149`
    - Oracle6 未来60日参考：`832.4020`
    - Oracle6 捕获比例：`18.1791%`
    - 60日正窗口率：`29.4118%`
    - Oracle6 平均召回：`0.5882`
  - 对比：Stage544 best family 模式仍明显优于多数 basis 模式，但仍远低于 Oracle6；basis 不是当前缺失的关键选择器。
  - 图表视觉复盘：覆盖图显示多数非核心产品已有 basis，但 AO/LU 仍为零；季度 edge 图中最好 basis 只有约 `140` 元/产品，远低于 `500` 晋级线；累计曲线显示 basis 线长期低于 Stage544 best 且远低于 Oracle6；Oracle6 热力图显示 `ao.SHFE/lu.INE` 全红。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_report_stage547_noncore_basis_monthly_selector_diagnostic_v1.md`
- raw basis：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_raw_basis_stage547_noncore_basis_monthly_selector_diagnostic_v1.csv`
- scored samples：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_scored_samples_stage547_noncore_basis_monthly_selector_diagnostic_v1.csv`
- coverage：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_coverage_stage547_noncore_basis_monthly_selector_diagnostic_v1.csv`
- selections：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_selections_stage547_noncore_basis_monthly_selector_diagnostic_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_summary_stage547_noncore_basis_monthly_selector_diagnostic_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_decision_stage547_noncore_basis_monthly_selector_diagnostic_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic_chart_stage547_noncore_basis_monthly_selector_diagnostic_v1.png`

## 结论

- 本阶段结论：月度基差能补齐一部分非核心产品覆盖，但固定 basis 选择器预测力不足，不能晋级动态 sleeve 选品。它最多作为解释/监控层，或与仓单、期限结构、产业链价差、会员持仓、舆情时间戳等更强外生状态合并后再审计。
- 是否进入下一步：不进入交易候选；允许进入“多源外生状态数据工程/解释层”。
- 下一步：不继续调 basis 权重、family cap、TopN 或相关阈值。若继续选品，只能先补 AO/LU 数据源、修复会员/仓单源，或建立真正点时化的产业链/舆情账本。

## 过拟合反思

- 运行前判断：不是过拟合。评估日期来自 Stage543，公式和晋级线预先固定，没有看结果调参数。
- 运行后判断：不是过拟合；但如果继续在 basis 权重、cap、TopN 上救结果，就会变成过拟合。
- 原因：当前最强 basis 模式离晋级线很远，继续微调只能拟合噪声。

## 继续价值反思

- 运行前判断：有价值，因为 Stage246 证明 basis 是唯一局部可用的外生状态源。
- 运行后判断：basis 单因子继续价值低，选品总方向仍有价值。
- 原因：Stage241/242 证明选对品种有上限空间；Stage247 证明单靠月度 basis 不能事前复刻该空间。下一步要么补更本质的数据源，要么回到 Stage526 正常成本候选，不继续救 basis 小参数。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
