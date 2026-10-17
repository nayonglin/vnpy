# Stage262 早期逐日主力行情覆盖独立审计（含Stage263全周期资格输入）

- line_id：`futures_trend_rollover_shape_same_volume`；记录时间：2026-10-17 17:02 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`；HEAD `e41a0a01d53b7256001e45e686acad53667ef7bf`。
- 阶段性质：独立只读数据审计；先读registry与Stage261，再核验真实主力映射和SQLite逐日bar，不使用dbbaroverview替代逐日覆盖。
- 是否重要突破：否；识别出SM的具体缺口并产出可复用覆盖合同，未产生alpha、绩效或新训练标签。
- 是否触发正式A/B：否；未修改正式代码、策略参数、模型、生产物料、月池、CTP、邮件或定时任务。

## 外部调研与判断

- [vn.py官方BarData定义](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py)：bar携带symbol、exchange、datetime、interval及OHLC等字段，不自带“该品种在当日可训练”的认证。
- [vn.py官方SQLite实现](https://github.com/vnpy/vnpy_sqlite/blob/main/vnpy_sqlite/sqlite_database.py)：按symbol、exchange、interval与日期范围读取，数据库唯一索引也是symbol/exchange/interval/datetime。已与本机安装版本、实际SQLite schema分别核对。
- 判断：必须用`映射date + 真实main_contract_vt的symbol/exchange + interval=d`匹配；不能只按产品概要或合约字符串证明覆盖。CZCE三位代码存在跨十年别名，例如数据库`CF505`同时含2015和2025记录、`SM501`同时含2015及2024/2025记录。仅按合约求首末日会把未来十年的数据错当早期覆盖。
- 该检查只能认证本机映射与本机bar的交集，不能替代交易所上市日、独立供应商数据质量或交易日历认证。零成交/四价相同不自动判坏；实际匹配样本没有零成交，SM有27根四价相同的有效日线。

## 方法与输入绑定

- 新增研究脚本：`tools/stage262_audit_early_bars.py`，支持`--start/--end/--output-json/--output-csv`；仅使用`.py311/bin/python`标准库读取并审计，脚本运行时不导入执行引擎。
- 数据库连接为`mode=ro`，另设`PRAGMA query_only=ON`并使用读事务；审计前后对所有输入重算SHA，输入未变。
- 映射SHA256：`55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325`。
- 数据库SHA256：`273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`。
- OHLC有效条件：全部有限、严格正数，且`low <= min(open,close) <= max(open,close) <= high`。同一映射日若存在多根日线、重复/冲突映射或无效OHLC，逐日`coverage_ok=False`。
- CSV保留每个映射交易日×18品种一行；空主力映射保留False，不能把空映射前的零PnL当真观测。
- 本次只增加审计区间/输出路径参数；无新增、修改或删除策略/模型参数，无正式源码修改。

## 覆盖结果

| 品种 | 2015—2019预期日 | 实际匹配日 | 缺口日 | 早期首个有效映射日 | 截至2026-10-08全周期实际日 |
| --- | ---: | ---: | ---: | --- | ---: |
| AP.CZCE | 492 | 492 | 0 | 2017-12-25 | 2129 |
| CF.CZCE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| FG.CZCE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| MA.CZCE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| OI.CZCE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| SA.CZCE | 18 | 18 | 0 | 2019-12-06 | 1655 |
| SH.CZCE | 0 | 0 | 0 | 无早期有效映射 | 737 |
| SM.CZCE | 1219 | 1142 | 77 | 2015-01-05 | 2779 |
| au.SHFE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| cu.SHFE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| hc.SHFE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| jm.DCE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| lc.GFEX | 0 | 0 | 0 | 无早期有效映射 | 777 |
| lh.DCE | 0 | 0 | 0 | 无早期有效映射 | 1390 |
| rb.SHFE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| ru.SHFE | 1219 | 1219 | 0 | 2015-01-05 | 2856 |
| si.GFEX | 0 | 0 | 0 | 无早期有效映射 | 916 |
| sp.SHFE | 268 | 268 | 0 | 2018-11-27 | 1905 |

- 有早期映射的14品种，其早期最后匹配日均为2019-12-31。SH/lc/lh/si的全周期本机有效映射起点分别为2023-09-15、2023-07-21、2021-01-08、2022-12-22，这些不是本次独立认证的法定上市日。
- 早期共`14187`预期品种日、`14110`实际唯一有效日；重复日线0、无效OHLC 0、重复有效映射0、无效非空映射0。
- SM缺77日：2015年76日、2016年1日；首缺2015-01-09，末缺2016-06-01。合约分布为SM501 2日、SM505 11日、SM509 21日、SM601 32日、SM607 10日、SM609 1日。完整日期及合约已写JSON。
- 这77日中73日在本机没有任何SM合约日线，另4日只有其他SM合约bar；不能据此判断是供应商缺数、无成交还是当时主力映射定义差异。未下载、未填充、未替换主力。
- Stage263全周期2015-01-01—2026-10-08共2856映射交易日、`40925`真实映射品种日、`40848`唯一有效OHLC日；缺口仍为同一77日。18品种逐日资格CSV共`51408`行，有效`40848`行，剩余行包括覆盖前空映射和77个映射缺bar日。

## 同一源引擎的科学边界

- 静态读到`run_qmt_roll_backtest.py`的默认行为：`preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))`；`PRELOAD_START_DT=2019-06-01`。
- 原Stage183入口只传`analysis_start`，未传`preload_start`。因此直接运行旧入口的`--analysis-start 2015-01-01`仍不能证明从2015回放；还必须由隔离研究入口显式固定预加载区间并验证实际引擎起止。
- 当前10个老品种的1219早期映射日全部有bar；SM需要按真实缺口剔除资格；AP/sp/SA依其真实覆盖起点进入。SH/lc/lh/si早期不进入训练池。由此具备推进隔离日线统一源的基础，但不具备“18品种从2015同时完整”的前提。
- 本阶段没有运行源引擎，没有生成position_changes/candidate_snapshots或108特征/60日标签；120日特征成熟和60日目标成熟须在统一源之后按逐日覆盖与真实源观测共同验收。
- 统一2015起点会改变2020后的账户复利/整数手数/候选轨迹。必须从同一个规范源切出2020后训练臂与额外早期训练臂，不能将旧冻结源与新统一源拼接后称为纯扩样。

## 验证、输出与耗时

- 早期JSON：`outputs/stage262_ai_sample_contract/early_daily_coverage.json`；本次重跑耗时约0.83秒。
- 全周期JSON：`outputs/stage263_ai_data_expansion/daily_coverage.json`；全周期审计耗时约1.69秒。
- 全周期CSV：`outputs/stage263_ai_data_expansion/market_daily_coverage.csv`；SHA256 `168c6105d89a516e34ab878fed87e8341af589a524dff0e133617524abd8c7b2`。
- 额外验证采用独立pandas路径：读取全表daily、一次性按date/main_contract merge并验证one-to-one，而非复用逐合约索引审计函数；确认40925/40848/77、全部缺口为SM、CSV无重复date/product、每交易日18行、所有有效CSV键与实际合并键逐项完全一致。不是独立agent复审；整体Stage263源回放完成后由主agent协调独立复审，本agent未重复回放。
- 模型训练0次，绩效回测0次，订单/撤单API 0次。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：均无新增或修改结果。

## 反思与后续

- 开始和结束过拟合判断：否；只检查预声明覆盖合同，没有按收益筛选品种、时期、参数或缺口处理方式。历史更长本身不保证泛化更好。
- 开始和结束继续价值判断：是；早期本机数据大部可核验，具体缺口和源入口时间边界已经明确，足以支撑下一步一次隔离规范源验证。不能承诺扩样会提高收益。
- TODO：统一源显式2015起点与CZCE年代隔离；共同源之上按本CSV与源观测验收120/60窗口；SM缺口不补下载；仅比较共同测试截面和相同标签合同；新回测完成后独立agent全面复核。
- 本agent只新增本线唯一stage和自己的审计脚本/输出，不修改LINE、registry、memory或back_log；合入由主agent统一整理。
