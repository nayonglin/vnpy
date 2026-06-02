# Stage213 Stage208部署约束审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 18:38 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读部署约束审计；直接读取 Stage208/209 固定候选日权益和保证金账本代理，不新增交易规则、不调参数。
- 是否重要突破：是。Stage213 将 Stage208 的“主候选 risk070”降级为高收益 paper，把 `risk060 + true xsmom` 提升为下一步精确券商保证金回放对象。
- 是否触发A/B：否。本阶段没有新增策略版本；只是对固定候选做部署资金、保证金和成本压力审计。

## 外部调研与判断

- 参考资料：
  - 上期所结算说明：成交后按持仓合约价值比例收取交易保证金，品种标准和风险控制规则会变化：https://www.shfe.com.cn/specialtopic/investor/settlement/
  - 中金所公开披露材料：保证金划扣、结算准备金和强平机制属于交易所/结算会员日常风险控制的一部分：https://www.cffex.com.cn/u/cms/www/202105/2817030498cn.pdf
  - 公开回测真实性资料普遍强调成交、滑点、保证金和风险管理漂移会侵蚀纸面收益；本阶段因此不只看权益曲线，而是把 `1x/2x/3x` 成本和 broker10 保证金冗余合并审计。
- 我的判断：
  - 实盘候选不能只看 `61.5万` 口径下的账面收益；如果需要额外现金才能保证不穿保证金或不破回撤，必须用部署资金收益率重算收益保留。
  - `risk070` 的收益略高，但保证金尖峰和成本压力不是小问题；`risk060` 牺牲少量收益，换来更厚的部署安全边界，更符合“真实可成交、偏差可控”的第一性目标。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage512_stage208_deployment_constraint_audit.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；新增审计维度 `cost_multiplier=1/2/3`、`broker10 margin cap=100/95/90/80`、`DD40` 所需现金、保证金所需现金、部署资金收益率。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：基础账户 `615,000`；另计算满足保证金/回撤约束所需的额外现金。
- 成本口径：Stage208 固定日权益为 `1x`；用日度 `slippage` 重构 `2x/3x` 成本压力。
- 样本过滤：无日期过滤、无品种过滤、无坏窗口剔除。
- 策略/归因口径：
  - `risk060 + true xsmom`：`stage079_next_real_risk060_clean_plus_stage103_xsmom_true`
  - `risk070 + true xsmom`：`stage079_next_real_risk070_clean_plus_stage103_xsmom_true`
  - broker10 保证金代理：`Stage402 start_2020 c3_margin * risk_multiplier + Stage208 xsmom_true_margin`，再乘 `1.10`；该项仍是代理，不替代最终券商保证金逐日回放。

## 结果

- `risk060 + true xsmom` 期末权益：`20,682,740`
- `risk060 + true xsmom` 总收益：`3263.0472%`
- `risk060 + true xsmom` 最大回撤：`-36.2870%`
- `risk060 + true xsmom` Sharpe：`1.2291`
- `risk060 + true xsmom` 总滑点：`1,231,020`
- `risk060 + true xsmom` 总交易次数：`1,220`
- `risk060 + true xsmom` 胜率：非零日胜率 `52.8614%`
- `risk070 + true xsmom` 期末权益：`21,210,535`
- `risk070 + true xsmom` 总收益：`3348.8675%`
- `risk070 + true xsmom` 最大回撤：`-38.5861%`
- `risk070 + true xsmom` Sharpe：`1.1674`
- `risk070 + true xsmom` 总滑点：`1,228,400`
- `risk070 + true xsmom` 总交易次数：`1,215`
- `risk070 + true xsmom` 胜率：非零日胜率 `52.4887%`
- 其他关键指标：
  - `risk060` 1x 无额外现金 broker10 最大保证金/权益 `96.4348%`，穿 `100%` 天数 `0`，2x 成本最大回撤 `-38.9342%`。
  - `risk070` 1x 无额外现金 broker10 最大保证金/权益 `122.7492%`，穿 `100%` 天数 `8`，2x 成本最大回撤 `-41.4962%`。
  - 若要求 `broker10 <= 90%` 且 DD40，1x 成本下 `risk060` 需额外现金 `473,826`，部署资金收益率 `1843.0614%`，相对 Stage079 部署收益保留 `37.2542%`。
  - 同样要求下 `risk070` 需额外现金 `2,201,732`，部署资金收益率 `731.1855%`，相对 Stage079 部署收益保留 `14.7796%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_report_stage512_stage208_deployment_constraint_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_deployment_matrix_stage512_stage208_deployment_constraint_audit_v1.csv`
- orders：沿用 Stage208/209 order ledger；本阶段无新增订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_daily_detail_stage512_stage208_deployment_constraint_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_event_days_stage512_stage208_deployment_constraint_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_decision_stage512_stage208_deployment_constraint_audit_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage512_stage208_deployment_constraint_audit_chart_stage512_stage208_deployment_constraint_audit_v1.png`

## 图表视觉复盘

- NAV 图上 `risk070` 末端略高于 `risk060`，但两者差距不大；相对收益优势不足以补偿保证金风险。
- Underwater 图上 `risk070` 在 2021-2022 更贴近 `-40%`，成本上浮后容易越线；`risk060` 的水下更浅，但仍不是 30% 回撤体验。
- 保证金图上 `risk070` 多次尖峰穿越 `100%`，最高到 `122.7492%`；`risk060` 最高 `96.4348%`，主要问题是是否要给 `90%` 舒适线留现金。
- 现金缓冲柱状图显示 `broker10 <= 90%` 时 `risk070` 需要的额外现金远高于 `risk060`，部署资金收益率被明显摊薄。

## 结论

- 本阶段结论：`prefer_risk060_true_xsmom_for_deployment_audit`。
- 是否进入下一步：是。
- 下一步：
  1. 固定 `risk060 + true xsmom`，做更精确的逐日持仓保证金回放，尽量替代当前 `c3_margin * risk_multiplier` 代理。
  2. `risk070 + true xsmom` 暂不晋级实盘候选，只保留高收益 paper，除非用户明确接受大额额外现金和 2x 成本破 DD40。
  3. 继续禁止扫 `risk=0.61/0.62`、xsmom 窗口/权重、ATR 倍数、K线形态阈值或坏品种过滤。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只读固定候选账本，没有根据结果改变交易规则，也没有使用坏窗口调参数。它把隐藏资金约束显性化，反而降低纸面过拟合风险。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但继续方向进一步收窄。
- 原因：Stage208 已经接近“真实可成交 + DD40 + 收益保留”的目标边界；现在最有价值的是精确实盘约束验证，而不是继续堆策略补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage208 候选晋级口径的重要边界。
