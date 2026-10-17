# Stage038：B_TS 独立金融复核准备

- line_id：futures_trend_triple_screen；时间：2026-10-18 03:38 CST；模式：限定审计准备；不是重要突破。
- 先读Stage035执行合同、0333 implementation plan及0330最终预算设计。独立B是新假说，原C失败和旧031/033证据不改；此阶段不读取B实际输出、不计算PnL、不运行引擎/训练/网络/全库资格或旧fixture suites。
- 新文件：`tools/stage038_independent_b_ts_account_review.py`；唯一输出准备收据 `outputs/stage038_independent_account_review/preparation.json`。精确未来source `outputs/stage036_b_ts_account/B_TS`，arm B_TS/attempt1；原033 SHA940ab118...和030 SHA3fe153...固定复用，不重写现金/库存/成本/真实身份/母单/原七门算法。
- 新增必要非金融fixture仅3组：原tilt12按风险上限10裁剪；三项原admitted gross前缀30000/60000且第一缩量不回收、错误45000前缀拒绝；B同日setup允许但signal<execution，unknown/native fallback一律拒绝。结果通过，旧fixtures重跑0，py_compile通过。
- 独立预算公式：rho_T=max(abs(T-S)*size,原minrisk)，m_T=T*size*marginratio；先核原contracts_by_risk/margin/single与T相等，再按R/L/K/E/B/cluster字段及原开关逐项floor，最终q不超过原a；gross前缀始终用原a*m，q0 filtered/b_ts_final_budget_zero且不补位。该公式是审计规范视图，最终必须按真实035 producer字段逐项绑定，不能用最终min掩盖pricing接合错误。
- 后续完整审查范围：new long/short_triple_screen；无context/unknown不得回native；held/add/roll隔离；已启用generic filters与volume-OI→OI→regular源规则；MRO过830而S仍804；u已知T和最终q贯穿预测预算，D实际F只决定实际R/margin且不得重算q。保留原1.10日收盘七门、1.65额外日收盘诊断、原佣金0披露及非完整分钟PIT边界。
- 当前pricing/strategy/036 runner均未给最终SHA/schema。actual入口对缺source/SHA/owner/schema/result_scope及producer字段adapter硬阻塞，不能由草稿或运行中输出推断冻结；root给最终源后再接完整审计，真实terminal0+summary/raw/seal齐全后才actual followup。
- 正式/策略参数新增修改删除：本审查0；B研究新增信号/T估价/finalbudget结构由收益前Stage035合同约束，本工具不新增策略数值旋钮。权益、收益、DD、Sharpe、滑点、成交、母单胜率全部N/A，金融回放/训练0，production_qualified=false，promotion_allowed=false。
- 外部调研与判断：沿Stage035已冻结CMT Elder、LEAN FI与Backtrader和本地真实预算/订单源码，准备阶段不重做泛搜；不能把经典结构或fixture通过当B金融优势。
- 开始/结束过拟合判断：本次新增否，只固化独立审计公式与时序，尚未见B收益；历史选择偏差仍须披露。开始/结束继续价值：是，独立B尚无金融证据，必须让其首个结果可经济复算；B若失败停止固定形状，不救参，不因准备完成声称目标已达成。

## 03:44 精确source/字段接合补充（仍无金融）

- root提供036 SHA34563257...、035pricing d45e8a5b...、035strategy fc357eb4...，当前逐文件SHA匹配。035决策/fill/冻结sizing字段逐项映射到独立B规范预算视图，原contracts计数与T先验、gross原量前缀、最终各整数cap与q、decision/candidate/fill字段保存均纳入。
- 受控复用：固定033/030源码SHA不动，在新038内存模块仅精确替换arm/attempt/owner schema/协议/明确alpha标志和B允许setup=signal的时序；每项替换有固定出现次数守卫。原现金、库存、成本、实际身份、母单/retry/roll与七门算术不改；B ordinary flat fallback明确拒绝，所有初始flat标签必须new long/short_triple_screen。
- 036 owner精确B_TS/attempt1、stage036_* manifest/context/seal/raw、runner writer及四项source_modules绑定；原033日收盘1.10/额外1.65/0佣金/零warmup与preflight子集规则复用，去掉旧C固定110条增长文字，不假设B同样数量。
- 静态复核已启用generic filter调用、volume-OI→OI→regular、short专属放行、原qmt源码SHA与三处T替换以及MRO；实际逐历史技术字段不重算，generic/OI行为需结合root独立真实B组合review界定置信度。新same_signal域分布变化明确列为模型校准局限。
- 原限定3组新非金融fixture继续通过，controlled adapter编译/import通过，旧fixture套件重跑0；未读B输出/市场价格大表/账户，未actual、金融/训练0。
- 当前038 SHA `00925f1ca5ba4b2df0bf1f28b93d19c6bdd378a6ec824c8328b6828bd17fdb25`。actual入口仍由EXECUTION_REVIEW_APPROVED=false硬阻塞；root execution reviewer若修源须先精确重绑，真实terminal0+全summary/raw/seal后才可实际审计。

- 03:45 root已交付独立真实B组合0/0/0收据SHA6a1b4a34...，035/036精确源未变；038现直接绑定该收据及最终源，完整adapter ready。actual仍由`ACTUAL_AUDIT_AUTHORIZED=false`硬阻塞，只有root真实terminal0 followup之后才启用；本阶段未运行账户审计。最终准备038 SHA `db56a08bfd35a0164b5d76f8605f6af6e2e742c09196f99cdfac068a6b8b7255`。

- 03:46 依root最终stage引用收尾，仅将独立review receipt重绑SHA `10c74fc9105b0ab937966817ef420b59f10c774c75a7ae42d4288ccc826c5d0c`；四源与0/0/0/真实3场景8fills未变，无fixture/测试重跑、无金融读取。038新SHA `e9d651be9467c04241809a86c1046881cbe8e9def7c55b1c41bf7c79f0603dd7`，actual flag仍false。
