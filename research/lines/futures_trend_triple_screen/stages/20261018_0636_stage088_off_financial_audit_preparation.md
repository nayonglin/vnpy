# Stage088：完整A_OFF/B_OFF账户的独立审计准备

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:36 CST。
- 模式：只读静态准备；不重审061/071，不读新账户途中PnL，不运行旧A0/C0/C_TS。
- 固定账户根：`outputs/stage065_pairwise_off_account/{A_OFF,B_OFF}`；150000本金、完整1641日、原费用/月AI保留，仅共同八项pairwise OFF。
- 结果：已给出精确helper清单、来源SHA和最小适配点；**没有执行账户审计，没有财务通过结论。** 084尚未最终pin，两个真实终态与实际路径/SHA均待root后续提供。

## 调研与判断

只读原033/038和其冻结030经济算法、065中性checkpoint/政策、062合同、057/058限制；按本次明确无网络边界没有重新网上/GitHub调研，不做新alpha。registry已读，本线仍由root统一索引。没有打开两个新账户根或任何新途中结果。

判断：可以复用经济算法，但不能直接执行旧033/038 main。它们仍固定旧C/B owner、旧schema、旧全等A门及ordered表假设。只允许薄的身份/字段接合，现金、库存、费用、母链、真实clock和预算公式不重写。

## 可复用的确切helper

完整签名、逐函数行号及SHA见`helper_inventory.json`，由stdlib AST解析取得，未import审计/策略模块。

| 任务 | 确切helper |
| --- | --- |
| 现金、权益、指标 | 030 `close(actual,expected,name,atol=1e-6)`、`reconstruct_metrics(d,t,capital)` |
| 单次库存/收盘margin | 030 `audit_inventory(source,d,t,parameters,settings)`，配033 `use_raw_positions_once(base,payload)` |
| 母链/retry/roll/end-open | 030 `reconstruct_episodes(t,candidates,conditional,rollover)` |
| 真成交/clock身份 | 033 `identity_audit(raw_usage,identities,exported_clock,exported_usage)` |
| raw→CSV等价 | 033 `serialized_csv_sha`、`raw_export_equivalence`的算法，适配065装饰/新字段 |
| owned checkpoint边界 | 033 `OwnedAccountUnpickler/checkpoint_binding`的来源/先验SHA模式；对照065 `_context/_raw_envelope/load_sealed_checkpoint`的新schema |
| B时序/最终q | 038 `b_artifact_review(bound,payload)`、`audit_b_timing(rows)`、`audit_b_budget_rows(rows)` |
| 完整设置差异 | 065政策 `check_settings_delta(reference,requested,actual,shared=...,reference_shared=...)` |
| 共同七门 | `stage001_compare.evaluate_metrics(a,c)`；仅在完整独立指标已核后调用 |

冻结经济算法030 SHA `3fe153c379b95b67aa1f083381b55786c1afb85efd5896f035d91c4eb55dac15`；033 `940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf`；038 `e9d651be9467c04241809a86c1046881cbe8e9def7c55b1c41bf7c79f0603dd7`。

## 最小新审计适配点

1. **owner、source、seal：**固定两个exact owner、arm/attempt1/run_id；允许的export source仅root给出的owner本身或其确切`exports/export_NNN`，不glob最新目录。真实tool终态与summary/raw/manifest/seal/context各SHA必须先验，再单次加载owned account-only raw。新schema为`stage065_*`，fixture_only=False、scope=full_2020_2026。checkpoint的writer是`stage065_account_checkpoint.py`，084金融runner是另一个已pin source，两者不能混为同一SHA。seal只是engine validation，不是独立财务通过。
2. **实际设置：**把旧“全等A”改为065严格八键OFF全字典门，保留未知键/漏键/非OFF差异拒绝；只能沿原normalize_reference归一shared空输入路径。reference漏掉的OFF项取已pin native MRO声明默认并入有效快照，不能get(None)蒙混。capital、日历、rates/slippages/sizes/ticks/margin及其他经济设置不变。核实际effective结果和pairwise runtime=None的封存证据，不在审计时重建strategy伪造运行时属性；月AI开关/路径/独立资格链继续保留。
3. **A与B分支：**A exact native strategy/engine，raw ordered=None，ordered_applicable=False，signal_machine_arm=None；不造空TS CSV或weekly/FI/intent成功声明。A仍做全部实际成交/母链/现金/库存/费用审查，给030母链helper的conditional可为空DataFrame。B外部owner=B_OFF，035+028 producer内部arm仍B_TS，不能全局替换成B_OFF；setup<=signal<execution，无unknown/native初始fallback，held/add/roll不混成新TS初始开仓。
4. **B OFF rank边界：**旧038 `audit_b_budget_rows`第248行把rank要求为正；OFF真实producer的`b_ts_final_budget_original_rank`应为0（065已接受反例源码明确[0,0,0]）。薄适配应另断言pairwise rank==0，用原稳定批次顺序/intent ordinal核gross前缀，不能把ordinal写成pairwise rank。只改此身份/排序门，不改rho、margin、各floor cap、q=min或保守原a前缀算术。B q0不能补位，quantity/selected_volume/T/S/forecast应从u候选到decision/fill完全贯穿，D实际F不重新算q。
5. **raw与导出：**065给所有CSV加research_arm与production_qualified，包括daily/clock/usage/identities；旧033序列化装饰只覆盖部分表，须按065确切格式比较，不能忽略额外差异。raw trades仅允许enum规范、证实的交易日/exit reason附加，实际trade/order/symbol/direction/offset/price/volume不变；sparse synthetic usage只由真实TradeData母身份补齐。payload字段/validation键取最终065+084实际schema，不照抄旧033的17键。
6. **provenance与最终比较：**旧reused_A0要求改为新共同policy/data/source绑定＋root提供的受限A0历史参照，不重跑旧账户或全市场哈希。1641日期逐项等于冻结reference且A/B完全一致，首2020-01-02、末2026-10-14，不靠单一count。061/071只核已审manifest/review/政策/层顺序绑定，不再重复其数据审查。

