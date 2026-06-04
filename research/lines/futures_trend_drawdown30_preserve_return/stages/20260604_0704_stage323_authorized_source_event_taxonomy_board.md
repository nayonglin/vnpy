# Stage323 授权源与事件 taxonomy 决策板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`
- 阶段性质：只读 source/event 可执行性审计；不联网抓新数据、不追加 master ledger、不新增收益回测、不改交易规则、不生成 paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否。事件 taxonomy 合同已定义，但没有自动事件 monitor，也没有 DCE 授权凭证。
- 是否触发A/B：否。没有形成可接入正式版本的交易规则或白名单。

## 外部调研与判断

- 参考资料：
  - DCE API SDK / PyPI `dceapi`，文档显示需要 `DCE_API_KEY/DCE_SECRET`：https://pypi.org/project/dceapi/
  - DCE API Rust 文档，覆盖 delivery/member/news 等服务形态：https://docs.rs/dceapi-rs/latest/dceapi_rs/
  - ICE DCE market data catalog，属于 licensed vendor route：https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce
  - AKShare futures docs / source routes：https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md
  - SHFE daily data page / daily warrant and ranking templates：https://tsite.shfe.com.cn/eng/reports/statistical/daily/index.html
  - CZCE static holding example：https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm
- 我的判断：
  - DCE `member_detail/warehouse/event` 的生产路线不应继续以 public-web 412/WAF 绕行为主，应转向授权 API 或正式数据服务。
  - ICE 等 vendor route 可以作为 market data/TCA 备选，但不自动覆盖 DCE member/warehouse 基本面特征。
  - `j/i/ag/CY/SR` 的事件 taxonomy 可以先定义语义、来源候选和 raw_text_hash 纪律，但没有自动抓取前不能算 event-ready。
  - 本阶段只是把“source 不可执行”拆成凭证、parser、static file、raw text ledger 四类工作，不解锁 selector。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `DCE_API_KEY/DCE_SECRET` 环境凭证检查，仅检查是否存在，不打印值。
  - `access_requirement_satisfied` source lane 字段，用来区分“无需凭证”和“需要凭证但缺失”。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 新增交易回测：无。
- 输入数据：
  - Stage620 fetch ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_stage_ledger_stage620_forward_source_collector_contract_v1.csv`
  - Stage620 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage620_forward_source_collector_contract_decision_stage620_forward_source_collector_contract_v1.json`
- 运行命令：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`
- 成本口径：无新增成本模拟。
- 样本过滤：只读 Stage620 固定的 `j.DCE/i.DCE/ag.SHFE/CY.CZCE/SR.CZCE` 五个 monitor products。

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
  - 决策：`authorized_source_event_taxonomy_contract_ready_selector_locked`
  - Stage620 raw hash rows：`11`
  - source lane rows：`29`
  - event taxonomy contract rows：`5`
  - DCE authorized credentials present：`0`
  - dceapi python installed：`0`
  - event auto monitor validated：`0`
  - selector unlocked now：`0`
  - master ledger appended：`false`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`
  - hard gates：`3/6`

### Source lane 分层

| lane_type | rows | 判断 |
| --- | ---: | --- |
| `current_third_party_forward` | 10 | basis/inventory 已可 forward monitor，但不能 history selector |
| `current_official_forward` | 1 | `ag.SHFE member_detail` 当前可 monitor，但样本深度不足 |
| `authorized_dce_api_candidate` | 6 | `j/i` 的 member/warehouse/event 候选，当前缺 `DCE_API_KEY/DCE_SECRET` |
| `licensed_vendor_candidate` | 2 | 可作为 market data/TCA 候选，不自动覆盖 member/warehouse |
| `official_route_repair_required` | 1 | `ag.SHFE warehouse` 需要修 parser/date/product contract |
| `official_static_file_repair_required` | 4 | `CY/SR` 的 CZCE member/warehouse 需要修静态文件日期与超时 |
| `manual_public_event_taxonomy_contract` | 5 | 已有 taxonomy 合同，但没有自动 raw-text monitor |

### Event taxonomy

