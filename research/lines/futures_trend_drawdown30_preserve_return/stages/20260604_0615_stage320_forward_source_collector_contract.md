# Stage320 forward source collector 合同

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 06:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage319 source endpoint 修复板的 collector 合同落地；默认 dry-run，不写 master ledger。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_report_stage620_forward_source_collector_contract_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_chart_stage620_forward_source_collector_contract_v1.png`
- 决策：`forward_source_collector_contract_ready_default_dry_run_selector_locked`
- 是否重要突破：否。非事件 collector 合同已可运行，但还没有真实 fetch 行和 PIT 样本深度。
- 是否触发 A/B：否。没有 paper selector、没有交易白名单、没有新增资金预算。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。
- 是否联网抓取外部源：否。默认 `dry_run`，只验证采集合同和 stage-scoped ledger schema。
- 是否追加 master ledger：否。

## 开始前反思

- 是否过拟合：否。本阶段是 source acquisition infrastructure，不看收益标签，不做历史 selector，不回填事件。
- 是否有价值继续：有。Stage319 已把 source 缺口拆成 route 修复项；Stage320 让这些修复项具备统一的 collector 合同和点时化字段。

## 外部调研与判断

- AKShare futures 文档和本地 `akshare==1.18.55` 均确认以下入口存在：`futures_spot_price`、`futures_inventory_em`、`futures_warehouse_receipt_dce`、`futures_shfe_warehouse_receipt`、`futures_warehouse_receipt_czce`、`futures_dce_position_rank`、`get_rank_table_czce`、`get_shfe_rank_table`。
- DeepWiki/AKShare futures overview 对 futures/commodities 数据源做了结构化说明，支持用 AKShare 作为入口，但不能替代我们自己的 `received_at/source_url/raw_hash/status` ledger。
- CZCE `FutureDataHolding.htm` 静态页可作为持仓排名 collector 的 source_url 模板之一。
- 我的判断：现在可以实现 collector 合同，但不能自动 fetch 并合入 master ledger；显式 fetch 需要单独运行、视觉复盘并确认每条 product-route 的 product match。

参考：

- AKShare futures docs：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
- AKShare futures/commodities overview：`https://deepwiki.com/akfamily/akshare/4.2-futures-and-commodities`
- CZCE holding 示例页：`https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm`

## 本阶段做了什么

- 新增 Stage620 脚本，读取 Stage619 endpoint catalog 和 route repair matrix。
- 为 25 条产品×路由生成 collector contract。
- 对非事件路由建立显式采集合同：
  - basis：`futures_spot_price(date, vars_list=[code])`
  - inventory：`futures_inventory_em(symbol=code)`
  - DCE/SHFE/CZCE warehouse：对应交易所仓单函数
  - DCE/SHFE/CZCE member_detail：对应持仓排名函数
- event/sentiment 保持 `source_taxonomy_required`，不实现假 collector。
- 生成 stage-scoped ledger schema，字段覆盖 `received_at_local/utc`、`source_url`、`raw_sha256`、`request_contract_sha256`、`usable_for_forward_monitor`、`usable_for_history_selector`、`selector_unlock_candidate` 等。
- 默认 dry-run 输出 25 行 `dry_run_not_fetched`，证明 request contract 和 PIT 字段，不作为 source evidence。
- 修正图表语义：`CY/SR inventory` 从 READY 降为 PROBE，避免把函数存在误读为产品级可用。
- 修正空 callable 字段清洗，避免 event/sentiment 行出现字符串 `nan`。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`
- 修改脚本：
  - 同一脚本内修正 stage ledger 文件名、产品路由图表标签、空字段清洗。
- 删除脚本：无。
- 新增参数：
  - `--mode dry_run|fetch`，默认 `dry_run`
  - `--source-date`
  - `--lookback-days`
  - `--timeout-seconds`
  - `--max-fetch-rows`
- 修改参数：无策略参数。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- mode：`dry_run`
- collector rows：`25`
- stage ledger rows：`25`
- non-event collectors ready：`20/20`
- event taxonomy missing：`5`
- fetched rows with raw_hash：`0`
- selector unlocked now：`0`
- master ledger appended：`false`
- paper selector allowed：`false`
- trading whitelist allowed：`false`
- hard gates：`6/8`

## 图表视觉复盘

- 左上图显示 basis/inventory/member_detail/warehouse 均为 `5/5` route、`5/5` collector implemented、`5/5` callable present；event/sentiment 只有 route，没有 callable/collector。
- 右上图显示 stage ledger 全部为 `dry_run_not_fetched`，说明本阶段没有把 dry-run 误记为真实 source evidence。
- 左下图显示 event/sentiment 全部为 `TAX`，`CY/SR inventory` 为 `PROBE`，其余非事件路由为 `READY`；这比第一版更准确。
- 右下图显示 `selector_unlocked_now` 和 `paper_or_whitelist_allowed` 仍为红色阻塞。
- 视觉结论：图表清楚区分了 collector contract ready、产品级 probe、event taxonomy missing 和 selector locked，没有把基础设施进度误画成交易候选。

## 结论

- 本阶段结论：Stage319 的 source 修复板已经有可运行 collector 合同，但仍没有真实 source rows。
- 可推进项：
  - 20 条非事件路由具备显式 AKShare 入口和 stage ledger 字段。
  - dry-run ledger schema 已覆盖 point-in-time 审计所需字段。
  - `--mode fetch` 已可用于后续显式 fetch probe。
- 不可推进项：
  - event/sentiment 仍缺 source taxonomy。
  - dry-run 行不能计入 PIT 样本。
  - `raw_sha256=0`，所以本阶段不能解锁 selector、paper、A/B 或 whitelist。

## 结束后反思

- 是否过拟合：否。没有根据收益挑选源、没有回填历史数据、没有把 collector 合同转成信号。
- 是否有价值继续：有。下一步可以在明确允许外部源 fetch 的条件下运行 `--mode fetch --max-fetch-rows`，形成第一批 stage-scoped source rows；之后才谈是否追加 master ledger 和累计 20 个 PIT 日期。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`：通过。
- decision JSON 复读：通过。
- 图表视觉检查：通过，已修正 `CY/SR inventory` READY 误导和 `nan` 字段问题。
- 输出文件存在：通过。

## 输出文件

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_decision_stage620_forward_source_collector_contract_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_report_stage620_forward_source_collector_contract_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_chart_stage620_forward_source_collector_contract_v1.png`
- collector contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_collector_contract_stage620_forward_source_collector_contract_v1.csv`
- stage ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_stage_ledger_stage620_forward_source_collector_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_gates_stage620_forward_source_collector_contract_v1.csv`

## TODO

- 显式运行小批量 `--mode fetch --max-fetch-rows`，只写 stage-scoped ledger，不追加 master。
- 视觉复盘 fetch status、product match、raw hash 覆盖和失败源类型。
- 若 fetch 通过，再设计 master ledger append gate；append 前必须确认 `source_url/raw_sha256/status/matched_product` 完整。
- 继续为 event/sentiment 建 source taxonomy；无 taxonomy 前禁止任何舆情 selector。
- 累计至少 `20` 个真实 PIT 日期后，再按 Stage561 协议做预测力审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage320。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入。
