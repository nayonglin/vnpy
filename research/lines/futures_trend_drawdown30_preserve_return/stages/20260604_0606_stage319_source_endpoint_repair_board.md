# Stage319 source endpoint 修复板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 06:06 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：基本面/舆情 source 合同修复板；承接 Stage317 的点时化 source/event ledger 阻塞。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage619_source_endpoint_repair_board.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_report_stage619_source_endpoint_repair_board_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_chart_stage619_source_endpoint_repair_board_v1.png`
- 决策：`source_endpoint_repair_board_ready_selector_still_locked`
- 是否重要突破：否。它把 source 缺口推进成可执行清单，但没有新增可部署 selector。
- 是否触发 A/B：否。没有 paper selector、没有交易白名单、没有新增资金预算。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段只核验 source endpoint 和 forward ledger 字段，不看收益标签，不扫参数，不做历史事件补丁。
- 是否有价值继续：有。Stage317 已证明基本面/舆情不能直接做 selector，但阻塞点是 source 合同不完整；修 source 是后续实盘可执行的必要前置。

## 外部调研与判断

- AKShare futures 文档显示 DCE 持仓排名、DCE/SHFE/CZCE 仓单等接口语义存在，且给出了目标交易所页面和接口字段。
- CZCE 静态 `FutureDataHolding.htm` 可直接访问，说明郑商所持仓排名可作为 forward collector 候选。
- SHFE/DCE 官方网页存在 WAF/页面可访问性不稳定问题，不能把“网页能打开”当成 source 完成；必须由 collector 逐日保存 `received_at/source_url/raw_hash/status`。
- 我的判断：source 方向值得继续，但只能 forward-only；不得回填历史 source_url 后声称历史 selector 可用。

参考：

- AKShare futures docs：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
- CZCE holding 示例页：`https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm`
- CZCE 仓单日报入口：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
- CZCE 持仓排名入口：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
- SHFE 仓单入口：`https://www.shfe.com.cn/services/delivery/warehousewarrant1/`
- DCE 持仓排名入口：`http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html`

## 本阶段做了什么

- 读取 Stage617 product route matrix、family readiness 和 decision。
- 读取现有 `external_state_forward_ledger.csv`、`black_ferrous_p1_source_forward_ledger.csv`、真实最小 sentiment/event ledger。
- 新增 Stage619 脚本，生成：
  - endpoint catalog；
  - route repair matrix；
  - gates；
  - decision JSON；
  - markdown report；
  - 可视化图表。
- 修正脚本语义：event/sentiment 不再因为交易所首页存在而被误记为 official collector；统一标为 `manual_event_source_discovery_required`。
- 不回放收益，不改策略，不生成白名单。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage619_source_endpoint_repair_board.py`
- 修改脚本：
  - 同一脚本内修正 event/sentiment source authority 和 repair action 口径。
  - 同一脚本内消除 pandas `replace` downcast warning。
- 删除脚本：无。
- 新增参数：无策略参数。
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

- monitor products：`j.DCE / i.DCE / ag.SHFE / CY.CZCE / SR.CZCE`
- route rows：`25`
- endpoint catalog rows：`25`
- official endpoint candidates：`10`
- future source_url/hash repairs：`4`
- build official collectors：`10`
- event discovery routes：`5`
- AKShare callable present rows：`20`
- selector unlocked now：`0`
- paper selector allowed：`false`
- trading whitelist allowed：`false`
- hard gates：`5/7`

## 修复矩阵解释

- `j.DCE/i.DCE`：
  - basis/inventory 已可 monitor，但旧 ledger 行缺 `source_url`，只允许未来行补合同字段。
  - member_detail/warehouse 有官方接口候选，但 DCE member parser 曾出现 `BadZipFile`，必须 forward forensic 修复。
  - event/sentiment 仍为 source discovery，不能 selector。
- `ag.SHFE`：
  - basis/inventory 有观测但 contract 不完整，需要未来行补 `source_url/raw_hash`。
  - member_detail/warehouse 有官方接口候选，但需确认产品/合约层聚合口径。
  - event/sentiment 仍为 source discovery。
- `CY.CZCE/SR.CZCE`：
  - basis 有观测但缺 source 合同字段。
  - inventory 需要先 probe 第三方支持。
  - member_detail/warehouse 有 CZCE 官方静态文件候选。
  - event/sentiment 仍为 source discovery。

## 图表视觉复盘

- 左上图把每个产品×路由压成 `OK/REPAIR/BUILD/DISC`：`j/i` 只有 basis/inventory 是 monitor OK，member/warehouse 仍要 BUILD，event 全为 DISC。
- 右上图显示 basis/inventory 有观测但官方候选主要集中在 member/warehouse；event 只有 endpoint catalog，不是 official collector。
- 左下图显示 `ag/CY/SR` 修复债务更重，尤其 P2 的 event discovery debt 仍未解决。
- 右下图显示 `selector_unlocked_now` 和 `paper_or_whitelist_allowed` 明确为红色阻塞。
- 视觉结论：图表没有把 source repair 误画成 selector 晋级，也没有把 event/sentiment 误画成可部署数据源。

## 结论

- 本阶段结论：source endpoint 修复方向成立，但 selector 仍锁定。
- Stage317 的阻塞被拆成两类：
  - 可工程推进：10 个官方接口候选、4 个未来 source_url/hash 修复、20 个 AKShare callable 入口。
  - 仍不可部署：5 条 event/sentiment discovery debt、selector `0`、paper/whitelist `0`。
- 不允许历史回填后升级 selector。所有修复必须从未来采集日开始写入 `received_at/source_url/raw_hash/status`，累计点时化样本后再审计预测力。

## 结束后反思

- 是否过拟合：否。没有根据收益挑 source，没有回填历史事件，也没有用 source 修复结果解锁 selector。
- 是否有价值继续：有。下一步可以把 source repair 从“板子”推进到 forward collector；但价值边界很清楚，source 未累计前仍不能进入 paper/A/B/交易白名单。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage619_source_endpoint_repair_board.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage619_source_endpoint_repair_board.py`：通过。
- decision JSON 复读：通过。
- 图表视觉检查：通过，已确认 event/sentiment 被正确画为 discovery debt。
- 输出文件存在：通过。

## 输出文件

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_decision_stage619_source_endpoint_repair_board_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_report_stage619_source_endpoint_repair_board_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_chart_stage619_source_endpoint_repair_board_v1.png`
- endpoint catalog：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_endpoint_catalog_stage619_source_endpoint_repair_board_v1.csv`
- route repair matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_route_repair_matrix_stage619_source_endpoint_repair_board_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage619_source_endpoint_repair_board_gates_stage619_source_endpoint_repair_board_v1.csv`

## TODO

- 实现 forward source collectors，最小字段为 `received_at/source_url/source_authority/raw_hash/status/product_vt_symbol/route`。
- 优先级一：DCE `j/i` member_detail parser forensic 和 warehouse route。
- 优先级二：`ag/CY/SR` 的 basis/inventory 未来行补 source 合同字段。
- 优先级三：为 `j/i/ag/CY/SR` 建 event/sentiment source taxonomy；无 taxonomy 前禁止舆情 selector。
- 累计至少 `20` 个 PIT 日期后，才能做预测力审计；在此之前 selector、paper、白名单均保持 `0`。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage319。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入。
