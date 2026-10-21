# Stage073 两条后续分钟证据追加与全域源复验

- line_id：`futures_ai_monthly_pool_generalization`；运行2026-10-20 23:10:18—23:11:00 CST，约41.7秒。
- 非重要alpha突破；独立研究来源，不触发正式A/B，不更换目标/source v1。

## 调研与判断

延续[交易所交易日原则](https://www.shfe.com.cn/content/lxjy/f18-3.html)和[上游RQAlpha时钟源码](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/trading_dates_mixin.py)的判断：精确epoch×source_trade_date不能用自然日或当前代表合约替代；参考时段与真实交易/PIT资格分开。Stage064找出的OI202301@2022-08-29、SH202605@2026-03-16为此前117输入之后的后续C2缺口，Stage067统一audit7来源组件，Stage072独审136检查接纳两条完整345分钟参考路径，保留1残缺和4无行。

本次只把两条独审资料加回同一冻结源，所有信号/费用/日级退出/C2/roll/逻辑T00anchor/固定2手规则原样；halfR/retry仅训练源False，C2=True。不存在为42个单日缺信号另改observability合同。

## 变更与参数

- 新增：073 wrapper与3个gate/旧金额位级守恒测试，红→绿；新119输入union与exact parents SHA。
- 修改/删除旧代码、策略/模型参数：0。旧117、055/056/058和所有历史run不覆盖。
- wrapper仅在当前进程调用旧058时绑定两个父review；源全量98产品域×201月=19,698格，4 workers；未省略任何未知品种。
- 058旧模板在新目录产生的Stage057-only说明由`evidence_lineage_erratum.json`显式更正；原receipt及SHA保留，权威append receipt逐项绑定旧Stage057117与新Stage0722，不能声称新两条被旧review审过。

## 结果

- 4,762旧known的四项float64金额及status/path/episodes完全不变；19,698行asof/role/clock未变。
- 5个后续阻塞窗全部恢复为条件点值，合计4,767；3,398成熟未知、233未成熟保留，不置0不删N。119条参考输入均被注入，2新增事件仍非physical/PIT/broker资格。
- 这是单品种冷启动累计episode unit-R条件结果，不是资金组合回测。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。
- 0 fit、0下载、0生产/CTP/订单/调度。source review见Stage074：138,490检查/0失败，包含22窗44次自组旧新回放和新C2手扫，未解决P0/P1/P2=0/0/0。

## 反思

开始/结束新增按成绩择参过拟合：否；仅追加事前按缺失识别的全部两事件资料，不按方向/收益选择，已知负值也保留。上游历史开发、静态经济和reference-session偏差仍在。继续价值：是，5完整窗是可验证的数据改善；不据此宣布预测提升。下一步固定完整N重算标签，冻结现有模型作评价，不因少8条标签立刻重训。