- `j.DCE`：`exchange_notice_delivery_margin`，来源候选为 DCE official notices / authorized DCE API news service，状态 `requires_authorized_dce_api_or_manual_raw_hash`。
- `i.DCE`：`exchange_notice_delivery_margin`，来源候选为 DCE official notices / authorized DCE API news service，状态 `requires_authorized_dce_api_or_manual_raw_hash`。
- `ag.SHFE`：`exchange_notice_warehouse_macro`，SHFE member 已部分验证，warehouse 仍需修复。
- `CY.CZCE`：`crop_supply_exchange_notice`，CZCE 静态文件和 USDA/NASS cotton 类事件只能先 forward/manual hash。
- `SR.CZCE`：`crop_supply_exchange_notice`，CZCE 静态文件和 USDA/WASDE sugar 类事件映射较弱，只能先 monitor。

## 图表视觉复盘

- 左上图：Stage620 route evidence 没有变化，`j/i` 只有 basis/inventory 绿，member/warehouse 红，event 紫；图表没有把 taxonomy 误画成 OK。
- 右上图：source lane inventory 显示最多的是 `current_third_party_forward=10`，其次是 `authorized_dce_api_candidate=6`。这说明当前进展主要是 monitor 证据和候选授权路线，不是可部署 selector。
- 左下图：event taxonomy states 全部为紫色状态，分别是授权 API/raw hash、静态文件需修复、SHFE 部分验证；没有绿色自动事件源。
- 右下图：`stage620_fetch_probe_loaded`、`current_forward_monitor_routes_exist`、`event_taxonomy_contract_defined` 通过；`dce_authorized_credentials_present`、`event_auto_monitor_validated`、`selector_unlocked_now` 均阻塞。视觉结论正确。

## 输出文件

- source lane catalog：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_source_lane_catalog_stage623_authorized_source_event_taxonomy_board_v1.csv`
- product route status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_product_route_status_stage623_authorized_source_event_taxonomy_board_v1.csv`
- event taxonomy catalog：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_event_taxonomy_catalog_stage623_authorized_source_event_taxonomy_board_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_gates_stage623_authorized_source_event_taxonomy_board_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_decision_stage623_authorized_source_event_taxonomy_board_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_report_stage623_authorized_source_event_taxonomy_board_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_chart_stage623_authorized_source_event_taxonomy_board_v1.png`

## 结论

- 本阶段结论：
  - “减少单笔风险、扩大品种池、选对品种”的下一步不能是宽池收益回测，而必须是 source 授权和事件 ledger。
  - `j/i` 的 DCE member/warehouse/event 不应继续以绕 public web 防护为主；更干净路线是授权 DCE API 或正式数据服务。
  - 事件 taxonomy 已经从完全 TAX 推进到 5 产品合同定义，但事件自动 monitor 仍为 `0`，不能 selector。
  - 当前没有新增风险预算、paper selector、交易白名单或 A/B。
- 是否进入下一步：进入，但只进入授权源/事件 raw-text ledger 补证。
- 下一步：
  1. 如果有 DCE 授权凭证，先做只读 `DCE_API_KEY/DCE_SECRET` 环境验证和 endpoint probe，不打印密钥，不追加 master ledger。
  2. 如果没有 DCE 授权凭证，先做 `j/i/ag/CY/SR` 的 manual/public raw-text event ledger bootstrap，字段必须包含 `received_at/source_url/published_at/raw_text_hash/product_mapping_method/status`。
  3. 对 `ag.SHFE warehouse` 和 `CY/SR CZCE static files` 做 parser/date/timeout 修复，而不是启动收益回测。
  4. 未有 `20` 个 PIT 日期、event auto monitor 和 live TCA 前，继续禁止 selector、paper、A/B 和交易白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有收益标签、没有参数搜索、没有历史白名单。
  - 有源不等于晋级；DCE 授权缺失和 event auto monitor 缺失均被明确画成红灯。
  - 输出是凭证/parser/raw-text-ledger 工作项，不是交易规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 这一步把“基本面/舆情能不能加”从泛泛讨论拆成了可执行源前置条件。
  - 继续价值在于补真实 source 与 raw hash，而不是追求更好看的历史收益。
  - 如果授权源或 raw-text ledger 能稳定积累，后面才能做预测力审计；否则扩池 selector 必须继续锁定。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage623_authorized_source_event_taxonomy_board.py`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage623_authorized_source_event_taxonomy_board_decision_stage623_authorized_source_event_taxonomy_board_v1.json`：通过。
- 图表已视觉检查并复查 `credentials_present/access_requirement_satisfied` 表达，确认不会把 taxonomy 或授权候选误读为可交易 source。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage323。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破、路线废弃或跨线合并。
