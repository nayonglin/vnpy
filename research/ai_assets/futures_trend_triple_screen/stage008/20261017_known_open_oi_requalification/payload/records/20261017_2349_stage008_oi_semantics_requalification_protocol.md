# Stage008 正确OI字段合同下重新验收既有单窗口数据

- line_id：futures_trend_triple_screen；冻结时间2026-10-17 23:49 CST。
- 性质：零网络、零金融、零策略变更的既有数据重新资格审查，不重下载，不覆盖Stage007原拒绝证据。

## 根因与调研判断

Stage007标准TqBacktest历史流实际成功获取345根完成分钟；原CSV日线七字段全部匹配，主库只有被当作closeOI的字段不匹配。原`import_tqsdk_all_futures_daily_to_db.py:115`明确把`row.open_oi`写入`BarData.open_interest`。目标及相邻两天SQL与原CSV也证实DB字段对应openOI：Aug12主库1,064,817，CSV openOI1,064,817、closeOI1,053,986。

这是原验收合同错误地解释了DB字段，不是正规数据权限失败，也不能据此认定分钟价格错误。沿用Stage007已核官方文档/GitHub和完成K线定义，按精确目标及来源语义重新审核，不能修改原值或用新字段掩盖差异。

## 重新资格合同

1. 输入仅Stage007 `network_attempt1/raw_completed_minutes.csv`、`completion_evidence.csv`及原receipt/quality，精确同SHA原日线CSV/DB、原helper和上述导入器源码。先确认原输入指纹未变、网络只1次、金融回放0；本阶段无TqApi实例化。
2. 345个唯一目标分钟、原夜盘网格、全部合法OHLC/量仓、逐行后继完成证据须通过；不把最后形成中K线补进来。
3. 原日线CSV继续核OHLCV、首openOI、尾closeOI七字段；目标真实DB只核OHLCV及其`open_interest`与首分钟openOI。DB未提供独立closeOI，明确标记N/A；不得伪造或把它写成“DB closeOI也匹配”。
4. 保存旧quality拒绝原因和新字段映射依据；输出单独requalification.json、证据小表/manifest，引用原raw而不改写。只有正确合同的全部必需项通过才能标本目标合格。
5. 小测试覆盖“DB=openOI而非closeOI”的反例、DB价格/量/openOI错误拒绝、完成证据不足拒绝；不重测SDK授权、不重跑已完成账户或旧周表。

## 边界及下一步

仅证明这个目标session可作为后续研究数据候选，不证明全部账号历史权限或整个候选数据覆盖。Stage007原来的`completed_quality_rejected`及源码保持原字节，不能回填成原验收就成功。

正式/对照策略继续使用既有DB的OI口径，不把此次数据合同修正混为将策略改成closeOI。任何同日closeOI信号研究属于另一个未来版本，需独立预声明A/B。

本阶段不自动写base/overlay、不批准C0_attempt3。完成独立复核后，再制定一次性批量需求计划（初始信号、换月OPEN与普通CLOSE分别列示），以实际需要收集完成数据，避免逐缺口金融回放。

过拟合判断：否，修正来自导入器源码/字段数值关系，未读PnL、不调整策略。继续价值：是，保留真实新数据并修正验收语义，避免把正确分钟误判为不可用，且不扰动原策略基准。
