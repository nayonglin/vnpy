# Stage006：全市场月度双向源的经济字段覆盖与最小来源边界

- line_id：`futures_ai_monthly_pool_generalization`；时间：2026-10-20 18:55 CST。
- 类型：小元数据只读聚合；非拟合、非金融回放、非正式比较臂；重要突破：否。
- 本轮只写本线 `outputs/stage006_economic_coverage/` 和本记录；不改 LINE/registry、其他研究线、正式物料、主行情或任务。
- 开始反思：新增按成绩调参型过拟合＝否；只问经济单位和来源是否可追溯，不读成绩选参数。继续价值＝是；全市场价格不能直接相加，先解决乘数、价格格点与未知来源，可避免伪排序增益。

## 判断

**现有资料足以支持冻结假设后的全市场隔离品种、单位风险双向研究源；不需要先重下载或重建全市场费用历史。**9502/9520 个有clean行情的真实epoch，有精确合约身份的vendor乘数、round_lot及可解释的tick/费用lookup。不能将这张静态快照当成逐日历史PIT条款，也不能直接搬用另一线的交易目标或现金政策。

18个缺精确条款的尾部epoch保留未知，不能乘数默认1、手续费默认0、用相邻合约期限解除未知。实际受影响accepted日线为36条，而不是把大批早期行情宣布不可用。未知出现在源/信号时应保留拒绝或结果区间，不删除该历史宇宙成员后重新排名。

## 调研与判断依据

本轮重新只读查验 RQAlpha 原作者 GitHub 的 [FutureInfoStore](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/data/base_data_source/storages.py) 和 [data_source.py](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/data/base_data_source/data_source.py)。lookup对精确 `order_book_id` 优先，再退到 `underlying_symbol`；该静态store没有提供历史effective-date版本。判断：可复用字段语义和身份优先级，不能因API有日期参数就宣称费用历史真值。

本机直接读 `stage265_deep_daily/rqalpha/futures_metadata.json`、`future_info.json`、Stage266 CSV inventory、`contracts`表、TqSdk规格CSV与`qmt_universe.py` AST。long-only Stage041仅作为已验收输入投影的交叉核对资料：没有读取该线标签、预测或金融成绩，没有承接其55/20信号、账户目标、成本数值或现金政策。独立实现合约归一化及原始metadata join后，9520键及9502已知epoch的乘数/round_lot/tick/两margin、费用type与三项费用率、期限字段均与原投影一致。

## 覆盖实数

| 字段/范围 | 本轮实读 | 适用解释 |
| --- | ---: | --- |
| contracts目录 | 10,880 epoch、98历史产品代码 | 身份目录，不是当年已发布上市公告 |
| contracts来源 | 10,862 RQ vendor；18 symbol-only | schema只有身份、listed/delisted/maturity和status，没有经济数值 |
| 原futures_metadata | 11,355条、10,862可归一真实epoch | 493条连续/不能归一身份未冒充真实epoch |
| 有clean行情 | 9,520 epoch、97产品、1,552,456行 | 本次仅从inventory求和，未重读价格 |
| clean精确epoch经济元数据 | 9,502 | 正乘数/round_lot、tick；费用为可解析非负数 |
| clean费用/tick lookup | 7,146精确contract；2,356产品default；18未知 | default保留独立来源标志，不能冒充合约历史记录 |
| future_info原表 | 7,574 unique键＝7,480 contract＋94产品 | by_volume或by_money；静态vendor快照 |
| margin来源分歧 | 2,164 clean epoch差异超过1e−12 | 两值同时保留，不能悄悄挑小者 |
| TqSdk产品规格 | 86行，86正tick/乘数 | 当前规格辅助；不是98域历史表 |
| qmt_universe | 18个显式ProductSpec，原RATES=0 | 正式旧域配置，不能当全市场零费用合同 |
| 无2010+clean行情的目录产品 | DCE.S，25个epoch | 保留母体，不造行情、费用或可交易样本 |

catalog三项生命周期各有18未知，均是上述symbol-only尾部；已知日期也只是vendor snapshot。日期非空不等于已经拿到当年公布时刻。

## 历史版本不能机械统一

清洗epoch中数值归一后，有14个“产品×字段”观察到多个乘数或tick值。以下为vendor合约元字段样例：

