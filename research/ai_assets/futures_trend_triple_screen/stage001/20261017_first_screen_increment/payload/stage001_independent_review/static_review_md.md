# Stage001 第一层周滤网：独立实现审查

- 审查者：`first_screen_independent`，2026-10-17 22:37 CST整理。
- 范围：本线预声明、周特征源码与冻结CSV、离线runner、原策略调用链、A0/C0 preflight。未运行金融引擎，本文当前不代表新账户业绩验收。
- 当前结论（22:44）：产品键P1已修复；首次A0的模型runtime不兼容经恢复冻结1.8全栈、固定概率smoke及A0_attempt2与旧账精确重现关闭。A0独立金融审账通过，尚未复核C0。保留一项不影响交易的P2诊断标签限制，生产资格始终false。

## 独立周状态核验

`stage001_independent_review.py --weekly-only`未导入实现模块，使用标量EMA递推，核对冻结19品种的77,368行：ready、方向、完整周计数、asof、reason均零差异；有效hist及前hist最大绝差`6.9278e-14`。source/calendar/module/tests/CSV的SHA全部与summary匹配。结果见`weekly_independent_checks.json`。

源码只向日期暴露其前一有源交易日的已完成ISO周。周内当前周数据不会用于当周决策。每周收益必须覆盖源calendar内该周所有交易日，任一缺失令该周无效并将指数/两条EMA/signal全部重暖。12/26/9递推在第34完整周才有首hist，第35周有前hist后才ready，下一ISO周使用。未上市和缺失阶段保持unknown，零斜率则为ready但无许可方向。这些定义与固定合同一致。

这项复核是明确calendar和已接受同合约r缓存上的时间/算术复核，未重新验收原始行情供应商或全市场清洗；Stage269的同合约身份和前日OI/量选择来自已接受上游证据。阅读上游源码确认参考合约先shift(1)，当日收益两端取同一contract_epoch，并未直接拼换月价差。

## 已关闭P1：真实产品键大小写导致静默失效

最初runner将`fu.SHFE`拼成`SHFE.fu`，但冻结CSV使用`SHFE.FU`。多数SHFE/DCE/GFEX产品会因此变成`feature_row_missing`并退回A0，候选不能检验声明假说。测试fixture也使用小写，未覆盖真实缓存接口。

独立审查向根和实现者给出具体键值证据后，实现者先将fixture改为真实大写缓存观察到2项失败，再统一lookup与context key的大写，12项runner测试通过。当前`build_research_strategy`使用`product_id=f'{exchange}.{product}'.upper()`，`WeeklyLookup`也规范化key。问题在首次账户运行前关闭，无需因其重跑任何金融账户。

## 入场门与账户副作用

原策略`_plan_flat_entry_candidates`仅对`context.current_pos==0`调用`_build_flat_entry_candidate_plan`。研究子类先保留原plan和原生AI/方向/规模拒绝原因，只有C0且原本native_openable、周ready且方向不符时清除native_openable；原规划器因此在并发计数和新增保证金计划前排除该plan。`on_bars`仅在candidate_status为opened后调用`_open_position`、`_reserve_intrabar_entry`及`_apply_state_target`，所以拦截发生在实际账户变更前。原plan中的诊断计算仍会发生，它不等于成交或资金预占。

研究子类只覆盖该方法。retry由Stage847在母成交的分钟事件链合成，不经flat planner；rollover在已有state合同不同时经`_handle_rollover`后continue；已有仓位的退出、止损、加仓未覆盖。账户完成后仍需以真实事件核验retry/rollover绕过，不以静态入口名称代替事件证据。

## 同源与离线身份

runner将四个已接受正确性修复源文件逐字节锁定为A_final3 SHA，锁定原分钟缓存`5c06124f…9189`、周CSV`d8bae990…f8e`。原s901组装参数在创建引擎前被捕获，preflight与旧A的effective_parameters和预期settings比较；运行后另捕获真实strategy属性，阻止环境变量悄悄改策略。共同空signal目录、实际输入读取指纹和运行后重hash共同约束AI、映射、元数据、成本和无供需输入的同源性。

旧adapter及其身份闸门未修改。m0008参数身份与修复源码漂移明确写入preflight，`production_qualified=false`、`formal_identity_gate=not_passed_for_production`。这是经用户授权的离线A0/C0研究，不能冒称正式A/B/C晋级或生产资格。

## 保留P2与置信度边界

