# QMT 357 独立股票回测

这是 `qmt_stock/357.py` 的固定参数迁移版本，使用已安装的 vn.py `StrategyTemplate` 和 `BacktestingEngine`，增加独立的股票现金账本与日线撮合。不是期货策略的配置分支，不连接任何交易账户。

## 快速运行

从仓库根目录执行：

```bash
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py runtime
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py test
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py backtest --snapshot history_201910_20260924 --start 2020-01-01 --end 2026-09-24
```

本机已保存2020起的冻结数据；省略`--run-id`会生成新结果目录，不覆盖已完成回测。下载和`prepare`只在首次建立相应快照时执行，同名已存在会拒绝覆盖。以下保留旧两年数据流程作历史对照：

```bash
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py download --provider baostock --start 20231001 --end 20251231
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py prepare --source examples/stock_backtesting/qmt357/data/downloads/baostock_20231001_20251231/source_panel.parquet --name baostock_202310_202512
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py backtest --snapshot baostock_202310_202512 --start 2024-01-01 --end 2025-12-31 --run-id fixed_2024_2025
```

下载先缓存供应商原始响应，失败可续用缓存；不会修改已有冻结快照或同名回测结果。Tushare 也可用 `--provider tushare`，只从环境读取 `TUSHARE_TOKEN`，不复制凭证或读取期货配置。2026-09-28 检查时已有 token 认证失败，实际迁移验证改用 Baostock。

原 `baostock` 数据合同只支持 `end < 2026-07-06`，保持冻结不变。新增 `baostock-sina` 长历史合同：分段处理2020创业板/2026主板ST限价，保留供应商真实停牌行，并用新浪实施分红送转补充Baostock缺失事件；跨源冲突停止核对。它有独立 `data/downloads/history_<start>_<end>/` 缓存，不覆盖旧下载或快照。

2020年至最新完整日的入口（截止日以下载清单实际发布日为准）：

```bash
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py download --provider baostock-sina --start 20191001 --end 20260924
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py prepare --source examples/stock_backtesting/qmt357/data/downloads/history_20191001_20260924/source_panel.parquet --name history_201910_20260924
.py311/bin/python -I examples/stock_backtesting/qmt357/run.py backtest --snapshot history_201910_20260924 --start 2020-01-01 --end 2026-09-24 --run-id fixed_2020_20260924_v2data
```

2019Q4仅作预热，不计回测收益。`annual_summary.csv/json`是同一个连续账户的逐年切片，不按年重置本金；2026年为截至实际末日的收益，不是全年收益预测。旧版十个模块和来源指纹保存在 `data/stage001_code.tar.gz`，哈希与旧回测manifest一致。

### 长历史数据校验

新浪保留同一HTML中的现金原始字符串，避免浮点解析抹去显示精度。跨源微小差异只接受可由原始显示位数证明的舍入，且有绝对上限；缺失现金不能直接置零。同日记录默认去重或报冲突，不能无条件相加。

公众股/原股东差异化分红、同日多个独立分配方案、普通加特别分红等，只有实施公告支持的明确证券/日期/原金额组合才允许裁决；每项保存原值、采用值、公告URL与文件SHA，见下载目录`action_audits/`与本研究线公司行为记录。规则不按交易盈亏选择来源，原始缓存不改动。

复权字段仍使用既定的后复权因子口径。部分历史记录存在前/后因子不一致的疑点，另有真实配股而非免费送股；不自动改因子、排除相关股票或反推现金/股数。若持仓经过无显式现金/送转的因子变化，回测会停止；即使未持仓，因子异常仍可能影响信号，不能据账本对平宣称数据无偏。月度池、历史修订和执行简化也意味着本次不是严格样本外或实盘收益证明。

## 隔离边界

- 策略：`signals.py`、`strategy.py`；配置：`config.py`；股票现金/撮合：`engine.py`。
- 数据与下载缓存：本目录 `data/`；回测结果：`outputs/<run-id>/`；vn.py 运行配置：`runtime/.vntrader/`。
- 研究记录：`research/lines/stock_qmt357_vnpy/`。不写期货的数据库、配置、日志、输出、调度器或研究线。
- 仅共享已有 Python/vn.py 依赖，不安装、升级或修改期货环境。请用上述 CLI，勿在已初始化期货 vn.py 的进程内导入引擎运行。
- 仓库的 `sitecustomize.py` 会预加载期货路径，且 editable `.pth` 在 `-I` 下仍存在。股票入口以子进程环境变量禁用该启动绑定并重新启动，再进入股票私有运行目录；没有修改全局环境或原启动脚本。

## 保留的策略

- 沪深300当日涨幅非负，且 MA5 > MA10 > MA20 才允许新开仓；退出不受市场门禁限制。
- 最近60根日线；BB20、2倍样本标准差；前次下穿中轨后重新上穿，结合 RSI14 < 40、MACD5/20/9 金叉。
- 原版是**三项条件任意两项**，不是“每次必须布林反转”。保留原评分排序和宽松 MA20/MA40 趋势条件。
- 排除 ST、非当时股票池、300/688前缀；不额外排除301/302，因为原代码没有该条件。
- 最多10只，单只预算50%、每日新开仓预算30%、现金缓冲5%；普通止损2%、止盈12%，以及原版涨跌停附近的特殊保护。
- 原代码近涨跌停候选过滤只出现在后续统计循环，未删除已生成候选；迁移不擅自添加这个新信号门槛。

