# Stage019：普通 latest-10000 有界批次协议

- 时间：2026-10-18 01:10 CST；研究线 `futures_trend_triple_screen`。本阶段不是重要 alpha 突破，只准备数据，不运行账户、不看 PnL、不训练、不改正式策略。
- 已核官方来源：[TqApi get_kline_serial](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方 API 源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)。本机 3.10.2 公开接口保留品种权限检查，独立字符串序列最大 10000 根；多品种列表会时间对齐，因此不用列表序列。普通 latest 接口与需要 tq_dl 的区间 DataDownloader 不同；本批不使用后者，不绕过授权。

## 冻结范围与选择

1. 只读已复审 Stage015 remaining（135 full、7942 anchor），排除无真实日线的 carry、原 Stage011 三个冲突以及缺合法七字段日参考的目标。只接受旧 manifest 绑定的原 CSV，或 Stage013 独立 receipt `194e4884…795` 允许的 4500 个精确目标；两条 no-successor 拒绝不豁免。
2. 估计普通 latest 窗口容量时，以当前自然日之后的下一个工作日为终点（本次 2026-10-19），已到期合约可取交割月自然月末这一保守上界。历史用真实 mapping 交易日；mapping 末日之后追加至终点的所有工作日，只作容量上界，不作为策略 bars。每交易日按冻结品种最大 session 分钟数计数，再预留 2 根；完整目标日到终点的上界不超过 10000 才候选。该估计依赖冻结交易时段，不声称真实 provider 覆盖。
3. 按候选 full 数降序、anchor 数降序、合约代码升序选最多 8 个合约，不使用收益。目标全部取完整 session 网格以沿用七字段资格，不新增 anchor-only loader。每 symbol 唯一目标分钟 ≤10000，总唯一目标分钟 ≤80000；各自复用未修改 Stage012 BatchCollector 的 observe/frames，小聚合器只负责分发和唯一性/预算门。

## 唯一连接与终态

- 先 prepare、focused tests、离线 preflight，root 审查后才可 `--run`；只允许一个普通 TqApi＋一个本地 TqSim，没有 TqBacktest、CTP、订单、取消、重连或接口自动切换。八个独立字符串 60 秒序列、data_length=10000 同批注册。正常鉴权与 SDK 检查不改，凭证不回显，SDK stdout/stderr/logging 丢弃。
- 570 秒统一软预算、600 秒 parent 硬预算、1.5GB worker peak RSS 门。wait_update 返回 False 只累计计数，继续同一连接直到总预算；真实异常立即终态。每个序列首次 ready 后完整扫描一次快照；仅存在后继且时间至少晚一分钟的目标 bar 被采集，末根不采。八个均已扫描即终态，缺目标保留 partial，不因周末缺实时更新等满预算。
- 原012核心/018/旧数据不改。raw 只保存目标 subset，completion_evidence、quality、worker/parent receipt 独立输出；quality 逐 session 完整网格＋原七字段匹配才 accepted。partial 不重试，不自动建 overlay，不据此重跑金融账户；后续仍需独立审查及与现有数据冲突门。

## 判断与结果口径

本次不是过拟合：选样只依据事前数据缺口和公开窗口容量，不使用候选收益；有继续价值：普通 latest 不占历史回测额度，能在一个有界连接尝试回收多个真实需求。金融指标（权益/收益/回撤/Sharpe/滑点/交易次数/胜率）均 N/A。新增的只有数据资源预算和确定性批次规则；没有新增/修改/删除 alpha 参数或回测结果。独立复核在真实终态后进行，本协议不授权金融回放或生产。
