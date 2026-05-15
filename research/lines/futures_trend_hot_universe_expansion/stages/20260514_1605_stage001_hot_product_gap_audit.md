# Stage001 热门缺口品种扩池初始审计

- line_id：futures_trend_hot_universe_expansion
- 当前模式：day
- 记录时间：2026-05-14 16:05
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy
- 阶段性质：新研究线创建 / 数据覆盖审计 / A/B预注册
- 是否重要突破：否
- 是否触发A/B：预注册A/B/C，尚未运行回测

## 外部调研与判断

- 参考资料：
  - 新浪财经转载2025年上半年全国期货期权市场交易持仓数据解读：豆粕、螺纹钢、玻璃、纯碱、PTA、白银、PVC、棕榈油、甲醇、燃料油、玉米等在成交量前30中。
  - 中国经济网转载中期协2025全年数据：2025年全国期货市场成交量90.74亿手、成交额766.25万亿元；各商品交易所成交额靠前品种包含白银、黄金、铜、PTA、焦煤、棕榈油、豆粕等。
  - QuantConnect commodity futures trend-following示例和Quantica trend-following容量研究：趋势策略品种池应重视跨市场分散、流动性、容量和合约乘数/保证金，而不是只按历史收益筛选。
- 我的判断：热门缺口品种值得系统测试；但第一步必须先审计数据覆盖和可交易性，否则会把数据缺失误判为策略不适合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage264_hot_product_gap_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 目标品种：`ag.SHFE, sc.INE, fu.SHFE, TA.CZCE, m.DCE, p.DCE, y.DCE, i.DCE, v.DCE, c.DCE, ao.SHFE`
- 修改参数：无
- 删除参数：无

## A/B/C 预注册

- A：`official_stage78_1_defensive_50w_no_sizing_cap`
- B：热门缺口品种独立/分组候选池，用于识别是否存在可交易趋势结构
- C：Stage78-1 + 通过数据覆盖和结构验证的候选扩池
- 通过标准：
  - C 不得显著恶化Stage78-1最大回撤、弱窗口和2026冷启动体验
  - C 在全样本、起始年份、季度冷启动、滑点压力和leave-one-product下必须有稳定证据
  - 不能因为单品种或单窗口收益好而晋级

## 回测/归因参数

- 数据区间：本阶段未跑策略回测；读取既有全市场宇宙审计文件，主覆盖窗口截至 `2026-04-30`
- 账户规模：暂不适用；后续按 Stage78-1 正式 `500,000` 口径
- 成本口径：暂不适用
- 样本过滤：只做目标品种数据覆盖、可交易宇宙和结构预筛状态审计
- 策略/归因口径：Stage78-1扩池候选前置审计

## 结果

- 期末权益：未跑回测
- 总收益：未跑回测
- 最大回撤：未跑回测
- Sharpe：未跑回测
- 总滑点：未跑回测
- 总交易次数：未跑回测
- 胜率：未跑回测
- 其他关键指标：
  - 目标品种数：`11`
  - 已在当前Stage78-1 `static18 + fu` 中：`1`，即 `fu.SHFE`
  - 当前 full-market tradable universe 合格：`4`，即 `ag.SHFE, sc.INE, fu.SHFE, c.DCE`
  - 当前 structural prefilter 通过：`1`，即 `fu.SHFE`
  - 需要先补数据覆盖：`7`，即 `TA.CZCE, m.DCE, p.DCE, y.DCE, i.DCE, v.DCE, ao.SHFE`
  - 可先做结构反事实add-one：`ag.SHFE, sc.INE, c.DCE`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage264_hot_product_gap_audit_report_stage264_hot_product_gap_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage264_hot_product_gap_audit_summary_stage264_hot_product_gap_audit_v1.json`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage264_hot_product_gap_audit_audit_stage264_hot_product_gap_audit_v1.csv`

## 结论

- 本阶段结论：用户提出的11个热门品种全部应该进入详细测试范围。当前最大阻塞不是“是否热门”，而是趋势全市场宇宙中 `TA/m/p/y/i/v/ao` 的近端主力日线覆盖率不足，不能直接用于策略适配结论。
- 是否进入下一步：是。
- 下一步：先补齐 `TA/m/p/y/i/v/ao` 主力合约日线覆盖；同时可以对 `fu/ag/sc/c` 做第一轮 add-one/counterfactual add-one 小实验。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只定义研究边界和数据质量门槛，不根据收益挑品种，也不调参数。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：如果基础宇宙漏掉高流动性大品种，Stage78-1的跨周期判断会偏窄；但必须先补数据和做结构验证，避免把扩池做成收益筛选。

## 合入建议

- 是否更新本线 `LINE.md`：是，已创建并写入当前状态。
- 是否更新 `research/registry.md`：是，新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段未跑回测，也未形成正式候选。
