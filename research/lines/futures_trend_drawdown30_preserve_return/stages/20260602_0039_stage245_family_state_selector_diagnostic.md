# Stage245 产品族状态事前选品诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-02 00:39 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；不修改 Stage526/Stage079/C3 交易规则，不生成交易候选
- 是否重要突破：否；但形成重要反证，说明现有价格/账本类产品族状态分不足以承担“选对品种”任务
- 是否触发A/B：否。本阶段没有产生可合入交易版本。

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟随长期证据说明跨资产/跨市场分散对趋势策略很重要：https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
  - `pysystemtrade` 的 instrument diversification/correlation 思路强调用品种相关性和分散乘数管理组合风险：https://github.com/robcarver17/pysystemtrade
  - 商品期货的 basis/term-structure、库存和动量在文献中常作为互补状态变量，说明单纯价格动量之外需要产业状态：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2990036
  - Tushare 会员持仓接口可用于交易所会员持仓排名，但本仓库 token 冒烟失败，暂不能作为 live pipeline：https://tushare.pro/document/2?doc_id=139
- 我的判断：
  - “降低单笔风险、扩大品种池、避免高相关”作为风险预算原则是对的，Stage244 已经证明它能改善 edge。
  - 但“选对品种”不是靠同一套价格/账本分数再加权就能解决。需要点时化产品族状态，最好来自基差、库存/仓单、产业链价差、会员/资金流和真实接收时间戳新闻。
  - 本阶段先固定低自由度产品族状态分，只验证方向，不扫权重或阈值。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage545_family_state_selector_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数/结构：
  - `TOP_K=6`
  - `LOW_CORE_CORR_THRESHOLD=0.30`
  - 通过定义：季度去重 Top6 未来60日相对全非核心均值 `>=500元/产品`、捕获 Oracle6 未来60日均值 `>=50%`、60日正月份率 `>=55%`、平均 Oracle6 召回 `>=2`、未来120日均值非负。
  - 产品族状态分：
    - `family_trend_state_score`
    - `family_memory_state_score`
    - `family_flow_state_score`
    - `family_lowcorr_state_score`
    - `family_blend_state_score`
  - 选择模式：
    - `family_trend_state_best1`
    - `family_memory_state_best1`
    - `family_flow_state_best1`
    - `family_blend_state_best1`
    - `family_blend_state_lowcorr030`
    - `family_blend_state_top4_cap2`
- 修改参数：无
- 删除参数：无

## 回测/诊断参数

- 数据来源：
  - Stage543 scored samples：`qmt_roll_stage543_ex_ante_product_selector_diagnostic_scored_samples_stage543_ex_ante_product_selector_diagnostic_v1.csv`
  - Stage544 family map：`qmt_roll_stage544_family_constrained_selector_diagnostic_family_map_stage544_family_constrained_selector_diagnostic_v1.csv`
  - Stage544 best 对照：`simple_family_cap1_lowcorr030`
- 样本口径：
  - monthly：全部评估月
  - quarterly_purged：每季度最后一个评估月，降低重叠持有期污染
- 只使用评估日可见特征：
  - simple趋势分、市场地形、历史策略账本、成交量/持仓量变化、流动性、低核心相关
  - Oracle6 只做召回/捕获审计，不进入打分

## 结果

- 期末权益：无新增账户回测；本阶段为产品族选择器诊断
- 总收益：无新增账户回测
- 最大回撤：无新增账户回测
- Sharpe：无新增账户回测
- 总滑点：无新增账户回测
- 总交易次数：无新增账户回测
- 胜率：无新增账户回测
- 对照账户指标引用：
  - Stage526 control：`23,369,505 / 3699.9195% / -36.2670% / Sharpe 1.6385 / 滑点 1,342,190 / 交易 905 / 非零日胜率 53.6330%`
  - Stage542 Oracle6 上限 C2：`23,488,930 / 3719.3382% / -36.1186% / Sharpe 1.6485 / 滑点 1,347,620 / 交易 1,150 / 非零日胜率 53.5615%`
