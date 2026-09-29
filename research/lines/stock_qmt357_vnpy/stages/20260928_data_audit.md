# Stage001：QMT 357 本地股票数据审计与独立快照入口

- 研究线：`stock_qmt357_vnpy`。
- 审计与实现收口时间：2026-09-28 14:22 CST（Asia/Shanghai）；快照自身记录 UTC 秒级时间。
- 是否重要突破：否；本次是迁移的输入资格与隔离工程，不是策略收益突破。
- 范围：只读审计既有本地股票数据；新增股票专用离线快照代码和测试。不改其他研究线、根历史总账、期货策略或期货配置。
- 调研：读取当前 `research/registry.md`、股票研究线和 `examples/alpha_research` 数据生产/加载代码。全任务外部调研与判断见本线 `LINE.md`；本子任务未联网、未下载行情、未读取密钥、未运行策略。

## 运行前判断

- 是否过拟合：否。数据校验和运行隔离不以收益结果选择参数，也不改变原策略技术指标。
- 是否有继续价值：是。只有首先确认指数、成分、复权及交易限制的可用性，迁移后的收益评价才有意义。

## 当前本地数据事实

实际使用仓库 `.py311/bin/python` 读取 parquet、shelve 与 SQLite 的 schema/覆盖；SQLite 均以 `mode=ro` 打开。

| 路径 | 当前实际内容 | 结论 |
| --- | --- | --- |
| `lab/csi1000_tushare_smoke/daily/000001.SZSE.parquet` | 5 行，2026-01-05 至 2026-01-09，2,919 字节 | 仅演示缓存 |
| `lab/csi1000_tushare_smoke/daily/000002.SZSE.parquet` | 同期 5 行，2,912 字节 | 仅演示缓存 |
| `lab/csi1000_tushare_smoke/component/000852.SSE.db` | 仅 2026-01-01、2026-01-10 两个键；每个键均为上述两只股票 | 人工静态 smoke 成分，不是真实历史中证1000，更不是沪深300 |
| `examples/alpha_research/native_results` | 当前不存在 | 老股票脚本默认数据路径不可用 |
| `.vntrader/database.db` | 交易所仅 CFFEX/CZCE/DCE/GFEX/INE/SHFE，SSE/SZSE/BSE 和 000300 查询为空 | 不存在可供迁移的股票记录；不复制或接入股票运行器 |
| `/Users/bytedance/.vntrader/database.db` | 同样只有期货交易所，无股票和 000300 | 不作为股票数据源 |
| `/Users/bytedance/Desktop/person/qmt_stock` | 三个策略源码 | 不含行情文件 |

两个股票 parquet 共 5,831 字节，schema 为 `datetime: Datetime(us)` 与 Float64 的 `open/high/low/close/volume/turnover/open_interest`。证券身份来自文件名。数据生产代码使用 Tushare `daily` 未复权价格，`vol * 100` 为股、`amount * 1000` 为元；`open_interest=0`。没有复权因子、ST、停牌、涨跌停、上市日期或公司行动字段。

检索范围还包括本仓库 worktree 及相邻 `vnpy*` 根目录的 `examples/alpha_research/native_results`，以及相邻 `qmt/qmt_2/research` 的相关文件名，没有找到完整股票面板或 000300 日线。旧 qmt 可见缓存/导出文件为期货。该结论表示限定范围内未找到，不声称整台电脑不存在股票数据。

不能用这 10 根股票 bar 产生原策略回测：它们缺少沪深300指数、真实历史成分、复权和交易限制，也不足原策略 20/60 日预热。此次没有把它们补造为可交易数据。

## 老股票代码的可复用经验与限制

- `vnpy/alpha/lab.py:load_bar_data` 支持按 `vt_symbol` 分文件的 parquet；但 `AlphaLab.__init__` 会自动创建目录。本次入口直接读取指定股票源，不实例化共享 AlphaLab。
- `analyze_stock_range_reversion_signal_attribution.py:normalize_stock_panel` 已区分 `qfq_*` 信号价格与 `raw_*` 成交价格，迁移延续这种职责区分。
- `build_stock_range_reversion_tushare_daily_panel.py:add_qfq_prices` 使用 `raw_price * adj_factor / latest_adj_factor`。复权价不能直接当作真实现金成交价。
- 老 Tushare builder 的 ST 源为空时会全填 `False`，缺涨跌停则按板块/ST公式推算，`FETCH_STK_LIMIT` 默认关闭。本次没有沿用这些静默可交易降级。
- `build_stock_range_reversion_research_panel.py:build_daily_component_membership` 选择不晚于交易日的最新成分快照。未来接入真实数据时仍需核对快照可获知时间，不把静态池当成历史成分。

