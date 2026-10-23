# Stage022 最新完成日数据探测（仅数据，不回测）

- 所属研究线：`futures_weekly_formal_no_half_r`。探测：2026-10-23T19:23:16.728063+08:00 至 2026-10-23T19:25:10.084716+08:00。
- 结论：**2026-10-23 原19品种 19/19 主力映射与真实逐合约日线可得**。19 条当日日线 OHLC、成交量均大于0，持仓量非负、价格区间有效；Tq serial 已完整接收。当前主力 quote 与当日主力表 19/19 一致。
- 新增仅数据快照，不是重要策略突破；新增/修改/删除策略参数均为无，财务结果均为未运行。
- 旧 stage005_data 缓存仍截至2026-10-22；daily.sqlite、mapping.csv、metadata.csv、universe.csv、completed_manifest.json 五项 SHA 前后不变，未覆盖旧键或旧数据。
- 10/22 重叠复核：主力映射19/19完全一致；真实合约 OHLC、volume、close_oi 19/19逐值一致，无供应商修订差异。
- 下载量：19合约，每份86400秒日线serial10行；另保存10/19—10/23共95条目标日线。新数据限 `outputs/stage022_latest_probe/`。没有分钟请求、账户回放、CTP、生产、邮件或下单；insert/cancel调用均0。

## 周线边界

- 10/23 是周五。实际调用冻结 `weekly_adapter.completed_weeks`，日历截至10/23时已确认10/19—10/23为完整周；加入未来日历后的结果相同。
- Tq 日历下一交易日为10/26。**无需未来10/26日线来完成10/23周线**；10/26只作下一交易日的日历知识。
- 截至10/23的回放不得读取10/26未来日线或计入其开盘成交。10/23形成的新周信号，按nextdailyopen模型成交时应归入10/26，超出本次截止窗口。

## 数据与证据

- 完整原始收据：`outputs/stage022_latest_probe/probe_receipt.json`。
- 当日映射：`outputs/stage022_latest_probe/target_mapping.csv`。
- 当日真实合约行情：`outputs/stage022_latest_probe/target_daily_20261023.csv`。
- 原始19份日线serial、逐合约receipt、Tq日历、主力quote及10/22重叠核对均保存；probe源码及所有文件SHA绑定在同名阶段JSON。
- 本结论**只覆盖最新日可得性**，不代替2015历史覆盖、21完整周预热、金融执行验收或独立审查。

| 品种 | Tq主力真实合约 | 10/23开盘 | 10/23收盘 | 成交量 |
| --- | --- | ---: | ---: | ---: |
| AP.CZCE | AP701.CZCE | 5695 | 5725 | 274795 |
| CF.CZCE | CF701.CZCE | 15780 | 15855 | 311949 |
| FG.CZCE | FG701.CZCE | 828 | 836 | 1.22e+06 |
| MA.CZCE | MA701.CZCE | 3195 | 3219 | 2.35894e+06 |
| OI.CZCE | OI701.CZCE | 10281 | 10343 | 246468 |
| SA.CZCE | SA701.CZCE | 939 | 963 | 1.35193e+06 |
| SH.CZCE | SH701.CZCE | 1613 | 1579 | 524803 |
| SM.CZCE | SM701.CZCE | 5806 | 5940 | 477608 |
| au.SHFE | au2612.SHFE | 880 | 864.36 | 286554 |
| cu.SHFE | cu2611.SHFE | 107850 | 108740 | 93295 |
| fu.SHFE | fu2701.SHFE | 4947 | 5139 | 814996 |
| hc.SHFE | hc2701.SHFE | 3218 | 3209 | 566523 |
| jm.DCE | jm2701.DCE | 1384 | 1427.5 | 695671 |
| lc.GFEX | lc2701.GFEX | 92980 | 97280 | 459010 |
| lh.DCE | lh2701.DCE | 9905 | 9825 | 144219 |
| rb.SHFE | rb2701.SHFE | 3054 | 3047 | 853959 |
| ru.SHFE | ru2701.SHFE | 19500 | 19705 | 432877 |
| si.GFEX | si2612.GFEX | 8585 | 8640 | 131714 |
| sp.SHFE | sp2701.SHFE | 4632 | 4648 | 314430 |

## 调研与判断

- 官方 [Tq API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html) 支持86400秒日线；`is_serial_ready=True`用于确认订阅数据完整到达。沿用本仓库Stage173/Stage278主力表与真实合约取数方式，未用连续价格替代。参考官方 [GitHub](https://github.com/shinnytech/tqsdk-python)。
- 上期所[交易时间](https://www.shfe.com.cn/services/calenderandholidays/tradinghours/)与广期所[合约时段](https://www.gfex.com.cn/gfex/sytslqhhy/202307/9ad927b8ec4c458594e172fd1ada2a9b.shtml)用于核对日盘结束；本次快照在北京时间19:23—19:25取得，属于日盘收市后数据。
- 是否过拟合：**否**。这只是固定19品种、固定最新日的数据核验，不筛盈亏、不改参数。
- 是否有价值继续：**是**。10/23真实数据与周界已齐，后续可按已冻结策略合同准备2015—最新完整日的独立回放；不能据此宣称2015全段已就绪。
- NO_PROMOTION：不形成生产资格或晋级结论。
