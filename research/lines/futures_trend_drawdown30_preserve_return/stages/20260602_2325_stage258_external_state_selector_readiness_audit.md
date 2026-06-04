# Stage258 外生状态选品器 Readiness 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:25 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读资格审计；不做收益回测，不生成交易候选。
- 是否重要突破：否；但给“降低单笔风险、扩大品种池、避免高相关、选对品种”路线补上数据资格边界。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AQR `Demystifying Managed Futures` / trend-following 资料：趋势跟踪长期有效性来自跨市场、跨品种分散和波动/风险预算，而不是样本内赢家放大。
  - `pysystemtrade` / Rob Carver 框架：多品种趋势组合应强调 instrument diversification、相关性和风险预算。
  - 商品期货动量/期限结构文献：momentum、term structure、basis、inventory、hedging pressure 等变量更接近“趋势土壤”，但必须点时化，不能事后回填。
- 我的判断：你的方向成立，但当前短板不是风险壳，而是 selector 数据资格。Stage257 已经反证简单宽池/上一年为正宽池；继续价值在于 forward 外生状态账本和未来预测力审计，不在继续扫 `risk/cap/corr/maxpos`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage558_external_state_selector_readiness_audit.py`
- 修改脚本：初跑后收紧舆情账本判定，研究记录 `.md` 不再算可交易舆情账本；只有 CSV/JSON 且同时包含接收时间与品种映射才算候选账本。
- 删除脚本：无。
- 新增参数/闸门：
  - `MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT=20`
  - `MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT=20`
  - `MIN_HISTORY_READY_PRODUCTS=6`
  - `MIN_ORACLE6_FORWARD_READY_PRODUCTS=5`
  - `MIN_ROUTE_FORWARD_READY_RATE_PCT=60`
  - `STRONG_FEATURE_IC=0.15`
  - `WEAK_FEATURE_IC=0.10`
- 修改参数：无交易参数修改；仅修改舆情账本候选定义。
- 删除参数：无。

## 审计输入

- Stage549 forward ledger：`external_state_forward_ledger.csv`
- Stage543 事前选品诊断 summary。
- Stage550 产品机会几何、特征 IC、单品种诊断。
- 本地舆情/新闻文件盘点。

## 结果

- 决策：`opportunity_exists_but_selector_data_not_ready`
- Readiness gates：`5/9` 通过。
- 通过项：
  - annual opportunity exists：`7/7` 年 top6 PnL 为正。
  - point-in-time external ledger exists：`1` 次 forward run，`1` 个接收日期。
  - route forward coverage usable：最佳 route forward ready `75.6757%`。
  - oracle6 external state covered：`6/6` Oracle6 至少有 1 条 forward route。
  - existing ex-ante feature strong：最强 mean IC `0.1549`。
- 失败项：
  - enough forward observations：`1` run / `1` date，低于 `20/20`。
  - history selector ready：`0/37` 产品 history-ready，低于 `6`。
  - sentiment forward ledger ready：`0` 个结构化舆情/新闻候选账本。
  - prior historical selector passed：Stage543 通过行数 `0`。
- route readiness：
  - basis：forward ready `28/37`，history ready `0/37`。
  - inventory：forward ready `24/37`，history ready `0/37`。
  - member_detail：forward/history 均 `0/37`。
  - warehouse：forward/history 均 `0/37`。
- Oracle6 readiness：
  - `al.SHFE/c.DCE/v.DCE/y.DCE` 各有 `2` 条 forward-ready route。
  - `ao.SHFE/lu.INE` 各有 `1` 条 forward-ready route。
  - 全部 history-ready route 均为 `0`。

## 回测指标

- 期末权益：不适用，本阶段不做收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_chart_stage558_external_state_selector_readiness_audit_v1.png`
- 左上 readiness gates 中，红色失败集中在 forward 样本深度、history selector、舆情账本和历史 selector 通过数；这说明目前不是“没有机会”，而是“不能证明能事前选中机会”。
- 右上 route coverage 显示 basis/inventory 有 forward 覆盖，但 purple 的 history-ready 全为 `0`，不能回填 2022-2026 做 selector 回测。
- 左下 feature prior 显示 `hist_drawdown_120d` 和 `core_corr_252d` 有弱/中等先验，但 Stage543 真实选择器仍无通过项，所以不能单独承担选品。
- 右下 sample depth 显示当前 forward runs/date 只有 `1/20`，舆情候选账本 `0/1`，最短板非常明确。

## 输出文件

- readiness gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_readiness_gates_stage558_external_state_selector_readiness_audit_v1.csv`
- route readiness：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_route_readiness_stage558_external_state_selector_readiness_audit_v1.csv`
- Oracle6 readiness：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_oracle6_readiness_stage558_external_state_selector_readiness_audit_v1.csv`
- feature prior：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_feature_prior_stage558_external_state_selector_readiness_audit_v1.csv`
- sentiment inventory：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_sentiment_ledger_inventory_stage558_external_state_selector_readiness_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_decision_stage558_external_state_selector_readiness_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_report_stage558_external_state_selector_readiness_audit_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage558_external_state_selector_readiness_audit_chart_stage558_external_state_selector_readiness_audit_v1.png`

## 结论

- 低单笔风险 + 扩大品种池 + 避免高相关，是正确的组合工程方向，但不是 alpha 本身。
- Stage550 证明非核心每年都有可抓的趋势机会；Stage257 证明简单宽池抓不住；Stage258 进一步证明当前还没有足够资格把外生状态做成实盘 selector。
- 当前允许做：继续积累 basis/inventory forward ledger；补舆情/新闻结构化接收账本；未来达到 `20` 次/`20` 日接收样本后，再做预测力审计。
- 当前不允许做：用 Stage549 单次账本回填 2022-2026 历史选品；继续扫 `TopN/risk/cap/family cap/相关阈值/maxpos`；直接接入 Oracle/hindsight 产品池。

## 过拟合反思

- 运行前判断：不是过拟合。它只检查点时化数据资格、样本深度和既有诊断证据，不看未来收益、不调交易参数。
- 运行后判断：不是过拟合，且降低了后续过拟合风险。因为本阶段主动把 `history selector ready=0/37`、舆情候选账本 `0` 写成硬边界，避免把解释性外生材料误用成历史回测信号。

## 继续价值反思

- 运行前判断：有价值。Stage257 已经说明宽池结构不够，必须判断“选对品种”是否具备真实前置数据基础。
- 运行后判断：仍有价值，但价值在数据工程和 forward paper，而不是收益回测。
- 下一步 TODO：
  - 建立可定期复跑的外生状态账本更新任务，至少积累 `20` 个接收日期。
  - 舆情/新闻若接入，必须记录 `received_at/source_url/raw_hash/product_mapping`，否则不得进入回测。
  - 等 forward 样本足够后，只做一次固定预测力审计：库存/basis/会员/舆情状态能否提高未来 3/6 个月品种趋势收益排序。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为选品路线边界经验。
