# Stage320：既有纯52因果生成核心

时间：2026-10-20 02:55（Asia/Shanghai）。所属线`futures_full_market_long_signal_ai`；非重要突破。依据317/318、315 `forward_preparation_acceptance.json`与319最小计划实施，只有本工具、同名test、本stage及自身implementation输出。0actual、0fit/cash/SQL、0真实价格/大表、0旧suite；T0未设、forward未启动。

实现完成，唯一新synthetic组GREEN。`tools/stage320_causal_forward_core.py`没有CLI、接收器或资金入口，固定部署原130 `main/2023-01-01` portable/scaler。源代码、测试、tiny终态与依赖SHA见[实现bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage320_causal_forward_core/implementation/source_bundle.json)。

## 四个纯入口

- `WilderState.append(u_index,bar)`仅追加当前已完成、当时接收的OHLCV/quality/closeOI；严格源calendar索引递增。保留原042 seed、lastN/run/lastclose、20low队列与21bar特征窗口；invalid或源calendar缺口按原042重置。`to_dict/from_dict`可严格JSON保存恢复，`to_series`供核心消费；窗口状态代表最新u，历史u须用其原快照。
- `build_u_observations(series_by_epoch,u_index,dates,economics,products,*,D_context)`生成完整固定products父域、真实月份候选、raw26、原anchor与状态。兼容原EpochSeries样式或WilderState；任何数组先截<=u。新产品当前观测记unsupported，未来才出现的行不影响旧u；未选、无bar、未知经济映射均保留，不代理邻月。
- `infer_scores(raw_rows,model,scaler)`按原26raw/26missing列序使用固定mean/scale、52coef及intercept，输出全部候选与design52/score；raw不完整不构成新资格门。不fit、不滚动重居中。runner负责绑定317的原小模型/scaler身份。
- `select_u(observations,scores,dates,*,D_context)`调用原156 AST定义，保持原u资格、positive、D<K先于argmax、score/epoch/action并列及普通/_F family规则；返回choices/audit/boundaries，并生成原131所需signals及`prepared=({u:signals},{u:full_anchor_references})`。原157 `apply_boundaries`同样抽取调用。

`D_context={confirmed:bool,D_index:u+1,D_date:实际下一源session}`由外层当时calendar/receiver证明，不能从未来bar存在推断。未确认时只向156暴露<=u日历，保留unknown；confirmed选择不得把unknown-D下生成的旧资格直接升级，需以同一confirmed上下文重建。真实deadline/T0归321，连续own-state归322。

## 固定数学与边界

AST只编译固定小源码中的明确纯函数/常量，不执行旧129/070的模块import、label入口、action_stream、simulate_action、训练或CLI。原129 own11/maturity_pool/maturity13与原130 design、原042价格/费滑/经济资格、原070 unit_estimate、原156选择和157边界均固定SHA。004原母hash及OI状态定义复用，母anchor仍最大正V→OI可用/较大→epoch；月份与_F不混池。

own11使用21有效连续bar的SMA20 TR；Wilder N先20TR seed再递推，不能用21bar重播预算N。第20根原u资格可为1而own11前11列NaN，保留原missing模型，不偷偷要求21bar或全26有限。maturity peer统计排query，front pair仍取完整pool；原q_missing不当新veto。最后两列维持2N单位，不能换成现金0.25N。

原042 calendar外lifecycle返回`len(calendar)`哨兵；selected signal额外保留封存`source_lifecycle_target_date/source_lifecycle_state`、原source index及K target/state。322可据新确认calendar解析同一pending target，不把旧长度当真实退出日、不用新metadata覆盖过去target。signals还含N/low20/uclose、cap、anchor、有效lifecycle/来源及K全部字段。数值接口raw/candidate缺失为NaN，外部journal转JSON null并保留原因；WilderState自身严格JSON-safe。

## 唯一tiny组与验证

遵循TDD先写测试：第一次RED因核心未实现；同组扩展的未来新品种状态与D上下文升级断言先暴露错误，随后修复。最终命令`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/test_stage320_causal_forward_core.py`：exit0、1方法/4子例、0.223秒。没有旧suite或真实数据。

子例覆盖：20根N=2、次根2.9、JSON续接2.855及gap/invalid reset；独立手算固定scaler/原missing列给score5和6；未来巨幅bar及未来新品种不改变旧u raw/reference/status；20根资格与21根own区别、完整父域、OI并列、全pool basis/query排除及stress成本2NM；高分K已过候选先排再argmax、普通/_F优先、pendingK且真实D早于target的原允许分支、D未知不补资格、原131信号字段完整。

新增/修改/删除策略参数与金融结果均0；权益/收益/DD/Sharpe/滑点/胜率不适用。此前318/root已复核官方预处理与维护者因果不变性原则，按本次授权不重复外网。当前实施不是新增历史结果搜索；历史择题风险仍存在。继续价值在于按既有政策接真实新证据，不能把synthetic GREEN宣称未来接收/连续资金/alpha或实盘资格完成。仅待323有限静审及321/322接线，不启动实际观察。
