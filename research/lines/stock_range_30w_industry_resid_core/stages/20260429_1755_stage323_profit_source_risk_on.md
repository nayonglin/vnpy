# Stage323 收益来源归因/risk-on仓位探针

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 17:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：收益来源归因 + 现金账户不加杠杆的加仓探针。
- 是否重要突破：否；明确了收益来源，但否定了当前简单risk-on加仓。
- 是否触发A/B：否；股票震荡独立研究线，不接入第78。

## 外部调研与判断

- 参考资料：
  - Volatility Managed Portfolios：`https://www.stern.nyu.edu/sites/default/files/assets/documents/Volatility%20Managed%20Portfolios.pdf`
  - Smoothing volatility targeting：`https://arxiv.org/abs/2212.07288`
  - QuantPedia Cross-Sectional Equity Mean Reversion：`https://quantpedia.com/quantopian-quantpedia-trading-strategy-series-cross-sectional-equity-mean-rever/`
  - Backtesting a Cross-Sectional Mean Reversion Strategy in Python：`https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/`
  - GitHub risk-parity topic：`https://github.com/topics/risk-parity`
- 我的判断：收益 timing 比风险 timing 更容易过拟合。横截面均值回归的收益经常来自压力后的反弹日，而不是表面“好市场”。所以可以研究收益来源，但不能看到某个状态赚钱就直接加仓。

## 本次变更

- 新增脚本：`examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `breadth_ret20_healthy_plus25_cap100`
  - `breadth_ret20_healthy_cash_to_full`
  - `strategy_not_hot_plus25_cap100`
  - `strategy_not_hot_cash_to_full`
  - `breadth_healthy_strategy_not_hot_cash_to_full`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2019-01-15 到 2026-04-27。
- 账户规模：`300,000`元。
- 成本口径：30万整手成交回放、涨跌停/停牌阻断、ADV参与率约束、最低佣金压力。
- 样本过滤：固定第316-322阶段四个代表形状。
- 策略/归因口径：
  - 收益来源归因使用前一日可见市场宽度、指数状态、策略自身慢状态。
  - risk-on探针不加杠杆，目标毛仓上限`100%`。
  - `gross100`场景已接近满仓，risk-on主要检验`gross70`现金仓位能否在好状态补仓。
  - 含策略自身状态的risk-on规则使用基准路径状态，只作为探针，不作为正式路径依赖候选。

## 结果

- 跨场景正收益状态：`21`个。
- 最高正收益来源不是“健康市场”，而是压力/修复状态：
  - `prev_index_drawdown_120_state=dd120_mid`
  - `prev_breadth_ma60_state=ma60_weak`
  - `prev_strategy_ret60_state=ret60_down`
  - `prev_strategy_dd120_state=strategy_dd120_mid`
  - `prev_index_vol60_state=vol60_mid`
  - `prev_breadth_ret20_state=ret20_weak`
- 交互正收益最强：
  - `strategy_dd120_mid__dd120_mid`
  - `dd120_mid__ma60_weak`
  - `strategy_dd120_mid__ma60_weak`
- 收益集中度：
  - 四个代表形状的前10%赚钱日贡献约`47.83%`到`48.81%`的正收益。
  - 前10%亏钱日贡献约`51.14%`到`51.38%`的负收益。
  - 说明收益和风险都高度集中，简单加仓容易同时放大尾部亏损。
- 行业近似贡献：
  - 第320候选形状贡献靠前行业包括`半导体`、`电气设备`、`通信设备`、`小金属`、`医疗保健`。
  - `软件服务`、`建筑工程`等在近似贡献中偏弱。
- 分数桶近似贡献：
  - 在选中股票内部，`selected_score_low`贡献反而最高，`selected_score_top20`不是最强。
  - 这提示当前分数更像准入/排序工具，不宜简单按更高分加仓。
- risk-on探针：
  - 20个探针中提高收益：`11/20`。
  - 同时提高收益且不恶化回撤：`0/20`。
  - 进入高收益且20%以内回撤：`0/5`候选形状探针。
- risk-on收益最高：
  - 场景：`industry_resid_core_h10_top5_gross70_ind1_strategy_not_hot_cash_to_full`
  - 期末权益：`484,626`
  - 总收益：`61.54%`
  - 最大回撤：`-41.60%`
  - Sharpe：`0.396`
  - 总成本折算：约`231,303`元
  - 总交易次数：`19,687`
  - 胜率：`51.98%`
- 更温和的候选形状risk-on：
  - 场景：`industry_resid_core_h10_top5_gross70_ind1_strategy_not_hot_plus25_cap100`
  - 期末权益：`476,329`
  - 总收益：`58.78%`
  - 最大回撤：`-32.94%`
  - Sharpe：`0.410`
  - 总成本折算：约`191,782`元
  - 总交易次数：`18,526`
  - 胜率：`51.80%`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_report.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_summary.csv`
- orders：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_orders.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_daily.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：收益来源可以归因，而且主要来自“弱宽度/指数中等回撤/策略回撤后的修复”，不是简单好市场；但当前简单risk-on加仓会放大回撤，不能升级。
- 是否进入下一步：进入，但方向不是继续加仓扫状态。
- 下一步：转向信号层和组合构成，研究如何减少前10%亏损日/亏损行业暴露，而不是在收益来源状态粗暴补仓。

## 过拟合反思

- 运行前判断：风险较高。
- 运行后判断：未把探针升级，过拟合风险可控。
- 原因：收益来源研究天然接近收益 timing；本阶段用预注册规则、现金账户上限和质量检查约束，结果显示加仓不达标。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但加仓方向暂时否决。
- 原因：收益来源和亏损集中度给出了下一步线索：策略的问题不是缺少风险放大，而是亏损日/行业/分数结构没有被有效隔离。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，当前状态未变成正式候选或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内日常研究记录。
