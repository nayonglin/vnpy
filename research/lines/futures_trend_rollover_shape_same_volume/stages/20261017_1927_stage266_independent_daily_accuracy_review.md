# Stage266 全市场日线独立准确性与读取器验收

- line_id：`futures_trend_rollover_shape_same_volume`
- 记录时间：2026-10-17 19:27 CST；工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`。
- 阶段性质：独立只读验证；不实现或导入 root 清洗逻辑，不修改清洗器、主库、Stage265、LINE/registry、生产、策略或模型。
- 是否重要突破：数据工程验收完成；不构成 alpha、训练或实盘资格突破。不触发 A/B。

## 外部调研与判断

- [TqSdk API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)：K 线起点时间、`open_oi` 起始持仓与 `close_oi` 结束持仓有不同语义。
- [RQAlpha Bar 源码](https://rqalpha.readthedocs.io/zh-cn/latest/_modules/rqalpha/model/bar.html)：日线日期来自原 datetime；`is_trading` 按成交量大于零；不能根据收盘 OI 推造开盘 OI。
- [SHFE 官方日行情](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=kx)：收盘、结算、成交量和持仓应按各自列读取。无成交报价不能自动变成真实成交 K 线。
- 判断：验收应绑定冻结来源、原行位置、数量合同与可证伪的字段定义，不能声称交易所历史每行绝对真实。OHLC 无真值的跨源冲突整日隔离，数量未知不按年份猜除二；不同来源重复观察不相加。

## 本次变更

新增本线独立工具 `stage266_independent_validate.py`、`test_stage266_independent_validate.py`、`stage266_independent_reader_review.py`、`stage266_independent_delta_review.py`、`stage266_independent_finalize_report.py`。仅新增验证器 CLI 参数 `--contract/--output-dir/--mode` 及增量验证的 `--delta`；无交易参数变更。

先冻结验证设计并完成故障注入；核心独立验证器 28 测试通过。读取器为另一 agent 实现，本 agent 只读源码及运行其 27 测试，未改读取器或其测试。

## 最终数据与证据

- 最终 DB：`outputs/stage266_clean_daily/clean_daily.sqlite`，SHA256 `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`。
- 最终合同：`outputs/stage266_clean_daily/contract.json`，SHA256 `3009ee06c0db70f6df3736569392c5d1da2a593ca3b0b95825ad601b139f4149`。
- 1,552,456 唯一合约日，9,520 个有数据的完整交割年月身份，97 个来源产品（含独立 F 家族），2010-01-04 至 2026-10-16。
- 源家族分布：official 282,317；old_tq 772,305；recent_tq 12,441；rqalpha 485,393。这里是最终选中整行来源，不能再与原始/官方观察量加总。

| 交易所 | 最终行数 | 有数据合约身份 | 七列完整行 | 实际首日 |
| --- | ---: | ---: | ---: | --- |
| CFFEX | 67,345 | 692 | 33,619 | 2010-04-16 |
| CZCE | 390,570 | 2,408 | 203,813 | 2010-01-04 |
| DCE | 471,418 | 2,935 | 241,487 | 2010-01-04 |
| GFEX | 24,682 | 138 | 16,189 | 2022-12-22 |
| INE | 62,785 | 396 | 45,339 | 2018-03-26 |
| SHFE | 535,656 | 2,951 | 244,299 | 2010-01-04 |

全部六所末日为 2026-10-16。GFEX/INE 未虚构上市前历史；有数据合约身份数不代表当日仍上市合约数或官方完整历史上市总数。

### 全量与最后单调增量的证据链

1. 在删除旧库价格争议前的 `4191dc...598` 快照，独立逐行读取 1,552,466 个选中原源记录，逐字段核对 OHLC、日期、原始量仓、冻结换算因子、源位置、完整交割年月、生命周期边界及显式开盘 OI。全部通过；4,831 个源文件 SHA/bytes 全同，SQLite 完整性/主键/外键及日历检查通过。
2. 9,520 个导出 CSV，1,552,466 行、23,286,990 个字段，与该快照 SQLite 全同。排除文件 1,146,274 个来源观察，来源账守恒；有 2 个 `CZCE.ZC710` 身份拒绝发生在 raw 计数器之前，独立单列，不隐去、不补造原始总数。
3. root 在只读旧库 OHLC 对比中又发现 10 个无真值价格冲突。本 agent 保存删除前临时 SQLite，并独立证明最终数据库**恰删除指定 10 行、没有新增行、没有任何保留行字段修改**；sources/contracts 表完全相同。十行全为 RQ close-only，七列完整行减少 0。
4. 对这 10 个受影响 CSV 重新逐字段核对，全部一致；其他 CSV inventory receipt 不变。最终 2,294 个数量争议键及 304 个价格争议键逐键查询，泄漏均为 0。最终数据因此是全量通过快照的严格单调子集，无须再次回读原源。
5. 临时副本校验旧 SHA 后删除，回收 378,552,320 字节，保留 `temporary_snapshot_cleanup.json` 与完整增量证据。旧主库及主力 mapping SHA 复核保持不变。

### 量仓与来源重叠

784,746 行有原源观察到的开盘 OI；767,710 行开盘 OI 保持空值。`open_interest` 全部是 `close_oi` 别名，未使用旧私库可能代表开盘 OI 的别名。原源 TQ 开收持仓不同的 746,600 行提供了时点差异实证。

9 月独立重算 TQ/RQ：TQ 10,595 个观察，双方有成交 9,243；OHLC 相同 9,230、差异 13；成交量及收盘 OI 均 9,243 同；TQ 开盘 OI 与 RQ 收盘 OI 相同仅 415。差异及原源行号另存 CSV，不择价修补。

### 读取窗口与月度 108 特征的范围勘误

实际 `INE.SC.202212` 截至 2022-11-29 的 120 个预期交易日窗口通过。内存删除预期日（仍有大于 120 个总观察且伪造 attrs）、缺开盘 OI、将 close OI 复制但标为未观察、V0 平价、错 OHLC、负 OI、false flag、混合交割身份共八种故障均拒绝；实际缺开盘 OI 读取仍为 NaN/unusable。

**物理字段 `legacy108_row_usable/train_eligible` 与函数 `require_legacy108_window` 的历史命名不准确：它们仅表示旧 CSV 七列完整性和保守显式日历窗口，既不是月度 108 特征的必要条件，也不是充分资格。** 本 agent 实读 `analyze_qmt_roll_ai_product_suitability_walkforward.py` 的 120/240/274/336 附近代码，确认月度特征来自策略 PNL 与候选/信号滚动统计，不直接读取开盘 OI。784,746 只能称七列完整行；原 18 池 18,649 是另一 agent 给出的保守 CSV 窗口，不能据此认定 2010–19 不可训练。总报告绑定 root 的 `feature_dependency_clarification.json`。统一策略 PNL/信号、成熟前瞻标签与月度样本尚未生成。

## 交付与验收边界

- 总入口：`outputs/stage266_independent_validation/independent_review_summary.json`。
- 原全量：`independent_validation.json`、`csv_export_validation.json`、`excluded_conservation_validation.json`。
- 最终增量：`final_monotonic_delta_review.json`；不覆盖原快照指纹，不冒称在新 hash 上重跑旧读取器测试。
- 双源证据：`september_TQ_RQ_overlap.json`、`september_TQ_RQ_price_differences.csv`。
- 读取器独立审查：`independent_reader_review.json`、`reader_tests.log`；验证器 `validator_tests.log`。
- 最终分层覆盖：`coverage_by_exchange_year_product.csv`、`coverage_by_exchange_year.csv`、`coverage_by_contract.csv`。
- 最终结论：`PASS_BOUNDED_SOURCE_CONTRACT_ACCURACY_AND_READER`，P0/P1/P2=0/0/0。36 个选中行只有 current/official symbol 元信息，其边界原样保留，不伪造官方上市证明。被拒原行的守恒采用冻结清洗账，未独立重建每个被拒字段，也不宣称来源完整性或交易所每行绝对真。
- 下载、主库写入、财务回测、策略执行、订单、训练样本生成、模型拟合均为 0。期末权益/收益/回撤/Sharpe/滑点/交易数/胜率均不适用，未运行回测。

## 反思与后续

- 运行前后过拟合判断均为否：只验固定字段与原源，不依据收益挑来源或参数；无真值冲突采取同一单调隔离标准。
- 运行前后继续价值均为是：已获得可证伪的有界读取准确性。后续价值在独立绑定统一策略 PNL/信号与样本成熟度，不应反复搜索来源直到得到想要的策略结果。
- 不修改本线 LINE/registry 或根总账，由 root 统一登记。下一步若构建训练样本，应另行冻结真实月度特征依赖、统一回放来源、标签成熟度与切分合同；本阶段未授权或执行这一步。
