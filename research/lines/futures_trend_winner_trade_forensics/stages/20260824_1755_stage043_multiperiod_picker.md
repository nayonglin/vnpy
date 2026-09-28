# Stage043 全量复盘 HTML 多周期选择器与 10/30 交易日 K

- line_id：futures_trend_winner_trade_forensics
- 当前模式：全周期复盘工具交互与聚合周期补全
- 记录时间：2026-08-24 17:55 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / codex/stage130-option-probe
- 阶段性质：复盘工具优化，不是策略优化或回测实验
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Plotly JavaScript function reference（`Plotly.react` 用于高效更新数据和布局）：https://plotly.com/javascript/plotlyjs-function-reference/ ；Plotly layout xaxis reference（`matches` 让多个轴共享数据坐标范围）：https://plotly.com/javascript/reference/layout/xaxis/
- 我的判断：多周期不应各自使用独立日期轴或随单笔窗口重新起算。10日/30日 K 应按品种交易日历的绝对序号固定、非重叠分桶；所有面板使用同一交易日坐标，并通过 `matches='x'` 联动缩放。最新不足完整周期的桶保留，但悬浮标签必须披露实际日数。

## 本次变更

- 新增脚本：无，复用并扩展 Stage038/Stage042 生成器。
- 修改脚本：research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增功能：六项复选 chip（30日K、10日K、月K、周K、日K、15分钟K），默认仅勾选30日K和日K；至少保留一个选择；非尾部交易跳过15分钟面板但保留选择状态。
- 新增聚合：10/30个交易日固定分桶 OHLCV，包含 MA5/10/20/40 与 1,230 个交易日隐藏预热；不足周期标签显示 `实际日数/目标日数`。
- 测试：tests/test_stage038_profit_loss_multiscale_monthly.py 增至13项，覆盖固定非重叠分桶、OHLCV、尾部不足桶和默认多选状态。

## 回测/归因参数

- 数据区间：沿用 Stage847-C9-15w 冻结日序列，请求截止 2026-08-17。
- 账户规模：150,000（仅沿用旧 summary）
- 成本口径：沿用旧 1.0 成本倍数，本次未重算。
- 样本过滤：全部 402 笔完整开平仓 episode；73 笔原尾部有15分钟K，329笔非尾部不画分钟线。
- 策略/归因口径：`--reuse-strategy --reuse-market --no-market-download`；未重跑策略，未下载行情。

## 结果

- 期末权益：12,652,824.10（旧 summary 沿用，非本次新回测）
- 总收益：8,335.2161%（旧 summary 沿用，非本次新回测）
- 最大回撤：-56.2069%（旧 summary 沿用，非本次新回测）
- Sharpe：1.3410（旧 summary 沿用，非本次新回测）
- 总滑点：1,611,870（旧 summary 沿用，非本次新回测）
- 总交易次数：821（旧 backtest trade count；图表按402笔episode聚合）
- 胜率：52.4577%（旧 nonzero daily win rate，非 episode 胜率）
- 其他关键指标：402 episode = 158盈利 + 238亏损 + 6持平；每笔30日K为9至58根、10日K为27至171根；15分钟数据46,013根且缺失交易日为0；HTML大小22,670,546字节，SHA256=`c32f95e45eff467540b303aac9f4a954c7b2f1fbbe351454d0ebf0bd019d57b9`。
- 独立 reviewer：未触发；本次没有产生新回测数据，只重组现有行情并生成可视化。

## 输出文件

- report：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/index.html
- summary：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/summary.json
- orders：无新订单产物
- daily：复用 Stage038 已有 strategy_daily.csv
- quality：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/chart_manifest.csv

## 验证

- 单元测试：`.py311/bin/python -m unittest tests.test_stage038_profit_loss_multiscale_monthly`，13/13通过。
- JavaScript：生成的页内业务脚本通过 `node --check`。
- 静态产物：402条 manifest 与402条嵌入记录一致；六周期字段齐全；默认选择严格为 `day30,daily`；73/329分钟覆盖口径不变。
- 真实浏览器：六周期同时选择后6个K线面板均出现；6个x轴范围一致，5个从轴均 `matches='x'`；主轴改为 `[1300,1400]` 后六轴同步；非尾部交易提示并跳过15分钟面板，切回尾部自动恢复；最后一个周期不能取消。

## 结论

- 本阶段结论：用户可按需组合六种周期；默认30日K+日K；10/30日 K 是固定交易日桶而非滑动窗口；所有可见周期对齐并同步缩放，原进出场标记与73笔分钟线范围保持不变。
- 是否进入下一步：否，当前可视化诉求已闭环。
- 下一步：若后续研究从这些图提出策略假设，必须单独立项并做样本外验证，不能把视觉印象直接转成正式规则。

## 过拟合反思

- 运行前判断：否。只改变聚合展示和交互，不改变信号、仓位、开平仓或参数。
- 运行后判断：否。没有产生新回测结果，全部交易结果与73/329分钟覆盖口径保持不变。
- 原因：新增周期用于观察，不参与策略决策；固定日历分桶还减少了逐笔窗口起点造成的视觉偏差。

## 继续价值反思

- 运行前判断：是。原固定四面板无法按研究问题裁剪，且缺少10/30交易日中周期。
- 运行后判断：是。默认视图更聚焦，任意组合仍保持坐标对齐；非尾部分钟数据边界也没有被掩盖。
- 原因：它提升全量复盘效率和跨周期可比性，同时不引入新数据源或策略风险。

## 合入建议

- 是否更新本线 `LINE.md`：否，本次为有界复盘工具增量。
- 是否更新 `research/registry.md`：否，研究线未变更。
- 是否追加根目录 `memory.md/back_log.md`：否，不是 alpha 突破、路线废弃或正式候选。
