# Stage406 正式版 Stage372 原 AI 池 + 鸡蛋 + maxpos5 纠正回测

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-07 16:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 Stage372/20万扩池纠正实验
- 是否重要突破：否，但修正 Stage405 实验定义
- 是否触发A/B：是，属于可能接入正式版的品种池/并发候选

## 外部调研与判断

- 参考资料：
  - Aspect Capital `Diversification in Trend Following`：趋势跟踪扩市场有价值，但市场组合与流动性/相关性会影响组合效果。
  - Man Group `A Trend Following Deep Dive: The Optimal Market Mix for a Trend Follower`：趋势跟踪市场组合会改变机会分布和组合效率。
  - 商品期货动态组合研究与 CTA 资料：扩市场要关注组合风险预算与原有收益源是否被稀释。
- 我的判断：用户澄清后，正确实验应是“保留原正式 AI 池，再额外加入鸡蛋”，不是 full-market AI 重排。这个修正能检验鸡蛋作为卫星市场是否有边际，而不污染原 AI 选择器。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5.py`
- 修改脚本：无正式策略修改。
- 删除脚本：无。
- 新增参数：
  - `jd.DCE`
  - `AI_STRATEGY="stage693_official_stage372_original_ai_plus_jd_entry_filter"`
  - `max_concurrent_positions=5`
- 修改参数：
  - B 分支只把 `maxpos4` 改为 `maxpos5`。
  - C 分支逐月完整保留正式 AI eligibility 的原产品，再额外加入 `jd.DCE`，并使用 `maxpos5`。
- 删除参数：无。C 不使用 full-market AI 重排，不删除正式 AI 池中原有产品。
- 正式配置：未修改。
- CTP/下单：未连接 CTP，未调用 order API。

## 回测/归因参数

- 数据区间：沿用 Stage653/Stage372 全周期回测口径。
- 账户规模：`200,000`
- 成本口径：正常成本、`2x`、`3x` 滑点压力。
- 样本过滤：正式 AI eligibility `2019-12-31` 至 `2026-05-29`，每个 eval_date 追加鸡蛋。
- 策略/归因口径：
  - A：当前正式版 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - B：只放宽并发 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos5`
  - C：原 AI 池 + 鸡蛋 + maxpos5 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_maxpos5`

## 结果

- A 正式版：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次，`299` 手
- B 仅 maxpos5：
  - 期末权益 `7,511,205`
  - 总收益 `3655.6025%`
  - 最大回撤 `-38.7987%`
  - Sharpe `1.5831`
  - 总滑点 `434,330`
  - 总交易次数 `661`
  - 胜率 `52.2748%`
  - broker10 峰值 `77.3076%`
  - 强制减仓 `15` 次，`474` 手
- C 原 AI 池 + 鸡蛋 + maxpos5：
  - 期末权益 `7,674,990`
  - 总收益 `3737.4950%`
  - 最大回撤 `-32.7510%`
  - Sharpe `1.6160`
  - 总滑点 `453,450`
  - 总交易次数 `744`
  - 胜率 `53.1753%`
  - broker10 峰值 `76.9406%`
  - 强制减仓 `15` 次，`382` 手
  - 收益保留 `87.6494%`
- C 相对 B：
  - 期末权益 `+163,785`
  - 总收益 `+81.8925pp`
  - 最大回撤改善 `+6.0477pp`
  - Sharpe `+0.0329`
  - 交易 `+83`
  - 2x/3x 成本 DD 改善 `+5.8113pp/+5.5369pp`
- C 相对 A：
  - 期末权益 `-1,053,295`
  - 总收益 `-526.6475pp`
  - 最大回撤改善 `+5.9203pp`
  - Sharpe `-0.0118`
  - 交易 `+111`
  - 2x/3x 成本 DD 改善 `+5.6872pp/+5.4156pp`
- 成本压力：
  - C `2x/3x` 成本 DD 为 `-34.9683%/-37.3493%`，优于 A 的 `-40.6555%/-42.7649%`。
- AI 审计：
  - 鸡蛋被额外加入 `52/52` 个 eval_date，选择率 `100%`。
- 产品归因：
  - 鸡蛋自身净 PnL `+518,620`
  - C 相对 A 主要改善：`jd +518,620`、`hc +222,610`、`ma +83,760`、`sa +75,140`、`sp +62,940`
  - C 相对 A 主要恶化：`jm -627,480`、`oi -541,360`、`fu -188,760`、`fg -120,120`、`si -110,175`、`au -104,560`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5_report_stage693_official_stage372_original_ai_plus_jd_maxpos5_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5_summary_stage693_official_stage372_original_ai_plus_jd_maxpos5_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5_daily_stage693_official_stage372_original_ai_plus_jd_maxpos5_v1.csv`
- product_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5_product_delta_stage693_official_stage372_original_ai_plus_jd_maxpos5_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5_chart_stage693_official_stage372_original_ai_plus_jd_maxpos5_v1.png`

## 结论

- 本阶段结论：`official_stage372_original_ai_plus_jd_maxpos5_rejected`
- 是否进入下一步：不直接进入正式版；可保留为风险更低但收益下降的观察形态。
- 核心判断：
  - 用户澄清的假设成立一半：原 AI 池不变时，鸡蛋确实有正贡献，且明显优于“只放宽 maxpos5”。
  - 但它仍低于当前正式版 A，收益少 `526.6475pp`、期末权益少 `1,053,295`，原因是共享资金/持仓路径下仍挤占了 `jm/oi/fu` 等核心右尾。
  - C 的风险路径更好，最大回撤从 A 的 `-38.6713%` 改善到 `-32.7510%`，2x成本 DD 从 `-40.6555%` 改善到 `-34.9683%`。
- 下一步：
  - 不把 C 替换正式版。
  - 若用户愿意接受“收益下降换风险路径改善”，可做多起点/YTD/弱窗口审计。
  - 若目标仍是提高收益，则不要在主账户共享风险池硬加；转为鸡蛋独立小 sleeve 或状态化 maxpos5。

## 过拟合反思

- 运行前判断：不是过拟合；这是修正实验定义，保留原 AI 池，只加一个卫星品种和一个并发槽。
- 运行后判断：不是过拟合；但若继续围绕鸡蛋月份、方向、年份或 topN 做补丁，会转为过拟合。
- 原因：结果显示真实结构权衡，鸡蛋正贡献但共享路径挤占核心右尾，不是单一阈值问题。

## 继续价值反思

- 运行前判断：有价值；直接回答用户真实假设。
- 运行后判断：有继续观察价值，但不是正式替换候选。
- 原因：C 相对 B 改善明显，相对 A 风险改善明显，但收益仍低于 A。后续价值在“防守型分支/独立 sleeve”，不在继续手工扩池救收益。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage406 纠正结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，属于正式候选纠正反证。
