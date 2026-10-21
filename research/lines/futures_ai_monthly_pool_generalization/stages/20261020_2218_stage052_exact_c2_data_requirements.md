# Stage052 精确C2首阻塞数据需求

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 22:18 CST；非重要突破。仅本工具/测试、本stage及stage052输出，不改LINE/registry/模型或正式策略。
- 范围：046b中mature+asof成员、first_unknown_reason精确为`c2_order_or_fill_unknown_without_minute_path`的2209行，复用冻结042 loader/source只读重放；非新alpha、非收益择参，047既定负结论不改。
- 结果：2209/2209原首次未知date/reason/status/path数/known数/allknown逐项一致；全部held state可提取，按exact epoch×source_trade_date去重910个需求，910种状态，85产品/798epoch；trade_date2010-08-03至2026-09-18。34窗口held≠当日target，63窗口roll新层；722需求多窗复用、最多4窗，不是获救标签计数。
- 提取合同：state.contract为唯一held来源；entry/stop/qty/配置guard/effective fill tick、源OHLC、当日actual source-reference tape、原episodeR与fresh日、previous trace pending里的current layer信号日均保留；缺精确state/record/tape则unknown不编。metadata order_book_id仅原vendor hint，不以epoch末4位机械拼CZCE或broker native。完整2209映射、910需求/状态和固定12均匀事前输入索引trace样本保存，不重复巨量全case JSON。
- 时间与资格：source_trade_date不转自然日，T00仅逻辑daily-open假设，不编09:00；需求是历史规则下完整trade session含适用晚盘/跨午夜/日盘，周末/节假日不机械减1自然日。session物理起止留空、认证False；source_execution_tick_native_hint仅LC tick lookup字符串，不能当cache/broker身份。
- 运行：2026-10-20 22:15:16—22:15:36，4worker，19.88秒。原source SHA/DBstat不变；补充后验核对046b coverage/panel/econ/calendar哈希均仍等冻结值，不回写原runtime收据。计算产物：`outputs/stage052_exact_c2_data_requirements/`。
- 实现验证：9项TDD先红后绿，含held/target不同、roll两时钟、missing exact不猜、pending不可冒充actual tape、firstunknown拒不一致、同合约日期不同stop状态保留、NaN metadata hint。独立053 reviewer已收到全部产物，054作者已收到910需求schema和CSV；本作者不自审。独审尚未完成，不提前声称复核通过。
- 调研与判断：重查vn.py维护者BarData定义（README就近链接）与本线已独审源合同；通用timestamp/metadata不能证明历史会话。精确held需求比050 product-day hint更可执行，但只补首阻塞仍不保证后续60日known，execution未知不补fill。
- 参数新增/修改/删除：模型/alpha/费用/半R/C2无；仅新增诊断工具与状态需求字段。未新增分钟、fill、训练标签或fit；下载/订单/生产修改0。账户权益/总收益%/最大回撤/Sharpe/总滑点/总交易次数/胜率均N/A，本轮是固定源重放提取，不是收益优化回测。
- 开始/结束新增收益选参过拟合：否，原firstunknown选择且未查收益救模型；继续价值：是，供054既有缓存核验及后续数据补齐。完整标签恢复数量、未来模型提升与正式交易资格仍未证明。

- 22:19补充：Stage053已完成63364独审检查、9测试0失败，P0/P1/P2=0/0/0；独立核2209映射、910需求/状态、3640精确SQL键与43自组SQL→039 trace窗口。仅接纳exact first blocker需求，不转授session/native/完整60日资格。独审输出哈希仍匹配，原runtime summary未回写，另见post_review_acceptance.json。
