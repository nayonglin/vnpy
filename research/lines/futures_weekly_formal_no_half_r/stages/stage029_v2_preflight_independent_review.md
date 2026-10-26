# Stage029 v2 运行前独立审查

- 结论：**PASS_V2_PREFLIGHT_OFFLINE_RESEARCH_WITH_DECLARED_LIMITATIONS**；P0=0、P1=0、P2=0。允许按19:43修订合同执行R002/Q001/R003离线回放。无金融结果认证，无生产资格。
- 独立审查员：stage029_exit_design_review；本人金融回放0、下载0。仅新增本审查MD/JSON，未修改实现、旧回放或旧审查。

## 独立验证

v2冻结源码、测试及最终runner SHA均已重新读取匹配，详见JSON。22项v2测试由审查员独立重跑，全部通过；另独立重跑8项metadata delta测试通过。真实元数据纯构建确认唯一新增cu2612.SHFE：size5、slippage10、rate0、margin0.12、tick10；旧规格和保证金键值全保留。runner已显式断言和输出新铜tick/margin。

实际继承的_handle_rollover已由fixture调用：旧仓正常关闭、旧target=0并记录rollover_close，新仓selected/final volume=0、不创建新target或预留；拒开后另一个品种的每日margin减仓仍执行。真实核心sizing全字典与v1一致；Stage804多头更紧止损公式及有效路径adjustment事件精确保持，资格预检仅抑制重复事件并在finally恢复同一列表。

## 审查结论

仅有限正值周stop落有限正值计划价错误侧时，返回明确的零手数拒开。long stop>=plan、short stop<=plan统一拒绝；原stop/周末/计划价不改，预算标注not_evaluated。缺周、日期错位、未来周、epoch、未知方向、非有限/非正价格、metadata和父级sizing异常仍硬失败；不存在泛catch转零。原v1_entry_stop_price/_open_position硬闸和基础audit保留，guard记录不被过滤。

拒开有独立ledger，审计零size与ownership前后相同，并与flat/rollover候选上下文核对。实际open通过order_id连接anchor.signal_date，再核合约/方向/entry context；不能用成交日代替信号日，也不把同合约以后合法开仓永久禁止。缺anchor、拒开仍targeted/opened、所有权变化或关联开仓成交均拒验。callback硬异常登记engine failure并原样抛出，避免被后续calculate_result KeyError遮蔽。

runner保留双合同绑定、原19/15万/maxpos19、RSI唯一参数delta、旧来源与N002闭包、无AI/分钟/代理、实际日库、物理epoch、持仓正量覆盖、次交易日同约open及完整日历闸门。审查发现的一处旧类名标签已修正为WeekCloseExitStrategyV2；最终runner SHA已绑定。旧v1 adapter/test/runner仍与R001 input_manifest逐SHA一致。

## 研究边界

v2是看到R001执行失败后对拒单语义的实质修订，不是v1原始结果；旧失败及其原始物料不变。此前独立核过的2538来源和33条增量证据继续适用，但不把精确取值说成多源共识、全部历史正确或PIT证明。有效观察周跳自然周、Stage028源争议、主力历史时点、零手续费/静态规格/日open容量和重复样本内研究限制保留。全仓早先1652项仍有5 failures/45 errors，不宣称全仓通过。

金融回放每臂完成后仍需独立会计/数据/逻辑/置信度审查，硬失败或截断attempt不接受为完整绩效。未做数值拟合、挪stop或择源救参；但失败后补全语义必须披露为v2。继续一次固定证伪有价值，不表示允许晋级或扫描参数。
