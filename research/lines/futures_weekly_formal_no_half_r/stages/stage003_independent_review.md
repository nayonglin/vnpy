# Stage003 关闭半R/C2/AI的周线研究独立复核

- 复核时间：2026-10-22 21:31 CST；独立agent=stage003_independent_review。
- 范围：代码/实际开关、基础池、周线因果、成交语义、完整输出财务与原行情。未修改实现，未另跑策略。

## 首轮只读审查

- D_attempt001实际类=WeeklyIndicatorsStrategy；enable_stage847_half_r_stop_retry=False、enable_stage827_intraday_c2_stop=False、enable_ai_product_pool_filter=False。
- 原AI方法False时直接允许基础池品种，不加载月度快照；实际product_universe_csv为19行原基础池，未扩大全市场。AM=41、5日换月、target_contract_only保持。
- 关闭止损没有关闭首分钟成交锚校验；日线价格风险/盯市保留。周线adapter、指标周期值/聚合方式未变。成功分支还核验AI disabled/0快照及盘中事件/scan0。
- 首轮terminal=failed，2026-10-22T21:29:23.559234+08:00—2026-10-22T21:29:54.884596+08:00：RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:fu2109.SHFE:2021-06-21:2021-06-18 21:00:00')")。原分钟锚缺失，严格闸正确退出。无全窗metrics，不能当0收益或当已经完成。
- 缺口可在冻结本机tqsdk_stage462_completed_preclose_full_dates_shard/SHFE/fu2109_completed_minute_backtest.csv找到对应真实完成分钟（非0量占位）；是否补入须由主runner冻结证据后复跑。
- 当前配置逻辑未见新增P0/P1；当前P1=1为D未完成数据覆盖阻断，不能给全窗财务资格。后续成功新attempt另作完整复核，不删除首轮记录。

## 研究判断

- 过拟合：本轮新增风险否，固定模块消融且未按盈亏改参数；原周线历史覆盖/历史品种选择偏差未消失。
- 继续价值：是，真实补缺后可回答本组合改动；不能单独归因C2与AI，不能用单窗直接晋级。

最终结果待完成attempt独立核验后追加。


## 2026-10-22 21:51 CST 最终D独立复核

- 最终输出：D_attempt011；该组已完整2020-01-02—2026-10-22共1647账户日；前述失败数据闸保留，不计成绩。
- 当前无剩余P0/P1/P2阻断，可报告离线结果；**RESEARCH_ONLY_NO_PROMOTION**。本独审没有重新运行策略。

| 指标 | A 正式同数据 | C 周线/半R关闭 | D 周线/半R+C2+AI关闭 |
| --- | ---: | ---: | ---: |
| 期末权益 | 2,250,195.00 | 252,800.00 | 323,250.00 |
| 总收益% | 1400.130000 | 68.533333 | 115.500000 |
| 最大回撤% | -49.070504 | -15.066180 | -16.340226 |
| Sharpe 252/样本标准差 | 1.362404 | 0.704659 | 0.729030 |
| 总滑点 | 605,850.00 | 5,450.00 | 7,360.00 |
| 成交笔数 | 817 | 72 | 100 |
| FIFO闭合匹配段 | 414 | 36 | 50 |
| 扣双边滑点匹配段胜率% | 30.193237 | 38.888889 | 44.000000 |
| 手数加权胜率% | 23.405093 | 34.782609 | 40.865385 |
| 期末未平手数 | 0 | 0 | 0 |

### 实际开关与变更范围

- 实际类WeeklyIndicatorsStrategy，半R/C2/AI filter均False；AM41、5日换月、target_contract_only不变。C→D有效参数仅C2与AI两项True→False，半R此前C已False，没有其他风险/资金/成本/指标阈值变化。
- 实际基础池19品种；82条候选AI enabled均0、allowed均1，signal_date空，score/rank均0。AI资格门确实不再阻拦基础池，未扩市场。成功runner独立运行时还核AI load_status=disabled、eval_dates空；审查代码确认False分支不加载AI月池。
- 盘中事件、半R事件、C2事件和分钟scan均0，未隐式启用另一盘中模块。保留其他日线价格风险及原首分钟成交；不是关闭全部止损。
- raw metrics/spec note/label仍属正式来源元数据；D实际身份以arm/result_scope/profile、实际设置及本审查为准，不能把继承note解读为半R或AI仍开启。

### 原始数据与会计独立重建

- 独立逐笔现金流＋日末真实仓位重建权益，最大残差1.16e-10；逐合约日PnL最大残差3.64e-12；逐日滑点0差，signed volume0差。rates均0/commission0，收益口径为固定滑点、手续费0，不是实际完整扣费后承诺。
- D实际436条持仓或成交合约日逐行核SQLite真实收盘，缺失/非法/差价0。
- D100条实际成交锚按精确minute与raw开盘核对0差、bar failures0。两个盘中模块关闭，所以要求scan0；未把不需要盘中路径误报为缺数据。
- 6508输入逐SHA重算0差，postflight不变；90份分钟proof共357575行，原raw hash/逐值、原冻结CSV身份、Tq serial与完成snapshot边界均通过。带parent_proof的派生单分钟另核旧C输入清单SHA、parent当前SHA与source元数据逐项一致；新Tq单分钟同样保留raw及snapshot边界。
- 首分钟catalog共42369行；只填base+proof缺键，catalog同键冲突候选不接受且已有值不替换。D实际新消费20个catalog独立锚，按其source_path定向读取原CSV逐值0差，原SHA在冻结清单。合并后minute重复/冲突0。
- 23677条周bar与SQLite日线重聚合逐行0差；源会话集合、OHLC、volume sum/OI last均一致。41为已接受观察周，非保证连续41自然周。

### 置信度及解释限度

- 本组真实财务及实际消费数据内部一致性置信度高；单窗不证明穿越周期、真实成交容量或生产资格。旧metrics.deployable_pass仅历史研究布尔，不能当晋级证据。
- 周线41观察门槛与真实合约有限历史覆盖仍在：102日无ready目标，中位仅3个；低交易/低回撤须结合暴露，不宜归为信号alpha。AI关闭减少AI月池选择层，但不消除原策略/基础池历史选择和同样本研究偏差。
- 同时关闭C2与AI，只能比较合并作用，不能单独给C2或AI因果结论。保留原A/C/D及全部负结果，不扫阈值救参。
- 过拟合：本次新增否，固定用户指定模块消融，补数据不改策略；继续价值：本次请求已可回答。若要晋级或做结构优劣结论，需另冻结独立起点/成本及等暴露验证合同，本次不进行。

机器可读证据：outputs/stage003_independent_review/final_audit_result.json；审计脚本：outputs/stage003_independent_review/stage003_independent_audit.py。

### 暴露及年度收益差的补充复核

- D平均保证金/权益4.674902%（使用保证金300日），C为2.347974%（148日）。D收益提高同时增加暴露，不是等暴露对照。
- D相对C期末增加70,450元；逐年利润差以2025年71,460元为主。D Sharpe相对C仅提高0.024370，最大回撤略恶化；不能用单一有利年份和小幅Sharpe提升声称稳健优越。
- 这仍是C2与AI共同关闭的联合消融，无法单独归因哪一模块；不晋级。新增逐年复核表为outputs/stage003_independent_review/annual_comparison.csv。
