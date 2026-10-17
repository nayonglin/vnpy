# Stage023 真实等待请求的单packet公开补数工具

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 01:34 CST。
- 当前授权：协议/helper/必要离线测试和prepare实现；不实际连接、不金融、不自行prepare虚构生产请求。真实request出现后root与独立review通过preflight才唯一run。
- 目标：响应021当前真实订单数据缺口，减少上界下载及金融从头重放。不是alpha迭代或执行fallback。

## 请求身份与分包

1. 与022约定唯一生产路径：`outputs/stage001_first_screen/C0_attempt3/data_wait/request_<canonicalSHA>/request.json`，同目录必须有已原子保存的`request_fingerprint.json`，含request绝对路径、canonical SHA和实际文件SHA。CLI显式提供实际文件SHA；路径、文件、fingerprint、021公开canonical算法均必须一致。
2. 日期必须在2020-01-01至2026-10-14原周期且为原mapping真实交易日；每个requirement的symbol/kind来自请求active_orders，full为完整canonical网格、anchor仅首键，拒重复、错日期、错kind/格和空缺口。无账户/PnL读取。
3. 按symbol代码排序每packet最多8合约，`--packet-index`显式分包；记录packet_index/count及covers_whole_request，多packet绝不把单packet成功称全请求齐备。各packet原始文件只保留其精确请求键，不保留暖机快照额外行。
4. 显式fixture-root仅供离线test/prepare身份契约；fixture_scope=true的packet无条件禁止真实run，不能把测试路径当真实引擎请求。

## 已有日线参考与正常数据通路

1. 原A_final3 manifest SHA绑定mapping和日线CSV；原CSV目标日须唯一且有更晚真实日线行证明完成。完整时段须七字段有限；anchor须真实日线open，有openOI则核。没有原CSV时仅可使用已签013精确accepted并含后继证据的目标七字段；013明确拒绝目标、参考缺失或未完成日线在preflight前拒绝，不临时查询DB/日线兜底。
2. provider时点只取目标日后下一mapping真实交易日09:01–09:05；末端没有下一mapping日期即拒绝，不猜周末或假日、不扩mapping。独立合约公开get_kline_serial(60,10000)，正常TqAuth/TqApi/TqBacktest及本地TqSim；不下单、不改认证、不升级SDK，不用DataDownloader或私有接口。
3. 复用未改Stage012 BatchCollector的首次全窗和更晚bar后继语义，只输出请求键；复用未改018 collect_with_budget，False在同一api继续至570秒总预算，600秒父硬限，无应用重连、重auth、自动重试或接口切换。真实权限/配额/网络错误脱敏保留并停止，不绕过。
4. full逐session核完整网格、唯一合法OHLCV/OI、后继及已绑定日线七字段；anchor核真实首分钟raw合法七值/后继、其open与同SHA已接受日线open一致（有openOI则核），资格明确anchor_only_not_full_session。日线open只是交叉核验，成交数据仍来自真实分钟raw，绝不以日线价格生成分钟。

## 产物与资格分工

- 输出`outputs/stage023_request_provider/request_<SHA>/packet_NNN/`下packet_manifest/preflight，唯一network_attempt1含raw/evidence/quality/parent/worker、安全阶段错误/进度；均绑定request hash、packet身份与源SHA。原base/overlays/旧stages不写。
- 工具从不写引擎response，从不生成`independent_review=true`，也不签021 receipt。root在各实际packet完成后交独立agent审核，另组全request精确data/receipt，再写022 response；未全部合格不恢复引擎。
- 参考[官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)及018实际正常窗口证据；不新增通路探针。
- 必要tests先RED后GREEN：8合约分包不能冒称complete、canonical/fingerprint/末端mapping拒绝、anchor用途及raw-open核验、拒绝/未完成日线无fallback。已有Collector/等待预算测试复用，不再重复全测。
- 新增/修改/删除策略参数：无；账户/alpha/AI/0.5R/价格/顺序未变。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；金融、订单、撤单、CTP、模型拟合、生产写入均0，production_qualified=false。
- 过拟合判断：否，由实际订单和固定数据合同请求，不根据收益挑数据；继续价值：是，在保持执行语义的同时少下载、少重跑。未获资格不能用截断成绩替代完整结果。
- 不改LINE/registry，由root统一登记。
