# Stage006 当前重建版质量特征绑定器

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:38 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读重跑保存 frames + 当前重建版 closed-lot/outcome + entry/first-minute 标签绑定；不改策略、不连接 CTP、不调用下单。
- 是否重要突破：否。属于数据闭环补齐，不是正式候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Deflated Sharpe Ratio / PBO：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551`
  - Bailey DSR PDF：`https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf`
  - Hudson & Thames meta-labeling/triple-barrier：`https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/`
  - A Century of Evidence on Trend-Following Investing：`https://fairmodel.econ.yale.edu/ec439/hurst.pdf`
- 我的判断：
  - DSR/PBO 的核心约束是不能在多回测、多候选里 winner-picking，所以本阶段只补固定口径数据，不按结果筛参数。
  - 长期趋势跟随研究强调右尾和分散化，本阶段标签只能作为只读诊断，不能直接削仓或过滤。
  - meta-labeling 可以作为后续“主 C9 信号不变、二级质量标签只调风险预算”的研究方向，但前提是当前版本标签覆盖和稳定性足够。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage006_current_quality_feature_binder.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读输出标签 `entry_open_relation_bucket`、`first_bar_relation_bucket`、`tag_ai4_6_entry_or_first_aligned` 等。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-06-30`
- 起点：每年 `01-01` 和 `07-01`，共 `17` 个冷启动起点
- 账户规模：`150,000`
- 成本口径：沿用当前线上重建 C9/15w wrapper `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 策略/归因口径：
  - 用 Stage901 `_run_live_c9` 重跑同口径，保存 `trades/entry_risk/entry_candidates/trade_events/intraday_events/curves`。
  - 用 Stage719 `_build_closed_lots` 构建当前重建版 `closed_lots`。
  - 用 Stage861 full minute bars 绑定开仓日第一分钟，生成 entry/first-bar 方向标签。

## 结果

- Stage006 复跑和 Stage167 基准逐起点完全一致：`end_equity/total_return_pct/max_dd_pct/sharpe/total_trade_count` 最大差异均为 `0.0`。
- 多起点结果：
  - 期末权益最低/中位/最高：`152,851.60 / 455,463.70 / 14,900,482.00`
  - 总收益最低/中位/最高：`1.9011% / 203.6425% / 9,833.6547%`
  - 最大回撤最差/中位：`-56.2069% / -47.2779%`
  - Sharpe 最低/中位/最高：`0.2860 / 1.1937 / 1.4786`
  - 总交易次数：各起点 `29` 到 `807`
- 当前逐笔/标签：
  - `entry_candidates`：`9,751`
  - `trades`：`6,696`
  - `entry_risk`：`3,132`
  - `closed_lots` / `quality_features`：`3,401`
  - `entry_first_bar_available`：`899/3,401 = 26.4334%`
- 质量桶只读结果：
  - `all_closed_lots`：`3,401` 笔，PnL `71,392,804.00`，胜率 `43.6048%`
  - `ai_rank_4_6`：`803` 笔，PnL `20,275,609.80`
  - `entry_or_first_aligned`：`337` 笔，PnL `1,279,174.00`
  - `ai4_6_entry_or_first_aligned`：仅 `27` 笔、`3` 个产品、`2` 个年份，PnL `9,140.00`
  - `missing_first_bar`：`2,502` 笔，PnL `60,667,340.00`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_report_stage006_current_quality_feature_binder_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_summary_stage006_current_quality_feature_binder_v1.csv`
- daily/curves：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv`
- trades：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_trades_stage006_current_quality_feature_binder_v1.csv`
- closed_lots：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_closed_lots_stage006_current_quality_feature_binder_v1.csv`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_quality_features_stage006_current_quality_feature_binder_v1.csv`
- quality_summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_quality_summary_stage006_current_quality_feature_binder_v1.csv`
- 绝对权益资金曲线：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_absolute_equity_chart_stage006_current_quality_feature_binder_v1.png`
- quality chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_quality_chart_stage006_current_quality_feature_binder_v1.png`

## 结论

- 本阶段结论：当前重建版逐笔结果和 entry/first-minute 标签绑定已经打通，且复跑口径与 Stage167 基准一致；但 Stage861 首分钟覆盖只有 `26.4334%`，旧 Stage016 的 `ai4_6 ∩ entry/first_bar aligned` 在当前重建版多起点样本里只有 `27` 笔、`2` 年，不足以直接写候选策略。
- 是否进入下一步：进入，但下一步仍应是数据/只读代理，不是策略上线。
- 下一步：Stage007 优先补分钟覆盖缺口或做覆盖样本内的冻结 meta-label 只读审计；如要研究鸡蛋，应先补 `jd.DCE` full-universe monthly AI 分数或独立非挤占候选生成，不得直接塞入共享 AI topN。

## 过拟合反思

- 运行前判断：否。目标是补当前重建版逐笔/分钟标签缺口，不调规则、不筛参数、不按结果挑品种。
- 运行后判断：否。只读重跑同口径 `17` 个起点并绑定固定分钟标签，没有修改 C9、AI 池或交易阈值。
- 原因：标签阈值使用固定 `0R` 方向判断，结果不用于改规则；质量桶样本不足时明确降级，不做救参。

## 继续价值反思

- 运行前判断：有。Stage005 已确认缺 closed-lot/outcome 和 entry/first-minute 标签；不补齐就无法判断后续优化是否可靠。
- 运行后判断：有，但要降级推进。现在闭合 lot/outcome 可审计，绝对权益曲线也已补；但分钟覆盖不足，不能直接进入策略候选。
- 原因：当前证据能支持“继续补数据/做代理”，不能支持“已有高质量信号可加大风险投入”。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、跨线合并或重要突破。