## 本次版本改动

新增 `examples/stock_backtesting/qmt357/data.py`，只依赖 pandas 与标准库：

- `prepare_snapshot(source: Path, name: str, universe_mode='historical') -> Path`：只读一次本地 CSV/parquet 原始字节；校验后复制为包内 `data/<name>/panel.parquet` 和 `manifest.json`；拒绝已存在目录、非法名称、路径逃逸与快照符号链接。
- `load_snapshot(path: Path) -> tuple[pd.DataFrame, dict]`：仅在专用股票数据目录内读取；校验 panel 哈希、规范化合同和 manifest 汇总，不再访问原始源文件。
- 原始 OHLC 为未复权成交价格；单独保留 `adj_factor`。`volume` 单位为股。
- 严格必需字段：`date,vt_symbol,open,high,low,close,volume,adj_factor,limit_up,limit_down,is_st,is_member`。
- `vt_symbol` 支持 `.SH/.SZ` 转为 `.SSE/.SZSE`，不接受期货交易所。日期必须是无时区的日级日期，同证券/日期唯一。所有股票日期必须存在于 `000300.SSE` 指数日历。
- OHLC、因子、股份倍率必须有限且为正；成交量和现金分红必须有限且非负；高低价必须包含开收盘。股票涨跌停必须为有限正值且下限小于上限。指数涨跌停可缺失，但指数 `is_st/is_member` 必须为 False。
- 布尔状态仅接受真实 bool、0/1、true/false；缺失或未知状态拒绝。
- 可选 `cash_dividend` 默认为 0（每股现金分红），`split_ratio` 默认为 1（股份倍率）。manifest 披露复权因子变化但没有显式公司行动的行数，并要求持仓遇到这类变化时由回测引擎拒绝运行；因子不能替代公司行动会计。
- 少于 60 个指数交易日或任一股票少于 60 行，manifest 标记 `insufficient_history=true`，不伪造预热记录。
- `universe_mode` 允许 `historical/static_snapshot/custom`。模式本身不构成历史成分验证；仅 parquet 源的 pandas attrs 同时声明 `historical_membership_verified=True` 和非空 `membership_source` 时记录源方声明，并明确 `membership_verification_basis=source_declaration`，不是独立第三方验证。
- manifest 记录源路径、源文件 SHA256、规范化副本 SHA256、数据覆盖、行数/股票数量、单位和公司行动口径。

新增参数：股票快照 source/name/universe_mode 和上述显式输入字段。修改参数：无。删除参数：无。修改/删除已有数据：无。

## 验证与结果

按 TDD skill 与 writing-good-tests 引用先编写真实本地文件测试。空接口阶段 `37 failed`，实现后：

```text
.py311/bin/python -m pytest examples/stock_backtesting/qmt357/tests/test_data.py -q --tb=short
37 passed in 4.52s
```

测试验证 CSV/parquet 两种输入、源文件保持不变、删去源文件后独立读取快照、字段规范化和默认值、哈希与篡改、目录逃逸和符号链接、禁止覆盖、状态/价格/日历/指数合同、历史成分声明与公司行动缺口。测试的 `DATA_DIR` monkeypatch 仅位于测试文件，指向 pytest 临时目录；生产代码没有外部配置覆盖。

没有新增、修改或删除回测结果。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均不适用。本次不构成收益实验，因此不触发回测结果独立 reviewer。

## 运行后判断与后续

- 是否过拟合：否。所有校验来自固定数据/会计/隔离合同，没有利用回测收益调参。
- 是否继续有价值：是。股票入口已可在获得合格离线源后冻结可复验输入；当前最大限制仍是缺完整股票/沪深300/成分/复权/公司行动数据。
- TODO：由主任务完成专用股票引擎、配置、命令行和总体验证；在定位或补齐明确数据源后先制作独立快照，再固定参数回测并按要求进行独立评审。
- 不改 LINE.md、registry.md、其他研究线、期货配置或运行资源。
