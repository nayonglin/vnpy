# Stage285 Stage526 非 CSV live 执行证据发现审计

- 时间：2026-06-03 23:48 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage585_stage526_non_csv_live_evidence_discovery.py`
- 决策：`non_csv_live_evidence_gap_not_closed`
- 是否重要突破版本：否。它是执行证据盲区审计，不是策略候选。
- 是否改策略：否
- 是否回测收益：否
- 是否允许晋级：否
- 是否允许声明真实交易无偏差：否

## 背景

Stage283 只扫描了 `backtest_outputs` 中 live/evidence/execution/fill/ledger/shadow/simnow/ctp 相关 CSV，结论为 Stage526 的 P0 live TCA 有效样本 `0/9`。本阶段补充扫描 CSV 之外的证据形态，包括 `.vntrader/log`、`.vntrader/database.db`、JSON summary、console txt、Markdown report 和研究记录，确认是否存在被 Stage283 漏掉的真实 CTP/SimNow/order/trade/fill 证据。

外部调研与本地代码判断：

- vn.py `OrderData/TradeData` 的实盘证据字段应至少能覆盖 `vt_symbol/orderid/tradeid/direction/offset/price/volume/datetime/status` 等核心信息；本地 `vnpy/trader/object.py` 与 `vnpy/trader/gateway.py` 已确认 `on_order/on_trade` 事件链。
- TCA 证据不能只停留在成交价，还需要 `VWAP/implementation shortfall/participation/unfilled_volume/broker reject` 这类可比较执行质量字段。
- 参考资料：vn.py GitHub `https://github.com/vnpy/vnpy`；CME Futures TCA PDF `https://www.cmegroup.com/education/files/TCA-4.pdf`；QuestDB order-level implementation shortfall recipe `https://questdb.com/docs/cookbook/sql/finance/implementation-shortfall-order/`。

## 版本改动

新增：

- 新增非 CSV 证据发现脚本 `analyze_qmt_roll_stage585_stage526_non_csv_live_evidence_discovery.py`。
- 新增字段扫描口径：
  - 核心 order/trade 字段：`vt_symbol/order_id/trade_id/direction/offset/price/volume/datetime`
  - TCA 字段：`avg_fill_price/unfilled_volume/vwap/implementation_shortfall/participation/broker_reject`
- 新增 SQLite 只读表级盘点。`.vntrader/database.db` 即使为 104MB，也不再按大文件跳过，而是只读打开表结构并对相关文本列最多抽样 `5,000` 行。
- 新增自引用污染防护：排除本阶段自身 `qmt_roll_stage585_stage526_non_csv_live_evidence_discovery_*` 输出，避免上一轮报告被下一轮误扫成 live TCA 证据。
- 新增 gate 图红绿满条显示，让失败项在图上直接可见。

修改：

- 修正 SQLite gate：只统计 `read_ok=1` 的真实可读表，不再把 `too_large` 行误计为已检查通过。

删除：

- 无。

## 结果

本阶段不是收益回测，因此无新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率结果。Stage526 参考口径仍为：

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- Ulcer：`14.4691`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 非零日胜率：`53.6330%`

非 CSV 证据审计结果：

- 扫描文件：`2,137`
- 已读/已检查：`2,136`
- 敏感连接配置跳过：`1`
- 通用结构化 order/trade 候选：`58`
- P0 符号匹配文件：`90`
- P0 覆盖符号数：`3/3`，即 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE`
- P0 结构化 trade evidence 文件：`4`
- P0 live TCA close 文件：`0`
- SQLite 可读表：`4`
- SQLite 错误行：`0`
- gate：`6/8`

SQLite 细节：

- `.vntrader/database.db` 只包含 `dbbardata/dbbaroverview/dbtickdata/dbtickoverview` 四张表。
- `dbbaroverview` 中能匹配 P0 符号，但这是行情 overview，不是订单/成交回报。
- `dbtickdata/dbtickoverview` 行数为 `0`。
- 当前 `.vntrader/database.db` 没有 order/trade/fill/TCA 表，不能补 Stage283 的 live fill 样本。

## 图表复盘

图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage585_stage526_non_csv_live_evidence_discovery_chart_stage585_stage526_non_csv_live_evidence_discovery_v1.png`

视觉分析：

- 左上图显示绝大多数非 CSV 文件可读取，只有 `1` 个敏感路径跳过，说明扫描覆盖面足够；新增 SQLite 也已真正进入 `sqlite_scanned`。
- 右上图显示三个 P0 符号都有大量文本匹配：`fu2509.SHFE=169`、`lc2505.GFEX=160`、`AP505.CZCE=148`。这说明问题不是“找不到 P0”，而是匹配大多来自历史研究、分钟补数、报告或行情库。
- 左下图显示 P0 文件中常见 `offset/vt_symbol/direction/volume/price`，也能看到一部分 `vwap/implementation_shortfall/participation` 字样；但 `order_id/avg_fill_price/unfilled_volume/datetime` 覆盖不足，尤其没有同一个 P0 证据链同时具备核心成交字段和 TCA 字段。
- 右下图两条红色失败项很明确：`stage526_p0_live_tca_close_evidence_found=0`、`zero_execution_bias_claim_allowed=not allowed`。通用执行材料存在，但不能关 Stage526 真实成交偏差。

## 结论

Stage285 进一步确认：Stage526 当前仍只能称为“正常成本主候选/执行评审候选”，不能声明“真实交易不存在偏差”。CSV 外部没有补出任何可关账 live TCA 样本；Stage283 的 `0/9` 有效样本结论保持。

下一步不是调策略，而是执行证据工程：

- 把 SimNow/CTP/券商真实 `EVENT_ORDER/EVENT_TRADE` 回报落成结构化账本。
- 每个 P0 类别至少累计 `3` 个可比样本。
- 每个样本必须同时具备 signal/order/fill/avg_fill/filled/unfilled/VWAP/implementation shortfall/participation/broker reject/filter 字段。
- 与行情窗口合并计算 `actual_vs_window_vwap_bps`、`actual_implementation_shortfall_bps` 和窗口参与率。
- 未满足前，Stage526 不可作为“真实无偏差”实盘承诺。

## 反思

是否过拟合：否。本阶段不改交易规则、不调参数、不跑收益，只做固定证据发现与字段覆盖审计；还主动修复了 SQLite 误计和自引用污染，降低了证据污染风险。

是否值得继续：是。目标要求“真实可成交且不存在实盘偏差”，执行证据是硬前置。当前继续优化策略本体或扩池 selector，都不能替代真实 order/trade/TCA 账本。

## TODO

- 在 Stage78/Stage526 执行链中接入结构化 `order_trade_live_tca_ledger`。
- 对 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 每类累计 `3` 个真实可比 live fill 或独立全日分钟证据。
- 每日/每次虚拟盘后自动输出 TCA gate：filled=100%、unfilled=0、VWAP<=50bps、shortfall<=75bps、participation<=25%、无 broker reject/filter。
- 继续保留低单笔风险扩池 selector 为 forward collection，未达 Stage284 硬闸门前不启动收益回测或交易白名单。
