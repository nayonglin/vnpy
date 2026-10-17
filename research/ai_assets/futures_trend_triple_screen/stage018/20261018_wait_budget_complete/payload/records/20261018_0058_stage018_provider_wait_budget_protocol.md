# Stage018 单连接总等待预算修正

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 00:58 CST。
- 当前模式：仅实现、合成测试和离线preflight；真实连接由root与独立review通过后唯一执行，不由实现agent启动。
- 阶段性质：有确切SDK语义依据的采集控制流修正；不是新alpha或正式发布，production_qualified=false。

## 外部调研与判断

- 官方API文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html ，官方GitHub：https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py 。已安装3.10.2的api.py第2043–2058行也明确：wait_update到deadline无业务数据更新返回False；这不等于权限拒绝、连接终止或历史不存在。
- Stage017第198–199行在首次False即抛TimeoutError，Stage012也有相同潜伏分支。这个控制流问题确证；Stage017实际64.247秒、raw0的具体异常位置因原safe_error未存阶段/trace，只能推断，不能声称修正后数据一定可得。
- 不修改历史Stage012/017字节，不升级SDK、不修改授权，不使用下载接口或私有网络通路。

## 固定设计

1. Stage017 batch_manifest.json原字节复制到新输出，SHA固定a58a875df23d2dda6c797d94e7f46275f0b832377325ef7cf68423b7601a0219；不重选目标：8合约、39session、12945目标分钟，AP210.CZCE/2022-04-06完整225分钟强制包含。provider时点仍2022-04-07 09:01–09:05、每合约独立公开get_kline_serial(60,10000)。原manifest中的Stage017协议身份保持原义，Stage018协议另列preflight。
2. 一个正常TqAuth/TqApi/TqBacktest和本地TqSim。沿原Stage012 BatchCollector完成bar/后继证明，不改Collector或认证，正常tq_dl只读布尔不改变接口。
3. 短wait_update窗口仍最多30秒，但False仅累计idle_waits、写安全阶段枚举并继续同一api；总预算从worker初始化前的monotonic起算570秒，600秒父硬kill。只有目标齐全、总预算到期、BacktestFinished或真实异常才停止。不重新构建api、不重auth、不自动重连/重试，不自动切换接口。SDK自身正常行为未改。
4. 新增安全诊断仅phase、计数、elapsed、ready serial数，不记录原exception文本/trace、token、配置内容或SDK原始输出。真实异常立即停止并记录异常类型与既有安全类别。
5. 合成测试先RED再GREEN：False/False/True可恢复；连续False耗尽同一570秒预算；真实权限异常立即停止。离线preflight绑定新工具/协议、原017 manifest/preflight及原输入与SDK。不得覆盖已有输出或attempt。
6. raw/evidence/quality仍独立保留，只有完整网格、合法七字段、明确后继及原CSV七字段一致才具备候选资格；真实结果必须独立审查。Stage016仍须AP210新的实际独立资格，不由本阶段preflight自动放行；不启动C0。

## 参数与记录边界

- 新增参数：无；新增行为为30秒idle继续到既有总时限。修改/删除策略参数：无。
- 账户/策略/AI/费用/0.5R：未变；无账户引擎、PnL、下单、撤单、CTP或旧数据写入。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A（数据采集控制流，非金融回测）。
- 过拟合判断：否，依据公开SDK语义修正等待控制，不按收益改目标。
- 继续价值：是，先排除本地提前退出；如唯一新连接仍失败，如实保留后停止，不连环救试。
- 不改LINE/registry，最终统一由root登记。
