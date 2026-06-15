# Stage067 - Stage891 日内分钟规则路线级证据收束

- 时间：2026-06-15 09:38 CST
- 当前模式：day
- line_id：`futures_trend_stage819_intraday_rules`
- model_tag：`stage891_stage890_intraday_route_closure_v1`
- 源候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 阶段性质：只读路线级证据收束；不新增交易规则、不接真实组合引擎、不改 Stage372 官方正式版、不改官方候选配置、不连接 CTP、不调用下单、不触发 A/B。
- 是否重要突破：否。它不是新 alpha，而是把 Stage861/863 与 Stage878-890 的证据统一收束，防止继续隐性救参。

## 外部调研和判断

- 参考资料：vn.py 官方 GitHub 用于确认本地回测/组合回放与可视化工作流背景；CME open interest / volume 资料支持 OI 和成交量作为参与度辅助信息；CME stop/risk order 资料支持预设止损与实时错误处理。
- 我的判断：外部资料只支持“参与度可以解释、止损必须预设”的研究原则，不支持继续扫描 `first60/OR15/R倍数/成交量/OI/品种/年份`。Stage891 的正确动作是路线收束，而不是再创造一个小变体。

## 本次版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage891_stage890_intraday_route_closure.py`
- 新增记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260615_0938_stage067_stage891_intraday_route_closure.md`
- 新增输出：
  - route matrix：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_route_matrix_stage891_stage890_intraday_route_closure_v1.csv`
  - scorecard：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_scorecard_stage891_stage890_intraday_route_closure_v1.csv`
  - visual index：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_visual_index_stage891_stage890_intraday_route_closure_v1.csv`
  - summary chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_summary_chart_stage891_stage890_intraday_route_closure_v1.png`
  - report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_report_stage891_stage890_intraday_route_closure_v1.md`
  - decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage891_stage890_intraday_route_closure_decision_stage891_stage890_intraday_route_closure_v1.json`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 官方正式版 Stage372：未修改。
- 官方候选配置：未修改。

## 数据与视觉覆盖

- Stage861 全周期 entry-day 分钟K覆盖：`341/341 = 100%`
- Stage861 pressure key dates 覆盖：`19/19 = 100%`
- Stage891 visual index 统计图像证据：`10` 组 manifest，`95` 页 PNG。
- 其中 Stage861 entry atlas `57` 页，pressure atlas `3` 页；Stage878、Stage879、Stage880、Stage881、Stage882、Stage883、Stage889、Stage890 均有对应 atlas manifest 与页面。
- summary chart 尺寸：`2700x2250`

## 新增回测/代理结果

本阶段不新增真实回测，只做既有证据的只读收束。关键复核结果如下：

- Stage863 C9 仍是唯一有正价值的骨架：相对 C4 期末权益 `+4,621,339.60`，最大回撤改善 `+4.5602pp`，Sharpe `+0.031584`；但 max broker10 `114.3987%`，高于 C4 `111.4255%`，不能直接推广为官方替代。
- Stage879 early OI guard 真实引擎失败：相对 C9 期末权益 `-8,646,381.40`，最大回撤改善 `+7.1620pp`，但 Sharpe `-0.063081`，max broker10 `119.3842%`。
- Stage882 同手数 `+0.5R` pyramiding 真实引擎失败：相对 C9 期末权益 `+84,248,252.10`，但最大回撤恶化 `-19.0568pp`，Sharpe `-0.057171`，max broker10 `203.4450%`。
- Stage883 固定 1 手 sleeve 真实引擎失败：相对 C9 期末权益 `+1,046,670.05`，最大回撤改善 `+1.4687pp`，但 Sharpe `-0.008835`，max broker10 `127.4316%`。
- Stage889 C9 loss body 最优代理仅 `+72,650.00`，正年份 `1`、负年份 `4`，不稳定。
- Stage890 first60 volume triad 最优代理仅 `+90,000.00`，触发 `1` 笔，样本过小。
- Stage891 scorecard 结论：新研究线与候选隔离已证明；全周期逐笔与K线视觉覆盖已证明；非AI规则审计已证明；但推广/A-B 触发条件未满足。

## 决策

- decision：`stage891_intraday_route_closed_no_promotable_minute_rule_yet`
- 结论：基于当前候选的全周期逐笔分钟K研究已经形成完整证据链。C9 是有价值骨架，但 Stage878-890 的外生参与度、时段边界、顺势加仓、sleeve、C9亏损形态、成交量三元参与度都没有给出可推广的新分钟规则。
- 操作：不接真实引擎、不触发 A/B、不改官方正式版、不改官方候选配置。

## 反过拟合反思

- 运行前：否。Stage891 只汇总冻结证据，不新增阈值、窗口或品种/年份过滤。
- 运行后：如果继续在 `first60/OR15/0.5R/1R/成交量/OI/sleeve手数/品种/方向/年份` 上救参，就是过拟合。证据显示这些方向要么样本太小，要么真实引擎伤害 Sharpe、broker10 或右尾。

## 继续价值反思

- 运行前：有价值。路线级收束能避免把失败的代理误当作继续探索空间。
- 运行后：当前分钟K本体路线的继续价值已经很低，只应作为复盘标签和历史证据保留。若继续本目标，应转向两个方向之一：账户级非交易层生存线，或新的低自由度外生信息源；不应继续微调现有分钟K小变体。

## 后续规划和 TODO

- 不把 Stage891 写入根目录 `memory.md` / `back_log.md`，因为这不是正式候选或重要突破。
- 不更新 `research/registry.md`，避免并行冲突。
- 下一步若继续本研究线：只允许先做“下一研究方向设计草案”，明确是否仍属于用户目标的分钟级入场/出场；如果不能证明属于该目标，应暂停本线而不是硬凑规则。
