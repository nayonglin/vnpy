# Stage322 forward source fetch probe

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 06:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：显式联网 source fetch 探针；只写 Stage620 scoped 输出，不追加 master forward ledger，不做收益回测，不改交易规则，不生成 paper/交易白名单，不连接 CTP，不调用订单 API。
- 是否重要突破：否。`j/i` 的 basis/inventory 已有真实 fetch 证据，但 selector/TCA/live context 仍锁定。
- 是否触发A/B：否。没有形成可接入正式版本的交易规则或白名单。

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档/GitHub：https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md
  - AKShare futures/commodities overview：https://deepwiki.com/akfamily/akshare/4.2-futures-and-commodities
  - CZCE 会员持仓静态样例：https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm
- 我的判断：
  - AKShare 能提供部分基差、库存、会员持仓、仓单入口，但“函数存在”不能等同“产品级可实盘源可用”。
  - 对扩池选品来说，必须保留 `received_at/source_url/raw_hash/product_match/status`，否则后续会把历史回填或解析偶然成功误当成可执行 alpha。
  - 本阶段只允许把成功 route 计入 forward monitor 证据，不允许计入 history selector、paper selector 或交易白名单。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`
- 新增脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数新增。
- 修改参数：无交易参数修改。
- 删除参数：无。
- 关键修正：
  - `date/datetime/Timestamp` 序列化改为 JSON safe，避免真实 fetch 行写 JSON 时失败。
  - `futures_spot_price`、`futures_inventory_em`、`futures_dce_position_rank`、`get_shfe_rank_table` 增加 request-bound 产品匹配，避免返回行不含产品代码时误判为 no product match。
  - no-match 或 empty response 不再立即返回，继续按 lookback 日期和大小写候选探测，最后保留最有解释力的失败行。
  - fetch 模式决策名区分 `rows_collected` 与 `no_usable_rows`。
  - 图表左下角从 `collector readiness` 改为 `fetch/ledger status`，把 `OK/FAIL/TAX/WAIT` 与真实 ledger 状态绑定，防止把 collector 合同误读为 source 证据。

## 回测/归因参数

- 新增交易回测：无。
- 运行命令：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py --mode dry_run`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py --mode fetch --max-fetch-rows 20 --timeout-seconds 12`
- 数据范围：
  - basis source date：`20260603`
  - member detail lookback 最后失败行：`20260530`
  - inventory request_key：`latest`
- 成本口径：无新增成本模拟。
- 样本过滤：只跑 Stage620 固定的 `j.DCE/i.DCE/ag.SHFE/CY.CZCE/SR.CZCE` 和 `basis/inventory/member_detail/warehouse/event_or_sentiment` 25 个 product-route。

## 结果

- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增回撤曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增 Sharpe。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易滑点。
  - Stage526 参考：`1,342,190`
- 总交易次数：无新增交易。
  - Stage526 参考：`905`
- 胜率：无新增胜率。
  - Stage526 非零日胜率参考：`53.6330%`
- 本阶段关键指标：
  - 决策：`forward_source_fetch_probe_stage_scoped_rows_collected_selector_locked`
  - mode：`fetch`
  - collector rows：`25`
  - stage ledger rows：`25`
  - fetched rows with raw_hash：`11`
  - non-event collectors ready：`20/20`
  - event taxonomy missing：`5`
  - selector unlocked now：`0`
  - master ledger appended：`false`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`
  - hard gates：`6/8`

### Product-route 状态

| route_group | ok | empty_source_response | error | timeout | not_attempted |
| --- | ---: | ---: | ---: | ---: | ---: |
| basis | 5 | 0 | 0 | 0 | 0 |
| inventory | 5 | 0 | 0 | 0 | 0 |
| member_detail | 1 | 4 | 0 | 0 | 0 |
| warehouse | 0 | 0 | 3 | 2 | 0 |
| event_or_sentiment | 0 | 0 | 0 | 0 | 5 |

