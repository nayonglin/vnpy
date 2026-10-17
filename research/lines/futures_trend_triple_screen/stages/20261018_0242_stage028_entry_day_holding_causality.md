# Stage028执行前补充：条件入场当日的持仓行情边界

- line_id：futures_trend_triple_screen；2026-10-18 02:42 CST；在任何C_TS金融收益前固定。
- 来源：root直接读取原on_bars、_process_layer_stops、_update_dynamic_stops与新adapter，发现分钟层正确仍不足以保证收盘持仓逻辑正确。

## 必要修正及其机制

若D上午曾触及80，11:00才以111条件入场，入场以后最低108，原D全日low80不能被当作该持仓入场后的base/prev2day止损命中，也不能污染layer的持仓极值。这是时间边界问题，不是见到策略收益后改规则。

最小接合点为研究策略的`_build_daily_env_gate_snapshot(day_contexts)`：先让原实现用真实完整D日线/history计算原环境快照，再仅对D内真实conditional entry且收盘仍有持仓的context替换持仓用target_bar/同合约actual_bar。视图为原bar的独立copy：O=真实首次母entry fill；H/L只从真实分钟>=该entry所在分钟聚合；C、volume、OI仍保留真实D收盘可见原值。AM、指标history、native信号、AI和原环境快照均保留完整D市场日线，不把持仓区间bar误作市场指标输入。

首触发分钟的不利极值可能发生于入场前，也按既定保守合同允许发生于入场后；其pre-entry open不用于持仓价格。整根更早分钟一律排除。母单0.5R/retry仍按首次母entry以后的共同日管理语义，不另做只截取retry在场区间的新规则。下一个交易日恢复完整当日bar；普通、unknown回退、已有仓与roll路径不改。

精确后缀分钟缺失必须fail-closed；不得退回D全日H/L。原指标/账户估值已按真正Dclose计算，这一步不在盘中使用收盘数据分配数量，只修正D收盘对刚建立持仓的价格观察域。原生手数q/S及七门不变。

必要验证仅一个新反例RED/GREEN：上述80/111/108场景，持仓context low须为108，原bar/history/AM/env仍保留80；再核普通路径不变与缺分钟拒绝。无需重跑FI/原始数据资格或金融基准。

本补充无金融结果，金融累计仍5attempt/2完成；不是收益突破，production_qualified=false。开始/结束过拟合判断：否，未看新PnL，只修复已直接证实的先后边界；继续价值：是，否则条件入场对照会混入根本不存在的持仓前止损。总目标保持active。
