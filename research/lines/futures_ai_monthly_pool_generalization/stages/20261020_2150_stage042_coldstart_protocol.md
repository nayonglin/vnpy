# Stage042 全月flat冷启动future60 source覆盖诊断协议

- 2026-10-20 21:50 CST，line_id=futures_ai_monthly_pool_generalization；执行前协议，非重要突破。所有98域×201月末=19698行预先保留。
- asof普通非_F/非固定fu、本日AM41ready、截至本日过去120共同source日都有代表才eligible；不读取未来覆盖决定候选。fu固定行、_F分域、不足或缺失行均保留。
- 全新研究目标：eval日Dclose flat开始，可排eval信号D+1 entry，至future第60共同source日Dclose的连续净unitR；包含普通平仓后fresh重入与roll，不是原108源或旧目标。qty/roll_qty固定2是本研究归一化delta，不称正式量；fresh普通新entry重定本episode初始R，roll保持原episodeR。
- target及fresh取Stage040当日代表，无未来complete换约；held epoch bar/AM41单独从cleanDB取，不能用新代表顶替。每天必须显式fresh_signal None或字典；未来ready/代表缺失即未知，不伪造无信号；不可恢复的未知保持。
- 所有daily.open anchor明确evidence_id daily-open-assumption，执行时间source日期T00:00:00/logical_bar_label_not_physical=True，不伪装09:00或真实session；分钟路径默认None。C2保留且只有daily neither/confirm条件识别，stop/both保留未知；halfR/retry关闭只本训练源。
- 经济源Stage006静态historicalFalse，byvolume/bymoney结构映射，缺失保留None；显式extra slippage0是base-reference，不是压力过关；configured guard tick与LC历史effective fill tick分开。非tick grid的源价不round救活，转unknown。
- 先TDD、固定12分层product-month pilot含AU/JM既有月末及no-signal例，核时钟/费用/未知语义后自动全量。原库每product一次只读，缓存同epoch41/history，最多4workers，并与root协商CPU。全量仅存逐row小summary；固定pilot/每种异常首例保留fulltrace，数据/代码bindings可复现。任何异常保留input_error行，不丢cohort。
- 新增模型/alpha参数无；qty2与冷启动目标/逻辑open为明确研究定义，不是择优。预期金融账户权益/收益/回撤/Sharpe/滑点/真实交易次数/胜率N/A；fit、下载、订单、正式修改均0。实际条件source数值与覆盖单独记录，不称正式绩效或训练资格。
- 调研判断沿Stage010/021官方vn.py/GitHub和本线冻结source/Stage039合同：asof候选与未来成熟分离，未知路径不能直接重排top-half。开始新增收益选参过拟合否，阈值未扫、未看结果改源；继续价值是，量化全池robust rank可识别性而非追求漂亮回测。结束反思随结果记录。
