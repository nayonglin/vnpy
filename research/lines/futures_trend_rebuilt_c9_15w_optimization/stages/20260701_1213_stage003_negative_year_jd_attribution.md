# Stage003 重建版 C9/15w 负年度与鸡蛋接入归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因，不改策略逻辑
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- Time-series momentum 的长期研究支持跨市场趋势跟随，但核心收益来自分散化和少数右尾，不能为了年度平滑随意砍右尾。
- Deflated Sharpe、PBO、purged/CPCV 相关框架提醒：多参数、多候选、多窗口 winner-picking 会严重放大虚假发现概率。
- Kelly/fractional Kelly 与期货 position sizing 资料的共同判断：加大风险投入前，必须先证明入场时可见的边际胜率或损益分布优势，否则只是放大估计误差。
- 本阶段采纳：先用冻结 Stage167 输出做只读归因；否决：直接按 `2023/2026`、单品种或某个阈值扫参。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_rebuilt_c9_stage003_negative_year_jd_attribution.py`
- 修改策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增负年度归因口径。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据来源：冻结 Stage167 当前重建 C9/15w 输出。
- 曲线：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- 候选：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_entry_candidates_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- 年度收益：Stage002 年度拆解结果。
- 账户规模：`150,000`。
- 终点：`2026-06-30`。
- 策略逻辑：未重跑、未修改；只读曲线与候选上下文。

## 结果

- Stage167 中位总收益：`203.6425%`。
- 80% 收益保留线：`162.9140%`。
- 当前负年度行：`29`。
- 负年度分布：
  - `2018`：`1` 行，最差 `-3.9197%`。
  - `2022`：`2` 行，最差 `-16.9640%`。
  - `2023`：`10` 行，最差 `-15.3644%`，中位 `-5.4131%`。
  - `2026`：截至 `2026-06-30` 的未完成年度/半年度路径，`16` 行，最差 `-12.3566%`，中位 `-9.1716%`。
- 最差年度窗口：
  - `2021-07` 起点 `2022` 年，年度收益 `-16.9640%`，年内最大回撤 `-37.8018%`，peak-to-end 回吐 `-33.0539%`，broker10 峰值 `63.0504%`，开仓 `43` 次，AI block `42` 次。
  - `2021-01` 起点 `2023` 年，年度收益 `-15.3644%`，年内最大回撤 `-31.7259%`，broker10 峰值 `80.7461%`，开仓 `35` 次，AI block `55` 次。
  - `2022-01` 起点 `2022` 年，年度收益 `-15.2867%`，年内最大回撤 `-35.7859%`，broker10 峰值 `64.5100%`，开仓 `37` 次，AI block `34` 次。
- 正负年度上下文对比：
  - 负年度中位收益 `-8.3430%`，正年度中位收益 `61.7888%`。
  - 负年度中位交易次数 `32`，正年度 `85`。
  - 负年度中位开仓次数 `16`，正年度 `40.5`。
  - 负年度中位开仓率 `24.2424%`，正年度 `27.8146%`。
  - 负年度中位 AI block 率 `31.8182%`，正年度 `28.2357%`。
  - 负年度中位 broker10 峰值 `40.6203%`，正年度 `72.0270%`。
  - 负年度中位打开品种数 `10`，正年度 `15`。
  - `candidate_drawdown_*` 沿用源表原值，源表接近 `0.50` 时代表约 `50%` 组合回撤状态，不是 `0.50` 个百分点。
- Skip reason 对比：
  - 负年度：`short_signal_rejected 36.8382%`、`ai_product_pool_blocked 33.9504%`、`opened 25.9904%`、`sizing_zero_volume 3.0359%`、`concurrent_limit 0.1851%`。
  - 正年度：`short_signal_rejected 37.9007%`、`opened 33.2057%`、`ai_product_pool_blocked 23.3759%`、`concurrent_limit 3.0071%`、`sizing_zero_volume 2.5106%`。
- 鸡蛋 `jd.DCE`：
  - full-market universe：`PASS`，数据和元数据可用。
  - 当前 Stage182 AI 池：`FAIL`。
  - 最新 Stage182 pool：`FAIL`。
  - Stage167 候选：`FAIL`。

## 归因判断

- 当前年度负收益不是因为 AI 没启用：Stage167 的 post-AI 审计已经 `FAIL=0`，负年度窗口也存在 AI allowed/blocked 元数据。
- 不能简单理解为“仓位不够所以亏”：正年度的 broker10 峰值和开仓广度反而更高。负年度更像是有效趋势机会少、AI 拦截占比更高、开仓数和 opened products 更低，个别失败窗口仍有较高 broker10 压力但没有换来趋势收益。
- 鸡蛋 `jd.DCE` 数据可用但没有进入当前 AI 池和 Stage167 候选。结合历史 Stage405/406/407，本线不得直接把鸡蛋塞进共享 AI rerank/topN，因为旧记录显示共享池挤占核心右尾后收益保留会显著恶化。
- “超高质量信号加风险”下一步应先做入场时可见的质量标签，例如 AI rank/score、趋势广度、OI/价格一致、候选拥挤度、组合回撤状态、保证金压力和历史同类信号表现；不能用未来 MFE/MAE 或最终盈亏。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_report_stage003_rebuilt_c9_negative_year_jd_attribution_v1.md`
- negative_year_attribution：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_negative_year_attribution_stage003_rebuilt_c9_negative_year_jd_attribution_v1.csv`
- annual_context：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_annual_context_stage003_rebuilt_c9_negative_year_jd_attribution_v1.csv`
- negative_vs_positive：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_negative_vs_positive_context_stage003_rebuilt_c9_negative_year_jd_attribution_v1.csv`
- skip_reason_context：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_skip_reason_context_stage003_rebuilt_c9_negative_year_jd_attribution_v1.csv`
- product_context：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_product_context_stage003_rebuilt_c9_negative_year_jd_attribution_v1.csv`
- negative_bar_chart：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_negative_year_bar_stage003_rebuilt_c9_negative_year_jd_attribution_v1.png`
- context_chart：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_annual_context_scatter_stage003_rebuilt_c9_negative_year_jd_attribution_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage003_negative_year_jd_attribution_decision_stage003_rebuilt_c9_negative_year_jd_attribution_v1.json`

## 结论

- 本阶段结论：当前重建版还没有达到新目标；失败集中在年度路径稳定性，而不是 AI 审计缺失。
- 鸡蛋应走非挤占接入设计：独立 sleeve / 独立风险槽 / 账户级 selector，不能先进入共享 AI rerank 并挤占核心池。
- 高质量信号加风险有继续价值，但必须先做冻结质量标签代理，再进入真实组合引擎 A/C 回测。

## 过拟合反思

- 运行前判断：否。只读归因冻结输出，不产生候选策略。
- 运行后判断：否。没有根据某个失败年份改参数，也没有做 winner-picking。
- 风险提醒：下一步如果直接按 `2023/2026` 或鸡蛋单品种表现调规则，就会进入过拟合高风险区。

## 继续价值反思

- 运行前判断：是。目标要求比当前基准更强，必须先定位失败形态。
- 运行后判断：是。归因已经把下一步从“盲目加鸡蛋/加风险”收敛到“非挤占鸡蛋 sleeve + 入场可见质量标签”。
- 后续规划：Stage004 先整理历史反证清单；Stage005 再写一个冻结的质量标签/鸡蛋非挤占代理，不直接上真实策略。

## 合入建议

- 是否更新本线 `LINE.md`：是，补 Stage003 当前状态。
- 是否更新 `research/registry.md`：暂不需要；Stage003 不是正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段未产生正式候选或重要突破。
