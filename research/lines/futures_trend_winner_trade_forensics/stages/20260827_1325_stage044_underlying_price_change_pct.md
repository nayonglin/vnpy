# Stage044 全量复盘 HTML 标的价格涨跌幅

- line_id：futures_trend_winner_trade_forensics
- 当前模式：全周期复盘工具指标补全
- 记录时间：2026-08-27 13:25 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / codex/stage130-option-probe
- 阶段性质：复盘工具优化，不是策略优化或回测实验
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本次未引入外部算法或数据源；采用标准持仓成交量加权退出价与简单价格收益率定义。
- 我的判断：用户需要的是标的本身从开仓价到实际平仓均价的上涨/下跌比例，不能用账户收益率、R倍数，也不能因多空方向反转符号。部分平仓必须按各次平仓手数加权，避免只取最后一笔造成失真。

## 本次变更

- 新增脚本：无，复用并扩展 Stage038/Stage042 生成器。
- 修改脚本：research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增字段：`weighted_exit_price`、`price_change_pct`、`price_change_label`。
- 展示规则：净利润卡片第二行显示 `价格上涨 x.xx%`、`价格下跌 x.xx%` 或 `价格持平 0.00%`；上涨红色、下跌绿色。
- 计算口径：`加权平仓价 = Σ(平仓价 × 平仓手数) / Σ平仓手数`；`标的涨跌幅 = (加权平仓价 - 开仓价) / 开仓价 × 100%`；空头不反转符号。

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
- 其他关键指标：402条嵌入记录保持不变；SM201.CZCE 多头开仓价8624、两笔等量平仓价11500/11100，加权平仓价11300，显示`价格上涨 31.03%`；rb2210.SHFE 空头显示`价格下跌 10.05%`。
- 独立 reviewer：未触发；本次没有产生新回测数据，只更新可视化派生字段与页面展示。

## 输出文件

- report：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/index.html
- summary：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/summary.json
- orders：无新订单产物
- daily：复用 Stage038 已有 strategy_daily.csv
- quality：research/lines/futures_trend_winner_trade_forensics/outputs/stage042_c9_15w_all_trade_multiscale_html/chart_manifest.csv

## 验证

- TDD：新增部分平仓成交量加权测试；实现前因缺少`weighted_exit_price`失败，实现后通过。
- 单元测试：`.py311/bin/python -m unittest tests.test_stage038_profit_loss_multiscale_monthly`，14/14通过。
- Python/JavaScript：生成器通过`py_compile`；生成 HTML 的页内业务脚本通过`node --check`。
- 静态产物：402条嵌入记录；73/329分钟覆盖口径不变；`intraday_missing_days=0`；HTML SHA256=`0de9ae85919df84a95f30542e75be1c2d012ef45fa92fdaaff2bf06f6a8bdb0d`且与summary一致。
- 真实浏览器：SM201净利润卡片显示`价格上涨 31.03%`；rb2210空头盈利卡片显示`价格下跌 10.05%`且为绿色。唯一控制台错误为浏览器请求未提供的`favicon.ico`，与业务页面无关。

## 结论

- 本阶段结论：净利润卡片现在同时表达盈亏金额和标的真实价格方向/幅度；部分平仓采用手数加权均价，多空均保持价格本身的原始涨跌方向。
- 是否进入下一步：否，当前展示诉求已闭环。
- 下一步：如要增加持仓方向收益率，应另设字段并明确命名，不能替换本次原始价格涨跌幅。

## 过拟合反思

- 运行前判断：否。只增加确定性的成交派生展示，不调整策略、信号、参数或样本筛选。
- 运行后判断：否。交易episode数量、回测结果、分钟覆盖范围均未变化。
- 原因：公式由实际开平仓价格与手数唯一决定，不参与交易决策。

## 继续价值反思

- 运行前判断：是。净利润金额无法直观看出标的实际运行幅度，尤其多空和多次平仓场景容易误读。
- 运行后判断：是。金额、R倍数和标的涨跌幅现在各自表达不同维度，复盘解释更完整。
- 原因：新增信息来自既有成交事实，成本低且能减少方向性误判。

## 合入建议

- 是否更新本线 `LINE.md`：否，本次为有界复盘工具增量。
- 是否更新 `research/registry.md`：否，研究线未变更。
- 是否追加根目录 `memory.md/back_log.md`：否，不是 alpha 突破、路线废弃或正式候选。
