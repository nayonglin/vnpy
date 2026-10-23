# Stage022 长历史扩展逻辑预审

- 时间：2026-10-23 19:29（Asia/Shanghai）。研究线：futures_weekly_formal_no_half_r。
- 请求：当前M原19、15万、cap19、三MA周线、21完成周ready/41缓存，无MA40/MACD/AI/半R/C2，扩展为2015-01-01—2026-10-23。无金融结果。
- 本阶段只读源码、SQL元数据与accepted输入。没有回测、下载或旧工具修改；重要突破否，参数/绩效新增修改删除均无。

## 判定

**新隔离适配方案有条件可行；旧M入口不能仅替换日期后直接宣称全窗完成。** 无需把全部CZCE名称改成四位，只要最终合并输入能证明native/日期→物理交割月身份唯一、相邻物理代不重叠且真实gap>366日，现AM重置即可继续使用；但AM reset不能代替策略state/target/order的跨代授权检查。

当前阻断的是尚需完成的新数据及通用边界证明，不是判定策略alpha失败。不得用某品种/年份/收益表现作为修复条件。

## 暖机与2019默认值

- 当前冻结M mapping范围2010-01-04—2026-10-22；M日线SQLite实际2015-01-05—2026-10-22共1,257,339行。根source DB最早2015-01-05、末2026-10-14。日历早于行情不表示已有行情预热。
- 已实读Stage266 clean accepted：2010-01-04—2026-10-16共1,552,456行；2014年57,549行/790物理epoch，首01-02末12-31。这是全市场数量，不能冒充原19在2015起点全部ready；须逐映射目标检查2014及合约上市寿命。
- `s772._preload_for_start:87–90` 对2015返回start−365即2014-01-01。`s847._run_profile:426–435`会临时替换START/END/PRELOAD并传给engine.set_parameters，因此沿实际调用链正确传2015时，不会被qmt_universe默认2019-06-01静默截断。
- 仍须记录实际engine.start、最早/最晚history_data与初始化/交易开始日期，防止新runner漏改旧2020调用、旧DATA绑定或固定日期。M runner的preflight、真实_run_live_c9、metrics窗口仍写死2020—10/22，必须新入口统一参数化。
- `on_init`读取warmup_days；基类默认80，但M实际setting为90，延续M必须保持90；vendor engine先把前90个全局日切片用于初始化，再设trading=true。这个全局暖机与单合约21个完成周是两道不同门。真实2014可覆盖时，全球初始化可在2015前完成，同时trade_start_date应明确2015-01-01，禁止2014成交；合约刚上市不足21周仍应自然不ready，不伪造暖机。
- 如果某必要输入未取得足量2014，不能把2015早段直接丢掉；应报告实际不足及不可交易覆盖，或明确现金预热。不能移起点、用0前缀或事后补持仓。

## 完成周与截止日

`weekly_adapter.py:6–17`按ISO年/周和实际交易日历判定最后session；25–47仅在全部expected日齐全时封周。2014开头若缺2013末同周日期，第一周应拒绝而不是当完整周；一整年预载后不影响正常21周逻辑。新快照必须覆盖10/23真实完整日K与mapping；10/23是周五，齐全时应封存该周，不能沿旧10/22截断继续保持末周未完成。

若10/23产生周信号，下个交易日超过账户结束，则只记录未成交挂单/target，不越界撮合、不强平、不删除末周信号。所有2015+账户日、ready诊断和缺周证据都要导出。

现 `weekly_adapter.on_bars:59` 与 `stage008.on_bars:49` 仅记录>=2020诊断。这不会关闭2015策略，却会漏掉2015–19覆盖证据；新wrapper应新增统一的请求窗口诊断通道，或只补父类未记录的日期，不能为记录而重复调用on_bars或使2020+重复。

## CZCE复用、AM与物理身份

`weekly_adapter:31–34`在相邻真实bar间gap>366时重置inner和pending，能消除旧周close/量/OI输入。只读accepted源中，原8个CZCE产品2014—2026范围发现145对同native物理epoch，最小真实gap3282日，0对重叠或gap<=366；源截止10/16，最终新快照需重新验证。

