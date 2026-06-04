# Stage253 年度动态选品产品族/相关性约束审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 21:53 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 结构反证；固定 Stage252 年度动态 top6 sleeve，只增加产品族和低核心相关约束复核。
- 是否重要突破：否。重要反证：产品族更分散并没有改善路径，反而把 Stage252 的卫星小收益切没。
- 是否触发A/B：是。A=`stage526_r080_pc25_maxpos4`；C0=Stage252 `dynamic_prevtop6_r050_pc15_maxpos3`；C1=`dynamic_prevtop6_familycap1_lowcorr030_r050_pc15_maxpos3`。

## 外部调研与判断

- 参考资料：
  - AQR `A Century of Evidence on Trend-Following Investing` / Trend Following 页面：趋势跟随长期有效性来自跨市场、跨资产分散，而不是单一市场拟合。
  - Rob Carver / `pysystemtrade` 文档：组合构建中明确使用 instrument correlations 与 diversification multiplier，说明相关性治理是趋势组合工程中的正统问题。
- 我的判断：
  - “扩大品种池 + 降低单笔风险”方向本身仍有第一性原理支持；但本地 Stage252 已经显示 edge 很窄，因此本阶段不能继续扫 TopN/risk/cap，只允许检查这个 edge 是否能在更分散的产品族/相关性壳下存活。
  - 若 family/corr 约束后收益消失，说明 Stage252 的小收益更接近“年度动量集中抓对少数品种”，不是“越分散越稳”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve.py`
- 修改脚本：无正式策略脚本修改；只修正该审计脚本与生成报告中的产品集中度字段口径。
- 删除脚本：无。
- 新增参数：
  - `prev_year_top6_familycap1_lowcorr030`：上一年单品种真实账本按 PnL 排序；优先选择 `abs(core_corr)<=0.30` 且同产品族最多 `1` 个的 `6` 个非核心商品。
  - 固定继承 Stage252：`risk_multiplier=0.50`、`product_cap_ratio=0.15`、`max_concurrent_positions=3`、`max_single_trade_capital_usage_ratio=0.35`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-27`，交易从 `2021-01-01` 起动态年度白名单生效。
- 账户规模：Stage526 核心沿用 `50万` 真实可成交候选；卫星 sleeve `11.5万`，合成账户仍按 Stage526 + sleeve PnL 口径评估。
- 成本口径：正常成本 `1x`，并输出 `2x/3x` 成本压力。
- 样本过滤：非核心商品全集；不接入 Oracle/hindsight 产品池。
- 策略/归因口径：Stage526 核心不替换；非核心商品全集进入引擎，每年 `YYYY-01-01` 只允许上一年已知白名单产品新开仓，已有持仓自然退出或换月。

## 结果

### A：Stage526

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- Ulcer：`14.4691`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`

### C0：Stage252 top6 参考

- 期末权益：`23,422,160`
- 总收益：`3708.4813%`
- 最大回撤：`-36.0822%`
- Sharpe：`1.6432`
- Ulcer：`14.3839`
- broker10 最大保证金/权益：`98.7159%`
- 总滑点：`1,346,350`
- 总交易次数：`1,105`
- 胜率：`53.7130%`
- 卫星PnL：`52,655`
- 2x/3x 成本最大回撤：`-38.8577%/-41.8410%`
- 63/126日 p05 收益：`-17.9491%/-10.6848%`

### C1：Stage253 family/corr 约束

- 期末权益：`23,368,605`
- 总收益：`3699.7732%`
- 最大回撤：`-36.2325%`
- Sharpe：`1.6387`
- Ulcer：`14.4557`
- broker10 最大保证金/权益：`99.5577%`
- 总滑点：`1,345,010`
- 总交易次数：`1,025`
- 胜率：`53.7791%`
- 卫星 standalone：`114,100/-0.7826%/-14.4708%/Sharpe0.0171`
- 卫星PnL：`-900`
- 2x/3x 成本最大回撤：`-39.0236%/-42.0245%`
- 63/126日 p05 收益：`-18.1804%/-10.9599%`
- 年度卫星PnL：`2021 +5,525`、`2022 -180`、`2023 -3,945`、`2024 +2,950`、`2025 -5,250`、`2026 0`。
- 主要产品贡献：`v.DCE +10,320`、`ao.SHFE +9,820`、`i.DCE -11,050`、`SR.CZCE -3,690`、`CY.CZCE -3,625`、`c.DCE -3,110`。

## 视觉复盘

- 账户权益图：黑线、紫线、绿线几乎重合，说明这个方向对主账户影响很小；但紫线长期略高，绿色约束版基本回到 Stage526。
- 回撤图：绿色版正常成本略浅于 Stage526，但没有超过 Stage252 top6；最痛水下仍集中在 2021-2022，结构性问题未变。
- 卫星PnL图：紫线在 2021-2022 快速拉开并保持正贡献；绿色版在 2023 后回吐，2025 再次下行，最终接近零以下。
- 持有体验图：绿色版 63/126 日 p05 均低于 Stage252 top6，几乎回到 Stage526；“更分散”没有改善任意启动体验。
- 年度白名单图：绿色版每年产品族数从 Stage252 的 `3-6` 提到稳定 `6`，证明约束确实生效；但路径收益没有随分散改善。
- 成本压力图：绿色版 3x 成本仍为 `-42.0245%`，与 Stage526/Stage252 一样失败。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_report_stage553_family_corr_dynamic_annual_selector_sleeve_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_chart_stage553_family_corr_dynamic_annual_selector_sleeve_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_summary_stage553_family_corr_dynamic_annual_selector_sleeve_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_cost_stress_stage553_family_corr_dynamic_annual_selector_sleeve_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_rolling_holding_stage553_family_corr_dynamic_annual_selector_sleeve_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_combined_daily_stage553_family_corr_dynamic_annual_selector_sleeve_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_positions_stage553_family_corr_dynamic_annual_selector_sleeve_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage553_family_corr_dynamic_annual_selector_sleeve_decision_stage553_family_corr_dynamic_annual_selector_sleeve_v1.json`

## 结论

- 本阶段结论：`family_corr_dynamic_selector_not_promotion`。
- 是否进入下一步：Stage253 不进入下一步；Stage252 top6 仍只保留为 paper/验证候选。
- 下一步：
  - 不再在 Stage252 top6 上叠加 family cap、低核心相关阈值或邻近相关阈值救援。
  - 若继续年度选品，只做 Stage252 的剔除最大贡献产品/年份、白名单生效时点和部署材料性复核。
  - 若要真正解决“选对品种”，需要回到 forward 外生状态账本，等待库存/basis/会员/舆情真实接收时间戳样本，而不是继续用当前价格/账本特征做小条件。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：Stage253 本身不是过拟合，但结果反证继续微调 family/corr 小条件的价值。
- 原因：本阶段只使用上一年已知单品种账本、静态产品族和历史核心相关，不看未来收益；但继续把 `0.30` 调成 `0.25/0.35`、或把 family cap 从 `1` 调成 `2`，就会变成历史收益补丁。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：总目标仍有价值；当前 family/corr 约束子方向继续价值低。
- 原因：图表和指标都显示“更分散”没有提升收益或持有体验，说明 Stage252 的 edge 来自少数年度强品种的集中捕捉；继续做相关性小数只会牺牲材料性。下一步应做 Stage252 的稳健性反证或转回 forward 外生状态。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage253 反证。
- 是否更新 `research/registry.md`：是，当前最新关键阶段更新为 Stage253。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段有真实回测并改变后续研究边界。
