# Stage024 C0完整路径独立复核与固定形状否决

- 时间：2026-10-18T02:03+08:00；line_id=futures_trend_triple_screen。不是alpha重要突破；是一次固定形状的完整负结果。只读验收，无新增金融/网络/模型拟合/生产修改。金融累计5次尝试、2次完成；3次失败全部保留。
- 结论：真实完整C0结果在已接受数据合同下可复验，P0/P1=0；固定七门5过2失败，收益与Sharpe不达标，停止本周方向许可形状，不扫MACD、不降低收益目标，不进入该形状多周期。

|指标|A0已验基准|C0本次|
|---|---:|---:|
|期末权益|2,262,595|1,190,295|
|总收益|1408.3967%|693.53%|
|最大回撤|-48.78985%|-43.03173%|
|Sharpe|1.367364|1.185018|
|总滑点|605,450|267,840|
|成交fill数|816|647|
|完整母订单episode|318|251|
|母episode胜数/胜率|113 / 35.5346%|89 / 35.4582%|
|broker10峰值|63.1242%|62.1882%|
|>100%天数 / 存活|0 / 是|0 / 是|

收益少714.8667个百分点，回撤改善5.7581个百分点，但Sharpe下降。滑点节省337,610仍不能弥补毛损益下降1,409,910，净利润少1,072,300。七门中lower_drawdown、margin_peak_not_worse、margin_over100_days_not_worse、candidate_survives、nonempty_candidate通过；higher_net_return、sharpe_not_lower失败。原DD40绝对门仍不通过，不以相对改善冒称低回撤目标完成。逐年损益仅作描述，保存在annual_net_pnl_comparison.csv，不据局部年份救失败。

## 经济账本、执行与真实母交易

复用既有独立标量现金/持仓mark及母订单helper，只重算C0，A0账本不重跑。1641日与A0逐日同序。现金流权益最大残差1.16e-09，internal权益2.33e-10，netpnl累计0，position日PnL3.64e-12，滑点/佣金0，闭合cycle加期末MTM残差6.98e-10。510728条持仓记录的起止/逐日净成交/持仓PnL及按实际margin比率重建均通过；647笔trade、usage、clock一一对应，411个ordinary anchor时间/价格/合约/交易日精确一致，无legacy fallback。389次完整scan，缺失0，failure0。

320个闭合合约cycle合并为251个完整母订单episode，89胜；69条同日retry母链已证，6条换月reopen链已证，期末1个未闭合合约MTM=2400，排除未闭合根的胜率。母episode定义与A0相同：普通开仓母订单及同日retry合并，换月新合约reopen按另一个普通母订单处理，不冒称已证明跨合约趋势母信号谱系。247个opened flat计划中246个匹配真实ordinary flat开仓；si2310/2023-08-23余1条仅计划快照，现有审查不推断未成交具体原因，不能把opened标签当fill。A0同口径也有1条不匹配计划（CF009/2020-05-11）。实际交易统计全部基于fills。

## 数据、逻辑和资格

actual settings、effective parameters、资金150000、成本、0.5R和retry1均与A0一致，实际runner_used=aaa0cc50…37582c，源diff/数据栈/协议未漂移。最终manifest覆盖原1590项stack指纹及新增交付；不重复1950源全量哈希或历史分钟重聚合。既有base/002/011/015/016/020资格按原receipt继承，并不声称全历史分钟价格重新认证。唯一动态cu2609/2026-08-14首anchor真实minute及21:01后继、013 open/openOI已独立签发；原同一engine恢复，15项动态文件终局SHA绑定，旧键改0，新1键与A0实际anchor/scan读集合交集0。

891条门审计与冻结周cache逐值一致，751 ready/140 unknown，77 blocked；unknown保持A0行为，ready asof严格前ISO周。只initial flat计划入门，69 retry及6 rollover开仓事件另有来源链，不重新过周门；已有退出/账户规则保持原代码。7条门允许计划后来被原concurrent_limit拒绝，属下游原规则，不能当周门误拦。复用已验completed ISO week、35连续完整周、缺失重暖及unknown合同，不重算EMA。

## 限制、置信度及后续

保留2项已接受P2：首次finite前reason诊断标签可随后续上市存在性变动，交易字段不前视且reason禁止用于交易；022预加载后的旧_GLOBAL引用未完整恢复，限单次独立CLI退出，无本次经济/磁盘影响。不修冻结源码、不重跑。生产m0008身份不一致仍显式production_qualified=false。

账务和执行一致性置信度高，结论限这条已接受来源下的完整历史路径；2020–2026已见历史及累计研究选择风险保留，没有新严格OOS、fresh-start、成本压力或统计显著性主张。负结果足以否决本次预声明形状，不泛化否定其他经典三重滤网实现。调研判断复用本线设计阶段Elder及官方多周期/TqSDK资料，本轮不再外连；本结果显示此低自由度叠加未保住收益。

新增/修改/删除alpha参数：均无。新增回测结果：C0_attempt3完整结果；修改/删除回测结果：无，失败attempt保留且不展示截断成绩。过拟合判断：本验收否，无收益选参或放宽门槛；既有历史选择偏差不消失。继续价值：完成负结果归档有价值；继续救此形状无价值。后续TODO：停止本形状及多周期，不扫周参数；如继续总体目标，须另立机制不同、预声明的新假说。LINE/registry由root统一整理，本review未改。