`entirely_missing`使用全输入段是否存在有限r，追加首次上市的未来数据可能使过去reason从`missing_product_returns`变为`missing_previous_week_returns`。ready/direction/hist/hist_prev/asof均不受影响；runner仅将reason用于unknown诊断，不据其交易。按根决定仅披露，不为标签重算缓存。后续严禁reason作为交易信号、AI字段或资格依据。

固定19产品全日历74.82%覆盖含未上市日，只是数据诊断。真实生效比例必须以native初始flat-entry计划和实际母信号另计。旧statistics_audit的complete_episodes按母订单合并retry，不自动跨换月继承，因此其胜率应称“母订单+同日retry的完整episode”，不能无证据扩大成跨换月整段趋势胜率。

调研：[pandas官方窗口文档](https://pandas.pydata.org/docs/user_guide/window.html)和[官方GitHub EWM源码](https://github.com/pandas-dev/pandas/blob/main/pandas/core/window/ewm.py)支持递推和min_periods语义；该材料证明计算定义，不构成alpha有效性证据。

开始/当前过拟合判断：本次无按收益选参，新增选参型过拟合为否；原策略AI与累计已见历史选择偏差仍在。继续价值：有，先完成固定真实账户比较和独立对账才能决定假说是否成立。尚未看到A0/C0新结果时，不声称更高收益、更低回撤或OOS通过。

## A0 首次失败的独立复核（22:37）

首次A0在`2020-03-13`进入原AI的pairwise概率调用时，1.6.1消费者加载1.8.0生产者的持久化LogisticRegression，发生缺`multi_class`错误。`run_failure.json`保留了原bar错误，外层`KeyError(datetime.date(2020,3,13))`是vendor继续calculate_result的次生错误。目录只有attempt_started、engine.log与run_failure，没有metrics/daily，状态明确为失败且没有可接受绩效。独立检查见`A0_failed_attempt_checks.json`，未启动账户audit。

[scikit-learn官方持久化文档](https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations)明确跨版本加载不受支持。下一尝试只能恢复有证据的已接受历史runtime/既有shim并记录来源；不能任意补字段、重训或依据收益挑版本。恢复后仍需A0与旧账经济/成交哨兵可解释一致，再讨论C0。原失败产物保留，不将此次异常归因于周滤网alpha。

## A0_attempt2独立金融复核（22:44）

恢复的数值栈取既有Stage263/267相同FROZEN_SITE：sklearn1.8.0、numpy2.4.4、pandas2.3.3、scipy1.17.1、joblib1.5.3。模型SHA不变、未fit、未补估计器字段，5行固定非行情输入的StandardScaler+binary sigmoid手算概率误差0。`runtime_restore_checks.json`保留scope，概率smoke本身不代替账户验收。

独立脚本读取完成的A0_attempt2导出，未导入金融引擎。现金流+逐日持仓市值对账户权益最大残差`3.7253e-9`元，内部权益残差`1.8626e-9`，日净PnL累加残差`4.6566e-10`，成交滑点/手续费残差均0。重算期末权益`2,262,595.00`、收益`1,408.3967%`、最大回撤`-48.78985%`、Sharpe`1.367364`、滑点`605,450`元、816fill，与metrics一致；broker10峰值`63.12423%`，超100%/90%及破产日均0。

402个完整合约cycle、318个母订单+retry完整episode、113赢，胜率`35.53459%`。84条retry按实际母订单身份继承，8次换月开仓有同日targeted换月诊断及目标合同/方向/手数证据，501条分钟请求全complete且missing0。期末1个未平仓合同净盯市`4,800`元已纳入权益守恒。换月不强行冒称新初始母信号；统计术语保持此前定义。

886个flat-entry计划与886条实际候选一一对应周状态，A0无拦截。原生可开328条中ready270、unknown58，不能用全日历74.82%替代真实候选覆盖。

独立旧账哨兵不引用根的快捷比较：1,641日的11个经济/持仓列最大绝差全0；816fill的trade_id、order_id、symbol、交易日、物理时刻、方向、offset、价格、手数、净手数逐项精确同旧A_final3。实际策略属性与effective_parameters仅归一化共同空signal目录后完全相同。证据见`A0_attempt2/account_checks.json`、`baseline_sentinel_checks.json`及独立cycle/retry/rollover表。A0可作为本轮固定对照，单条历史路径没有新增严格OOS、独立起点或成本压力资格。