## 财务算术与胜率清单

每笔唯一实际trade_id：
`slippage=q*size*slippage_parameter`，
`commission=q*size*F*rate`，
`cash=-signed_q*size*F-slippage-commission`。

独立权益=`150000+累计成交cash+Σ期末signed_pos*saved_close*size`，逐日对齐raw combined、daily net_pnl累计、internal equity；逐日费用/成交数分别相等。原rate若为0应如实报告，不虚构佣金或宣布成本稳健。net_pnl、equity及母链net_cash已经包含成本，不能再扣一次；不触发intent无真实fill不收费用，retry/roll每个真实fill各计一次。

库存按成交signed_volume独立累积，逐合同/日期验证start/end、缺失非零仓位、期末mark、position net_pnl、active合约/产品和margin；复用已核raw positions单遍，不重开大CSV。只允许纯零且在起点之前的warmup行剔除，不能隐藏非零账。

母链以实际OPEN order/trade为根，匹配唯一native或conditional候选；same-day retry必须同合约/交易日、真实母单及严格先后，成本并入同root。roll reopen须实际旧合约close链和足量/先后证据，作为不同episode保留roll lineage。任一root仍有期末在途/持仓，则该root全部闭合cycle也不进入已完成母单胜率分母；期末open MTM仍计入总账。母胜率=`net_pnl>1e-6`的完整母链/完整母链数，不能用fill数或单次平仓cycle冒充。

## Margin、时钟与PIT

- 收盘exchange margin=`Σabs(end_pos)*saved_close*size*margin_ratio`；原七门日收盘broker10倍率**1.10**。原native入场预算倍率**1.65**，另报日收盘1.65诊断，不能替换原七门或宣称全分钟PIT组合峰值。
- B的T/S/q在u冻结，按原已admitted量a保守gross前缀复算最终q；F只决定实际风险/margin，gap可高于forecast，不能据u门宣称fill-time已重核或实际风险必受限。
- clock/usage/raw actual identity逐trade完全匹配；真实队列fill序号连续、执行时钟非降、signal<=execution、night session按真实trading_date；synthetic必须连真实母trade，不猜缺失普通身份。
- B所有合法intent含未触发项需full session资格；未触发项不得有phantom order/fill。D内首次持仓的entry suffix请求及first-bar open=真实F行为按冻结实现＋已接受因果反例和实际请求链接确认，不重聚合分钟。
- 057/058的两项历史pairwise PIT P1仍限定旧A0/原B，不能被OFF新结果洗白。新OFF确实去掉该决策依赖须凭实际封存证据；它不等于全系统model-free，月AI资格链和其他历史选择/数据PIT限制仍独立。账本正确不是可部署性或新OOS证明。

## 对比模板与实际命令边界

同一报告必须列：旧A0（受057/058限制的固定反事实）、原B真实失败/N/A、A_OFF、B_OFF。旧A0固定描述为权益2,262,595、收益1408.396667%、DD−48.789850%、Sharpe1.367364，来自既定062/065描述，本准备未读/重跑其账。

先报告新两臂独立算术与完整1641日，再用原evaluate_metrics的收益、DD、Sharpe、broker10峰值、超100天数、生存和非空七门比较B_OFF/A_OFF；另列与旧A0受限参照的绝对收益/回撤位置。只赢更弱A_OFF不能宣布原目标达成，summary/deployable flag也不能代账。即使描述性全期门通过，PIT、原成本局限、固定多周期/独立OOS和研究选择资格仍未自动成立，promotion/production=False。

`audit_input_template.json`只是一份**等待root实际终态的输入模板**，所有新终态/源SHA/指标均null或未开始，不能作为readiness或审计通过receipt。

已实际执行的准备命令仅stdlib AST/有限source SHA清单，完整命令与exit0在`preparation_evidence.json`。旧CLI的确切形式为：
`.py311/bin/python .../stage033_independent_checkpoint_account_review.py --completion-evidence ABS`和
`.py311/bin/python .../stage038_independent_b_ts_account_review.py --completion-evidence ABS`，但它们固定旧owner/schema，038还ACTUAL_AUDIT_AUTHORIZED=False；**不得直接用于OFF或现在执行**。没有现成的OFF actual审计CLI，本阶段不虚构新文件/参数；root给最终084及两臂终态后，只需把以上明确helper接入一个冻结的薄适配器，才形成可执行命令。

## 本次结果与反思

只写Stage088及其outputs。代码/策略参数/金融结果新增修改删除均0；权益、收益、DD、Sharpe、滑点、交易数、胜率均N/A（旧A0只作为标明受限来源的既定描述）。新账户/旧A0/C0/C_TS访问0，旧suite/金融/网络/模型load-fit-predict/全市场hash0，未改084作者文件或LINE/registry，未stage/commit/push，未另派reviewer。

开始及结束过拟合判断：**否**，这是在看新结果前固定算术和证据标准，不按PnL调参。开始及结束继续价值判断：**是**，最小身份/rank/原生A适配点已明确，能避免把错误owner、弱基准或summary通过误当真实金融结论。当前只完成准备，实际审计等root提供两个真实工具终态与准确路径/SHA。