- `j.DCE`：basis OK、inventory OK、member_detail empty、warehouse error、event not attempted。
- `i.DCE`：basis OK、inventory OK、member_detail empty、warehouse error、event not attempted。
- `ag.SHFE`：basis OK、inventory OK、member_detail OK、warehouse error、event not attempted。
- `CY.CZCE`：basis OK、inventory OK、member_detail empty、warehouse timeout、event not attempted。
- `SR.CZCE`：basis OK、inventory OK、member_detail empty、warehouse timeout、event not attempted。

## 图表视觉复盘

- 左上图仍保留 collector implementation：basis/inventory/member_detail/warehouse 的函数和合同均存在，event/sentiment 只存在 route 需求，没有 collector。
- 右上图显示真实 stage ledger row status：`ok=11`、`empty_source_response=4`、`error=3`、`timeout=2`、`not_attempted=5`，说明成功证据只覆盖部分 route。
- 左下图已修正为 fetch/ledger status：
  - `j/i` 的 basis、inventory 为绿色 OK。
  - `j/i` 的 member_detail、warehouse 为红色 FAIL。
  - event/sentiment 为紫色 TAX，明确是 taxonomy 缺口，不是网络偶发。
  - `ag` 比 `j/i` 多一个 member_detail OK，但 warehouse 仍失败。
- 右下图显示 promotion gates：基础合同和 fetch 行通过，但 `selector_unlocked_now` 与 `paper_or_whitelist_allowed` 仍为 BLOCK。这是正确状态。

## 输出文件

- collector contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_collector_contract_stage620_forward_source_collector_contract_v1.csv`
- stage ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_stage_ledger_stage620_forward_source_collector_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_gates_stage620_forward_source_collector_contract_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_decision_stage620_forward_source_collector_contract_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_report_stage620_forward_source_collector_contract_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_chart_stage620_forward_source_collector_contract_v1.png`

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势、避免高相关、选对品种”方向继续成立，但可执行表达仍然是“先补独立风险槽的 source/TCA/live 证据”。
  - `black_ferrous(j/i)` 已从完全阻塞推进到 basis/inventory 可 forward monitor，但距离可交易 selector 仍远。
  - 不能因为有 `11` 条 raw hash 行就晋级：`j/i` 仍缺 DCE member_detail、DCE warehouse、event/sentiment taxonomy、live TCA 和 live context。
  - 当前没有新增风险预算、paper selector、交易白名单或 A/B。
- 是否进入下一步：进入，但只进入补证与 forward monitor。
- 下一步：
  1. 针对 DCE `j/i`，优先修 member_detail 和 warehouse 官方/授权源；如果 DCE WAF/412 不可绕过，只能找可授权替代源，继续保留 `source_url/raw_hash/received_at`。
  2. 为 `j/i/ag/CY/SR` 建 event/sentiment taxonomy，先做事件源目录和 raw text hash，不做情绪 selector。
  3. 累计至少 `20` 个 PIT received_at 日期后，再按 Stage561 类协议做 source 稳定性和预测力审计。
  4. 扩池侧继续寻找两个非高相关、非同族重复、source 可执行、容量合格的新独立经济驱动；禁止历史收益榜白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有收益标签、没有回测收益排序、没有调交易参数。
  - 成功源只允许 `usable_for_forward_monitor=1`，`usable_for_history_selector=0`，且 `selector_unlock_candidate=0`。
  - 失败 route 被明确保留为 FAIL/TAX，而不是为了推进候选而忽略。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但仍必须收敛。
- 原因：
  - `j/i` 作为 P1 新独立风险槽的 source 证据从 `0` 推进到 basis/inventory OK，路线有实际进展。
  - 但 source 只完成一半，且扩池最终目标仍缺两个独立风险槽；继续盲目收益回测没有价值。
  - 下一步价值在于 source/TCA/live context 的闭环，不在于增加更多历史赢家品种。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py --mode dry_run`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage620_forward_source_collector_contract.py --mode fetch --max-fetch-rows 20 --timeout-seconds 12`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_decision_stage620_forward_source_collector_contract_v1.json`：通过。
- 图表已视觉检查，左下角已确认显示真实 fetch/ledger 状态，不再误导。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage322。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破、路线废弃或跨线合并。
