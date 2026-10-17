# Stage013 94个精确合约缺失日线的正规恢复合同

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 00:23 CST。
- 性质：数据恢复，非金融回测/训练/策略变更。输入Stage011的4518个缺CSV需求，对应94个精确合约，159个full_session与4359个anchor；不包含3个既有分钟冲突，也不把16个无真实日线carry诊断当下载目标。

## 调研与判断

本机`download_tqsdk_all_futures_daily_csv.py:60-73,157`使用普通TqApi的公开`get_kline_serial(symbol,86400,data_length)`获取日线，ns经UTC转上海后直接取日期，不套夜盘分钟交易日推移。SDK仍在api.py:791-795/auth.py:203-214执行正常行情授权，不修改授权、不用`tq_dl`或私有网络接口。[官方API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方GitHub](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)。旧脚本会跳过已有文件且未排除末根，不能原样运行；本阶段只复用公开接口与时间映射。

94合约同时含已到期与未到期品种，按已冻exact symbols订阅，不按expired筛掉当前合约。DB每合约最多339根，公开10000长度足够只是容量依据，不保证当前账户权限或历史覆盖。此举有价值，因为补分钟不能解决缺日线校验依据，先恢复日线可让既有本地分钟重新获得资格。

## 单次获取与资格

1. 一个普通TqApi(account=TqSim(),auth=本机既有配置)，不用TqBacktest，不连接券商、CTP、不委托。最多94个独立单合约86400秒序列，data_length=10000；统一一次连接、570秒软/600秒硬预算、内存预算1.5GB；每个symbol读取后保存进度。权限/配额错误停止，不自动重连，不改成别的接口掩盖原失败。
2. 连接前冻结需求表/主DB/mapping/原导入器/SDK/API源码SHA；无endpoint覆盖，凭证只查存在不输出。SDK原始stdout/stderr/logging丢弃，只保留安全错误类别和允许字段receipt。
3. 原始快照保留本地，过滤padding/id<0/非法时间/非法OHLCV/OI，按同合约原id/time排序去重。只有存在严格更晚日bar且successor_id更大的目标才算完成；最后有效日bar无后继就拒绝，不因已到期而豁免。记录原ns/上海时间/映射trade_date及后继，不能把形成中日线混入训练。
4. 对精确需求日逐目标查询只读DB的唯一真实日线：新provider的OHLCV及open_oi必须分别匹配DB OHLCV/open_interest。固定检查openOI而不是在open/close之间择优匹配；原导入器把open_oi存入DB的已核合同为依据。本目标若不符就隔离，不泛化“全DB字段都已证明”。close_oi只来自新provider独立字段，DB closeOI明确N/A。
5. 新合格日线写本研究outputs下的独立daily overlay，保留旧CSV所需的trade_date与OHLCV/open_oi/close_oi核心格式，附source/完成证据清单；不覆盖项目根旧CSV、不修改DB或既有策略。未获DB目标验证的非需求历史只能算raw，不能自动作为合格训练数据。
6. 单次结束保存全部成功、拒绝、权限失败/超时及源SHA。独立agent核新增日线/交易日映射/完成性/DB六字段合同；取得合格日线后另一次必要本机分钟资格构建，不重跑旧完整Stage011，不自动启动C0。

## 验证、边界与反思

小测试仅覆盖最后日bar剔除、后继id/time、CST日期映射和DB openOI反例；实际权限验证只一次。若缺历史或权限失败，保留原失败，不重新标成成功；该来源不解决3个旧分钟冲突，也不证明剩余账户全路径可行。

金融指标全部N/A。开始过拟合判断：否，恢复精确缺失数据并核既定字段，不按收益改参数。继续价值：是，直接推进159个full需求的资格条件，目标仍是完整真实对照，不把数据恢复本身当策略成功。
