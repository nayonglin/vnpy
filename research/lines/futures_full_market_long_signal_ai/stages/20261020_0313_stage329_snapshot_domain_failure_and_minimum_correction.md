# Stage329：真实输入暴露目录域错误，限定必要修复

- line_id=futures_full_market_long_signal_ai；2026-10-20 03:13 CST；沿用原分支。非收益突破、非金融/正式A/B。
- 327首次真实演练exit1，0.370524秒，错误original complete98/95 domain mismatch。nativecache实际加载1，econ/日dataSELECT/评分/journal/资金账户均0。失败现场完整保留，不重写成成功。
- 因果明确：新326把有native行的产品域硬要求等于完整目录98/95。004小roster实际98，其中DCE.S的source_observation_rows/qualified_candidate_rows/contracts_with_candidates均0，其余97非零。无native产品是应保留的不可用父行；不能要求它有价格，也不能删掉它后称97为完整市场。当前未再读NPZ epochs，因此97是原小metadata结论，不冒称第二次实际缓存统计。
- root和328实际审查均接受这是新adapter的P1，覆盖328静审对这一域门的core0判断；不是旧数据损坏、原模型缺失或金融策略失败。325尚未被实际调用。
- [机器决定](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage329_snapshot_domain_failure/decision.json)授权必要纠正：330单独源文件保存326原版，完整母域取roster98；native集合核原roster正数域，DCE.S保留no-current。只新增1组目录缺native回归，不重跑warmup/caller/旧套件，不改模型、止损、风险或参数。328仅delta审，之后root另冻331一次尝试，额外cache1、econ1/daySELECT1（前者已有1消耗，后二者尚未使用）。这不是自动retry，必须先因果修复和新source绑定；若仍失败保留现场。

本阶段实际无金融绩效，权益/收益/DD/Sharpe/滑点/交易/胜率N/A，累计453fit/246cash与先前1金融partial不变；新增的是1输入接线失败attempt，不算现金回测。T0/forward0，无真实state。

运行后过拟合判断：没有按收益修参，旧历史择题风险仍有。继续价值：有，修复完整目录与观察域的混淆是用户全市场目标所必需；没有价值的是因为无价格目录而重做全套历史数据资格。调研判断沿327官方SQLite/Freqtrade因果边界，本故障由本地精确roster和真实终态解释，无需扩外部搜索。正式/生产/其他线/Git未改。
