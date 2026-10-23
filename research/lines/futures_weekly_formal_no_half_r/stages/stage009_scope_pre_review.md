# Stage009 缺失键新增范围修订：预绩效独立审查

- 审查时间：2026-10-23 15:29 CST；line_id=futures_weekly_formal_no_half_r。接受判断首次于任何完整G绩效之前发出，本记录亦未读取/使用G完整收益；只审数据范围、执行接受门和纯边界测试，不运行资金。
- 结论：`PASS_SCOPE_PRE_REVIEW_PENDING_G_FINAL_AUDIT`，未发现必须阻止G002启动的P0/P1/P2。允许冻结这次数据范围合同后执行G002；不代表G绩效、可执行性或生产资格已经通过。
- G001及其任何成交前source overlap失败继续保留，原raw、patch、旧输入/工具/输出不可改。不把本修订称作OI标准化，也不把G001改称完成回测。

## 五条接受条件（预先判断，非据G收益调整）

1. 旧base、所有prior proof保持原1e-8严格互校；旧Stage003 catalog先按原“只补缺”优先级并入legacy。旧key的全部OHLCV/OI与metadata不可覆盖，不能让新raw抢旧catalog键。
2. 全部新G层先严格互校，然后对所有已有legacy key统一排除新值，包括完全同值的交集；只添加原不存在的key。不能只针对两个坏key择优处理。原/新值、不同字段、请求身份与全部excluded overlap完整留痕。
3. 固定353个预声明data-only请求；任一请求key存在旧新冲突即拒绝。实际引擎的所有fill和所有captured anchor请求的actual_time、expected_start也必须逐个交叉冲突ledger，任何命中均否决整个run；退出/换月不能靠未列入预取353躲过审查。
4. 原旧零量bar原样保留；实际使用零量/非法量继续触发执行否决。canonical首分钟、精确raw open、真实持仓日线正量、会计守恒与费用模型均保持，不切换09:01，不用daily open，不按坏成交删产品或改资金路径。
5. 完整冻结修订合同、353 tasks、原冲突两份证据、旧/新raw/proof和工具SHA闭包；只新增v2 runner/controller/scope辅助工具，不修改旧文件。G最终必须再独立审数据、逻辑、会计、执行、置信度和bug；未通过只能保留明确条件诊断，不救成绩、不晋级。

## 发布后只读实现审查

- stage008_missing_key_scope.merge_missing_key_scope先校验legacy唯一及新层全字段互校，再统一枚举交集；每个legacy key保留原row，对旧新数值差逐字段记录，不按成交价格、量或未来表现排序。请求冲突抛RequestedKeyOverlapConflict，随异常保留完整scope_report。范围函数不修改传入DataFrame。
- runner先用原stage005_merge构建旧层，随后以原legacy覆盖顺序补入catalog，检查重复；scope在此之后运行。后层catalog_loader因此没有新键可抢，保留旧缓存语义。新G只按stage008_minute_patches目录归入new层，原stage003/stage005仍prior层。
- runner冻结scope pointer/合同、353 tasks、root及独立冲突证据；保存minute_layer_scope。完成账本后，实际clock fills分别运行canonical时间/price/raw正量审查；scope_consumption额外核全部fill以及anchor actual/expected，任何冲突或非法key均fail-closed。两个接受JSON和anchor CSV均落盘，拒绝结论汇入metrics与terminal。
- canonical正量接受门已经更新为传全calendar，按每笔trading_date重算canonical_open_timestamp；正量09:01不能冒充09:00。只验成交后的接受性，不改变已发生的模型账本。
- controller只对明确missing错误下载真实分钟；zero-volume/anchor-mismatch的terminal会生成明确diagnostic pointer并停止。已有attempt或log均拒绝复用，G001保留；不把零量数据误当可下载缺口。
- harvest_new_sources仅把新planned/from_G raw交由原canonical/raw/proof校验；旧119源继续由已冻结旧层供给，没有改写旧key的路径。

## 验证与局限

- 独立执行既有scope 15项及更新canonical执行门9项：24项全部通过（0.105秒），无金融回放。涵盖旧零量/正量价格和metadata不可覆盖、同值也排除、新新冲突仍拒绝、请求冲突留完整报告、真实新增值保持、timezone、actual fill及anchor actual/expected冲突否决、正量09:01不能冒充canonical等边界。
- 读取root全量真实data-only测试及完整769排除ledger：旧legacy含catalog1,793,236行全字段/metadata原样保留，新83层2106行/2050 unique，全部769已有key统一不导入，其中2冲突、0预请求冲突；新增1281=47预请求+1234额外canonical，old overrides=0。该全量测试由root执行，本次独审独立复核其计数/断言一致性与实现，未重复运行资金或据收益选择数据。
- 两冲突仍为CF005.CZCE 2020-01-02 09:00、21:00：旧first-seen未完成分钟与新完成bar经济数值不同，非字段语义可标准化；两者保留在ledger内，实际消费必拒绝。
- 当前只能接受预绩效数据范围修订，不确认G完整会计、实际消费冲突为0、实际首分钟量、trade/clock完整对应、最终输入SHA或策略收益。最终G产物出现后另做全面独审。
- 过拟合判断：修订在G完整成绩前、统一所有旧key、没有收益/赢家选择或alpha阈值修改，因此没有新增按成绩拟合；重复同窗及非PIT限制不消失。继续价值：可完成用户明确指定的单一三均线原19消融；不扩大参数搜索或晋级。

## 本次读取版本SHA256

- tools/stage008_missing_key_scope.py: `5375a658af930d86a1851005a3c36f146e470d3a5a598ebbf0183be22af961d9`
- tools/run_stage008_three_ma_missing_only.py: `c332e051f414f0d847a90ca7c63b940dd500c0ce07152dc7c39231a3234f41f3`
- tools/stage008_complete_replay_missing_only.py: `51cad636598ae40686bc37341a7439d3ec0fadfcb26968a875662913b3b21331`
- tools/stage008_harvest_new_sources.py: `550faea59bc89e3948c43082bb493cd8dc8e25a38c8e0583a6e8ce6b93395c54`
- tools/stage008_execution_audit.py: `447c95ea76f7c2d8823fbb235fc75b6d98de3c330deb3f882903d94134f9d221`
- stages/20261023_1521_stage009_missing_key_scope_amendment.md: `fbabbf2495c15a1bface9589e047169d1138a609da364be9584493b67ff2f102`
- outputs/stage009_scope_data_test_with_catalog.json: `62c929e51ace9e36039caca526fc519a22d154af22d2a97d81a03dff919665e8`
