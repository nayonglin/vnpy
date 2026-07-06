# Stage069 Stage013 full-cycle intraday stop

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T20:43:56
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否；这是执行/退出 overlay 研究，不是 alpha 新信号，本轮不晋级
- 是否触发A/B：否；未达到可晋级结论前只做隔离研究

## 外部调研与判断

- Backtrader stop order execution 文档提示 stop 触发和成交价要区分；本阶段把开盘穿越 stop 记为更差开盘成交。
- CFTC/CME 对期货 stop with protection 的说明也强调触发价不等于保证成交价；本阶段不做完美成交假设。
- 本次判断：只用原策略已经存在的动态保护线，不扫 R 倍数、stop buffer、重进次数、日期或品种。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage069_stage013_fullcycle_intraday_stop.py`
- 修改正式入口：无
- 删除文件：无
- 新增研究参数：`enable_stage069_fullcycle_intraday_stop`、`stage069_daily_reentry_once`、`stage069_max_reentries_per_day=1`
- 修改正式参数：无
- 删除参数：无

## 回测参数

- 起点：`2021-07` 到 `2026-01` 逐月，共 `55` 个起点/臂
- 终点：`2026-07-02`
- 对照臂：A Stage013 baseline；C1 全周期动态保护线分钟止损不重进；C2 全周期动态保护线分钟止损、每天最多一次收复同一保护线重进
- 资金：`150,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_candidate_ai_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`

## 结果摘要

- A baseline：正收益 `37/55`，最小/中位收益 `-25.9013%/13.0154%`，最差回撤 `-49.2195%`，最长水下 `1070` 天，总交易 `9801`。
- C1 no reentry：正收益 `31/55`，最小/中位收益 `-40.7410%/25.2059%`，最差回撤 `-63.4046%`，最长水下 `556` 天，总交易 `9787`，Stage069 事件 `728`。
- C2 daily reentry：正收益 `24/55`，最小/中位收益 `-42.8993%/-16.3664%`，最差回撤 `-63.9587%`，最长水下 `820` 天，总交易 `10992`，Stage069 事件 `787`，重进 `576`，二次失败 `480`。
- 分年观察：C1 在 `2022/2023` 启动月明显改善，但 `2024/2025/2026` 启动月明显恶化；C2 在 `2024/2025` 几乎全线恶化，且重进后再次失败比例高。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数见 summary/variant_summary；胜率不在本阶段新增，避免合成重进场成交被误读为独立 alpha 胜率。

## 统计口径 Review

- C1/C2 只改变 prev2day/base/layer 动态保护线的日内触发时间；AI 月度池、入场信号、仓位计算保持 Stage013。
- C2 的重进锚点是同一动态保护线，不是原始入场价；同一根分钟K不允许先止损再重进，重进从下一根分钟K开始搜索。
- 开盘直接穿越 stop 时按开盘价成交，避免止损价完美成交偏乐观。
- layer partial stop 也可被分钟线触发；只有全仓边界允许每日一次重进。

## 独立审计补充

- 独立 agent 复核结论：研究线内只读反证结论有条件通过，数据支持 Stage069 不晋级。
- 高风险口径：base/layer/profit-lock/trailing 类动态保护线可能先用当日完整日K更新，再回扫当日分钟线触发，存在执行顺序/PIT 风险；prev2day stop 边界来自前两日，相对安全。
- 因此 Stage069 不能作为执行级精确日内止损证据，只能作为反证和诊断；若继续，应先改成分钟级顺序更新或只使用开盘前已知边界。

## 结论

- 决策：`stage069_fullcycle_intraday_stop_keep_research_only`
- 原因：全周期动态保护线日内止损是结构性风控尝试，但本轮没有同时改善最小收益、最长水下和最差回撤；每日一次重进场显著增加换手和二次止损，说明“止损后当天收复同一保护线即重进”这条规则在震荡段过于敏感。

## 后续规划和 TODO

- 停止 C2 这种“当天收复同一保护线即重进”的形状，不做 stop buffer / 次数 / 品种救参。
- C1 只保留为诊断工具，不晋级；如果继续研究，应转向更慢确认，例如收盘确认、次日开盘确认、账户状态门槛或储备金层，而不是日内立即重进。

## 过拟合反思

- 运行前：否。规则来自结构性执行问题：把已有动态保护线从日线收盘触发提前到分钟触发；不新增产品、日期、R倍数或窗口扫描。
- 运行后：否。三臂固定、全月起点复验，不按 2022/2023 个别路径调整阈值；若后续开始调 stop buffer 或 reentry 次数才会转为过拟合。

## 继续价值反思

- 运行前：有。Stage068 已显示持仓后亏损大于开仓日亏损，且止损触发到成交存在额外损耗。
- 运行后：有，但只作为反证和诊断继续有价值。C2 已经被证伪；C1 说明日内止损能缩短部分水下但会牺牲左尾，下一步更有价值的是慢确认/资金层，而不是继续调同日重进参数。
