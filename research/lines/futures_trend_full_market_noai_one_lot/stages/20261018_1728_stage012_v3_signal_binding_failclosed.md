# Stage012 第三次回放的开仓状态闸门失败

- 时间：2026-10-18 17:28 CST；重要突破：否。真实金融启动累计3，完整完成0。
- v3在2015-07-30、成交计数BACKTESTING.134处停止。实际stack明确Stage827 line199，即当前state不存在或方向与open不匹配；不是line205的layer日期/数量匹配失败。
- 该次35项测试通过后启动，code_start_hashes已保存；protocol/日志/失败收据保留。failure_snapshot为空，不足以法证具体合约，不能臆断品种或以此设置黑名单。
- 开仓成交价同步由先前静默漏更新改为严格校验后暴露此问题。旧target在state reset后残留/重挂可以产生此路径，需合成测试确认并以当前有效唯一pending layer作为开仓资格；失效开仓禁止成交，不凭空重建layer。
- 另有效pending layer可能跨缺行情日重挂，订单重建日不能冒充原始signal日；严格唯一匹配contract/direction/unsynced one lot，不使用未来信息或任意选择层。
- 新增/修改/删除有效回测结果0；期末权益/收益/DD/Sharpe/滑点/交易/胜率均N/A。未生成结果HTML。独立agent继续审查本失败与RED行为fixture。
- 开始/结束新增过拟合：否，未依收益选择版本；继续价值：是，修复信号意图与实际委托身份的一致性。所有固定参数不变。
