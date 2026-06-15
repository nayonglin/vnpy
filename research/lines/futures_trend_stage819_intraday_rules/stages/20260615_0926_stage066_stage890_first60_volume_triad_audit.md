# Stage066 - Stage890 first60 price/OI/volume 三元参与度审计

- 时间：2026-06-15 09:26 CST
- 当前模式：day
- line_id：`futures_trend_stage819_intraday_rules`
- model_tag：`stage890_stage889_first60_volume_triad_audit_v1`
- 源候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 阶段性质：C9 本体只读参与度审计；不新增交易规则、不接真实组合引擎、不改 Stage372 官方正式版、不改官方候选配置、不连接 CTP、不调用下单、不触发 A/B。
- 是否重要突破：否。成交量维度没有把 first60 逆向左尾从右尾修复中稳定分离出来。

## 外部调研和判断

- 参考资料：vn.py 官方 GitHub 用于确认当前仓库技术栈背景；CME 关于 open interest / volume 的教育资料支持把 OI 与成交量作为参与度辅助信息；CME stop order 风控资料支持“错了实时止损”的纪律。
- 我的判断：成交量/OI 可以作为趋势参与度解释变量，但不能因为概念正确就直接写规则。本阶段只允许一个低自由度检验：first60 成交量是否大于前一交易日 first60 成交量，不扫描倍数阈值、分钟窗口、品种、方向或年份。

## 本次版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage890_stage889_first60_volume_triad_audit.py`
- 新增记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260615_0926_stage066_stage890_first60_volume_triad_audit.md`
- 新增只读特征：`early_volume_state = volume_expanded / volume_faded_or_equal / volume_missing`
- 新增只读三元状态：`early_triad_state = price_side + oi_side + volume_state`
- 新增只读代理：`V1-V5` first60 逆向后第 60 根退出代理。
- 修改参数：无。
- 删除参数：无。
- 官方正式版 Stage372：未修改。
- 官方候选配置：未修改。

## 数据与输出

- 输入：Stage889 C9 loss-shape features、Stage861 full minute bars。
- C9 closed lots：`401`
- base closed-lot PnL：`53,950,264.60`
- 主要输出：
  - 报告：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_report_stage890_stage889_first60_volume_triad_audit_v1.md`
  - features：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_features_stage890_stage889_first60_volume_triad_audit_v1.csv`
  - triad summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_triad_summary_stage890_stage889_first60_volume_triad_audit_v1.csv`
  - proxy summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_proxy_summary_stage890_stage889_first60_volume_triad_audit_v1.csv`
  - proxy yearly：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_proxy_yearly_stage890_stage889_first60_volume_triad_audit_v1.csv`
  - summary chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_summary_chart_stage890_stage889_first60_volume_triad_audit_v1.png`
  - atlas manifest：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_atlas_manifest_stage890_stage889_first60_volume_triad_audit_v1.csv`
  - decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage890_stage889_first60_volume_triad_audit_decision_stage890_stage889_first60_volume_triad_audit_v1.json`

## 新增回测/代理结果

- decision：`stage890_first60_volume_triad_tiny_positive_proxy_no_engine`
- `price_adverse__oi_up__volume_missing`：`75` 笔，PnL `-2,719,401.30`，loser PnL 覆盖 `29.6263%`，但 winner PnL `8,097,400.00`，big winner `2`。
- `price_adverse__oi_down__volume_missing`：`91` 笔，PnL `811,933.50`，loser PnL 覆盖 `21.6241%`，winner PnL `8,707,070.00`，big winner `1`。
- 非 missing 成交量桶很稀疏：`price_adverse__oi_down__volume_expanded` 仅 `1` 笔；`price_adverse__oi_up__volume_faded_or_equal` 仅 `1` 笔；`price_adverse__oi_down__volume_faded_or_equal` 仅 `3` 笔。
- `V1_exit60_adverse_oi_up_volume_expanded`：触发 `0` 笔，delta `0`。
- `V2_exit60_adverse_any_oi_volume_expanded`：触发 `1` 笔，delta `-155,000.00`，正年份 `0`，负年份 `1`。
- `V3_exit60_adverse_oi_down_volume_expanded`：触发 `1` 笔，delta `-155,000.00`，正年份 `0`，负年份 `1`。
- `V4_exit60_adverse_oi_up_volume_faded`：触发 `1` 笔，delta `+90,000.00`，winner_cut `0`，loser_saved `90,000.00`，正年份 `1`，负年份 `0`。
- `V5_exit60_adverse_oi_down_volume_faded`：触发 `3` 笔，delta `+10,770.90`，winner_cut `0`，loser_saved `10,770.90`，正年份 `1`，负年份 `0`。
- 本阶段不是完整组合回测，不新增期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率口径；这些指标不能从只读 proxy 直接替代。

## K线视觉检查

- summary chart 尺寸：`2700x1500`
- atlas page001 尺寸：`2700x1950`
- 视觉结论：亏损覆盖最高的柱主要来自 `volume_missing` 桶；真正有前一交易日 first60 成交量对照的逆向桶样本数过小。图上两个正 delta 柱高度也只有 `+0.09m` 和 `+0.0108m` 级别，不具备进入真实引擎的规模。

## 结论

Stage890 关闭 first60 成交量三元参与度作为立即交易规则的路线。成交量这个维度在概念上有解释价值，但现有可实时对照样本太稀疏，最好的正代理只有 `1` 笔、`+90,000`，不能支撑规则化；扩大阈值、换倍数、换分钟数或按年份/品种补救都属于过拟合。

## 反过拟合反思

- 运行前：否。本阶段只用 `volume_ratio_to_prev > 1` 这个结构性二分，不扫阈值。
- 运行后：继续在该方向救参会过拟合。正结果来自 `1` 到 `3` 笔极小样本，不是跨年份、跨行情结构的稳定规律。

## 继续价值反思

- 运行前：有价值。成交量是价格/OI 之外的一阶参与度信息，值得做一次低自由度审计。
- 运行后：本分支没有继续接引擎价值。继续价值只在复盘解释标签；若继续本研究线，应离开 C9 入场日分钟K本体小变体，转向账户级非交易层生存线，或寻找更强且低自由度的外生信息源。

## 后续规划和 TODO

- 不接 Stage890 到真实引擎。
- 不触发 A/B，不写 `back_log.md`，不追加根目录 `memory.md`。
- 不扫描成交量倍数、first60 长度、OI 阈值、品种、方向、年份或 K线组合。
- 下一步建议：如果继续本研究线，做一次路线级收束，明确 Stage878-890 已经覆盖 OI/成交量/分钟K本体/新增仓/pressure 分支，避免在候选版上继续做低样本微调。
