# Stage254 Stage252 年度top6剔除脆弱性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 22:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读候选脆弱性审计；不新增交易规则，不调品种数、风险比例、产品族或相关性阈值。
- 是否重要突破：否。重要判断是 Stage252 年度top6 小 edge 不是单一年份/单一产品独撑，但材料性仍不足。
- 是否触发A/B：是。A=`stage526_r080_pc25_maxpos4`；C=`dynamic_prevtop6_r050_pc15_maxpos3`；B 不单独评估，因为本阶段审计的是 Stage252 已有 C 候选。

## 外部调研与判断

- 参考资料：
  - AQR trend following / managed futures 资料：跨市场趋势跟随的核心优势来自多市场分散和低相关风险源，但分散不能消除亏损风险。
  - Rob Carver / `pysystemtrade`：系统化期货组合中需要显式处理 instrument correlations、risk overlays、weight estimation 和 diversification multiplier。
  - 商品期货 trend-following / risk parity 文献：风险平价和相关性治理有理论价值，但趋势本身的信号质量与可交易承载通常比复杂权重更重要。
- 我的判断：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓到部分品种趋势，同时避免高相关”方向在第一性原理上成立。
  - 但本地 Stage253 已反证“机械产品族/相关性约束越分散越好”；因此 Stage254 不继续扫约束，而是先检验 Stage252 的收益是否依赖少数年份/品种。
  - 如果剔除最强年份或最强产品后 C 直接回到或低于 Stage526，就说明当前年度选品更像 hindsight concentration；如果仍略优，则可继续做部署材料性复核，但不能直接晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage554_stage252_leaveout_fragility_audit.py`
- 修改脚本：无正式策略脚本修改；仅在新增审计脚本中修正 pandas Series 显式存在性判断，并设置 matplotlib cache 到 `/private/tmp/matplotlib`。
- 删除脚本：无。
- 新增参数：
  - 剔除最强正贡献年份 Top3：逐年 remove。
  - 剔除最差负贡献年份：remove_worst_year。
  - 剔除最强正贡献产品 Top5：逐产品 remove。
  - 剔除最差负贡献产品：remove_worst_product。
  - 剔除 Top2 正贡献产品、Top2 正贡献年份。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage552/Stage252 已生成的 `2020-2026` 连续动态年度选品真实成交日表与逐合约 positions。
- 账户规模：沿用 Stage526/Stage252 账户口径。
- 成本口径：正常 1x 成本为主，同时输出 2x/3x 成本压力。
- 样本过滤：只读取 Stage252 `dynamic_prevtop6_r050_pc15_maxpos3` 和 Stage526 control。
- 策略/归因口径：
  - 从 Stage252 真实逐合约 positions 聚合到产品/年份维度。
  - leaveout 反事实只从已成交卫星 PnL 中剔除指定产品/年份贡献，不重新选择新产品，不改变核心仓、风控、下单逻辑。
  - 剔除负贡献产品/年份只作为归因，不允许变成黑名单。

## 结果

- Stage526：期末权益 `23,369,505`，总收益 `3699.9195%`，最大回撤 `-36.2670%`，Sharpe `1.6385`，Ulcer `14.4691`，总滑点 `1,342,190`，总交易次数 `905`，非零日胜率 `53.6330%`。
- Stage252 top6：期末权益 `23,422,160`，总收益 `3708.4813%`，相对 Stage526 `100.2314%`，最大回撤 `-36.0822%`，Sharpe `1.6432`，Ulcer `14.3839`，broker10 最大 `98.7159%`，穿100天数 `0`，总滑点 `1,346,350`，总交易次数 `1,105`，非零日胜率 `53.7130%`，卫星累计PnL `52,655`。
- 剔除最强年份 `2022`：期末权益 `23,400,920`，总收益 `3705.0276%`，相对 Stage526 `100.1381%`，最大回撤 `-36.1252%`，Sharpe `1.6413`，卫星累计PnL `31,415`。
- 剔除最强产品 `al.SHFE`：期末权益 `23,402,860`，总收益 `3705.3431%`，相对 Stage526 `100.1466%`，最大回撤 `-36.2652%`，Sharpe `1.6403`，卫星累计PnL `33,355`。
- 剔除 Top2 产品 `al.SHFE+y.DCE`：期末权益 `23,383,600`，总收益 `3702.2114%`，相对 Stage526 `100.0619%`，最大回撤 `-36.4200%`，Sharpe `1.6382`，卫星累计PnL `14,095`。
- 剔除 Top2 年份 `2021+2022`：期末权益 `23,380,620`，总收益 `3701.7268%`，相对 Stage526 `100.0488%`，最大回撤 `-36.2670%`，Sharpe `1.6388`，卫星累计PnL `11,115`。
- 年度卫星PnL：`2021 +20,300`、`2022 +21,240`、`2023 -4,235`、`2024 +20,010`、`2025 -4,660`、`2026 0`。
- 产品卫星PnL：`al.SHFE +19,300`、`y.DCE +19,260`、`v.DCE +13,320`、`ao.SHFE +10,120`、`bu.SHFE +6,160`、`nr.INE -4,950`。
- 任意启动持有体验：
  - Stage526 63/126日 p05：`-18.2169% / -10.9700%`
  - Stage252 top6 63/126日 p05：`-17.9491% / -10.6848%`
  - 改善：`+0.2678pp / +0.2852pp`
- 成本压力：
  - Stage526 2x/3x 最大回撤：`-39.0565% / -42.0555%`
  - Stage252 top6 2x/3x 最大回撤：`-38.8577% / -41.8410%`
  - 3x 成本仍不通过 DD40。
- 图表视觉复盘：
  - 账户权益主曲线几乎重合，Stage252 改善肉眼不可见，说明材料性很弱。
  - 卫星累计PnL并非由单一 `al.SHFE` 或 `2022` 完全撑起，剔除后仍保持小幅正贡献。
  - 剔除 Top2 产品或 Top2 年份后仍略高于 Stage526，但优势只剩 `0.0619%/0.0488%`，已经接近噪声级别。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage554_stage252_leaveout_fragility_audit_report_stage554_stage252_leaveout_fragility_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage554_stage252_leaveout_fragility_audit_summary_stage554_stage252_leaveout_fragility_audit_v1.csv`
