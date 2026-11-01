# Stage020 复盘来源与精确行情预审

2026-11-01，研究线 futures_weekly_short_ma_slope_gate。只读已冻结 Stage019 交付与旧 Stage014 2026 年独立窗口，不新跑金融、下载行情、连接 CTP/SMTP、访问生产或启动 HTTP 服务。不改策略，不构成新 OOS 或晋升依据。

Stage019 外层 delivery receipt 与独审验收及全部交付 SHA 绑定通过；74 原金融输出逐份实读 SHA 不变。18 个完整平仓轮次精确覆盖36实际成交，没有残余。逐轮重新按成交方向、数量、合约乘数、费率和双边滑点核对：毛损益25,310减总滑点2,930（手续费0）等于净损益22,380，8盈10亏。净利润不能误用 canonical 旧账的毛 PnL。

17个实际合约按开仓日唯一 contract_epoch_id 绑定，同一 epoch 有实际退出日；physical_epoch_daily 与 SQLite 每日OHLCVOI逐项一致。36成交实际交易日与日开盘价一致，夜盘自然时钟另行保留，不把周五21点画到周五日K。所有持仓期产品交易日都有精确合约日K，没有持仓期缺日。18轮前300根真实日K均因合约上市历史不足而截断，12轮平仓后不足50根，不得补齐、混用十年前别名或无披露换主力背景。

已知分钟资格仅查两个既有 downloaded_futures 根下17目标合约精确文件名，以及4个 canonical 已知bundle路径和已批准 daily.sqlite 的1m表，没有全局/home扫描。发现52候选路径（内容重复会去重），SQLite还有1m，不等于全部可用。以冻结产品交易日历映自然时钟，18:00后推进到下一产品交易日，周五夜归周一；同合约同时间戳冲突拒绝。仅同物理epoch、有限合法OHLCVOI、全天聚合与已批准日线OHLCV及末OI完全一致、每个15分钟桶恰有15个真实分钟才准入；无插值/补齐/代理。

原 entry−5至exit+5 窗共411合约日，174日合格、3354条15m；237日未合格，其中229无缓存、8日OHLCVOI不一致（包含4日尾桶不完整）。174日原分钟数均为225或345；输出又独立反向重聚日线并检查3354条时钟，共3528项通过。只有8合约有任意合格分钟，且hc/rb仅入场前少量背景；不能称全部交易或持仓期分钟完整。

为避免 canonical 截可见窗后才计算MA造成可避免空值，另在同一52候选/同SQLite范围向前拓最多3真实交易日，提供单独隐藏暖机CSV：198合约日、3858条15m。它多于原窗的24日/504条只供均线暖机；不是198个年度独立日期。原174日每条OHLCVOI逐key与新CSV完全一致，原v1证据不覆盖或改写。缺失完整交易日后的MA应断段重新暖机，或明确标注仅合格可用bar参考，不能伪称跨未知日的连续市场MA。自然周末、假日和午休不作为数据缺口。

复验文件：Stage020_review_preflight.py/json（431项）；Stage020_review_expected_rounds.csv；Stage020_review_local_minute_inventory.json；Stage020_review_minute_qualification.py/json 与 Stage020_review_qualified_15m.csv；Stage020_review_minute_qualification_v2.py/json 与 Stage020_review_qualified_15m_warmup.csv。实际逐文件SHA在对应JSON中。HTML/records/manifest/浏览器交互尚待主任务实现并独审，此预审不声称页面已经验收。

过拟合判断：没有新增参数优化；重复呈现既有样本不是新OOS。继续价值：有，能够逐笔核对真实模型成交、行情与净损益，并诚实呈现分钟/上市前后史缺口。后续只审派生复盘页，不扩大金融窗口或救参数。
