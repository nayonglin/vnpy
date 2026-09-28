# Stage021 会员来源历史起点与盘口路线排重

- line_id：`futures_trend_xgboost_history_compatible_root_utility`
- 当前模式：有界来源核验、旧研究排重；不训练、不回测，reviewer0。
- 记录时间：2026-09-06 05:27 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 阶段性质：修正Stage020后续数据重建决策，不修改其冻结结果。
- 是否重要突破：否。排除当前不合格来源，不是新增alpha或整个XGBoost方向终止。
- 是否触发A/B：否。

## 外部调研与判断

- [AKShare现行期货文档](https://akshare.akfamily.xyz/data/futures/futures.html)及[官方源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py)声明，`futures_gfex_position_rank`的数据起点为2023-11-10。本地安装的同名函数docstring一致。判断：当前API承诺范围不包含起点之前的历史；修复HTTP传输也不能证明早期数据就绪。
- 该证据来自API维护方，不是已核验的交易所原始历史完整性证明。本轮没有取得交易所原始公告；不以转载公告或接口HTML推断“任何供应商都不存在更早数据”。
- [天勤API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[官方GitHub实现](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)确认历史tick接口包含买卖一价量，`get_tick_data_series`为专业版能力。判断：L1报价包含分钟OHLCV之外的信息，但不等于逐笔订单、完整深度、主动成交方向或可执行队列回放；公开产品能力不等于当前账户权限与样本覆盖。本轮未登录或调用行情API。
- [BigQuant会员数据说明](https://bigquant.com/data/datasources/cn_future_member_position)未提供可核验的早期GFEX逐日同合约/历史版本证据。页面时间字段不能无依据当作最早实际观测日，不据它替换来源或启动抓取。

## 本次变更与执行

- 约05:19开始核对GFEX起点；05:26重新执行只读CSV与内存SQLite审计，exit0，两算法事件ID完全一致。
- 05:27仅新增本阶段记录并更新本线`LINE.md`；新增/修改/删除脚本均无，策略/模型参数无变化。
- 仅读Stage019全部276事件的`event_id/decision_date/required_source_date/product_vt_symbol/contract_vt_symbol`。不读取本线收益标签，不改变生命周期、不计算集中度训练值。
- 使用`.py311/bin/python -B`、标准库`csv/sqlite3/ast/hashlib`；AST只提取安装版函数docstring，没有import AKShare或触发其网络行为。
- 行情接口请求0、重试0、凭据读取0、标签生成0、历史fit/predict0、策略回放0、reviewer0。外部网页检索属于资料调研，不是行情回填。

## 固定范围与结果

- 原区间2020-01-02至2026-08-28、本金150,000、全部276事件保留。没有删品种、缩区间、调60样本门或补中性值。
- 276事件中14个GFEX事件；其中2个所需前一交易日早于2023-11-10。

| 决策日 | 所需源日期 | 实际合约 | 事件ID |
| --- | --- | --- | --- |
| 2023-08-23 | 2023-08-22 | si2310.GFEX | ab171dde7a57cec84377b3e3d10f537f8ed0c860e75e70a69f9517115f8da3dd |
| 2023-11-06 | 2023-11-03 | lc2401.GFEX | f35fba0ed75356bf196dccd4c40021f81c4b38afce0c84cae7fabb010e90e0dc |

- 标准库按GFEX后缀和ISO源日期比较获得以上2项；将相同5列装入内存SQLite后执行下列独立查询，排序后的完整事件ID列表精确一致：

```sql
SELECT event_id
FROM events
WHERE contract_vt_symbol LIKE '%.GFEX'
  AND required_source_date < '2023-11-10'
ORDER BY event_id;
```

- Stage020首个GFEX探针恰为2023-08-22，早于接口声明起点。此前未先检查这个约束是排重遗漏；旧线`futures_trend_c9_minrisk_highquality/stages/20260619_2303_stage029_member_rank_backfill_route_audit.md`已经记录过同一日期边界。
- 不能据起点反推Stage020返回HTML的技术原因；传输失败和历史范围不匹配是两项独立问题。也不把其余12个GFEX事件自动视为可用。
- Stage019的117可用/122范围外/37范围内缺失保持原样，Stage020的5请求/2载体可读保持原样。新证据改变的是后续决策，不追改旧报告使它看似事先已知。

## 盘口路线排重

- 只读旧线Stage065/067/073/078/255/259等记录，确认Tq历史L1报价、覆盖扩展、分钟价格来源差异都已研究过。旧Stage067的重入盘口稳定性门失败，旧Stage073记录原分钟价格与Tq tick top-book不一致；不重新下载以复现已知“接口存在”。
- 旧线采用不同年份范围、事件和基准。本轮只将其作为排重与风险线索，没有重算其原产物，旧绩效/覆盖计数不迁入当前276事件资格，不把旧重入规则失败称为当前根入场XGBoost已被反证。
- 精确重建正式执行价是执行回放问题，不是所有外生报价特征的普适前提。若未来研究严格决策前的报价特征，仍需单独证明同一实际合约、时间戳与截止时点、字段语义、样本覆盖及机制适合持仓周期；不能拿同一分钟事后报价或价格源差异当alpha。
- 当前没有据此提出可启动的新盘口模型，没有检查当前天勤权限、购买服务、下载tick或改变原回测价格源。

## 回测记录

- 新增/修改/删除回测结果均无。
- 本阶段期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。Stage016失败结论保留，不拼接旧线绩效。
- 原全周期收益提高且回撤下降目标仍未达到；资料或源检查不是有价值模型版本。

## 输出与验证

- report：本文件；无新模型、预测、行情或绩效工件。
- 事件覆盖CSV：`artifacts/stage019_member_concentration_source/event_coverage.csv`，SHA `d7184780f506b9e0e991896aec761ec1484d92dd15a22d1a2841c120366e321b`；本次重读校验276唯一事件ID。
- 安装版`.py311/lib/python3.11/site-packages/akshare/futures/cot.py`，SHA `7a243a4c79e889e2a3e7c9f77135c4e2d88b6c5f2f556e9ee80d5ba963444c2f`；函数docstring包含`20231110`。
- 本次复核Stage019/020摘要SHA分别为`4d8a0e2e8cadd016f3db20ff98196bf1219f4919d91dca8787e87dcf02615ad7`、`e9130a7fe5694527b4a46c3fc043de563e26480a05e599474dc8c23db7f65c6f`，未变。
- Stage016/017摘要SHA分别为`743577f2f983d5597f59d871c3be853eb11b49e9a757baef88c60977455fcb5d`、`fa4b05a0d655203bd848340c14b97e4fbedca21a1d12acb0ad5f436ce8c505eb`，未变。
- 本轮没有代码修改，不重跑全量pytest。上轮278 passed仅作历史记录，本轮实际验证为事件/源身份、CSV-SQL双算法及生产只读身份检查。
- 05:26生产工作区仍干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。本轮命令均完成，无行情会话或后台任务遗留；无CTP/订单/生产写入/commit/push。

## 结论与后续

- 本阶段决策：`stop_current_member_source_rebuild_provider_history_excludes_required_events`。停止当前来源的全276会员集中度候选准备和批量回填，不继续修复其余交易所来挽救这份来源合同。
- 只有新取得合法、同合约、所需历史日期和时间语义可核验的独立来源证据，才重新评估会员路线；不把删除2事件、SHFE子集、零填充或更晚起训当当前合同的修补。
- 天勤路线只完成排重，不启动旧盘口规则救援。后续方向先说明相对已失败机制的新信息与可证伪预测，再检查当前样本的无未来数据资格；没有新证据时不为继续而继续跑探针。
- reviewer按用户最新要求执行：仅有价值的真实模型版本才启动；当前约定为完整C收益与回撤双目标及事前稳健性通过后启动，不为常规改动、数据检查或失败候选拉起。

## 过拟合反思

- 运行前：否，本轮只核对来源范围，不按收益调参；既有研究选择偏差仍存在。
- 运行后：没有新增拟合或交易规则；当前结论是数据边界，不是新的样本外证据。阅读旧失败结果会影响方向选择，应如实记账，不能宣称整个研究流程无选择偏差。

## 继续价值反思

- 运行前：是，确认历史起点能以低成本避免无效批量重建。
- 运行后：本次核对有价值；重复修复当前会员接口或重新做天勤可下载性检查无价值。总体目标保留，但下一次执行必须有新机制/来源证据，而非增加同类审计数量。

## 合入建议

- 更新本线`LINE.md`：是。修改其他线/registry/根总账：否，未发生跨线合入、正式候选或全路线终止。