- orders：不适用，本阶段不重新生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage554_stage252_leaveout_fragility_audit_leaveout_daily_stage554_stage252_leaveout_fragility_audit_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage554_stage252_leaveout_fragility_audit_decision_stage554_stage252_leaveout_fragility_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage554_stage252_leaveout_fragility_audit_chart_stage554_stage252_leaveout_fragility_audit_v1.png`

## 结论

- 本阶段结论：决策 `stage252_top6_survives_leaveout_next_validation`。Stage252 年度top6 小 edge 通过单一最强年份/产品剔除审计，不是“一剔就死”的 hindsight 候选。
- 是否进入下一步：可以进入下一步验证，但仍不能晋级正式候选。
- 下一步：
  - 做 Stage255 白名单生效时点和连续持仓语义复核，确认年度切换没有无意泄漏或不真实换仓。
  - 做部署材料性复核：如果只能改善 `0.23%` 总收益、`0.18pp` 回撤、`0.27pp/0.29pp` 3/6个月左尾，还要增加 `200` 笔交易和更多执行复杂度，是否值得 paper。
  - 不继续扫 `TopN/risk/product_cap/maxpos/family cap/相关阈值`。

## 过拟合反思

- 运行前判断：不是过拟合。原因是只审计固定 Stage252 候选，不修改选品规则。
- 运行后判断：本阶段不是过拟合；但如果下一步为了放大这 `0.23%` 总收益优势去调 TopN、风险比例、相关阈值或品种白名单，就会转为过拟合。
- 原因：剔除审计主动测试候选是否脆弱，而不是根据结果修补候选；负贡献产品剔除没有被当作黑名单。

## 继续价值反思

- 运行前判断：有价值。因为 Stage253 反证机械分散后，需要判断 Stage252 是否仍有真实结构残留。
- 运行后判断：继续价值有限但存在。它说明“减少单笔风险 + 年度选对品种”不是完全无效，但当前 edge 太小，只能做最后一轮部署材料性和语义真实性复核。
- 原因：Stage252 对全周期、回撤、Ulcer、3/6个月左尾和成本压力均有小幅改善；但图表上主曲线几乎重合，材料性不足，不值得继续大规模扩参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage254 结论和下一步边界。
- 是否更新 `research/registry.md`：是，本阶段改变最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：是，Stage252 是否脆弱会影响后续选品方向，应追加重要合入摘要。