| 产品/字段 | 已观察版本（clean epoch数） |
| --- | --- |
| PB乘数 | 25（24）；5（169） |
| RU乘数 | 5（26）；10（152） |
| FU乘数 | 50（68）；10（126） |
| FB乘数 | 500（53）；10（92） |
| TS tick | 0.005（20）；0.002（15） |
| LC tick | 50（12）；20（33） |

不得用当前乘数覆盖历史；也不得将这些min/max标称月范围当公告生效区间，或把产品fallback与精确合约字段差异直接解释成真实改约。FU等值的范围有重叠，证明“按某个日期一次切换”的粗暴修补不可靠。全部观察汇总见summary的`multiversion_fields`。

## 可执行的最小来源设计建议

1. 固定身份：`EXCHANGE.PRODUCT.YYYYMM` join 精确epoch，保留CZCE十年区别及普通/F差别；本线普通双向筛选域仍按上游预声明处理F，不因数据或经济结果临时改域。
2. 先固定来源合同再生成金融源：每epoch保存乘数/round_lot；tick/费用按精确contract优先、product snapshot fallback。保留两份margin原值、费用类型、三费率、源SHA、scope与历史假设标志。可直接使用本目录CSV中的原字段，但本轮CSV本身不签发financial_ready。
3. 建议本线下一协议独立预声明单位风险双向源的手续费、滑点和保证金情景；不能不加区分地继承long-only现金政策，也不能把vendor收费当精确历史。结果至少区分gross、预声明base、stress，不按成绩择优保留一种。若目标采用R单位，分母使用入场前可知止损距离×历史epoch乘数，并明确成本是分子扣减还是计入初始风险，避免重复计费或事后归一化。
4. 隔离品种独立账户/单位风险：不借跨品种资金、共享槽位或后验pairwise，保证月度标签主要描述品种对统一策略的适应性。真实合约roll损益、交易成本和旧持仓退出应逐笔记账，不能拿连续价格跳空当经济盈亏。
5. 生命周期：listed/maturity/delisted作为快照假设使用；首根/末根bar只作可观察性，不拿未来末bar决定过往退出。真实合同月份不等于最后交易日。研究asof宇宙、可观察特征时刻、目标成熟时刻分别记录；缺未来价格/经济条款不是0收益或负类。
6. 18未知保留：这18个全是2027新尾epoch；当前不从donor复制期限或乘数。若下一协议生成信号碰到未知，应记录`economic_unresolved`及影响范围；缺项不阻止其他已知epoch的有界研究，但完整月份标签需明确未知对排名上下界的影响。
7. 现有small sources完成内容绑定即可推进；不必再hash 400MB DB，不应泛化成全市场金融回放前的大型公告工程。条款缺历史PIT限制历史精确声称和生产资格，不等于研究不能开始。

## 产物与执行凭据

- `outputs/stage006_economic_coverage/inventory_economics.py`：仅小metadata、`SELECT * FROM contracts`及PRAGMA，无daily_bars/H5读取，无fit/财务/下载接口。
- `summary.json`：计数、版本、已知来源哈希和DB只stat绑定，`financial_ready=false/historical_pit_qualified=false/production_qualified=false`。
- `epoch_economic_inventory.csv`：10,880目录行，包括has_accepted_clean_epoch、accepted行数、原字段和未知状态。
- `product_economic_coverage.csv`：98历史产品域；不删无行情S。
- 两次轻量聚合exit0，分别0.248秒、0.267秒。第一次版本统计将数值等价的`5`与`5.0`分组分开，已统一数值字符串后修正；纯展示统计78降为14，原条款/覆盖未变。第二次同时增加费用type/三费率交叉核对断言；无价格、策略结果或选择规则变化。
- 不在本次宣称“回测独立review通过”；本次没有回测，后续金融结果必须交独立agent核验。

## 回测记录与反思

无新增/修改/删除策略参数，新增仅元数据输出schema与来源状态。无回测，期末权益/总收益/最大回撤/Sharpe/滑点/交易次数/胜率均N/A。没有拟合、下载、金融回放、CTP、账户或凭证访问。

结束反思：新增按成绩选参型过拟合＝否；本轮没有读取模型或金融新成绩，也没有依据覆盖重新挑宇宙。历史规格的静态重建偏差、策略后验选择与相关样本仍存在。继续价值＝是；9502/9520精确元数据表明经济单位不是全市场扩域的根本阻塞，下一步应冻结本线源合同并做小型身份/现金恒等式样例，而不是再扩泛盘点或立刻拟合。
