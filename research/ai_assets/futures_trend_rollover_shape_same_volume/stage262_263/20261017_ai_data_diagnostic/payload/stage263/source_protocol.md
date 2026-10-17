# Stage263 统一AI源生成前协议

- 冻结时间：2026-10-17，生成前写入；研究线 futures_trend_rollover_shape_same_volume。
- 仅一次规范日线账户轨迹：analysis_start=preload_start=trade_start_date=2015-01-01，analysis_end=2026-10-08；本地无2014日线，不伪造预加载。
- 源策略保持 floor35/200,000/risk0.045，既有pairwise固定模型与经济规则；不改C9/15万正式配置，不接CTP，不下载，不生成HTML/多起点扫描。
- 研究子类仅隔离CZCE三位合约跨代历史：真实bar再次出现且与前次真实bar相隔至少5周年时，先断言该合约无持仓、目标、挂单或待结算诊断，再重建同尺寸ArrayManager、移除无余额旧mark。pairwise CSV历史按真实候选日和相同epoch截断，保持原CSV来源及无数据时原AM回退；不改模型权重。
- 主力映射和数据库只读，缺口不填零、不下载、不换主力；SM已知缺失供后续特征120日/标签60日完整窗口排除。没有候选的真实观察日可为零，缺数据日不能冒充零PnL。
- 固定pairwise权重来自后验冻结资产；本研究是给定这些权重的条件诊断，不是2015—2019当时可部署的历史PIT证明。源策略AM140与早期仅主力段日线可能使早期源信号极稀疏，结果原样保留，不缩短AM救参。
- 两训练臂仅从本次一次来源构建的同一全历史108特征/60日目标面板切2020+与2015+；共同2022-01—2026-06测试行、标签、purge合同逐值一致。不能另跑2020账户或混入旧Stage183冻结CSV。
- 输出source_position_changes.csv、source_entry_candidate_snapshots.csv、source_daily.csv、source_trades.csv、source_summary.json，保留完整engine.log、epoch重置审计、源码/数据/model/runtime SHA与统计。亏损不救参。完成后独立agent复核。
- 开始反思：无收益寻优，本轮是在修正覆盖与代际身份；有价值，因为可将纯扩样与账户起点、源码版本效应分离。但更多历史不保证更多有效标签。
- 调研：Microsoft Qlib [trunc_segments/RollingGen](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py) 与 [TimeAdjuster.truncate](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/utils.py) 以交易日历和未来标签跨度截断训练段；本项目使用逐行真实label_end，不以品种行数gap代替交易日。没有引入Qlib模型。
