# Stage250 产品机会几何审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 01:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读诊断；不做收益回测，不生成交易候选。
- 是否重要突破：否；但确认“选对品种”方向不是完全死路，上一年正收益延续有弱信号，值得下一步真实 sleeve 回放。
- 是否触发A/B：否。本阶段没有生成 C 版本；若下一步做 `prev_year_positive` 或 `prev_year_top6` 的真实 sleeve 组合回放，应先按 `skills/version-ab-experiment/SKILL.md` 做 A/C。

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟踪长期证据：多市场趋势跟随长期有效，但核心是跨市场分散和风险控制，不是用样本内赢家替代规则。
  - `pysystemtrade`：强调 instrument diversification、相关性与风险预算；这支持产品族/相关性壳，但不支持随意挑历史收益最高品种。
  - 期货趋势组合的公开工程实践普遍重视 point-in-time 数据和交易成本，避免用事后产品收益直接构造品种池。
- 我的判断：减少单笔风险、扩大品种池、每年抓部分品种趋势收益是合理方向；但真正难点是事前识别“当年哪个品种有趋势土壤”。当前价格/账本类特征只能提供弱信号，外生状态仍需 forward 账本积累。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage550_product_opportunity_geometry_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数/诊断口径：
  - Oracle6 仅作为 hindsight 上限标签：`al.SHFE/ao.SHFE/c.DCE/lu.INE/v.DCE/y.DCE`
  - 非核心商品池：Stage541 非核心产品，剔除 `CFFEX`
  - 年度窗口：`2020-2026`
  - 选择器模式：`all_noncore_equal`、`hindsight_top3/top6`、`oracle6_hindsight_basket`、`prev_year_positive`、`prev_year_top3/top6`、`prev_year_family_cap1`
  - point-in-time 特征 IC：Stage543 已有 `ai_probability/simple_trend/market_terrain/strategy_memory/hist_pnl/core_corr/low_core_corr/OI变化` 等特征，对未来 `60/120` 日单品种 sleeve PnL 做横截面 Spearman IC。
- 修改参数：
  - 初版误把 2020 纳入上一年赢家延续，已修正为上一年模式只从 `2021` 开始评估。
- 删除参数：无。

## 回测/归因参数

- 数据区间：读取 Stage541 单品种真实下一窗口成交账本、Stage543 事前样本、Stage544 产品族映射；不重新跑交易引擎。
- 账户规模：单品种机会来自 Stage541 的 `115000` sleeve；本阶段只做机会/可预测性诊断。
- 成本口径：沿用 Stage541 单品种真实成交成本，不新增成本假设。
- 样本过滤：非核心商品产品 `37` 个。
- 策略/归因口径：年度机会分布、上一年延续、特征 IC、相关性结构、Oracle6 诊断；不接入组合，不生成订单。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`annual_ex_ante_selection_has_signal_needs_true_sleeve_replay`
  - 非核心商品平均年度正收益品种率：`20.4633%`
  - 年度 Top3 平均产品族数：`2.8571`
  - 年度平均 PnL：
    - `hindsight_top6`：`61,237.1429`
    - `hindsight_top3`：`45,323.5714`
    - `oracle6_hindsight_basket`：`39,745.7143`
    - `prev_year_positive`：`24,104.1667`
    - `all_noncore_equal`：`23,724.2857`
    - `prev_year_top6`：`23,003.3333`
    - `prev_year_family_cap1`：`14,985.0000`
    - `prev_year_top3`：`9,640.8333`
  - 最好事前年度模式：`prev_year_positive`
    - 年数：`6`
    - 平均选择品种数：`8.3333`
    - 平均未来年度 PnL：`24,104.1667`
    - 正年份率：`83.3333%`
    - 平均 Oracle6 重叠：`3.8333`
    - 平均产品族数：`5.1667`
  - 特征 IC：
    - 未来60日最好：`hist_drawdown_120d`，mean IC `0.1214`，正IC率 `70.8333%`
    - 未来60日第二：`low_core_corr_rank_pct`，mean IC `0.0886`
    - 未来120日最好：`hist_drawdown_120d`，mean IC `0.1549`
    - 未来120日第二：`core_corr_252d`，mean IC `0.1408`
    - `simple_trend`、`ai_probability`、`strategy_memory_equal` 在未来60日 IC 近零或偏负。
  - 相关性：
    - 全部非核心活跃产品 pair 平均绝对相关：`0.0191`
    - 同产品族 pair 平均绝对相关：`0.0347`
    - 跨产品族 pair 平均绝对相关：`0.0169`
    - Oracle6 涉及 pair 平均绝对相关：`0.0194`
  - Oracle6 诊断：
    - `lu.INE` 总 PnL `87,510`，核心相关 `0.1543`，最大 broker10/sleeve `44.9181%`
    - `v.DCE` 总 PnL `50,705`，核心相关 `0.0647`
    - `al.SHFE` 总 PnL `51,925`，核心相关 `0.0184`
    - `ao.SHFE` 平均非核心相关最低，`0.0095`
  - 图表视觉复盘：
    - 年度热力图显示 Oracle6 并不是同一年一起爆发，`v/c` 相对持续，`lu` 明显受 2026 近端贡献影响。
    - 正收益品种数量从 2020 的 `16` 个降到 2023 的 `4` 个、2026 当前 `3` 个，说明机会宽度本身会大幅变化。
    - 年度选择器条形图显示 hindsight 与 Oracle6 明显高于事前模式；`prev_year_positive` 只略高于全非核心，不能直接晋级。
    - 特征 IC 图显示最强信号不是 AI/simple 趋势，而是“最近120日回撤较浅/低核心相关”这类风险土壤变量。
    - 散点图显示 Oracle6 集中在低核心相关且正 PnL 区域，说明相关性壳有效；但低相关不是充分条件，灰色低相关亏损点也很多。
    - 同族相关性高于跨族，继续支持 family cap 作为风险预算约束。

