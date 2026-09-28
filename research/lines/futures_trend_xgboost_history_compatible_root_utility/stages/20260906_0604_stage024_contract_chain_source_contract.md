# Stage024 合约链来源重建合同

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 时间：2026-09-06 06:04 CST；模式：有界数据来源实验，不是策略回测。
- 是否重要突破：否；reviewer：0；既有授权覆盖研究数据重建，不重复申请。
- 原目标保持：2020-01-02至2026-08-28、15万元、同一冻结A，最终要求收益提高且最大回撤下降。

## 排重与研究判断

- 旧Stage049-053已有合约OI占比、OI排名、前两大合约集中度和主力映射变更；旧curve-account有期限结构、OI/volume HHI和OI加权期限相对rank10的差值，固定模型已失败。禁止复活这些阈值或把同一模型换名。
- 尚可核查的不同对象是入场实际合约相对其他交割月的持仓迁移速度，严格使用决策前完整交易日。此处只查来源，不读取特征-收益关系，不预设临期必然有害，也不生成模型值。
- [CME Pace of the Roll](https://www.cmegroup.com/trading/paceoftheroll/user-guide.html)将逐日OI变化用于观察换月；[LEAN示例](https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/BasicTemplateFuturesHistoryAlgorithm.py)展示合约链、到期过滤和OI读取。两者只支持可观测机制，不证明本策略alpha。
- [Daal等成熟效应研究](https://citeseerx.ist.psu.edu/document?doi=0c20f6e87e3a28d72de5cc32fae49f91986bb929&repid=rep1&type=pdf)报告多数合约不满足统一成熟效应，故拒绝固定单调临期过滤。

## 已确认缺口

- 旧全市场normalised_daily_bars为894144行，2021-01-18至2026-06-30；原SHA仍为`f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
- 旧目录4603合约，缺原276事件涉及的29个合约；该目录本来按较晚source_start过滤，不把此缺口当成供应商不存在历史。
- 冻结回放源数据库SHA仍为`a683e8d99c1925ef2af546e62b61f62c9946d21ea4e5be4af42737a80f77eef5`。2019-12-31/2026-08-27日线总行数210/37，尾部不能当全链；此行数包含其他类型合约，不解释为完整普通期货数量。
- 回放contract_metadata仅86行，主要为品种连续合约，无expire_date或delivery_year/month，不可用来猜逐合约到期日。

## 唯一目录资格执行

1. 保留原276事件、18非FU品种、189实际合约的完整身份集合；只读event_id、decision_date、product_vt_symbol、contract_vt_symbol，不读原特征值或标签。
2. 复用安装版TqSdk的`TqSim + TqBacktest(2026-08-28,2026-08-28)`；仅查询18品种普通期货的目录与元数据，含已下市。每批最多80合约，不创建真实交易账户，不调用下单接口，不修改共享数据库或映射。
3. 保存供应商返回的必要原始元数据，再复用旧normalise_catalog，数据起点2019-11-01、终点2026-08-28。保存供应商delivery_year/month与expire_date，拒绝缺失、重复、非法年月和代码年月不一致；不按代码猜真实到期日。
4. 原189实际合约必须全部在目录且产品身份、事件日期不晚于expire_date。结果只能称目录必要条件，不是全链行情覆盖或历史版本PIT认证。
5. 原始元数据范围外的合约按事前起点剔除，所有原返回记录保留。目录成功才制定行情获取清单；本阶段行情下载0、策略回放0、历史fit/predict/标签0。技术错误保留失败回执，不循环重试；不按已知盈亏删事件或缩区间。
6. 数据源输出只在本线`artifacts/stage024_contract_catalog/`；禁止覆盖已有输出。冻结代码、测试、合同、事件源、被复用源码及安装版API身份，查询前后检查不变。凭证只由vn.py现有设置读取，不打印或保存。

## 反思与后续

- 开始过拟合判断：本次否，只核查预先限定的身份与来源；整个反复历史研究仍有选择偏差。源码/数据资格不能当样本外成功。
- 开始继续价值判断：是，实际合约链机制缺少全周期可信来源，先验证必要元数据可得性；若不合格就不付出全量行情与模型成本。
- 没有新增/修改/删除回测结果；权益、收益、回撤、Sharpe、滑点、交易数和胜率均不适用。Stage009/016冻结失败结论不变。