因此不应机械改CF505为全局四位而冒险改变既有margin/tick override语义。应冻结完整物理epoch ledger（交易所/产品/交割YYYYMM/native/真实日期/来源），保证每条日bar及每个周source_days恰属一个物理合约。不能用当前年或10年gap猜交割月，不能把跨代close串成一条“真实合约”周history。

原AM reset只清inner/pending，不清strategy states、target_data、pos_data、active orders；completed/max_count仍是跨历史诊断容器。因此应按physical epoch分组说明ready和周条数，不能把多代合计叫单合约暖机。

关键顺序：`s502.new_bars:135–136`先cross_delayed_orders，后strategy.on_bars/AM.update。故跨epoch安全检查必须在第一根新代bar撮合前完成：旧pos=0、旧target=0、无旧active order。若旧实仓或旧委托仍存在，失败并保留证据，不清仓改账后继续。旧state若仍有旧代planned layer，即使数字pos=target=0，也应记录并按一致归属不变量处理，不能仅凭同native名称把它授权给新代。

最小实现是在新isolated engine/wrapper作数据/授权边界检查，不改三MA、风险阈值或持仓收益规则。先验证最终数据非重叠与gap条件，再沿用现AM reset；若条件不成立，应失败并要求真正的epoch-aware reader，而非调整366阈值适配某几个品种。

## Stage278可复用的范围

`stage278_daily_engine.py:8–24`在rebalance前对“非零target但没有当前state.contract/layers合法归属”统一置0：没有实际pos时阻止凭空开仓，有实际pos时只形成平仓目标。这个通用授权清理适合新增隔离wrapper，合法当前计划必须保留，所有清理写receipt；不能按品种年份或盈亏删交易。

其限制：owned只看native membership，不能证明同名旧layer属当前epoch；不能解决真实缺持仓行情、旧实仓或跨代挂单，因此要与撮合前epoch闸联合。也不能静默重建layer或修改全局风险/连亏记忆。

**只借target cleanup，不借Stage278整个撮合器。** 它的cross_delayed_orders:62–70会在缺日/0量时延期，daily_context仅要求晚于信号日；搬入会把M的“下一交易日真实日Kopen，缺源拒绝”放宽为“后续某个有行情日”，违反当前用户口径。保留Stage011严格next_trading_day与正量/合法OHLC检查、held/traded每日真实行情门，不用旧价carry承认过期仓位。

## 数据拼接和必要验证

新增2014 accepted输入必须与保留M2015+原键作先验单位核对。Stage266 unit_contract声明single_sided_contracts且仅对已锁source有效；不能让同物理合约的2014 accepted与2015原源在volume/OI上因单双边单位不同制造跳变。保留旧值、记录重叠/来源差；不能看收益挑源或随手改旧量值。

新运行前至少验证：2015实际start/preload和90日全局暖机；2014目标合约21周来源；周末/节假日/年界及10/23封周；三位两代gap和第一周不混；旧pos/target/order跨代失败；合法目标保留/孤儿目标只平；strict次交易日成交未被延期；2015+诊断完整且不重复；cap19和全部模块关闭不漂移。新运行后仍须独立财务/原行情审查，不将本设计预审当已接受绩效。

## 反思与后续

本次没有拟合或按绩效救援，过拟合判断否；扩长历史仍受原策略开发选择偏差，不能自动称严格OOS。继续价值是验证固定M跨更长周期的行为，前提是上述通用输入/状态边界先成立。可继续做新隔离实现和数据证明；在条件未满足前不应启动可对外报告的完整绩效。保持NO_PROMOTION。

源SHA、SQL观察范围和前置不变量见同名JSON；clean数据库即时SHA已核与其dataset_manifest一致。

实际参数补核：M spec.overrides没有trade_start_date/preload日期键；最终trade_start_date由_build_setting按请求起点设置，仍需新runner捕获证实为2015-01-01。M实际warmup_days=90（非基类默认80），本文件已校正，未改策略参数。
