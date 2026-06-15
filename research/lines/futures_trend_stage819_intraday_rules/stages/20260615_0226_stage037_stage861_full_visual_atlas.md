# Stage037 Stage861 完整分钟K视觉图谱重算

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 02:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据归因 + K线视觉图谱重算
- 是否重要突破：否。它是证据覆盖里程碑，不是策略收益突破。
- 是否触发A/B：否。没有新策略、没有候选接入、没有真实引擎变更。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub README 对 `cta_strategy`、`cta_backtester`、`portfolio_strategy` 的定位说明，支持继续把研究、回测和实盘执行隔离：<https://github.com/vnpy/vnpy/blob/master/README_ENG.md>
  - backtesting.py 文档的事件式 backtest 输入/成本/逐 bar 运行口径，支持用完整 OHLCV/分钟级数据检验规则语义，而不是只看日线结果：<https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html>
  - 公开止损/移动止损示例只说明止损应在 bar 推进中实时更新，不支持直接复制参数：<https://greyhoundanalytics.com/blog/stop-losses-in-backtestingpy/>
- 我的判断：外部资料只支持工程纪律，即“数据完整、逐 bar、止损和仓位风险分层”；不支持把 OR 长度、R 倍数、重试次数或品种方向阈值直接搬进本线。Stage861 的任务应该是补齐证据图谱，不应该借补数成功直接写规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage861_stage860_full_visual_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `model_tag=stage861_stage860_full_visual_atlas_v1`
  - entry atlas 每页 `6` 笔 closed lots
  - pressure atlas 每页 `7` 个 key dates
  - 只读允许位：`new_rule_allowed=0`、`engine_allowed=0`、`ab_allowed=0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage825/Stage819 closed lots 全周期，入场年份覆盖 `2018` 到 `2026`。
- 账户规模：不适用，本阶段不跑组合权益曲线。
- 成本口径：不适用，本阶段只重算分钟K特征和视觉图谱。
- 样本过滤：Stage825 全部 `341` 笔 closed lots；Stage849 全部 `19` 个 pressure key dates。
- 策略/归因口径：读取 Stage825 closed lots、Stage849 pressure features、Stage860 combined patch minute bars，并与原 Stage825 minute sources 合并，形成全量分钟K证据集。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 决策：`stage861_full_visual_atlas_complete_no_rule`
  - full minute bars：`1,479,592`
  - full minute symbols：`216`
  - Stage860 patch minute bars：`38,354`
  - entry lots：`341`
  - entry-day covered lots：`341`
  - entry-day missing lots：`0`
  - entry-day coverage rate：`100%`
  - pressure key dates：`19`
  - pressure covered dates：`19`
  - pressure missing dates：`0`
  - pressure coverage rate：`100%`
  - entry atlas pages：`57`
  - pressure atlas pages：`3`
  - 入场年覆盖检查：2018 `25` 笔、2019 `45` 笔、2020 `74` 笔、2021 `61` 笔、2022 `45` 笔、2023 `28` 笔、2024 `26` 笔、2025 `25` 笔、2026 `12` 笔均有正分钟K根数。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_report_stage861_stage860_full_visual_atlas_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_summary_stage861_stage860_full_visual_atlas_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_decision_stage861_stage860_full_visual_atlas_v1.json`
- full minute bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv`
- entry features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_entry_lot_features_stage861_stage860_full_visual_atlas_v1.csv`
- entry bucket stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_entry_bucket_stats_stage861_stage860_full_visual_atlas_v1.csv`
- entry coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_entry_coverage_by_year_stage861_stage860_full_visual_atlas_v1.csv`
- entry atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_entry_atlas_manifest_stage861_stage860_full_visual_atlas_v1.csv`
- entry atlas PNG：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_entry_atlas_page001_stage861_stage860_full_visual_atlas_v1.png` 到 `page057`
- pressure features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_pressure_key_date_features_stage861_stage860_full_visual_atlas_v1.csv`
- pressure atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_pressure_atlas_manifest_stage861_stage860_full_visual_atlas_v1.csv`
- pressure atlas PNG：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_pressure_atlas_page001_stage861_stage860_full_visual_atlas_v1.png` 到 `page003`
- orders：不适用
- daily：不适用
- quality：用本阶段 feature/manifest/PNG 完整性检查替代。

## 结论

- 本阶段结论：Stage860 解除数据覆盖阻断后，Stage861 已把全周期 `341/341` 入场日和 `19/19` 压力 key dates 转成可审阅的分钟特征与 K 线图谱。这个结果只证明“现在可以做全量视觉证据归纳”，不证明任何新的日内规则成立。
- 是否进入下一步：是，但只能进入 Stage862 证据归纳和低自由度规则假设审计。
- 下一步：基于完整图谱做“数据分桶 + 人眼K线复核”的一致性归纳，优先寻找跨年份、跨品种、跨方向都能解释的低自由度规则形状；仍禁止品种名/年份/方向黑名单、R 倍数小数扫描、OR 长度扫描、重试次数扫描。

## 过拟合反思

- 运行前判断：否。Stage861 只补全证据和图谱，不根据收益选择样本、不生成规则、不调参数。
- 运行后判断：否。输出覆盖了全部 Stage825 closed lots 和全部 Stage849 pressure key dates，没有按结果筛样本；但如果下一步直接把某一年、某品种、某几张图的形态写成交易条件，就会立刻变成过拟合。
- 原因：本阶段的自由度主要是图谱排版和特征汇总，不改变交易逻辑。真正的过拟合风险会出现在 Stage862 以后把视觉经验规则化时。

## 继续价值反思

- 运行前判断：有价值。Stage034 明确指出覆盖偏差严重，补数后必须重画全量图谱，否则规则研究仍在有偏样本上打转。
- 运行后判断：有价值。覆盖阻断已经解除，下一步终于可以对全周期交易同时做数据和视觉证据归纳；但价值不在继续生成更多图，而在抽象出可被反证的少数规则假设。
- 原因：分钟图谱的作用是帮助识别“错了就退、可有限重试、顺畅趋势不误杀”的结构边界，而不是服务于参数搜索。

## 校验

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage861_stage860_full_visual_atlas.py`
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage861_stage860_full_visual_atlas.py`
- 输出完整性检查：
  - entry features `341` 行，`entry_day_minute_bars > 0` 为 `341` 行，缺失 `0`。
  - pressure features `19` 行，`minute_bars > 0` 为 `19` 行，缺失 `0`。
  - entry atlas manifest `341` 行，PNG `57` 张。
  - pressure atlas manifest `19` 行，PNG `3` 张。
- 视觉抽查：entry atlas page001 和 pressure atlas page001 均非空并能显示 K 线、入场/止损/目标/OR 等辅助线；部分 pressure 图因尺度和样本长度显示较稀疏，但不是空图。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage037 最新状态和下一步。
- 是否更新 `research/registry.md`：否。本阶段是本线证据工程进展，不是跨线正式候选或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否。没有新正式候选、没有策略突破、没有跨线结论。
