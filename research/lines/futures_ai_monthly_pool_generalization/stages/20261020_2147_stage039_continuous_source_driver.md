# Stage039 连续单品种源与普通退出后fresh再入场

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:47 CST；day，机制进展，非重要收益突破。
- 用户已授权连续自主推进，root负责真实source/标签协议；本项只实现连续driver、合成挑战及唯一stage，不改LINE/registry/其他研究线。
- 接纳Stage037边界：单episode不等于月度适应性源。半R/retry仅训练源关，C2保留；正式未改。

## 协议与实现

实施前先写`outputs/stage039_continuous_source/protocol.md`。新增`tools/stage039_continuous_source.py`的`run_continuous_source(case)`，输入完整calendar/start_day/observed_through、旧格式sessions与预声明monthly_eval_days；每日fresh_signal必须显式None或direction/contract/qty/stop_price/signal_high/signal_low的外部已识别dict。此版不实现raw信号识别器、账户sizing或历史资料资格认证。

复用Stage034私有pending actual-reference fill→新entry C2→日close exit/roll顺序和Stage024账本/Stage026日级规则/Stage031 roll helper。普通full close尚pending不当flat抢开；旧close本日open已fill后，本日close可排新fresh到下session。C2分支只在实际flat分支考虑重入，held分支继续原episode。新fresh可换方向，每次独立新FixedRiskLedger和首次signed currency-R、layer状态/RSI flag/age/C2入场日；roll继续同book，不重设episode分母。

累计source R=已完成episode R之和+当前episode MTM R，日增量为累计差分。新增pending entry尚无fill不计费用/风险收益，不冒充已成交；episode descriptors因此可能包含pending未成交book，不等于交易数。部分退出实际fill后commit，普通partial不新建episode。已完成episode缺成本时，后续新book不会洗掉旧净值未知；gross/录入tape仍留。

trajectory unknown永久保留、不再自动执行未来fresh，不以新入场或flat状态清零。flat缺整source session或fresh观察也unknown（机会可能缺失），不默认无信号。所有路径保留，超256拒绝不截断。月度eval逐路径精确取eval day快照，未来行保留not_yet_observed，不提前成熟或丢行。完整候选宇宙/未来60日标签由root外层另定，不能从本helper输出宣称已具训练资格。

## 测试与实际合成运行

TDD先空API见10个缺feature assertion失败；随后实现，修正2个synthetic fixture中signal高低未随改动后D bar更新的输入错误，未放松signal-bar绑定。原10挑战全绿，再加普通partial flag→fresh reset及roll同book两个已实现合同回归，最终本项12测试通过。21:46本线discover共122项全通过（含其他并行新增测试，收据只代表该时点）。

21:46:23单次固定合成run：7 case、8 path、43日trace、6 known/2 trajectory_unknown、11 episode descriptors、21 monthly eval rows。新R不同、pending不抢开、C2两路径重入差异、未知sticky、旧cost未知、flat机会缺失及roll分母均保留。详见`outputs/stage039_continuous_source/run_20261020_214623_073325/` inputs/outputs/summary；本次不读取真实行情、不计算金融绩效，独立review由root后续安排/接纳，不把本项自测冒充独审。

新增研究API/累计字段/月度clock，正式/模型alpha参数新增、修改、删除0；金融回测结果新增、修改、删除0。权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；真实市场回放、fit、净60日训练标签、下载、订单、生产修改0。不是把7个合成case当7个历史独立经验。

## 限制、调研与反思

调研沿用本轮已核VeighNa官方GitHub target/actual-pos与本地完整MRO映射，判断是连续source必须先分清pending/actual和新fresh/roll分母。当前private Stage034复用意味着其close-first roll研究约束、局部shape非完整hard-block/账户资格、外部anchor/economics声明边界均继承；daily.open proxy即使上游给了evidence_id也只能显式研究假设，不能称实际session anchor认证。

开始/结束新增按真实收益选参过拟合：否，本项没有真实数据表现试算、择源或阈值扫描；既有来源覆盖和静态经济偏差仍存在。继续价值：是，把月度适应性的连续重入和跨episode未知累积做成可审机制，尚无模型预测力或收益改善证据。下一步root按预声明数据/标签协议接真实逐日信号/数据，再由独立agent审结果、数据、时钟、成本和bug；候选未知不删池，条件参考值不升级formal训练资格。
