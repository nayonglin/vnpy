# Stage342 低单笔风险扩池与选品关键性决策板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 10:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：回答“减少单笔风险、扩大品种池、每年抓部分趋势、避免高相关，是否可行”的决策板；只读复用既有 Stage563/638/639 输出
- 是否重要突破：否；方向被确认有价值，但不能晋级交易版本
- 是否触发A/B：否；没有新增策略候选、paper、白名单或实盘版本

## 用户问题

用户提出：是否可以减少单笔风险、扩大品种池，每年只需要抓到部分品种趋势收益，同时避免高相关品种风险；核心可能是选对品种。

## 外部调研与判断

- 参考资料：
  - AQR trend following research：`https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want`
  - Man Group trend-following optimal market mix：`https://www.man.com/insights/trend-following-optimal-market-mix`
  - Aspect Capital diversification in trend following：`https://www.aspectcapital.com/insight/diversification-trend-following/`
  - PyTrendFollow futures trend implementation：`https://github.com/chrism2671/PyTrendFollow`
  - PyPortfolioOpt / HRP portfolio construction：`https://github.com/PyPortfolio/PyPortfolioOpt`
- 我的判断：
  - 方向成立。趋势跟随的收益天然稀疏，不应把长期结果押在少数品种和少数大仓位上；更成熟的形状是“更多独立风险来源 + 每个来源更小风险预算”。
  - 但有效分散单位不是“品种数量”，而是独立经济驱动、低相关结构、流动性、source/PIT/TCA 和可事前识别的 selector。
  - 如果没有 point-in-time 选品器，直接扩池只会把趋势赢家、震荡亏损、同产业链高相关和流动性噪音一起纳入，历史上已经被 Stage563 反证。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage642_low_single_risk_expanded_pool_decision_board.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `CURRENT_EFFECTIVE_SLOTS=4`
  - `TARGET_EFFECTIVE_SLOTS=7`
  - `MATERIAL_BREADTH_PNL_THRESHOLD=50000`
  - 只读输入：Stage638 年度机会、Stage638 产品阶梯、Stage639 家族 source gap、Stage563 宽池 thesis summary
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage563/638/639 冻结输出，年度范围 `2020-2026`
- 账户规模：不新增账户回测
- 成本口径：不新增成本压力重放
- 样本过滤：
  - 年度机会：Stage638 非核心 oracle top6 年度机会
  - 产品阶梯：Stage638 产品族、相关性、材料性、部署状态
  - 家族缺口：Stage639 `energy_oil/base_metals/grains_oilseeds/petrochem`
  - 宽池反证：Stage563 全非核心低单笔 sleeve 与上一年为正 sleeve
- 策略/归因口径：
  - 不重放策略，不改变交易规则，不扫 `risk/cap/corr/maxpos` 小数
  - 不抓新行情，不连接 CTP，不生成 selector/paper/A/B/交易白名单

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`low_single_risk_expand_pool_thesis_valid_selector_source_not_ready`
  - annual opportunity years：`7/7`
  - independent family years：`7/7`
  - current / target effective slots：`4/7`
  - plain breadth sleeve PnL：`9,395`
  - plain breadth sleeve return：`8.1696%`
  - prev-year-positive sleeve PnL：`-18,245`
  - material low-corr products：`6`
  - deployable new products：`0`
  - active fetch families：`0`
  - high corr hit families：`3/4`
  - hard gates：`6/12`
  - promotion / paper / whitelist：`false / false / false`

## 家族动作板

