# Stage006 全历史股票数据冻结与质量审计

- line_id：`stock_qmt357_vnpy`；记录时间：2026-09-28 16:32（Asia/Shanghai）。
- 阶段性质：用户已确认的数据层扩展；非策略优化、非重要突破、非 A/B，不执行回测或交易。
- 仅新增 `history_download.py`、`tests/test_history_download.py` 和本股票独立数据/审计产物；v1 下载器、快照、历史输出、策略、引擎及期货资源不改。

## 调研、判断与实现

- 保留原策略仅排除代码前缀 300/688 的条件，保留 301/302；历史并集由全量月度沪深300快照确定，不按后验收益选股。
- [上交所2026规则说明](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml)、[深交所2026交易规则](https://docs.static.szse.cn/www/lawrules/rule/allrules/bussiness/W020260424690713155663.pdf)、[创业板2020规则](https://investor.szse.cn/institute/rules/t20200807_580310.html)支持按生效日期切换：主板 ST 于 2026-07-06 前5%、此后10%；sz.3* 于 2020-08-24 起20%。限价由原始 preclose 按分位 ROUND_HALF_UP 派生，明确不是真实交易所限价字段；IPO/复牌例外未建模。
- 新 API：`download_panel(start='20191001', end='20260924', *, client=None)`；原价按年、因子按股、分红按年独立缓存；错误不转空表，已发布源拒绝覆盖。
- 保留真实停牌 OHLC，仅 status=0 且 volume 空时赋0；status=0 但正成交量拒绝。公司行动使用专门代理完成的 BaoStock/Sina 严格对账、明确公告裁决，不从因子倒推现金/股份。
- TDD 定向测试29项通过；最终公司行动106项通过；根代理冻结后股票全套252项通过。源码冻结于16:25，启动与完成哈希一致。
- `history_download.py` SHA256：`413e7c4337c44a82bae0e71fd8b4936eb1ac837c264de84ab4c7e7b918745425`；公司行动模块：`3f49e3e96a4bc9bcc00e97d03044c0108dab2d560eec3a7fda6e27a26df1a65f`。其余源码哈希见 `source_build_freeze.json`。

## 冻结数据与可复验入口

- 独立目录：`examples/stock_backtesting/qmt357/data/downloads/history_20191001_20260924/`（下文相对文件均位于该目录）。
- 85个月度/末端快照，每份严格300只唯一且无未来 updateDate；实际应用为 `date > snapshot_date`，存在月度滞后。
- 历史筛选后股票420只，另含000300.SSE；日线692,550行；指数1,694个交易日，2019-10-08至2026-09-24。2019Q4仅供2020起的固定策略预热。
- 原始7,653个 Parquet 全部实际读取成功，80,510,805 bytes；每文件行数、字段及SHA记录于 `raw_inventory.parquet`。
- 16:22:21 未缓存指数查询请求至2026-09-28，供应商最新仍为9月24日，不能把本数据称为已覆盖9月28日；证据 `latest_index_probe_after_raw.json`。
- 冻结源：`source_panel.parquet`；SHA256 `656d96da2a3b4dee8582236ea051970f2c41368444daedb5b5c31739cdd8737f`。
- 最终 attempt：`20260928T082517676138Z`，`state=complete`、`current_failures=[]`；420只全部合并成功，旧错误另行归档，不混充当前状态。

## 采集失败与恢复证据

- 两个独立进程只在股票POSIX锁内写各自raw缓存，预取不写主manifest/events/panel；锁及真实双进程单股一次请求有测试。
- 旧预取退出/重新登入期间出现匿名供应商“用户未登录”，尾部退出又影响一只，共6只失败；这是观察到的会话关联，非已证明的服务端实现。失败响应未被当空数据缓存。
- 两旧进程自然结束后改为单连接补取；6只各18文件、1,694价行，原有缓存SHA不变。没有删股、删原始文件或发布部分面板。
- 证据：`login_failure_raw_inventory_before_six.json`、`raw_recovery_verification.json`、`prefetch_rebalance_20260928_1613.json`及独立进度日志。未来不要依赖多匿名连接登出互不影响；最终构建采用单进程。

## 全量质量审计

| 项目 | 结果与边界 |
| --- | --- |
| 现金/送转补齐 | Sina补22事件；公告限定裁决17事件；无法映射到真实bar的事件0 |
| 停牌数据 | 保留1,686行；其中带现金/送转动作仅600027在2024-07-25一行 |
| 停牌除息估值 | 600027前收6.08、现金0.15、当日原始OHLC/preclose均5.93；volume原为空、status=0，没有沿用6.08旧价 |
| 派生限价超限 | 41行，实际历史成员内0；不据此排股票或改价 |
| 无显式动作的因子变化 | 24行（21行当日为成员）：已核配股5、back单独跳变疑点9、未定性10；10行中9行fore/back与参考价同变，002466在2020-01-02因子变但preclose未变 |
| 成员-日历完整性 | 严格滞后快照应有440,341对，观测440,304对，缺37对；仅2股，均发生在各自最后可用bar之后，无观测存续区间内部缺口 |

- 所有24处因子仍保持原backAdjustFactor口径，cash/split缺口保持0/1，不换成fore、不当免费送股、不忽略持仓保护。5个已核配股的原公告URL及剩余逐行前后因子、fore、preclose/前close见 `final_factor_audit.json` / `factor_gap_details.parquet`。
- 9个back单独变化只称供应商字段疑点，不能把未修复数据误写成已证明错误或已正确；其余10个未定性仍是限制。
- 逐项产物：`final_data_quality_audit.json`、`missing_member_bars.parquet`、`missing_member_bars_summary.json`、`suspended_action_rows.parquet` / `.json`、`derived_limit_violations.parquet`。

## 两个合并退市缺口的制度原因

- 600837最后真实交易2025-02-05，自2月6日起连续停牌；[公司停牌原公告（港交所披露）](https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0204/2025020400693_c.pdf)。[上交所决定](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20250226_10773005.shtml)明确3月4日终止上市；[收购方换股实施公告](https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=10765300&stockid=601211)明确换为601211，比例0.62。Baostock仍有3月4日零量停牌占位，不能把它当真实最后交易日；3月5日至31日缺19个成员日。2月28日月快照仍含该股，3月31日不含，因此4月起才退出当前月度模型。
- 601989最后真实交易2025-08-12，自8月13日起连续停牌；[公司临2025-053原公告](https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-08-09/601989_20250809_7OO5.pdf)搜索索引原文与本地最后status=1日期一致，直连PDF抓取超时，亦用[同份公司公告镜像](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=11287892&stockid=601989)交叉读取。[公司终止上市原公告](https://static.cninfo.com.cn/finalpage/2025-08-30/1224625027.PDF)明确9月5日摘牌、换为600150、比例0.1339。原始最后零量停牌bar为9月4日，9月5日至30日缺18个成员日；8月31日月快照含、9月30日不含。
- 两项是已核实的合并退市加月度池滞后，不是漏下整年。**没有实现换股、现金选择权、碎股分配或交收期间估值**；若实际持仓暴露，不能据当前模型宣称可信完整绩效。额外证据 `merger_delisting_audit.json`，并不改变冻结源。

## 结果、反思与下一步

- 本代理未跑回测，期末权益、收益、回撤、Sharpe、滑点、交易次数及胜率均不在本阶段给出；由根代理固定策略回放及独立reviewer核对实际持仓暴露后记录，不能从数据完成推导alpha有效。
- 运行前/后过拟合判断：否。处理对象是完整历史成分并集、制度规则与一手公司行动，没有按收益挑选股票、改参数或修平因子。源本身的月度滞后和未建模事项仍须披露。
- 运行前/后继续价值：有。现在能区分真实缺数据、公司行动冲突、制度性退市、配股和供应商因子疑点，提供可复验输入；不能为了完成回测放宽保护。
- 后续：根代理prepare/固定回放、持仓异常暴露核验、独立审查；此后任何配股/换股模型变更须单独明确语义与验证，不在本冻结数据上暗改。
- 并行写入纪律：本代理只写此唯一Stage006；不改LINE.md、registry.md或根历史总账，由根代理统一整理。

## 18:15 晚间可用性补充（不改变上述冻结数据）

- 2026-09-28 18:15:21（北京时间）在确认没有其他供应商连接后，单连接、未用缓存查询000300至当天，已返回9月28日日线；open/high 4423.8156、low 4323.5694、close 4340.7550、volume 17127737300。查询后已logout。
- 新证据 `latest_index_probe_20260928_1815.json`；16:22尚未发布的旧证据完整保留，两者是不同as-of时点，不相互覆盖。
- 上述source仍严格截至9月24日，其SHA、snapshot和回测产物未改。已立即通知根代理：若完成“到今天”的请求，须另建独立增量数据/快照并固定回放，不得把9月24日版本改称9月28日。
