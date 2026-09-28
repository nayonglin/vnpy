# Stage024 合约链元数据重建缺口

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 当前模式：研究数据来源资格，不是策略回测。
- 时间：2026-09-06 06:07目录查询完成；06:09指定合约探针结束；06:12记录。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 是否重要突破：否；是否触发新A/B：否；reviewer：0。
- 上一目标轮分类：仅确认reviewer规则，无新增研究证据；本轮通过实际查询取得新目录并查明全周期缺口，属于证据进展，不是目标达成。

## 调研与判断

- [CME换月进度说明](https://www.cmegroup.com/trading/paceoftheroll/user-guide.html)使用逐日OI观察合约迁移；[LEAN官方示例](https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/BasicTemplateFuturesHistoryAlgorithm.py)演示合约链、到期过滤和OI读取。判断：可支持来源与经济机制核查，不支持直接承诺收益。
- [成熟效应原论文](https://citeseerx.ist.psu.edu/document?doi=0c20f6e87e3a28d72de5cc32fae49f91986bb929&repid=rep1&type=pdf)报告6,805个合约的大多数不满足统一成熟效应；不采用“越临近到期越差”的固定单调规则。
- 已读旧Stage049实现：开仓合约OI占比、排名、前两大集中度、主力映射切换都不是新信息；旧curve-account六原始描述量和八特征Ranker已失败。不复活这些阈值或旧模型。入场合约相对交割月的持仓迁移速度仍只是待验证对象，未定义或生成新训练值。
- [TqSdk官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)与本机3.9.4源码显示query_quotes可包含已下市合约，query_symbol_info返回delivery_year/month和expire_datetime。文档中的“包括已下市”不等于承诺所有历史年份完整。

## 本次变更与执行边界

- 新增`tools/stage024_contract_catalog.py`、`tests/test_stage024_contract_catalog.py`和两份事前数据合同；Stage024B为一次性研究驱动，只保存生成的来源回执，没有保留通用运行工具。
- 原276事件、18品种和189实际合约全保留，只读四项身份字段。新数据起点2019-11-01，查询时点2026-08-28，目录元数据每批80，300秒超时；没有模型参数变化。
- Stage024复用旧normalise_catalog，但先独立校验有限数值、整数年月、布尔expired和合约年月一致性。只读现有凭证，通过TqSim/TqBacktest访问数据服务，debug=False，不连接CTP或真实交易账户，不调用委托接口。
- 输出仅在本线；不写生产、共享数据库/映射、其他研究线、registry或根总账，没有commit/push。

## 结果

- 旧重建源894,144行，覆盖2021-01-18至2026-06-30；其4603合约目录缺原事件29个合约。旧目录本来受source_start过滤，这不是供应商全历史不存在的证据。
- Stage024于06:07:00至06:07:08完成：目录列表1200个唯一合约，15批元数据共1200行；规范化仍1200行、18品种，没有本地起点剔除。原189实际合约中176个存在，13个不在供应商目录列表。
- 缺失合约：CF005、CF009、FG009、OI009、SA009、SM009（CZCE）；jm2005、jm2009（DCE）；au2006、hc2005、rb2005、ru2005、sp2005（SHFE）。影响20个事件，决策日期2020-01-08至2020-07-17，跨11品种；其余256事件元数据产品和到期日期匹配。
- 决策`catalog_gap_stop_no_bars`。没有生成开仓合约OI占比/迁移速度等新特征，没有批量获取行情。此处“元数据匹配”不是完整行情覆盖、历史发布时间/版本无修订证明，亦不是交易能力或alpha。
- Stage024B在06:09:34至06:09:38尝试两个时间上下文的指定13合约查询：2026-08-28、2020-01-08，均记录technical_failure/Exception，未形成原始元数据表。回执没有保留安全错误信息及具体失败步骤，故不能确定异常在API建立还是symbol_info响应，更不能把它写成供应商明确拒绝或所有历史不存在。没有循环重试。合同标题分钟06:10是近似预估，文件在实际06:09执行前已写入并进入输入冻结；不追改原合同。
- 新增/修改/删除回测结果均无：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率不适用。已有Stage009/016失败绩效不变，没有新的可晋级版本。

## 验证

- 15项新增单测先全部因实现不存在失败，再全部通过。06:07整套304 passed in 37.08s；SDK日志/错误输出小改后的聚焦15 passed；最终现有全部相关测试304 passed in 26.26s。代码无历史fit/predict、标签、策略回放调用。
- 目录缺13个合约的集合，以标准库CSV集合差与内存SQLite左连接分别复算，完全相同。事件范围、20个受影响事件和11品种分布由身份表直接重建，不读取盈亏。
- 15批原始CSV拼接与raw_catalog逐字段一致；1200个查询ID与返回ID精确相同。另用标准库datetime/ZoneInfo/Decimal逐条复算到期日、年月和代码格式，与规范目录一致。
- 复算首次把CSV的`2020.0`与`2020`当字符串比较而失败；定位为浮点/整数序列化表示差异，改为Decimal精确数值比较并重跑整个只读核验，exit0。原目录请求、冻结代码和产物均未重跑或追改。
- Stage024的6输入/19输出、Stage024B的6输入/1输出身份全部复核通过。Stage016、Stage022摘要哈希不变。生产06:09仍干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`；本轮所有运行及测试会话已退出。

## 冻结产物

- `artifacts/stage024_contract_catalog/summary.json`：SHA `417a26acd7d5a9553c76cf3d9438b022716f2e1c04319af45e3d2835f823b778`。
- `artifacts/stage024_contract_catalog/catalog.csv.gz`：SHA `d6071eb322c161ef1471aed17210ac4b9cb147e6e5e856646072251c97f27a40`。
- `artifacts/stage024b_explicit_contract_probe/summary.json`：SHA `6c8783da4523359399412e326280999c26a28c9cf2e38d4dbe27c690a5f3a14a`。
- 原始目录、查询清单、15批原始返回和输入冻结均在对应artifacts目录。没有orders/daily/model新产物。

## 结论与后续

- 不启动当前目录下的全量合约链下载、特征或训练；不删20个早期事件、不把旧数据库尾部主力数据当全链、不猜真实到期日，也不缩短完整回测区间。
- 下一步须追溯早期实际合约日线的原始供应商、导入脚本及可验证元数据，或者取得其他合法完整来源。不能再把“目录查询成功”当历史来源完整，也不重复本次相同接口请求。
- 此次元数据失败不反证XGBoost或所有持仓迁移特征；但目前没有充分来源证据值得付出完整行情/模型成本。全周期收益提高、回撤下降的总目标未达到，保持目标不变。
- 过拟合反思：本次否，没有收益调参、模型筛选或按PnL取样；全体历史反复研究仍有选择偏差，历史开发验证不得称真正未见样本。
- 继续价值反思：追溯可信早期来源是，重复当前请求或拿缺口数据训练否。基础测试自检，只有真实候选提高收益、降低回撤并有稳健性证据后启动reviewer。
- 只更新本线LINE；不更新registry、根memory/back_log或全局记忆。
