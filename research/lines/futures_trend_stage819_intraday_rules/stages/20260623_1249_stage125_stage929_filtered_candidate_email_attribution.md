# Stage125 Stage929过滤候选邮件归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-23 12:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：C9/15w 实盘定时报告邮件可读性与只读归因增强
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Postmark transactional email best practices：强调 transactional 邮件主题要清楚、正文要让收件人快速知道发生了什么。
  - MailerSend transactional email best practices：强调 subject / pre-header 应简洁直达。
  - LinkedIn plain text transactional emails：纯文本事务邮件适合减少复杂样式依赖。
- 我的判断：
  - 手机邮箱里不能依赖 Markdown 表格；16:35 邮件应先说明最终有没有可执行指令，再把“底层候选但被过滤”的原因直接列出来。
  - 本次只做已有 Stage901/Stage182 产物的只读归因，不修改 AI 池排序、策略参数、开仓、止损、Stage260/905/927/931 闸门。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增逻辑：
  - Stage929 新增读取 Stage901 `entry_candidates` 与 Stage182 `latest_pool` 的过滤候选归因。
  - 16:35/21:05 邮件 subject 增加 `过滤候选=N`。
  - 邮件正文新增纯文本区块 `底层候选但未成最终交易`，逐候选展示品种、合约、方向、底层信号、未成最终交易原因、计划入场价、止损价、理论手数、每手保证金、AI池评估日/生效日、AI池排名、AI分数、Top8门槛分、距Top8门槛、简单适配分和主要拖分项。
  - 本地 report 同步新增 `底层候选但未成最终交易` Markdown 表格，便于归档。

## 回测/归因参数

- 数据区间：当前 Stage901/Stage182 最新正式实盘影子产物，验证目标日 `2026-06-22`
- 账户规模：15万 C9/Stage847 live profile
- 成本口径：不涉及新回测；只读 Stage901/Stage182 输出
- 样本过滤：`candidate_status != opened`、`skip_reason` 非空、`passed_initial_filter=1`
- 策略/归因口径：
  - 最终交易信号仍以 Stage901 pending/order、Stage260、Stage905 为准。
  - 被过滤候选只用于解释“为什么没有成为最终交易”，不参与报单。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 当前验证邮件构造 subject：`[C9/15w 官方报告][warning] 2026-06-22 待处理=1 可提交=0 过滤候选=2 下单API=0 rb2610.SHFE short/open 11手`
  - 当前过滤候选 `2` 个：`lc2609.GFEX`、`hc2610.SHFE`
  - `lc.GFEX` 归因：AI池排名 `17/18`，AI分数 `0.449757`，Top8 门槛 `0.551784`，距门槛 `0.102027`；主要拖分项为 60日净贡献 `-131,810` 排名 `18/18`、120日净贡献 `-156,440` 排名 `18/18`、60日最大单日亏损 `-106,050` 排名 `18/18`、120日波动 `13,676.56` 排名 `17/18`。
  - Stage929 验证退出码 `0`，`order_api_called_count=0`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_summary.json`
- orders：不适用
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：
  - 后续 16:35/21:05 Stage929 邮件不仅会展示最终交易信号，也会展示底层候选为何没有成为最终可执行指令。
  - 对 `lc.GFEX` 这类问题，邮件中能直接看到“AI池未入选、排名、分数、Top8门槛、主要拖分项”，不再需要人工翻 CSV。
- 是否进入下一步：是
- 下一步：
  - 观察下一封真实 16:35 邮件手机端排版；如果候选过多，再做摘要优先级压缩，例如只展示前 5 个或只展示 AI 池阻断候选。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本次不改策略参数、AI 排序、品种池、风控或下单逻辑，只把已有只读输出翻译进邮件。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：有价值
- 原因：
  - 实盘自动化必须让手机邮件直接解释“有无最终交易、为什么候选被过滤、是否需要人工操作”。这能降低误判和误操作风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
