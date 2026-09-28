# Stage045 Stage037 C 全周期逐笔多周期复盘 HTML

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：冻结研究产物只读复盘
- 记录时间：2026-08-27 21:05（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`（沿用当前工作区，不改正式策略）
- 阶段性质：历史版本可视化还原，不重跑策略
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：[Plotly JavaScript xaxis reference](https://plotly.com/javascript/reference/layout/xaxis/)、[plotly.js GitHub](https://github.com/plotly/plotly.js)。
- 我的判断：继续沿用既有共享交易日坐标与 `xaxis.matches` 同步缩放，不为 Stage037 C 新造坐标逻辑；这能保持 30日K、10日K、月K、周K、日K 的缩放一致性，也避免把研究版特殊处理带回正式页面。

## 本次变更

- 新增脚本：无，复用现有多周期 HTML 生成器。
- 修改脚本：`research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py`。
- 删除脚本：无。
- 新增参数：`--source-profile stage037c`，只接受固定 commit `ec4f1a39b48ed168662059aea7a98030a01a3ccf` 的 Stage037 C 冻结 CSV；新增严格 FIFO 已平仓 lot 还原。
- 修改参数：Stage037 C 仅允许 `--episode-scope all`，强制不下载行情、不绘制15分钟K，R 缺失时按净利润绝对值排序。
- 删除参数：无。

## 回测/归因参数

- 数据区间：冻结回测曲线 2018-01-02 至 2026-08-25；已平仓交易开仓日 2018-01-15 至 2026-08-18，平仓日最晚 2026-08-19。
- 账户规模：150,000。
- 成本口径：完全复用 Stage037 C 冻结汇总，不重新计算回测；冻结汇总总滑点 1,669,965。
- 样本过滤：仅 `experiment_arm == C`；733 条成交严格 FIFO，还原 373 个已平仓 lot、358 笔完整 episode；FU2609 多 169 手、SI2611 多 503 手在回测终点仍开放，不伪造平仓点、不绘图。
- 策略/归因口径：`stage037_C_long_short_mirror_hard_block`；成交/曲线/汇总来自固定 commit，日线来自 SHA256=`d7375edac99e182ba3524abfbed92abb035e101d05744cb801ec5c7b5dbd47f5` 的冻结 vn.py 数据库；不读取或下载15分钟数据。

## 结果

- 期末权益：17,051,717.30（冻结 Stage037 C 原始结果，本次未重跑）。
- 总收益：11,267.8115%。
- 最大回撤：-39.9147%。
- Sharpe：1.543941。
- 总滑点：1,669,965。
- 总交易次数：733 条成交。
- 胜率：非零日胜率 53.1984%；逐笔完整 episode 为 138 盈利、216 亏损、4 持平。
- 其他关键指标：358 笔完整 episode、227 个精确合约、373 个已平仓 lot、15分钟K行数 0；冻结包无完整逐笔 `entry_risk`，因此 R 全部显示 N/A。

## 输出文件

- report：`research/lines/futures_trend_winner_trade_forensics/outputs/stage045_stage037c_all_trade_multiscale_html/index.html`
- summary：`research/lines/futures_trend_winner_trade_forensics/outputs/stage045_stage037c_all_trade_multiscale_html/summary.json`
- orders：`research/lines/futures_trend_winner_trade_forensics/outputs/stage045_stage037c_all_trade_multiscale_html/closed_lots.csv`
- daily：`research/lines/futures_trend_winner_trade_forensics/outputs/stage045_stage037c_all_trade_multiscale_html/strategy_daily.csv`
- quality：`research/lines/futures_trend_winner_trade_forensics/outputs/stage045_stage037c_all_trade_multiscale_html/chart_manifest.csv`

## 结论

- 本阶段结论：已找到并锁定 Stage037 C 全周期冻结数据，生成独立研究版逐笔复盘 HTML；页面明确标注“研究版未晋级”，未覆盖 Stage042 当前正式策略复盘页。
- 是否进入下一步：可以直接人工复盘；不据此晋级策略。
- 下一步：如需研究 Stage037 C 的特定盈利/亏损形态，应先提出独立假设，再做跨周期样本外验证，不能从图形事后挑规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只还原冻结成交并绘图，不修改信号、参数、样本或回测结果；主要风险是视觉叙事诱发事后归因，已用研究版警示与“不可据此晋级”边界约束。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：截图只能证明汇总指标，逐笔 HTML 能核对方向、持有期、行情结构、极端盈亏与换月背景；同时保留了冻结 commit、源文件哈希和数据库哈希，可复验价值明确。

## 合入建议

- 是否更新本线 `LINE.md`：否，本次是有界可视化产物。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，不属于策略突破、正式候选或跨线合并。
