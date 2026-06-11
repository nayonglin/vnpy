# Stage804 Stage777 多头更紧初始止损年度起点验证

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 16:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage777 研究版本，年度多起点 A/C 回测
- 是否重要突破：否，负结论
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 做 A/C；A 为 Stage777 候选缓存，C 为本阶段多头止损变体

## 外部调研与判断

- 参考资料：
  - Investopedia position sizing 资料强调先确定止损/退出价，再按风险阈值计算头寸。
  - Concretum trend-following position sizing 文章强调趋势系统的入场仓位与波动/风险目标直接相关。
  - 公开 trend-following 资料普遍提示初始止损、仓位 sizing 和最大回撤是同一个风险系统，不能孤立优化。
- 我的判断：
  - 用户提出的“多头止损取更高值”在工程语义上成立：它让多头初始止损更紧，减少单手理论风险。
  - 但在本策略里，手数是按风险预算和止损距离反推的；止损更紧会提高 `contracts_by_risk`，因此它可能不是防守，而是隐性加杠杆。
  - 本次不能用单笔案例证明，应以年度多起点判断是否穿越周期。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly.py`
- 修改脚本：无正式策略文件修改
- 删除脚本：无
- 新增参数：`long_tighter_initial_stop=True`
- 修改参数：仅研究子类覆盖多头 `_entry_stop_price`
  - 旧逻辑：当 `close-low < 2%` 时，多头止损回退到 `close*(1-stop_loss_pct)`；否则用当日 low。
  - 新逻辑：多头初始止损统一取 `max(signal_day_low, close*(1-stop_loss_pct))`。
  - 空头逻辑完全不变，仍继承 Stage777 原函数。
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01-01` 至 `2026-01-01`，统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 成本、滑点、真实主力 next-open 代理、broker10 保证金口径
- 样本过滤：年度起点 9 个；成熟样本排除 `2026-01` 后为 8 个
- 策略/归因口径：
  - A：`official_candidate_stage777_50w_am41_oi08_old_ai_v1` 年度起点缓存
  - C：A + 多头更紧初始止损
  - 保持不变：AM41、旧正式 AI 池、基础等效风险 `0.40`、OI 命中恢复 `0.80`、maxpos4、关闭连败缩放和 recovery sleeve

## 结果

- 代表起点 2020-01，C 期末权益：`27,577,760`
- 代表起点 2020-01，C 总收益：`5415.552%`
- 代表起点 2020-01，C 最大回撤：`-56.0975%`
- 代表起点 2020-01，C Sharpe：`1.5525`
- 代表起点 2020-01，C 总滑点：相对 A 增加 `1,452,200`
- 代表起点 2020-01，C 总交易次数：`525`
- 胜率：本阶段主表未单独输出逐笔胜率，保留非零日胜率字段；后续若需要可从 trades/closed lots 单独抽取
- 年度起点汇总：
  - 全部 9 个起点：收益胜出 `4/9`，回撤胜出 `4/9`，Sharpe 胜出 `1/9`，收益+回撤双胜 `2/9`
  - 成熟 8 个起点：收益胜出 `4/8`，回撤胜出 `4/8`，Sharpe 胜出 `1/8`，收益+回撤双胜 `2/8`
  - 成熟样本收益中位差 `+25.003pp`，但回撤中位差 `-0.6193pp`，Sharpe 中位差 `-0.0906`
  - A 的 DD50 失败 `0`，C 的 DD50 失败 `2`（2019、2020 起点）
  - 多头止损被上抬 `2406` 次；旧止损距离中位数 `2.0%`，新止损距离中位数约 `1.1272%`
- 年度起点明细：
  - `2018-01`：A `3550.253%/-49.4213%`，C `5158.699%/-46.5025%`，收益 `+1608.446pp`，回撤 `+2.9189pp`
  - `2019-01`：A `4137.990%/-49.3661%`，C `5929.246%/-53.9421%`，收益 `+1791.256pp`，回撤 `-4.5760pp`
  - `2020-01`：A `2422.962%/-49.1145%`，C `5415.552%/-56.0975%`，收益 `+2992.590pp`，回撤 `-6.9830pp`
  - `2021-01`：A `1126.727%/-48.6695%`，C `1178.622%/-42.9311%`，收益 `+51.895pp`，回撤 `+5.7384pp`
  - `2022-01`：A `121.270%/-35.3554%`，C `95.656%/-33.6344%`，收益 `-25.614pp`，回撤 `+1.7210pp`
  - `2023-01`：A `179.513%/-22.1100%`，C `68.279%/-28.6321%`，收益 `-111.234pp`，回撤 `-6.5221pp`
  - `2024-01`：A `82.388%/-23.3469%`，C `41.195%/-22.8831%`，收益 `-41.193pp`，回撤 `+0.4638pp`
  - `2025-01`：A `83.832%/-16.2147%`，C `81.943%/-17.9172%`，收益 `-1.889pp`，回撤 `-1.7025pp`
  - `2026-01`：A `-4.974%/-15.5310%`，C `-15.668%/-19.8127%`，收益 `-10.694pp`，回撤 `-4.2817pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_report_stage804_stage777_long_tighter_initial_stop_yearly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_summary_stage804_stage777_long_tighter_initial_stop_yearly_v1.csv`
- orders：无单独 orders 输出
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_curves_stage804_stage777_long_tighter_initial_stop_yearly_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_stop_adjustments_stage804_stage777_long_tighter_initial_stop_yearly_v1.csv`
- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_equity_curves_stage804_stage777_long_tighter_initial_stop_yearly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_return_delta_bar_stage804_stage777_long_tighter_initial_stop_yearly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly_dd_delta_bar_stage804_stage777_long_tighter_initial_stop_yearly_v1.png`

## 结论

- 本阶段结论：不升级、不接 Stage777 官方候选。
- 核心原因：
  - 它确实放大了早期右尾收益，尤其 2018-2020 起点。
  - 但它不是稳定降风险，2019/2020 起点新增 DD50 失败，2023/2026 起点明显变差。
  - Sharpe 胜出只有 `1/9`，说明收益放大主要来自更高风险暴露，而不是机会质量提升。
- 是否进入下一步：否，不沿这个“多头止损更紧”形态继续扫参。
- 下一步：如果继续研究初始止损，应转向“止损用于退出，但 sizing 使用单独风险距离/ATR 下限”的解耦结构，而不是简单把止损点上抬后继续用它反推手数。

## 过拟合反思

- 运行前判断：有一定过拟合风险，但可验证。
- 运行后判断：不认为这是稳健优化；如果继续围绕 `1.5%/2%/low/MA` 等细节救参，会进入过拟合。
- 原因：本次改动来自具体单笔案例，并且实际效果是提高风险暴露；多起点已经显示收益和回撤方向不一致。

## 继续价值反思

- 运行前判断：有价值，因为它检验“更紧止损是否能减少开仓风险”的第一性问题。
- 运行后判断：这个具体版本继续价值低。
- 原因：结论已经清楚，更紧止损在当前 sizing 框架下不是纯防守，而是仓位放大器；后续价值在风险距离与退出止损解耦，而不是继续微调同一个止损公式。

## 合入建议

- 是否更新本线 `LINE.md`：否，本阶段为负结论，保持 Stage777 官方候选描述不变
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`
