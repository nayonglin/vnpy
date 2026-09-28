# Stage042 C9/15万全量交易多周期复盘图

- line_id：futures_trend_winner_trade_forensics
- 当前模式：全周期开平仓 episode 可视化补全
- 记录时间：2026-08-23 15:40 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / codex/stage130-option-probe / 098ca5b99
- 阶段性质：复盘工具与证据覆盖修复，不是策略优化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：这是现有本地 HTML 生成器和冻结行情文件的有界扩展，没有新的策略、数据源或绘图算法选型，因此未进行网络/GitHub调研。
- 我的判断：全部 402 笔均画月/周/日 K，只让原尾部 73 笔保留 15 分钟 K；这样既满足全量对照，也不为分钟数据不完整的历史合约伪造连续性。

## 本次变更

- 新增脚本：无，复用 Stage038 生成器。
- 修改脚本：research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py
- 删除脚本：无
- 新增参数：--episode-scope tail|all
- 修改参数：无
- 删除参数：无
- 测试：扩展 tests/test_stage038_profit_loss_multiscale_monthly.py，覆盖全量 episode、非尾部无分钟线、背景日缺口披露、轴同步和原尾部兼容。

## 回测/归因参数

- 数据区间：沿用 Stage847-C9-15w 日序列，请求截止 2026-08-17。
- 账户规模：150,000（仅沿用旧 summary）
- 成本口径：沿用旧 1.0 成本倍数，本次未重算。
- 样本过滤：全部 402 笔完整开平仓 episode；73 笔原盈利/亏损尾部有 15 分钟 K，329 笔非尾部不画分钟线。
- 策略/归因口径：--reuse-strategy --reuse-market --no-market-download；不重跑策略，不下载行情。

## 结果

- 期末权益：12,652,824.10（旧 summary 沿用，非本次新回测）
- 总收益：8,335.2161%（旧 summary 沿用，非本次新回测）
- 最大回撤：-56.2069%（旧 summary 沿用，非本次新回测）
- Sharpe：1.3410（旧 summary 沿用，非本次新回测）
- 总滑点：1,611,870（旧 summary 沿用，非本次新回测）
- 总交易次数：821（旧 backtest trade count；图表按 402 笔 episode 聚合）
- 胜率：52.4577%（旧 nonzero daily win rate，非 episode 胜率）
- 其他关键指标：402 episode = 158 盈利 + 238 亏损 + 6 持平；73 笔有完整 15 分钟线、329 笔无分钟线；2 笔 fu1905.SHFE 非尾部 episode 各有 11 个远端背景交易日缺口，页面明示披露，开/平仓日不缺失。

## 输出文件

- report：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/index.html
- summary：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/summary.json
- orders：无新订单产物
- daily：复用 Stage038 已有 strategy_daily.csv
- quality：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/chart_manifest.csv

## 结论

- 本阶段结论：全周期 402 笔已全部进图，非尾部不再绘制分钟线；月/周/日 K 保持共享轴缩放，尾部交易保持四周期。
- 是否进入下一步：否，当前用户请求已完成。
- 下一步：如需研究规则，应先形成可检验假设再做样本外验证，不能从单笔图形直接改参。

## 过拟合反思

- 运行前判断：否。只增加观测范围，不改策略规则或参数。
- 运行后判断：否。没有产生新回测结果，页面也声明复盘图不是交易规则。
- 原因：全量样本比只看极端盈亏更能抑制选择性偏差，但仍只是描述性证据。

## 继续价值反思

- 运行前判断：是。原 73 笔尾部图无法回答全周期分布问题。
- 运行后判断：是。73/329 分层保留了深度复盘能力，也避免强行补分钟数据。
- 原因：新产物可在单页对照全部 episode，且不污染原 Stage038 尾部产物。

## 合入建议

- 是否更新本线 LINE.md：否，本次为有界复盘工具增量。
- 是否更新 research/registry.md：否，研究线未变更。
- 是否追加根目录 memory.md/back_log.md：否，不是 alpha 突破或正式候选变更。