| 家族 | 年度 top6 命中年数 | 年度 top6 PnL 合计 | 高相关拒绝命中 | 官方 source 候选 | active fetch | 平均对 P0 最大绝对相关 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `energy_oil` | 6 | 130310 | 5 | 2 | 0 | 0.5492 | 趋势机会强但高相关，必须先证明独立 source/selector |
| `base_metals` | 6 | 102315 | 4 | 2 | 0 | 0.2850 | 官方源价值高，但当前公开 current route 被阻断，只能先找授权/官方下载 |
| `grains_oilseeds` | 6 | 74620 | 2 | 1 | 0 | 0.3717 | 多数是现有 P0 或同族深度，只能做 tie-break，不新增槽 |
| `petrochem` | 6 | 48895 | 0 | 1 | 0 | 0.4933 | 机会存在但 P0/数据源/独立性未闭合 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_report_stage642_low_single_risk_expanded_pool_decision_board_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_decision_stage642_low_single_risk_expanded_pool_decision_board_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_annual_board_stage642_low_single_risk_expanded_pool_decision_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_family_action_stage642_low_single_risk_expanded_pool_decision_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_product_focus_stage642_low_single_risk_expanded_pool_decision_board_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_gates_stage642_low_single_risk_expanded_pool_decision_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage642_low_single_risk_expanded_pool_decision_board_chart_stage642_low_single_risk_expanded_pool_decision_board_v1.png`

## 图表视觉复盘

- 左上图：年度 oracle top6 PnL 在 `2020-2026` 全部为正，说明“每年抓部分品种趋势”方向不是伪命题；但 `2026` 紫色 top1 share 接近 `90%`，说明仍有赢家高度集中风险。
- 右上图：`material_but_not_independent_slot=6`，但它们不是 deployable；`p1_source_tca_blocked=3`、`p2_forward_monitor=3` 只是工作流状态，不能当交易槽。
- 左下图：四个年度赢家家族全部位于 `0.15` 相关性观察线右侧；`energy_oil` 年度机会最大，但平均对 P0 最大相关最高，说明“机会大”和“能降低组合单槽风险”不是同一件事。
- 右下图：绿色只集中在年度机会、材料线索、识别高相关和 fail-closed 纪律；红色集中在简单宽池捕获、路径不劣化、上一年赢家 selector、7槽目标、新 deployable slot 和 active source。
- 视觉质量：图表无关键遮挡；左下 `energy_oil` 标注靠近右边界，但不影响读数和结论。

## 结论

- 本阶段结论：
  - 你的判断方向正确：减少单笔风险、扩大低相关机会集，是当前策略结构上最有价值的方向之一。
  - 但“扩大品种池”不能直接做成交易版本。已有证据显示：简单全非核心低单笔 sleeve 只贡献 `9,395` PnL，收益 `8.17%`，且路径略劣化；上一年为正 selector 还亏 `-18,245`。
  - 当前本质缺口是选品器和 source/PIT/TCA，不是单笔风险参数。没有可事前识别、低相关、source 可执行的新增风险槽前，不能把单槽风险实际降到目标。
- 是否进入下一步：继续，但只沿着 source/PIT/TCA/selector 做，不继续宽池小数扫参。
- 下一步：
  - `base_metals` 不再反复试当前公开 SHFE URL，只找授权/官方下载或 LME licensed/OLP 路线。
  - `lh.DCE` 已有官方月度源 master PIT，继续累计新自然日 PIT。
  - 继续寻找两个非 DCE、低相关、source 可执行的新独立经济驱动；每个新槽必须先过 source/PIT/TCA，再谈 selector 和交易化。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段没有用 hindsight top6 生成白名单，也没有扫参数或改变交易规则。
  - 年度赢家只用来判断“机会是否存在”，不作为事前选品器。
  - 结论是锁定晋级，而不是为了迎合扩池想法放宽门槛。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但必须缩窄。
- 原因：
  - 年度机会 `7/7` 存在，说明低单笔风险扩池的第一性原理成立。
  - 但简单宽池和上一年赢家 selector 都失败，继续扫小数价值低。
  - 真正值得继续的是构建可验证的独立风险槽：低相关、外生 source、PIT 样本、真实 TCA、固定 outcome，再决定是否允许新 selector。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage342 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
