# Stage132：EMA限价新增组件的一次整体独立审查

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 09:40 CST；审查者：`ema_limit_overall_review`。
- 当前工作区 `/Users/mac/Desktop/fian`；base=head=`4f42805c2c71f8492a44a6876a82672f410f44df`，开始及结束读取一致。六个新增文件尚未提交，按明确路径逐一审查，未用空的base..head diff冒称覆盖。
- 已读registry、124定义、125独立定义审查、126裁决、127计划及128 ledger；registry未列此已存在研究线，按root指派归入本线，不另建线或改registry。
- 性质：一次新增组件代码与有限fixture审查；非重要突破，不授金融或生产资格。未派子agent，未修改作者源码/测试、旧策略、HEAD/index/branch、LINE、registry或正式材料。

## 结论

**P0=0、P1=0、P2=0；component ready without fixes。** 六路径源码与交接SHA逐项一致，未见需要先修的真实native接合、源/时钟、经济账、signed分母、资源或身份缺陷。此结论仅覆盖当前固定组件及有界反例，不是全历史运行成功、alpha、金融readiness或生产认定。

按用户要求收束检测：阅读并核对作者129/130/131的真实RED/GREEN/compile收据；未重复六方法或旧suite。仅另写review-only脚本，一次运行两个有明确风险依据的接合反例；没有镜像实现定价或PnL。

## 调研与判断

继承121/123已固定的原著、作者官网与GitHub有限调研，本轮代码审查不重复联网。判断仍为：EMA13穿透限价可作为透明、可证伪的独立适配；26有效bar、positive-only、全量分钟近似和gap保护是本项目预先固定的约定，不能称Elder唯一原版或盈利证据。未读当前B输出或途中PnL，未据其损益选实现。

## 整体核查证据

1. **源与公式。** `stage127_ema_limit_model.py:97`一次读bytes，SHA核验后从同bytes解析；`:112`拒绝重复/未资格键；`:155`精确键和source bindings绑定；`:173`缺应有session或无效OHLC丢弃段，按单合约重暖。`:181`SMA13 seed、随后EMA13递归，`:187`只保留26个有效EMA bar并用正数分母；第38真实bar才ready。`:219`只由u/u−1与已完成窗口构成次日线性外推及方向tick舍入。未来毒化和source TOCTOU的具名反例有直接断言，未把metadata所含源引用当交易信号。
2. **状态、ID与初开量。** model`:306`换合约取消准备与旧intent，`:331`EMA unknown不消费setup，`:357`仅匹配DAY fill消费一次。新epoch/setup/intent用独立namespace，不借B/C owner。strategy`:48`先验`d*(L-S)>0`再进入035原定价算术；真实847/830/827/804/772/qmt MRO保留原recipe，非flat委托到原方法。`:75`最终预算只处理原admitted，按原量gross前缀累计，缩量/归零不回收或补位；`:280`仅最终正q冻结指令，028原snapshot位置reserve一次。测试真实L100/S95/size10→rho50/margin100，u.close99，原量22/22/22→22/3/0、gross0/2200/4400，仅reserve22和3。
3. **完整D资格与共同heap。** engine`:223`先调用资格callback，再用原session grid/entry_session检查完整D后scan；`:102`所有候选分钟先核OHLC和非负有限V，严格穿透一tick及floor(V)≥q，主口径首符合分钟、改善open与tick可达性均固定。`:132`悲观模型只检查紧接下一真实分钟，失败不寻找第三次，不延入下一D。`:291`保留ordinary稳定serial、限价和native synthetic的共同heap，pop才调用028真实激活、buy/short与native `_fill_order`，未复制PnL。未成记录保留资源，不造layer/order/费用。
4. **gap与真实经济账。** engine`:240`先计算signed F−S，错误侧risk为None，pre-fill`:280`注入context。strategy`:331`在827 diagnostic abs前分流，`:376`错误侧返回同母不利极值native保护CLOSE，不走847/827合法R或retry；真实两fill、setup消费一次、R=N/A、真实margin保留。`:319`必要的窄update_trade只补身份字段，恰一次super经济路径。131具名测试实际调用engine成交和`calculate_result`，多90→88、空110→112的成本、settled cash、native net_pnl一致；没有CSV虚拟平仓或额外扣成本。
5. **首分钟两consumer与retry。** engine`:171`独立深copy仅遮intrabar首分钟有利H/L/close，raw保留。strategy`:403`临时私有分钟映射供原847即时扫描，finally恢复；`:414`先用全日raw生成技术环境，再以同一view构建持仓lifetime bar。合法R保留原minimum-risk guard、0.5R及从下一分钟起的一次F reclaim，真实100→98→103→98可越L100，同q6/初始R4/stop98，实际四fill费用263.94、净损益−683.94只为经济恒等式fixture。
6. **工厂、OFF与组件边界。** strategy`:449`只copy profile并replace原八键OFF、接新strategy/engine；不调用旧arm工厂、prepare/checkpoint或runner，不实例化金融账户。真实构造测试保留formal输入，禁止joblib/model runtime路径；无`research_arm`，`research_mechanism=stage124_ema_limit_v1`且`financial_ready=False`。普通held/roll不匹配新context时继续原路径。