## 输出文件

- annual matrix：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_annual_matrix_stage550_product_opportunity_geometry_audit_v1.csv`
- annual summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_annual_summary_stage550_product_opportunity_geometry_audit_v1.csv`
- annual selection：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_annual_selection_stage550_product_opportunity_geometry_audit_v1.csv`
- feature IC：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_feature_ic_stage550_product_opportunity_geometry_audit_v1.csv`
- correlation summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_correlation_summary_stage550_product_opportunity_geometry_audit_v1.csv`
- product diagnostic：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_product_diagnostic_stage550_product_opportunity_geometry_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_decision_stage550_product_opportunity_geometry_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_report_stage550_product_opportunity_geometry_audit_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage550_product_opportunity_geometry_audit_chart_stage550_product_opportunity_geometry_audit_v1.png`

## 结论

- 本阶段结论：非核心品种每年确实存在趋势机会，且 Oracle6 的共同特征是低核心相关、低或可承受保证金、跨产品族分散；但事前选择能力仍弱，当前只能说明“上一年赚钱品种继续保留”有一点弱信号。
- 是否进入下一步：进入下一步真实 sleeve 回放，但只允许低自由度版本，例如 `prev_year_positive`、`prev_year_top6`，并且必须保持 Stage526 核心不被替换、新品种不挤占核心、family/corr 风险预算固定。
- 不得直接晋级：不能直接把 Oracle6 或年度 hindsight top6 作为实盘品种池。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只诊断机会几何，不生成策略版本；但使用 hindsight top/Oracle6 作为上限必须明确标注。
- 运行后判断：不是过拟合，但下一步风险升高。
- 原因：`prev_year_positive` 是低自由度、可事前执行的年度规则；但如果继续围绕 TopN、产品族、相关性阈值、小数和年度切点调参，就会变成过拟合。

## 继续价值反思

- 运行前判断：有价值，因为 Stage241/242 有上限空间，Stage243-249 说明现有动态 selector 和外生历史都不够。
- 运行后判断：有价值，但只能往一个很窄的方向走。
- 原因：年度延续信号只略强于全非核心，不能直接做交易候选；但它足以支持一次真实可成交、非挤占式、低自由度 sleeve 回放，检验能否对 Stage526 有材料性贡献。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
