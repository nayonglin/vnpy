# Stage107：严格signal day reader的定向独立复核

- line_id：`futures_trend_triple_screen`；2026-10-18 07:49 CST。
- 独立reviewer：`accepted_delta_review`；非106作者。
- **结论：P0/P1/P2=0/0/0，106单一reader边界接受。可供root按原104 completion安排一次新目录完整只读审计；107不构成完整母链/金融绩效接受。**

冻结receipt：`outputs/stage107_date_reader_independent_review/review_receipt.json`，SHA `5987f37d8ca3320b65906081b51549d91394037c1837b4968e267ce67a1b1123`。先给root确切SHA触发既定只读审计，再补本文；receipt未变。

## 身份与范围

新reader SHA `6688020ff61a6b14ae2cc0ce158c7f54cf2692d1696b53a525596c76ec4f4b49` / 6194 bytes；test SHA `e793ab33d71efff6df757d1e5f43965f9c393c0ab9ee4bfcd794e50f2b0780eb` / 2480。冻结原095 SHA仍`be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f`；数学全文未变。

读取root106最新合同，包含实施前raw_exports单一边界澄清；合同SHA `d7e00776a317c6b350cbec24b007be4429b06150d42561eef0690de2d78064d9`。106实施receipt SHA `caff520702c23f954cd781b6cf0c7fed80a63ba6fe2adfbfb1ad678410b39ea9`、实施stage SHA `67c87d668eed5dc6a7d04e8d3bb6f5e278a74f24e593238607ccc3eb14d22db0` 已核；文档补齐不重跑case。

只核新106 reader/test、原095不变和parent/新OUT；不重审金融数学、061/071/市场，不运行--audit、旧suite或金融。

## 单一边界与不变性

- private095中仅赋值base.raw_exports及base.OUT；原a_mothers、audit、roll/retry和全部现金/成本/母链算术不替换。
- 新raw_exports首先完整调用冻结原raw_exports，先完成raw↔导出与actual identity核验；再验证candidate/rollover CSV严格日标签，最后适配返回usage。
- 只深拷贝usage、只赋signal_date。trades、clock、hashes、identity四返回对象仍同一对象；原payload和原usage不改，其他数值/时钟不动。
- signal_day仅接受合法严格YYYY-MM-DD字符串或naive且精确等于normalize的pd.Timestamp；非午夜、aware、NaT、None、含时刻/不补零/非法日拒绝。CSV日标签同样strict_iso_day校验，不重写CSV，不放宽plan条件。
- 下游原audit merge、a_mothers和后置roll lineage共用同一规范列，没有第二处日期patch。新test分别覆盖首笔实际类型/值的候选join和tiny roll-close同日过滤；后者不是新增真实行情证据。

## 输出与parent闭包

新OUT固定`outputs/stage106_off_financial_audit/ARM/RUN_ID/`。原095的write以xb创建，base新算法receipt保留，再新增reader_account_checks绑定原算法receipt SHA与reader lineage；失败另存reader_failure_lineage，不覆盖原095/105失败。

五项固定BINDINGS均逐字节核SHA：原095、原095 audit_failure、105部分失败receipt、104同一completion、root106合同。105 receipt仍`8ecee989eb9a4acbe751e7abd7fefed14ff327c42ad141ee842445e900274f6a`，原audit_failure仍`2771b9f5edfd77ed1e25ffc4fd9fdaacbfaea48ce7bfc3dd1a44f361be0cc09c`。A参数还强制同104路径/SHA，不换账户或completion。

104 SHA `fd6272aeeb94b8546008224d54479aeab5e5e11d2cf5e73439c110b097f17944`；A_OFF run_id `7cf2c2bffdc34d8cbd926693aa75dd10`，global arm attempt2，root工具37421/chunk0832ea/exit0。仅读completion元数据，不打开账户raw、seal或CSV。受影响scope/provider/checkpoint/runner/095五源与100已固定字节相同；不将有限五源核验冒称全市场或完整来源资格重审。

## 实际验证

新增唯一具名test：
`DateReaderTests.test_raw_usage_day_reader_preserves_both_joins_and_rejects_unsafe_days`。

**reviewer fresh仅一次：exit0，Ran1，0 failure/error，0.024s。** 验证两join、usage原件/非日期列全等、四对象is不变及7类非法日期。test无作者输出路径，只把工具stdout保存107，原源码/断言和106 RED/GREEN/compile证据未改。

作者RED exit1/1test、GREEN exit0/1test及compile exit0仅按其固定证据核验；不算本reviewer重跑。完整实际命令、exit、stdout、source/parent SHA和静态边界核验见107 evidence.json，SHA `4f9191b20be2bb93e9d36fd63e5acd23ed82fa568321540a1382fbf0d87b11f4`；fresh_named_test.txt SHA `55587816294ef7f8fdd20a671de67f9968b5a087fd554335e652f289c0078d00`。

## 接受限界与反思

P1-105-001的日期reader缺陷在固定新代码中已接受；105原前序现金/库存/成本/1641指标通过仅按其pin receipt继承。本次没有运行完整审计，母链/胜率完整结论仍须后续同一封存账户只读审计；不改变金融attempt计数，不重跑策略。

实际--audit、金融回放、账户raw/seal/CSV读取、行情loader、模型load-fit-predict、网络、订单、旧suite均0。不改作者源、金融源、原095/105失败或104completion，不改LINE/registry/Git，不另派agent。新增/修改/删除alpha参数和完整金融结果0；所有新增绩效N/A，original_goal_achieved=false、production_qualified=false。原全局A1失败N/A、原B失败、A0受限、PIT和目标未达限制继承。

调研与判断限root无网络边界内的本地合同/冻结源/parent元数据，无新网上GitHub或alpha研究。开始及结束过拟合判断：**否**，修日标签类型而不按收益调参；继续价值：**是**，完整母链核验可以继续且无需再跑策略，但不能提前宣称账户已完整接受。