以上行号均指本线`tools/`下新127源码；相关028/035/native仅定向只读作为接口依据。六个具名方法与127计划逐一对应：`test_formula_source_and_future_poison`、`test_state_epoch_unknown_and_identity`、`test_real_limit_budget_off_identity_and_reservation`、`test_limit_scan_volume_day_end_and_private_view`、`test_real_gap_invalid_side_mother_and_cost`、`test_real_dual_consumer_retry_and_unfilled_resource`。最后两个明确使用真实native fill、诊断、母链、库存、成本和原`calculate_result`；纯扫描/数据断言没有冒称经济证明。

## 唯一补充运行

脚本：`outputs/stage132_ema_limit_overall_review/finite_review_probe.py`；命令`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage132_ema_limit_overall_review/finite_review_probe.py`，start chunk `16f7ea`、session `40383`、终态chunk `81bad8`、exit0。两项均不运行prepare/旧suite/金融/provider/model。

- **拒单schema接合：**作者错误侧L测试直接调用sizing，新增有限反例用合法u真实bar、L94/S95走完整native `on_bars`→planner→snapshot。结果q0、`invalid_stop_side`、无pending/fill/reserve，setup保留，无缺字段异常；验证拒单能接原schema。
- **空方真实holding consumer：**空F100/S104，intrabar首分钟raw open97/high101/low95/close96；私有lifetime low100后实际调用native `_update_dynamic_stops`，layer.lowest_price仍100，raw逐项不变，只有1次native初开、无retry事件。该反例直接验证空方实际持仓消费，未重写其算术。

复核作者收据：129最终GREEN `a500e1`、130 `7e2ee9`、131最终六方法GREEN `cc88d0`（6 tests/0.289s）及compile `9670c0`。130旧engine-test SHA在Task4追加前，131最终六SHA与当前一致，非漂移。131的`7110e4`是手算oracle将−2−5误写为−5，收据诚实保留且最终预期−7，未当实现RED或改经济结果。导入font-cache与TqSdk banner不当网络/provider证据。

## 拒绝作出的判断及原因

1. **收益更高、DD更低、Sharpe/生存门已通过：不判断。** 本轮零真实账户replay，fixture的−683.94只核经济恒等式，不能当策略样本。
2. **真实日线、逐日tick、分钟单边量已获资格：不判断。** 组件明确由调用者交付exact qualified keys、qualifier SHA、u资格execution_tick和资格callback，本轮未交付/验收真实数据资产；这不自动变成组件代码缺陷。
3. **真实排队可全量成交、gap close瞬间一定拿到极值：不判断。** 总分钟V/OHLC不能识别queue和逐笔先后；主/悲观近似及最差proxy已明确固定，悲观也不是账户全局下界。
4. **全部历史held/roll逐路径与原引擎普遍等价：不判断。** 已核实际delegation、nonflat原价及普通context不改；按范围不重跑旧suite，不用有限fixture冒充普遍证明。
5. **当前B的进度、终态、财务完整或PnL：不判断。** 未poll其handle、未读其运行目录或途中收益，仍由root独占。
6. **新金融arm/runner/checkpoint/readiness/生产资格：不判断。** 六路径无该交付；未来独立run_id、真实源资格和中性owner等仍由root另行处理，不能借B_OFF入口或本审查绕过。

## 记录、反思与交接

唯一新增为本文、review-only脚本、两例JSON证据和review receipt；作者源/测试、参数、回测结果新增修改删除均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、母链胜率均N/A。金融attempt/replay、训练、predict、provider、网络及真实订单API均0；`fixture_only=true`、`financial_ready=false`、`production_qualified=false`。

开始/结束新增过拟合判断均为**否**：只按收益盲124/126定义核正确性，未读取B收益、扫参数或选择金融口径；历史多轮选择偏差仍在。开始/结束继续价值均为**是，限于一次必要组件审查**：直接检查真实记账、signed风险和首分钟消费能排除可复现错误，当前证据已足够收束本轮，无需重复旧suite或无限加测。下一步交root处理原B终态和未来金融交接；本审查不启动金融。

不更新LINE/registry/memory/back_log，由root按合入范围整理。完整六SHA、命令和拒绝判断保存在`outputs/stage132_ema_limit_overall_review/review_receipt.json`；两例原始字段在`finite_probe_evidence.json`。
