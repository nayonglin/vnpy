# Stage016 V5资金来源、初始现金、周五报告及外层接线独立复审

- 时间：2026-10-31；精确封存时刻/SHA见JSON。仅新增独审，旧V1/V2、失败attempt及Stage014不改。
- 结论：离线组件条件接受。331个不同测试通过，依赖复绑另复跑17例，共348次执行。开放P0/P1/P2均0；真实来源、生产、master晋升及安装均false。
- 分项：provider50+warm13+旧47+原独立provider11+新增6=127；资金61+原独立40+新增CP5=106；report21+独立13=34；外层pipeline/daily/state/entry/readonly/config/health/907与新增编排=64。合计331。

## 核验结论

1. 初始CP要求完整fresh CNY原账户、精确15万元Balance与合法Available。初始Deposit只是观察基线，不扣R、不凭建议加E。同raw幂等，后来reset拒绝。真实最终日结缺失保留已知cash并阻新开；caller布尔不能创造statement parser。
2. planned/delivery/native身份唯一，父计划和实际child cap分列，成交量不冒充委托上限。同连接四原始epoch不能normalized补证；SHFE业务close与native offset并存。恢复fills先于累计order，query不冒称push。
3. CAPTURE五源、authority十二源锁门；registry要求真实FULL资格、原字节production manifest/activation和实际stable HEAD，材料source独立，不作祖先放宽。HMAC fixture只证明完整性，实际来源没有正样本。
4. report重算当前E/R/source/request/gap，缺actionable不默认true，E恢复不强付旧建议。私有文件、noFollow和冷并发锁保持，未知SMTP结果不盲重试。
5. 外层qualification先于数据/建状态，preview不可转live，事务提交→daily receipt→mail；receipt失败阻mail，提交后异常须reload/reconcile。

## 不接受范围

- 无真实CTP/银行/SMTP/订单、registry/key、金融、生产或Git index/commit操作。最终日结statement parser仍missing，真实到账E2E不接受。
- runtime、CLI、datareader/dataupdate仍在开发；JSON保留测试时SHA、17例复绑SHA及后续漂移。本批不接受新性能/service/SHFE batch/CLI/data整链，V6childproof另审。publish_execution当前not_installed。
- parent在基线后切候选default为weekly19；CURRENT仍m0008、material_ready=false。route/config/health测试为切前默认快照，不作为新default正式材料或生产通过。Stage914动态profile/activation builder/health只读检查，无真实production正例。
- 旧fund95/state27及原2P1+3P2失败证据不改，修复反例本批复验。封存工具遇到编码错误及两次运行中依赖漂移拒签，均未写实现/金融，最终剔除漂移源整体验收；不为后处理重跑金融。
- 调研判断：官方vnpy_ctp的onRspQry/onRtn语义应严格区分（https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py）；本地源码和反例是本次证据，资料/hash不授予真实来源资格。
- 是否过拟合：否，不改alpha、风险比例或历史起点。是否继续有价值：是，真实场外到账、日结连续性和执行接缝仍是生产必要证据。

源、日志、依赖漂移和历史证据SHA见JSON。本批receipt封存后不改。
