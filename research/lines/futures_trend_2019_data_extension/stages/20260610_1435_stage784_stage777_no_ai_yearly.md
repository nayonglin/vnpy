# Stage784 Stage777 关闭 AI 选品年度启动消融

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-10 14:35 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage777 单因子消融、年度多周期回测
- 是否重要突破：否，但属于重要负结论，明确 Stage777 对 AI 选品过滤有正依赖
- 是否触发A/B：否；只读研究，不接正式版

## 外部调研与判断

- 参考资料：
  - QuantInsti walk-forward optimization 介绍：强调滚动/多起点验证用于降低单一路径拟合风险，https://blog.quantinsti.com/walk-forward-optimization-introduction/
  - GitHub `walk-forward-validation` 相关项目集合：说明交易策略验证里常用 walk-forward / 多窗口外推，而不是单次全样本最优，https://github.com/topics/walk-forward-validation
- 我的判断：本次不是新增参数搜索，而是关闭一层现有 AI 选品过滤做 ablation。多年度起点是合理验证口径；若 AI-off 只是交易次数增加但收益/回撤全线恶化，说明 AI 池目前更像低质机会过滤器，而不是单纯限制机会数量。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage784_stage777_no_ai_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`MODEL_TAG=stage784_stage777_no_ai_yearly_v1`，`CANDIDATE_VARIANT=stage784_500k_am41_oi08_no_ai_yearly`，`YEAR_STARTS=2018-01..2026-01`
- 修改参数：
  - 基于 Stage777：`AM41`、基础等效风险 `0.40`、命中 `OI上升+价格沿方向` 恢复到 `0.80`
  - 仅关闭：`enable_ai_product_pool_filter=False`
  - 清空：`ai_product_pool_eligibility_path=""`、`ai_product_pool_strategy=""`
  - 保持关闭：`streak_risk_multipliers=1.0,1.0,1.0,1.0`、`enable_recovery_sleeve=False`
- 删除参数：无
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单

## 回测/归因参数

- 数据区间：年度起点 `2018-01-01`、`2019-01-01`、...、`2026-01-01`；统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：默认 1x，附带 2x/3x 成本压力
- 样本过滤：全部 `9` 个年度起点；成熟样本为交易日 `>=252` 的 `8` 个起点
- 策略/归因口径：Stage777 AM41/OI0.8 只关闭 AI 选品，和 Stage777 月度结果里的每年 1 月起点对比

## 结果

- 全部 `9` 个年度起点：
  - 正收益 `7/9`
  - 收益中位数 `43.0880%`
  - p10 收益 `-19.8642%`
  - 最小收益 `-40.3130%`
  - 中位最大回撤 `-56.2669%`
  - 最差最大回撤 `-62.9700%`
  - DD40 失败 `5/9`
  - DD50 失败 `5/9`
  - Sharpe 中位数 `0.4492`
  - 总交易次数 `4,544`
- 成熟 `8` 个年度起点：
  - 正收益 `7/8`
  - 收益中位数 `47.6240%`
  - p10 收益 `2.6523%`
  - 最小收益 `-40.3130%`
  - 中位最大回撤 `-56.4507%`
  - 最差最大回撤 `-62.9700%`
  - DD40 失败 `5/8`
  - DD50 失败 `5/8`
  - Sharpe 中位数 `0.6568`
  - 交易次数中位数 `567.5`
- 代表起点 `2020-01`：
  - 期末权益 `2,501,905`
  - 总收益 `400.3810%`
  - 最大回撤 `-56.2669%`
  - Sharpe `0.8644`
  - 总滑点 `462,870`
  - 总交易次数 `800`
  - 胜率 `51.0024%`
- 相对 Stage777 AI-on：
  - 全部 `9/9` 年度起点：AI-off 收益胜出 `0`，回撤胜出 `0`
  - 成熟 `8/8` 年度起点：AI-off 收益胜出 `0`，回撤胜出 `0`
  - 成熟收益差中位数 `-618.0750pp`
  - 成熟回撤差中位数 `-8.9365pp`
  - 成熟 Sharpe 差中位数 `-0.6080`
  - 成熟交易次数中位数增加 `+245.5`
- 年度细节：
  - `2018-01`：Stage777 `3550.253%/-49.421%/648笔`，AI-off `711.085%/-56.634%/937笔`
  - `2019-01`：Stage777 `4137.990%/-49.366%/602笔`，AI-off `848.035%/-56.979%/889笔`
  - `2020-01`：Stage777 `2422.962%/-49.114%/512笔`，AI-off `400.381%/-56.267%/800笔`
  - `2022-01`：Stage777 `121.270%/-35.355%/262笔`，AI-off `-40.313%/-62.970%/479笔`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_report_stage784_stage777_no_ai_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_summary_stage784_stage777_no_ai_yearly_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_comparison_detail_vs_stage777_stage784_stage777_no_ai_yearly_v1.csv`
- daily/curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_curves_stage784_stage777_no_ai_yearly_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_comparison_chart_stage784_stage777_no_ai_yearly_v1.png`
- equity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage784_stage777_no_ai_yearly_equity_curves_stage784_stage777_no_ai_yearly_v1.png`

## 结论

- 本阶段结论：关闭 AI 选品后，交易次数显著增加，但每个年度起点收益都低于 Stage777，且每个年度起点最大回撤都更差。AI 池在 Stage777 里不是简单“少开仓”，而是在过滤大量低质量机会。
- 是否进入下一步：不作为候选继续推进。
- 下一步：
  - 不做“关闭 AI 后再调风险/调 OI/调 AM”救参。
  - 若继续研究 AI，应做只读归因：被 AI 拦截的候选，按品种、方向、信号 case、OI 命中、后验 R 倍数分布拆开，判断 AI 是否过滤了共同劣质结构。
  - 若要降低 AI 过拟合风险，应做固定规则的 walk-forward 或按年份留出验证，而不是在 Stage784 负结果上反向调参。

## 过拟合反思

- 运行前判断：不是过拟合。它是单一现有模块的关闭消融，不新增自由参数。
- 运行后判断：不是过拟合，但反向救参会过拟合。
- 原因：结果跨 `2018-2026` 年度起点同向，AI-off 没有一个年度起点收益或回撤胜出，说明不是单一年份噪声。但如果据此继续扫 AI topN、风险倍率或品种黑名单，就是用历史结果拟合。

## 继续价值反思

- 运行前判断：有价值。能回答 Stage777 是否依赖 AI 池过滤。
- 运行后判断：作为候选无继续价值；作为归因有继续价值。
- 原因：候选层面已经全线弱于 Stage777；但它给出清晰方向：AI 的价值可能来自拦截低质量交易，应转向被拦截样本的因子归因，而不是关掉 AI。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage784 重要负结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加 AI 选品消融的结论摘要。
