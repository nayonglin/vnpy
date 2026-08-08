# Stage212 C9/15万大赢家三层K线图谱完成记录

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：只读研究输出重建；不回测、不改策略、不连接CTP
- 记录时间：2026-08-08 18:34（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage209图谱的展示与数据审计增强
- 是否重要突破：否；补齐跨周期观察上下文，但没有产生新的交易规则或策略证据
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Matplotlib/mplfinance GitHub公开实现与文档（`https://github.com/matplotlib/mplfinance`），重点参考多面板OHLCV图、共享日期轴和非交易间隔压缩的通用做法。
- 我的判断：15分钟窗口应继续按实际观测bar压缩空档；日线必须使用赢家自身逐月合约，不能用主连替换。上下周期放在同一图片有助于观察入场所处趋势阶段，但只看赢家仍有幸存者偏差，不能据此直接生成规则。

## 本次变更

- 修改脚本：`tools/stage208_c9_2r_winner_15m_atlas.py`
- 修改测试：`tests/test_stage208_c9_2r_winner_15m_atlas.py`
- 新增输出：`outputs/stage208_c9_2r_winner_15m_atlas/daily_source_manifest.csv`
- 新增参数：日线窗口 `before=60`、`after=5`；日线查询固定 `2010-01-01 -> 2026-07-15`
- 修改参数：单图由 `18x9` 改为 `18x12 @ 150dpi`；Atlas由 `24x13.5` 改为 `24x16 @ 100dpi`
- 删除参数：无
- 展示改动：删除15分钟成交量面板；新增日K面板和日成交量面板；日线入场日琥珀色、最终平仓日紫色、入场价蓝色虚线
- 数据边界：只读vn.py本地数据库中的精确月合约日线；不下载、不插值、不用主连或指数回退

## 回测/归因参数

- 数据区间：冻结样本 `requested_start_month=2020-01`；本阶段没有重跑回测
- 账户规模：15万元正式口径（继承冻结版本，本阶段不重新计算资金曲线）
- 成本口径：继承冻结回测，本阶段不重新计算
- 样本过滤：309个聚合事件中，`aggregate_r=sum(realized_pnl)/sum(risk_amount) >= 2.0` 的71笔赢家
- 排序：`aggregate_r`降序，其次`realized_pnl`降序、`entry_date`升序、`open_trade_id`升序
- 分钟窗口：开仓日前5个正式交易日 + 开仓日 + 后5个正式交易日
- 日线窗口：开仓前60根精确合约日K + 完整持仓期 + 最终平仓后5根日K
- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 结果

- 期末权益：未重跑，沿用冻结回测结果且本阶段不改写
- 总收益：未重跑，沿用冻结回测结果且本阶段不改写
- 最大回撤：未重跑，沿用冻结回测结果且本阶段不改写
- Sharpe：未重跑，沿用冻结回测结果且本阶段不改写
- 总滑点：未重跑，沿用冻结回测结果且本阶段不改写
- 总交易次数：未重跑；图谱输入为309个聚合事件，其中71笔>=2R赢家
- 胜率：未重跑，沿用冻结回测结果且本阶段不改写
- 单图：71张，`2700x1800 RGBA`
- Atlas：18页，`2400x1600 RGBA`
- 分钟覆盖：完整52、部分19、缺失0；与Stage209一致
- 日线覆盖：完整71、部分0、缺失0
- 精确日线合约：67个去重月合约，空合约0
- PNG完整性：89条SHA256，逐文件复算不一致0
- 安全边界：下单API 0、撤单API 0、`ctp_connected=false`

## 验证

- TDD过程：先观察 `daily_bars_to_frame`、`select_daily_window`、`load_daily_context`、`create_winner_figure` 和 `write_outputs(daily_context=...)` 的预期RED，再补最小实现。
- 定向测试：`.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py -v`，15/15通过。
- 机器审计：71张单图、18页Atlas、89/89哈希一致；日线来源manifest 67行且空合约0；coverage逐笔日线完整71/71。
- 视觉审计：抽查Rank 1、36、41、71和Atlas第1页，三层比例、红涨绿跌、入场/平仓标记、日期刻度与日成交量均可读；Rank 41分钟局部窗口偏短时仍保留完整日线背景。
- 全仓测试：`.py311/bin/python -m pytest` 新鲜结果为929通过、11失败、4个warning；11项既有失败为4个Alpha101 `cast_to_int`和7个Stage137 lazy-import/source-manifest drift，均不涉及本阶段文件，不能宣称全仓全绿，也不进入合并/PR收尾菜单。

## 输出文件

- report：`outputs/stage208_c9_2r_winner_15m_atlas/report.md`
- summary：`outputs/stage208_c9_2r_winner_15m_atlas/coverage_summary.csv`
- 日线来源：`outputs/stage208_c9_2r_winner_15m_atlas/daily_source_manifest.csv`
- 决策：`outputs/stage208_c9_2r_winner_15m_atlas/decision.json`
- 图片哈希：`outputs/stage208_c9_2r_winner_15m_atlas/png_sha256.csv`
- 单图与Atlas：同一输出目录，本地PNG不纳入Git

## 结论

- 本阶段结论：完成用户指定的“15分钟K线 + 日K + 日成交量”完整重绘；71笔赢家逐笔日线覆盖全部完整，分钟覆盖口径未被改变。
- 是否进入下一步：当前请求已满足；若研究形态，不应继续只看71笔赢家。
- 下一步：如需验证形态是否有效，回到309笔事件全集加入普通与亏损对照，并冻结单一、低自由度假设后再做样本外验证。

## 过拟合反思

- 运行前判断：否；本次只增强冻结样本可视化，不新增或调整策略规则。
- 运行后判断：否；所有策略输入、交易、排序和收益均未变化，只增加精确合约日线背景。
- 原因：图谱本身不改变回测，但如果从71笔赢家共性直接反推规则，会产生幸存者偏差；因此明确禁止直接推广。

## 继续价值反思

- 运行前判断：有；日线背景能补足只看11日分钟窗口无法辨认的中期趋势位置。
- 运行后判断：有，但当前图谱工作已闭环；Rank 41等分钟覆盖偏短样本证明日线层能提供独立上下文。
- 原因：继续绘图的边际价值已低，后续真正有价值的是用309笔全集做对照验证，而不是继续美化赢家图。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态为Stage212。
- 是否更新 `research/registry.md`：否，研究线归属未变化。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、策略突破或跨线合并。