## 明确的迁移差异

原版在14:50获取实时价，本地完整日线不能复原这一时刻。这里使用**收盘形成信号、下一交易日开盘尝试成交**，不使用当日收盘价成交，也不读取未来价格选股。固定费率、滑点都是可审计的研究假设，不代表券商历史账单。

修正原版资金重复扣减、每日限额未严格截断、成交前写入持仓等执行问题。只在真实模拟成交回报后入账；100股买入、T+1卖出、不融资不做空，缺行情/停牌不撮合。涨停开盘不买、跌停开盘不卖；受阻买单取消、受阻卖单保留。没有重建盘口排队或成交量冲击。

信号用截至当日的复权基准，成交与权益用原价和实际股数。持仓期间复权因子变化必须有对应分红/送转，否则停止运行。现金分红按税前金额在除权日计入可用现金，送转股份在除权日计入持仓；**未重建实际派息日、股份上市日、持有期分红税或配股认购**。这可能改变资金可用时间，不能作为精确实盘账本。

Baostock 的价格限制由当日 `preclose`、板块和历史 `isST` 推导（主板普通10%、主板ST于2026-07-06由5%变10%、创业板于2020-08-24改20%，分位四舍五入），并非交易所实际限价表；特殊无涨跌幅限制日没有被完整重建，下载目录的 `derived_limit_violations.parquet` 单独列出行情超出派生限价的行。历史沪深300池采用月度快照严格滞后到下一日期，不是当前成分倒灌，但仍不是逐日生效的完整成分事件表。所有限制进入快照和结果 manifest，不能称作无偏绩效。

## 输入与产物

可用 `prepare` 只读导入 CSV/parquet。必要字段：`date, vt_symbol, open, high, low, close, volume, adj_factor, limit_up, limit_down, is_st, is_member`；可选 `cash_dividend, split_ratio`。必须有沪深300指数 `000300.SSE` 和至少一只股票；股票交易状态不得缺省伪造。开始交易前至少59个预热交易日。

冻结快照保存行情和 SHA256，回放前校验。每次输出参数、代码哈希、数据身份、权益、委托、成交、信号、市场门禁、闭合交易、拒单原因和报告；`position_coverage.csv` 明确每个持仓日的缺行情/停牌、末次真实报价日期与旧价市值。期末不强制平仓，未成交委托单独记录。收益包含未实现盈亏；胜率仅统计扣成本后的已闭合交易。

默认本金30万元；佣金万三、最低5元、卖出印花税千一、每股滑点0.01元。印花税是固定保守研究假设，不是按历史税率切换。迁移不通过扫描这些参数选择最优收益。

## 外部参考与判断

- [vn.py组合策略引擎](https://github.com/vnpy/vnpy_portfoliostrategy)：参考其多标的策略与引擎分层；期货保证金盈亏口径不能直接充当股票现金账本。
- [Tushare历史成分](https://tushare.pro/document/2?doc_id=96)、[涨跌停价格](https://tushare.pro/document/2?doc_id=183)、[复权因子](https://tushare.pro/document/2?doc_id=28)：分开获取原价、历史资格与公司行为，不用当前成分或后复权价格直接模拟现金交易。

本版本用于验证可复验运行和迁移正确性，未进行参数寻优，也未证明跨周期稳定性或实盘可用性。

### 固定参数长区间结果

`outputs/fixed_2020_20260924_v2data/`：2020-01-02至2026-09-24，连续30万元账户，期末274,636.1673元，总收益-8.4546%，最大回撤-32.7893%，Sharpe -0.0570。共426笔买卖成交、213次闭合交易、44胜/169负，净胜率20.6573%；滑点17,118元、手续费含印花税20,246.1327元，期末空仓。年度结果在该目录`annual_summary.json/csv`与`report.md`，不能用旧两年正收益代替这次长区间结论。

源面板覆盖420只历史并集股票、692,550行。公司行为已补齐已确认的现金/送转，但仍有24处未建模/待解释因子变化，以及两只合并退市股票造成的37个成员日缺行情。它们是显式数据限制，不自动改因子或剔除股票；固定回放不是无偏alpha验证。审计、复核和完整中文记录统一保存在`research/lines/stock_qmt357_vnpy/stages/`。

本次没有新增调参拟合；长区间结果不支持跨周期稳定性。若继续研究，优先处理数据合同与归因，不围绕已看到的亏损直接寻优，也不接入期货正式版。

### 首轮真实样本的质量警告

`fixed_2024_2025` 已跑通并独立对账，但下载数据有10次因子变化缺少对应显式行动记录。其中包括临时/特别派息缺失、除息日停牌被省略，以及 `000002.SZSE`（2025-01-09）和 `302132.SZSE`（2025-02-18）两处未解释的因子变化。这10个事件日均没有期初持仓，未触发本次现金账本保护，但**不能因此排除信号或候选排序受影响**。这份收益只是带数据缺陷的迁移样本，不作为alpha有效性依据；后续应先修复并冻结更完整的数据，再做不调参复验。
