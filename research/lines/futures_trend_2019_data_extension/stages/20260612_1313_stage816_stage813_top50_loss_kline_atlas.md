# Stage816 Stage813 Top50亏损K线图谱

- line_id：`futures_trend_2019_data_extension`
- 当前模式：day
- 记录时间：2026-06-12 13:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读亏损法证图谱
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段没有新增互联网/GitHub 调研；任务是复用本地 Stage815 已落盘的闭合交易和 summary，扩展 Top50 可视化，不涉及新策略形状选择。
- 我的判断：直接从 Top50 图形反推过滤条件会高度过拟合；但把它作为左尾结构复盘样本有价值，尤其用于观察 OI 放大、趋势末端假突破、短周期急反和退出类型是否在第41-50笔继续集中。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage816_stage813_top50_loss_kline_atlas.py`
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage815_stage813_top40_loss_kline_atlas.py`，仅把图标题里的 TopN 文案改为跟随 `TOP_N`，不改策略逻辑。
- 删除脚本：无
- 新增参数：`TOP_N=50`，`PER_PAGE=4`，`PRE_BARS=50`，`POST_BARS=50`
- 修改参数：无策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-05-29`
- 账户规模：Stage813 候选口径 50万
- 成本口径：复用 Stage815 已落盘 summary；不重跑策略
- 样本过滤：按 `theory_loss_pct = -directional(entry->exit return pct)` 选择亏损比例 Top50 closed lots
- 策略/归因口径：`official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`

## 结果

- 期末权益：`26,293,495`
- 总收益：`5158.699%`
- 最大回撤：`-46.5025%`
- Sharpe：`1.3618`
- 总滑点：`2,029,740`
- 总交易次数：`673`
- 胜率：`53.3847%`
- 其他关键指标：
  - closed lots：`346`
  - loser lots：`176`
  - Top50 最差亏损比例：`6.3561%`
  - 第50名亏损比例：`1.9144%`
  - Top50 realized PnL 合计：`-17,811,230`
  - OI 放大命中：`24/50`
  - 缺失K线：`0`
  - 分钟聚合日线：`6`
  - Tushare 早期日线：`8`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage816_stage813_top50_loss_kline_atlas_report_stage816_stage813_top50_loss_kline_atlas_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage816_stage813_top50_loss_kline_atlas_summary_stage816_stage813_top50_loss_kline_atlas_v1.csv`
- orders：无新增
- daily：无新增
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage816_stage813_top50_loss_kline_atlas_top50_losses_stage816_stage813_top50_loss_kline_atlas_v1.csv`
- charts：`13` 页 PNG，已在会话中直接发送。

## 结论

- 本阶段结论：Top50 图谱生成完成。第41-50笔把左尾观察从 Top40 延伸到更宽样本，但仍只是复盘材料，不构成新规则证据。
- 是否进入下一步：是，仅进入人工复盘/归因，不进入参数扫描。
- 下一步：若继续，应把图中候选结构先转成预声明标签，再做全 closed lots、多起点、多年份统计；不能直接按这50笔定阈值。

## 过拟合反思

- 运行前判断：不过拟合。
- 运行后判断：不过拟合。
- 原因：本阶段没有新增或修改任何交易规则、策略参数、品种池或风控阈值；只是对既有 closed lots 画图。风险只出现在后续若用这50笔倒推规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Top50 相比 Top40 增加了尾部外沿样本，可以检查左尾结构是否稳定延续；但价值在复盘和归因，不在救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage816 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选或跨线合入。
