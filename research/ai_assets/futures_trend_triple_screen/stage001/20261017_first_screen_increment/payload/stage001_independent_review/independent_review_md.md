# Stage001 当前阶段独立审查结论

- 时间：2026-10-17 22:46 CST。
- 独立审查者：`first_screen_independent`。
- 结论：**周状态与入场门实现审查通过，A0_attempt2金融结果已独立验收；C0首次路径因真实分钟开盘缺口严格失败，未完成金融验收。当前不能判断第一层滤网的收益/回撤增量，也不能给出策略晋级结论。**
- 生产资格：始终`false`，未连接CTP、未调用真实订单/撤单API、未改正式策略源码或发布物料。

## 已完成的独立证据

1. 周缓存77,368行以独立标量EMA递推复核，未导入实现模块；上一完成ISO周、35完整周边界、缺失重暖、ready/方向/asof/计数全部零差异，有效hist最大绝差`6.93e-14`。五类输入/模块/测试/输出SHA匹配，未访问策略未来PnL。
2. 源码调用链证明C0门在原flat-entry plan后、原规划器并发/增量预算之前拦截，实际open/reserve/target副作用在后；原AI等拒绝原因保留，unknown保持A0。真实产品键大小写P1在首次账户运行前发现并修复。retry、rollover、已有仓位退出未覆盖。
3. 四项已接受修复源码SHA与A_final3匹配，原分钟缓存SHA固定，真实settings/effective_parameters与旧A仅归一化共同空供需目录后完全相同。m0008身份漂移显式保留，离线权限没有冒称生产资格。
4. 首A0因sklearn1.6.1消费者加载1.8模型而失败。冻结1.8全栈恢复、固定5行概率手算smoke、无模型fit或字节变更；A0_attempt2在新目录完成。两次失败attempt均完整保存，没有覆写。

## A0_attempt2金融复核

|指标|独立核验值|
|---|---:|
|期末权益|2,262,595.00|
|总收益|1,408.3967%|
|最大回撤|-48.78985%|
|Sharpe|1.367364|
|总滑点|605,450.00元|
|总成交fill|816|
|完整合约cycle|402|
|母订单+同日retry完整episode|318|
|该episode胜率|35.53459%（113赢）|
|broker10峰值|63.12423%|
|超100%/90%及破产日|0 / 0 / 0|

现金流加逐日持仓市值相对权益最大残差`3.73e-9`元，内部权益残差`1.86e-9`元，成交成本残差0；所有主要metrics独立重算一致。84个retry具备真实母订单继承证据，8个换月open具备同日targeted目标合同/方向/手数证据。期末1个未平仓合同净盯市4,800元纳入守恒。501条分钟扫描请求全complete、missing0。

独立旧账哨兵直接比较A_final3原CSV：1,641日11个经济/持仓字段最大误差全0，816fill的10个身份/经济字段逐项精确相同，A0成为本轮可信固定对照。

886个flat-entry计划对应886条实际候选，A0无拦截；原生可开328条中ready270、unknown58。固定19产品全日历覆盖74.82%含未上市日，不能替代该候选分母。完整episode按普通母订单及其同日retry合并，换月新合约订单另计，未冒称跨换月趋势母信号。

## C0未验收的具体原因

`C0/run_failure.json`的原bar异常为：`2020-05-18`、`rb2010.SHFE`、缺物理时刻`2020-05-15 21:00:00`的开盘anchor。按照已接受冻结会话合同，周五夜盘属于下周一交易日；该日已在2020年夜盘停盘排除区间之后。独立对原冻结分钟cache做精确合约/两日期定位，rb2010在2020-05-15和05-18均为0行，确有缺口，不是把自然日误当交易日。

该异常由严格开盘anchor门抛出，vendor即使吞掉bar异常，外层guard仍拒绝完成。目录仅attempt_started、空engine.log、run_failure，没有daily或metrics，因此没有C0完整路径可用于收益、回撤、胜率、被拦样本或成本比较。**不得把C0缺数据时的部分账户或乐观日线代理当成滤网负/正结果。**

目前未进行C0诊断循环、下载或扩大行情清洗。若继续，只能先取得可证明来源的这个新路径所需分钟数据，冻结为新输入身份并另建attempt；不得静默改原cache、放松严格门或扫MACD参数。

## 剩余限制与判断

- 保留P2：未来首次有限观测会改变历史`reason`的“全缺失/上周缺失”文字诊断，但不改变交易字段。reason只允许诊断，禁止用于交易、AI字段和资格判断；本轮不因标签重算周缓存。
- 已验收的是A0完整历史单路径和导出守恒，不是新严格OOS、独立起点、成本压力、原始供应商全市场QA或生产资格。模型/策略原有历史选择偏差保留。
- C0候选可验收性当前被数据门阻塞；没有新增策略alpha P0/P1结论，也没有可晋级候选。

调研与判断：[pandas官方窗口文档](https://pandas.pydata.org/docs/user_guide/window.html)、[官方EWM GitHub源码](https://github.com/pandas-dev/pandas/blob/main/pandas/core/window/ewm.py)支持计算语义；[scikit-learn官方持久化文档](https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations)支持冻结生产者/消费者环境的必要性。公开资料不能替代本地账户证据，也不能证明经典三重滤网必有alpha。

开始与结束过拟合判断：本次未按收益调参，新增选参型过拟合为否；累计已见历史风险仍在。继续价值：是，先以最小、可溯源补齐分钟数据完成这个固定假说的反证仍有信息价值；当前不值得跳过数据门或扩大参数搜索。

详细证据：`weekly_independent_checks.json`、`static_review.md`、`A0_failed_attempt_checks.json`、`runtime_restore_checks.json`、`A0_attempt2/account_checks.json`、`A0_attempt2/baseline_sentinel_checks.json`和`C0_failed_attempt_checks.json`。独立审查未运行任何金融引擎。
