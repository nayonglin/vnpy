# Stage021 同一研究引擎的阻塞式数据资格门

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 01:26 CST。
- 当前授权：仅纯门helper、必要合成测试和本协议；不接真实runner，不跑金融，不连接网络或下载，不改正式源码/旧Stage001。真实接合由root和独立审查另定。
- 目的：避免为保守可达上界预补全部潜在CLOSE锚点，也避免缺一个数据点就从头重跑策略。上界用于风险说明，不能把上界全部补齐当真实交易路径的必要条件。

## 源码依据与判断

- Stage827引擎第365–380行先收当前全部ordinary order context，再开始fill；第403–429行的订单状态、交易计数和strategy.update_trade均在context返回后。原context第312–358行读取数据后追加anchor审计，因此必须在调用原context之前等待，原context只调用一次。
- `qmt_roll_intraday_execution.entry_session`第77–122行与Stage847 retry均读取strategy的minute字典。OPEN完整时段已取得完成bar资格后，其后续scan/retry不需第二下载门；CLOSE只要求canonical首分钟真实合格anchor，不能改用daily-open。
- 复用[官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[官方源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)的完成记录与正常等待语义；helper不实现provider、不操作SDK授权。

## 最小接口

`qualified_wait_scope(engine_class, resolver, audit, qualified_existing_keys=..., qualified_anchor_existing_keys=...)`暂包该类的`_stage827_order_context`，首次调用懒绑定唯一engine，退出恢复原local方法或删除临时override以恢复继承状态，并恢复strategy原minute字典对象。新增分钟只存在目标strategy的隔离字典，避免改动共享s901全局cache；不增加另一套执行loader。

- 两个现有资格参数均支持精确`(vt_symbol, Timestamp)`集合或`predicate(symbol, Timestamp)->bool`，默认无隐式资格。common可供OPEN/CLOSE；anchor-only只供CLOSE，不能借给full扫描。
- 初始用途资格由root的受签数据栈提供：冻结基准/002/011/015/020实际键减残余source859，再加入016全部1500完整网格；anchor-only可另加固定Stage010 anchor需求中实际存在的859 canonical首键。该口径是继承已接受基准与用途限制，不是新认证全base价格。
- `resolver(request_dict)->QualifiedDelivery(absolute_receipt_path, receipt_sha256)`为同步接口；resolver只获得JSON数据请求，不获得engine/account引用，外部正常provider、日线七字段/后继核验及独立review由后续适配实现，不属于本helper。
- 请求内嵌`request_sha256`；公开同名函数按UTF-8、ensure_ascii=false、sort_keys、紧凑JSON、去掉该digest字段计算，避免file handshake哈希分叉。

## 等待和精确资格

1. 每次原context前，按当前engine.datetime、原mapping交易日历和canonical session_minutes枚举全部active orders，原引擎bar=None的订单同样不产生需求；直接context调用的当前订单也必须涵盖。相同symbol/day若有OPEN则full优先，否则CLOSE首anchor；不读取PnL，不改变顺序、订单、账户、bar或引擎时钟。
2. 只有缺物理分钟或缺对应用途资格的时段才产生请求；OPEN列完整grid，CLOSE列首键，同时注明实际缺/未资格键及现有源键。一次request覆盖当前批次全部未满足需求，不逐订单联网。
3. 同一engine调用栈同步暂停，resolver返回之前不调用原context。返回后核engine.datetime/订单身份/状态与bars对象未变，拒绝重入。若资格、数据或外部等待失败则抛错并保持fail-closed，不skip订单、不fallback、不在异常后重放bar或展示截断完整成绩。
4. receipt schema=`stage021_independent_minute_delivery_v1`，须independent_review=true、reviewer非空、qualified_research_data=true、P0/P1=0、原request hash；绝对data_path和data SHA须在source_fingerprints相同绑定。accepted_requirements必须精确等于请求的symbol/date/kind和完整required_timestamps，每项accepted=true且completed_bars_and_daily_qualified=true。
5. raw标准9列精确一键一行，范围必须恰等于accepted范围，拒错合约、多余键、重复、非法OHLCV/OI和SHA漂移。旧键七字段必须完全一致；只追加缺键，所有symbol检查完才提交。full交付进入动态common资格，anchor交付仅进入动态anchor资格，不能升级用途。
6. 全部当前需求满足后调用原context一次，由原引擎继续原成交队列/entry_session/retry。类方法和隔离字典在正常或异常退出均finally恢复；没有策略、价格、时间或订单顺序变更。

## 验证与边界

- 先RED后GREEN的必要合成测试：两订单一次resolver且原context各一次、等待期间fake账户/订单未动；未签/错request/错symbol/错SHA拒绝；旧值冲突和resolver异常下local/inherited恢复；anchor-only资格不能满足OPEN full。
- 这是有条件可行的研究包装器，不是完整C0回测或生产执行资格。真实runner还须证明vendor吞异常后仍fail-closed、初始用途资格、外部handshake等待预算、实际输入指纹及所有新增delta归档；独立review通过之前不进行真实金融接合。
- 新增/修改/删除策略参数：无；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。金融、网络、订单、撤单、CTP、模型拟合、正式源码及旧数据写入均0，production_qualified=false。
- 过拟合判断：否，数据需求由真实当前订单和固定执行语义决定，与PnL无关；继续价值：是，减少无效上界下载和从头重放，保持一次完整真实路径证据。不是用缺口跳单来提高收益。
- 不改LINE/registry，由root统一登记。
