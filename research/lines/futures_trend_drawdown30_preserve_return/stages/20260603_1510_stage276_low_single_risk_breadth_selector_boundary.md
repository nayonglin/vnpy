# Stage276 低单笔风险扩池与选品晋级边界审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 15:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读审计；不修改策略、不重跑交易引擎、不生成交易候选
- 是否重要突破：否
- 是否触发A/B：否。本阶段没有产生可接入正式版本的新策略候选，只冻结扩池/选品晋级边界。

## 外部调研与判断

- 参考资料：
  - AQR Trend Following：`https://www.aqr.com/insights/trend-following`
  - AQR Century of Trend Following evidence：`https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing-executive-summ`
  - Increasing Diversification of Commodities Trend-Following Strategies：`https://papers.ssrn.com/sol3/Delivery.cfm/4871376.pdf?abstractid=4871376&mirid=1`
  - GitHub PyTrendFollow：`https://github.com/chrism2671/PyTrendFollow`
  - GitHub MLM trend-following：`https://github.com/amstrdm/mlm-trend-following`
- 我的判断：趋势跟踪的跨市场分散方向成立，但不能把“品种数量”误读成 alpha。实盘结构必须先过风险预算、产品族/相关性、容量、执行和 point-in-time selector 样本闸门。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage574_low_single_risk_breadth_selector_boundary.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增审计闸门 `6` 个：年度机会、独立材料性容量池、候选内部相关性、可部署宽池不劣化、宽池材料性捕获、selector 就绪度。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取 Stage541/544/557/558/561/565/570 既有输出，主统计覆盖 `2020-2026`；可部署宽池壳延续 Stage557 口径。
- 账户规模：Stage526 核心 `50万` 实盘约束口径；非核心扩池 sleeve 使用既有 Stage557 低单笔风险壳输出。
- 成本口径：正常成本 `1x`，本阶段不新增成本压力回放。
- 样本过滤：非核心商品、Stage541 单品种机会、Stage565 容量质量、Stage570 3/6个月持有体验与贡献集中度。
- 策略/归因口径：只读晋级边界审计；严禁用 hindsight top 品种直接生成白名单。

## 结果

- 期末权益：Stage526 核心 `23,369,505`
- 总收益：Stage526 核心 `3699.9195%`
- 最大回撤：Stage526 核心 `-36.2670%`
- Sharpe：Stage526 核心 `1.6385`
- 总滑点：Stage526 核心 `1,342,190`
- 总交易次数：Stage526 核心 `905`
- 胜率：Stage526 非零日胜率 `53.6330%`
- 其他关键指标：
  - 决策：`breadth_thesis_valid_selector_boundary_not_ready`
  - 晋级闸门：`2/6` 通过。
  - 通过项：年度非核心机会 `7/7` 年 top6 为正；候选内部相关性不拥挤。
  - 独立材料性且容量通过候选：`5` 个，分别为 `lu.INE/v.DCE/y.DCE/ao.SHFE/c.DCE`，平均 `abs(Stage526日PnL相关)=0.0516`。
  - 候选内部平均绝对相关：`0.0147`；最大绝对相关：`0.0508`。
  - 可部署宽池不劣化：`0/3` 通过。
  - 全非核心 r020 sleeve：卫星累计 PnL `9,395`，组合 DD 相对 Stage526 劣化 `-0.1044pp`，Ulcer 劣化 `+0.0211`。
  - Stage256 upper：63日 p10 相对 Stage526 改善 `+0.0378pp`，126日 p10 改善 `+0.1264pp`，但它是历史白名单/上界，不是可部署 selector。
  - Point-in-time selector：forward runs `2/20`、dates `2/20`，real sentiment ledger `1/1`；仍禁止选品收益回测。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_report_stage574_low_single_risk_breadth_selector_boundary_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_decision_stage574_low_single_risk_breadth_selector_boundary_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_chart_stage574_low_single_risk_breadth_selector_boundary_v1.png`
- candidate map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- annual opportunity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_annual_opportunity_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- pairwise corr：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_pairwise_corr_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- risk shell：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_risk_shell_boundary_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- selector readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_selector_readiness_stage574_low_single_risk_breadth_selector_boundary_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage574_low_single_risk_breadth_selector_boundary_gates_stage574_low_single_risk_breadth_selector_boundary_v1.csv`

## 图表视觉复盘

- 左上散点显示：`lu/v/y/ao/c` 等候选确实在低核心相关区域，说明“独立趋势候选”不是幻想；但数量只有 `5` 个，未达到最小 `6` 个池深度。
- 上中年度图显示：非核心 top6 每年都有正机会，但 2023 明显偏弱，说明扩池收益不是稳定均匀流入，而是少数年份/少数品种贡献。
- 右上和左下显示：只有 Stage256 upper 改善 DD/Ulcer 和 3/6 个月左尾；三个可部署宽池壳全部劣化或没有改善。
- 中下 selector readiness 显示：real sentiment ledger 已绿，但 forward runs/dates 只有 `10%` 进度，核心阻塞是样本深度。
- 右下 promotion gates 显示：方向只通过“年度机会”和“内部相关性”两项，失败项集中在可部署捕获和 selector readiness，不是候选相关性太高。

## 结论

- 本阶段结论：用户提出的“减少单笔风险、扩大品种池、每年抓部分趋势，同时避免高相关风险”在结构上成立，但当前不可晋级。现在缺的不是品种，也不是相关性处理，而是真正 point-in-time 的选品预测力。
- 是否进入下一步：进入，但只允许继续数据资格和固定 selector 协议，不允许继续扫宽池风险小数。
- 下一步：保持 Stage526 为核心；继续累计 basis/inventory/sentiment/news/manual event forward 样本到 `20/20`；满足后按 Stage561 冻结协议做 `63/126` 日 IC、bucket 和 paper sleeve 审计。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有用未来赢家生成白名单，没有搜索风险小数阈值，只读取已冻结输出并把晋级闸门写清楚。Stage256 也被明确标为 upper bound，不作为可部署版本。

## 继续价值反思

- 运行前判断：有继续价值。
- 运行后判断：有继续价值，但路径必须收窄。
- 原因：独立材料性候选和年度机会都存在，说明方向不应废弃；但可部署宽池失败，说明后续价值只在 point-in-time selector 和真实执行监控，不在继续扩大品种池或调小数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage276 摘要。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为边界确认，不是重要合入事件。
