# Stage029 v2：无效周止损候选拒开与新增铜合约schema

- 时间2026-10-26 19:43:21 CST；line_id=futures_weekly_formal_no_half_r。用户已确认前三项；本修订为在任何完整收益可见前的确定性可执行性定义，不调止损价/参数、不择源、不延期。
- R_attempt001原v1在2015-03-16失败，未有完整财务结果：rb1510.SHFE周中short换月，周末2015-03-13止损2516，而当日计划参考2520。原guard方向错误合理拒绝；底层吞callback异常使最终表象KeyError。原v1代码e222b65a8951af1e30052d1a5fd172ac2a89b166dbb96f2bb2319c548157b452、旧runner、失败attempt/terminal/guards/inputs全部保留不改，绝不追认v1完成。
- **合同实质修订**：仅对“合格已完成周stop为有限正值、方向已不合法”的候选，把整回放硬失败改为订单级selected_volume=0拒开，并导出signal_date+contract+direction+entry_context、原stop、计划close、周末日期、zero size及未评估预算闸门。long stop>=plan、short stop<=plan均统一拒绝；不用abs距离制造可开仓风险，不移动stop。有效候选直接调用父级原sizing，保持其它参数和全部guard。原v1_open_position和_entry_stop_price硬闸不移除，不允许绕过零手数；缺周/非有限/非正值/未来日/epoch/未知方向仍硬失败，不catch通用异常转零。
- 换月旧仓仍按原5交易日逻辑关闭，新约无效则只拒新开，不延长旧仓/不新target/不占用预留。后续合法日期可重新按本来信号逻辑参与，不按合约永久黑名单。v2不等同原始v1合同，报告必须明示该差别与失败边界。
- 新代码以stage029_week_close_exits_v2.py及独立新测试实现，继承冻结v1；诊断/验收新增invalid_weekly_stop_rejections。旧v1 guard记录不得过滤伪装通过；v2拒开单列，证明0新开成交/0实际目标与预留。原initial_stop_audit只含有效sizing，v1基本audit继续有效。
- 可选异常溯源改进仅在新wrapper登记intraday_execution_failure并原样re-raise，禁止转小仓/改价；保证真实guard失败优先于calculate_result KeyError显示，不影响成功路径。
- 最新日输入schema预声明：fresh26主力新纳cu2612.SHFE，它不在旧N002 sizes/slippages/rates selected键集合。仅允许这一个具体合约新增到sizes/slippages/rates、以及setting/actual中margin_ratio_overrides的同键；值须与冻结产品规格/新mapping metadata构建一致；原所有键和值/其它字段必须精确不变。R仍只允许enable_rsi_partial_exit由True变False，以及路径归一化。不得借schema新增改旧合约费用、规格或保证金。
- Q26截至23前缀证明：原N所有既有财务键/字段精确复现；新cu2612零仓positions/已声明周源可额外出现，但旧日权益、成交/anchors、候选与events均不得改变。新增cu零行必须start/end/trade/PnL/fee/slip均0。不能只比headline或删除不一致行。
- 新完整金融attempt计划：R_attempt002=候选v2同旧截止23；Q_attempt001=原策略同新截止26；R_attempt003=候选v2同新截止26。每完成一臂即独立review，旧控制N002复用。未见完整性能前冻结本修订；不新增阈值试探。仍NO_PROMOTION，数据与PIT局限沿用。
- 反思：未新增数值拟合；但规则是在一次失败后补全，必须披露为v2，不能以“工程修复”抹掉研究合同变化。拒绝方向无效的有限风险头寸比挪动止损或借日K救价符合用户周线止损意图，因此继续固定回放有价值。
