# Stage015 Pilot Confirmation 与 jd.DCE 非挤占可行性

- 记录时间：`2026-07-01 14:00 CST`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage015_pilot_confirmation_jd_feasibility_v1`
- 阶段性质：只读归因；不改策略、不连接 CTP、不调用下单 API。
- 是否重要突破版本：`否`
- 决策：`stage015_readonly_attribution_no_live_change`
- 下一步：`pilot_confirmation_not_enough_skip_true_engine`；`jd_direct_add_not_supported_by_full_market_evidence`

## 本次目标

Stage014 确认 Stage013 小风险试探已触发但不足，本阶段只回答两个问题：

1. pilot 触发后，是否有可交易的 3/5/10 日确认信号，值得写成“确认后释放风险”的真实引擎候选。
2. `jd.DCE` 是否能作为非挤占候选填补 `2022-2023` 趋势空窗，而不是直接塞入共享 AI topN。

## 外部调研判断

- mlfinpy 的 trend-scanning label 资料说明，趋势标签适合作为“主信号后再确认”的监督/复盘工具，但不能把未来趋势扫描结果直接变成实时规则；本阶段只使用入场后可观察的 3/5/10 日路径做代理。
- CTA 仓位研究提示，仓位和风险预算释放可以改善收益/风险，但必须同时看实现时点和回撤；只看“如果从入场一开始就加仓”的上界会高估可交易收益。
- Quantiacs futures trend-following 开源例子可借鉴多品种矩阵化、月度横截面比较形状，但当前 C9 是多约束真实引擎，不能直接照搬简化趋势策略。

参考：

- https://mlfinpy.readthedocs.io/en/latest/Labelling.html
- https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
- https://github.com/quantiacs/strategy-futures-trend-following

## 数据和输出

- 输入：Stage013 `trades / entry_risk / entry_candidates / pilot_gate_events`。
- `jd.DCE` 输入：旧 full-market suitability 文件 `qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv`。
- 本阶段输出目录：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage015_pilot_confirmation_jd_feasibility/`
- 主要输出：
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_closed_lots_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_pilot_risk_link_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_pilot_lot_detail_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_confirmation_summary_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_entry_visible_summary_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_jd_month_audit_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_jd_feasibility_summary_stage015_pilot_confirmation_jd_feasibility_v1.csv`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_chart_stage015_pilot_confirmation_jd_feasibility_v1.png`
  - `rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_report_stage015_pilot_confirmation_jd_feasibility_v1.md`

## 核心结果

- closed-lot 总数：`3,393`。
- pilot 事件数：`639`。
- pilot -> entry_risk 匹配数：`639/639`。
- pilot -> closed-lot 匹配数：`623/639`。
- `2022-2023` focus pilot lot 数：`235`。
- `2022-2023` focus pilot lot 原始 1 手实际 PnL：`-19,700.00`。

确认信号结论：

- `2022-2023` 中，`confirm_10d_combo=True` 的 1 手原始结果看起来很好：`28` 笔、胜率 `100%`、原始 PnL `91,420`、平均 `2.679R`。
- 但更接近可交易的“确认后再加风险”代理为负：`confirm_10d_combo=True` 的 post-confirm extra PnL 为 `-1,132,760`。
- `confirm_5d_close_positive=True` 也是类似：`105` 笔、原始 PnL `171,100`，但 post-confirm extra PnL `-4,367,930`。
- 全样本中 `confirm_3d_close_positive=True` 的 post-confirm extra PnL 有 `+257,490`，但焦点段为 `-4,185,810`，不能解决目标失败段。

入场可见维度：

- `drawdown_bucket=dd_35_45` 在焦点段 `43` 笔、PnL `78,270`；`dd_30_35` 为 `192` 笔、PnL `-97,970`。这说明深回撤段不是线性更差，不能继续扫回撤阈值。
- `ai_rank_bucket=rank_1_3` 在焦点段反而 `-55,260`，`rank_4_6` 为 `20,140`，`rank_7_9` 为 `15,420`。这再次反证“高 AI rank 直接加风险”。
- `same_direction_correlation_max_corr >= 0.6` 的焦点段 `15` 笔、PnL `-43,900`，可作为后续账户状态风险治理线索，但不能按这个单维度直接交易化。

`jd.DCE` full-market 旧证据：

- `2022-2023` 共 `24` 个月，`ai_top8_count=3`，`simple_top8_count=6`，future top-half 仅 `9/24=37.5%`，中位 future 60d PnL `-895`。
- `2022H1` 有阶段性强：future top-half `5/6=83.33%`、均值 future 60d PnL `7,201.67`。
- `2023` 明显弱：`ai_top8_count=0`、`simple_top8_count=0`、future top-half `2/12=16.67%`、均值 future 60d PnL `-2,263.33`。
- 因此 `jd.DCE` 不支持直接加入共享 AI 池；若未来继续，只能做非挤占、小预算、强确认的独立候选。

## 回测字段

- 本阶段是否为正式回测候选：`否`
- 期末权益：`N/A`
- 总收益：`N/A`
- 最大回撤：`N/A`
- Sharpe：`N/A`
- 总滑点：`N/A`
- 总交易次数：`N/A`
- 胜率：`N/A`

## 结论

Stage015 不晋级真实引擎候选。

原因不是 pilot 没有信息，而是当前 3/5/10 日确认规则把真正可赚的早期趋势段错过了；从入场开始加仓的上界好看，但确认后再加仓的可交易代理在 `2022-2023` 目标失败段为负。`jd.DCE` 也不能直接救 2023，旧 full-market 证据更像阶段性机会，不是稳定填坑。

## 后续规划

1. 不继续扫 `3/5/10` 日、`0.5R`、combo 条件、回撤阈值、活跃持仓阈值或品种方向。
2. 下一阶段更值得看“账户层风险压力提前识别/降风险”，尤其是 Stage011 指出的 `2022-11-28` broker10 约 `90%` 保证金压力，以及 Stage015 里高相关度桶的亏损。
3. 如果继续 `jd.DCE`，必须先做当前重建口径的非挤占小预算真实引擎可行性，且不能替换核心 AI topN。

## 反思

- 开始前过拟合反思：否。本阶段只预声明两个只读问题，不按最差窗口直接写规则。
- 开始前继续价值反思：是。Stage014 已把剩余失败定位到 pilot 已触发但不足，检查“确认后风险释放”和 `jd` 非挤占有必要。
- 结束后过拟合反思：否。输出不晋级候选，且明确拒绝继续扫确认窗口/阈值/品种。
- 结束后继续价值反思：是，但方向需要收窄。继续价值不在确认后加仓，而在账户压力治理和非挤占外生品种的小预算真实引擎验证。
