# Stage021 平仓原因展示修复：独立验收

时间：2026-11-01T16:23+08:00；研究线 futures_weekly_short_ma_slope_gate；审查基准 bbe3f5971cd974c14f36f74e511b2341afc18bfa。审查对象 tools/Stage021_exit_reasons.py、对应test以及artifacts/stage021_2026_exit_reasons。结论 PASS_WITH_LIMITATIONS，未解决P0/P1/P2均0。此为纯展示修复，不是策略或金融结果变更；不是重要alpha突破版本，没有新增/修改/删除策略参数。

原Stage020的18完整轮次全部保留，36成交、8盈10亏、净利润22380、滑点2930/手续费0/残仓0不变。将每条新records仅删除meta.exit_explanation后，整个旧对象（包括全部行情、MA、坐标、PnL、成交及旧metadata）与已审Stage020严格相等。summary仅page_title及exit_explanations_added变化；chart_manifest.csv、closed_rounds.csv字节完全不变。故继承Stage019/020已封金融和行情审查，不重新跑其完整账本审计或金融引擎。

本次独立数值/来源502项通过。每条actual close以close_trade_id唯一对应原fills，按order_id对应唯一execution anchor，再按signal_date/symbol/raw_reason唯一对应trade_events，核成交手数/价格/自然时间/交易日和计划参考价。18actualclose恰用一次，没有将原2/27 hc2605/rb2605未产生对应actual fill的计划事件当成本18轮退出。exit_reasons.json与18条metadata逐项相等。

退出类别为周线技术保护9、风险组压力7、组合保证金风控1、换月1。具体规则独立读冻结源核实：

- prev2day历史命名在此配置实际是前两根已接受完成周K，stage029_week_close_exits.py:158–178以fresh完整周、同epoch、入场后至少2接受周替换父history；qmt_roll_portfolio_strategy.py:7593–7613取前两周低点并使长仓保护线只上移。四条显示没有误写两根日K。
- 基础仓保护由stage029_week_close_exits.py:142–155周末更新动态线、:184–200只接受新完成周收盘确认；qmt_roll_portfolio_strategy.py:7689–7715触发基础层即全平，:7021–7030是长close≤stop/短close≥stop，并非盘中high/low触价成交。底仓止损标签配文明确当时有效动态线，没有称固定2%亏损；实际本5条中4条long最终盈利，不从原因名称反推损益。
- 9条技术退出逐一对应原weekly_stop_audit的fresh/week_end/weekly_close/stop_price/triggered，确认不把signal周收盘当下一实际开盘成交价。四条前两周保护另对同物理epoch weekly_bars的前两完成周极值及入场后周龄，全部通过。
- qmt_roll_portfolio_strategy.py:7748–7803风险组压力降仓，与:9302–9349标准化回撤压力×max(组保证金压力,浮亏压力)对应；0.4不是保证金40%或亏损40%。实际配置适用base,add,donchian，本7轮全平。原退出事件未捕获当时压力，页面明确未封存而不伪造。
- qmt_roll_portfolio_strategy.py:7866–7957为另一条组合保证金风控：模型margin×1.65/E超过95%，目标80%，优先削减大占用仓。页面不把它冒称券商真实强平，不虚填原事件未封存的当时组合比率。
- 换月MA610→MA611，冻结rollover_delay记录9/29 scheduled、10/13经过5交易日due，10/14真实关闭7手；rollover_shape_same_volume显示final_volume0、skipped/no_positive_volume_allowed，页面如实写新合约未开仓，没有冒称已开新合约。

独立Node MCP对实际HTML的3内嵌脚本语法解析通过，并进行236项轻量DOM/Plotly.react参数模拟：全部18张原因卡片与已审metadata一致，平仓hover及annotation正确，切换/排序/盈利亏损筛选跟随当前交易，空筛选清掉上笔原因，只有无可绘分钟周期时原因仍跟随当前交易。旧的默认周期、全部可用period共享axes.matches、36成交标记、18/8/10筛选也保持；HTML内嵌records/summary与已审外部JSON一致，年度PNG仍是同一SHA字节。9作者纯Python测试独立重跑通过。不将root另份467检查与我236相加冒称独立唯一覆盖。

最终输出所有生成SHA及全部source pins实读相符，源Stage020冻结generation/acceptance与原74金融文件保持；源码本次只加入展示解释和小HOOK，不更改canonical行情聚合、坐标、缩放或其他研究线。根实现中的setting与actual在相关风险字段值一致，差异仅两个非策略资本字段，没有拿预期参数冒称实际参数。

浏览器状态：blocked_by_file_protocol_policy。真实Plotly绘图、实际像素和鼠标缩放仍未验证；236项是静态语法及合成DOM逻辑，不能写成浏览器PASS。没有尝试替代浏览器、rawCDP、HTTP服务或其它绕过。

置信度：对18条冻结退出来源、规则解释、保留的旧数据、JS逻辑较高；实际浏览器渲染未验证。零手续费、固定滑点、静态margin×1.65、历史PIT/容量及研究即时补资与人工实际资金时延差异沿旧审保留。此HTML不能新增生产或多周期资格（NO_PROMOTION_FROM_DISPLAY_REPAIR）。

调研与判断：按requesting-code-review独立复核以及既有recap合同和冻结源码，不需外部策略资料；没有新增调参性过拟合，既有样本展示不是新OOS。继续价值：有，补足用户指出的真实退出规则与当笔依据，保持既有数值不动。TODO仅主任务封外层交付并提供本地文件，浏览器限制继续明确披露。本次无金融重跑、行情下载、CTP/SMTP/生产、Git/index或HTTP服务操作。
