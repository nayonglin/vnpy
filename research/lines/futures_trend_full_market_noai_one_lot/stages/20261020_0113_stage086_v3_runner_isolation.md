# Stage086 v3独立入口与失败证据绑定

时间：2026-10-20 01:13（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。只复制冻结079为 `tools/stage086_run_fractional_risk.py`，加入085策略/引擎MRO、代码hash、v2 provenance及审计输出。不是收益突破、未跑金融，不修改旧079、078、074或v2源。

经济参数逐键与079一致；0.5% policy、baseline N manifest、起止时间、日线proxy/禁C2C9intraday/禁供需及原始行情绑定均不变。085修复延期原授权、资金及实际PnL事实，详情见同时间Stage085记录。原Stage078强制规划隔离与Stage074部分CLOSE保护在最终086实际栈继续通过。

新增来源绑定：

- 被阻断v2：`run_20261020_contract_weekly_risk05_v2`。
- v2 manifest SHA256：`b5357eef7ec6f3ce9a844bfbf680b7eb5fe24e4fb6e91dec6e87f6ea56933635`。
- v2 protocol SHA256：`ccba699bf4b3576d17442c9f655ec7596a385f13750c9c6b39ce50666dd2aa50`。
- 原v1失败protocol绑定及原N基线绑定继续保留。

新增 `pending_open_lifecycle_events.csv` 导出并被常规输出hash绑定；runtime失败快照保留近期pending事件。每个有效延期意向每天reset保留一条原receipt证据；重挂缓存派单与取消事件分别记录。账户快照增加物理/待开资金与cluster真实PnL只读字段。

P2透明披露：原078的quote_datetime是引擎缓存bar标签，可能是当日forward-fill事件日，不必然是原始实价日期。086仅在导出阶段按同一冻结market的最后可用报价日补 `causal_quote_asof`、`valuation_proxy` 和字段语义说明，不改变任何经济价格、订单、估值、信号或成交资格。JR202109 2021-08-11估值使用8/10真实close2552的情况由此可见。

延期映射前置检查限定于真实缺bar/低量延期或preserve见证的原receipt对象。普通首次T→T+1开仓没有新增映射门；使用原开盘风险/周线/生命周期检查。策略指标只接原真实信号bar，缓存派单不更新AM/history_data。

TDD/验证：085定向63项通过；086参数全键、MRO与provenance、asof只读导出3项通过；全研究线401项/31.034秒/OK。cmp确认079与v2 code_snapshot逐字节相同。源码hash `90ac9d27ef0326eb3a72be1e84e26e186d85e066e95f9eb2462b61aec4ce3bf4`，测试hash `159de4d6bd4876ddeeea6739f643532daff51cdabbf98ea02d895b6481f8289e`。

新增/修改/删除经济参数均无，新增有效金融结果无；本阶段权益/收益/回撤/Sharpe/滑点/交易次数/胜率不适用。不是过拟合，因为不使用收益选条件；有价值继续，因为v2独审的授权/资金事实错误必须先闭环。Root待独立Stage088通过后提交冻源、登记唯一新v3输出并运行；本作者不提供自身金融独立认证，不修改LINE、registry、Git或生产。