- Stage545 诊断结果：
  - 通过项：`0`
  - 决策：`family_state_selector_not_ready_external_state_needed`
  - 最好季度去重产品选择模式：`family_memory_state_best1`
    - 未来60日均值：`-77.5000`
    - 全非核心未来60日均值：`11.4087`
    - edge：`-88.9087`
    - Oracle6 未来60日参考：`832.4020`
    - Oracle6 捕获比例：`-9.3104%`
    - 60日正月份率：`41.1765%`
    - 未来120日均值：`-503.9706`
    - 平均 Oracle6 召回数：`2.2353`
    - 平均家族数：`6.0000`
    - 平均核心相关绝对值：`0.0376`
  - 最好产品族状态信号：`family_flow_state_score`
    - top family 未来60日均值：`-52.2222`
    - 相对全产品族 edge：`17.7700`
    - 60日正月份率：`41.1765%`
    - 平均 Oracle family 召回：`2.8824`
    - 未来120日 edge：`-161.6344`

## 图表视觉复盘

- 图表：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_chart_stage545_family_state_selector_diagnostic_v1.png`
- 视觉结论：
  - 左上 edge 图中所有产品族状态模式都在 `0` 轴左侧，离 `500` 元/产品通过线很远。
  - 右上正月份率和 Oracle 捕获图显示：正月份率最高也只有 `41.1765%`，Oracle 捕获为负或很低。
  - 左下累计图显示 Stage544 best family cap 仍明显优于 Stage545 状态先验，但仍远低于 Oracle6；Stage545 最好几条曲线后期转负。
  - 右下产品族频率显示 `base_metals/rubber/petrochem` 有正贡献，但选择器高频选到 `energy_oil/grains_oilseeds/black_ferrous/soft_agri` 等负贡献族，说明现有状态分无法判断“该启用哪个产品族”。

## 结论

- 本阶段结论：
  - 降低单笔风险、扩大品种池、避免高相关是正确的组合工程方向，但“选对品种”的关键不在当前这些价格/账本状态分。
  - Stage244 的静态产品族约束仍应保留为风险预算原则；Stage545 的产品族状态先验不应晋级。
  - 不继续扫 `family_blend` 权重、产品族数量、相关阈值或 TopN 小数。
- 是否进入下一步：是，但不是继续调当前选择器。
- 下一步：
  1. 优先做点时化外生状态路线：基差、仓单/库存、产业链价差、会员/资金流、真实接收时间戳新闻。
  2. 基差可先做“固定强逆风/顺风解释层”而非直接 alpha；仓单/会员/舆情必须先过覆盖和 live 可执行性。
  3. 若没有外生状态数据，当前最稳判断仍是 Stage526 正常成本候选，不把 Oracle6 变成实盘篮子。

## 输出文件

- script：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/analyze_qmt_roll_stage545_family_state_selector_diagnostic.py`
- family scores：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_family_scores_stage545_family_state_selector_diagnostic_v1.csv`
- selections：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_selections_stage545_family_state_selector_diagnostic_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_summary_stage545_family_state_selector_diagnostic_v1.csv`
- family signal summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_family_signal_summary_stage545_family_state_selector_diagnostic_v1.csv`
- contribution：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_family_contribution_stage545_family_state_selector_diagnostic_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_decision_stage545_family_state_selector_diagnostic_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_report_stage545_family_state_selector_diagnostic_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage545_family_state_selector_diagnostic_chart_stage545_family_state_selector_diagnostic_v1.png`

## 过拟合反思

- 运行前判断：否。
- 原因：本阶段是低自由度反证，只使用评估日可见特征，不用未来收益和 Oracle 标签打分。
- 运行后判断：继续扫当前产品族状态分会过拟合。
- 原因：
  - 结果显著失败，若继续改权重或阈值，只是在 17 个季度去重样本上追噪音。
  - 图表显示失败不是单个指标卡线，而是整体曲线和正月份率都弱。

## 继续价值反思

- 运行前判断：有价值。
- 原因：用户提出的“减少单笔风险、扩大品种池、避免高相关、选对品种”是 Stage239-244 后最自然的结构方向。
- 运行后判断：总方向仍有价值，但当前特征层继续价值低。
- 原因：
  - Stage244 证明产品族/相关性约束有边际价值。
  - Stage545 证明真正缺的是“产品族当时有没有趋势土壤”的外生状态，而不是价格/账本分数再加权。

