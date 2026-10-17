# Stage006 已接受 A0 的开盘 anchor 与真实日线 open 等价审计

- line_id：`futures_trend_triple_screen`
- 当前模式：离线、零账户、只读价格证据；`production_qualified=false`。
- 记录时间：2026-10-17 23:31 CST，读取时钟后记录。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。
- 阶段性质：固定 A0 路径的数据表达审计，未改变执行合同或增加 fallback。
- 是否重要突破：否；获得有限路径的开盘价关系证据，并明确发现不等价项。
- 是否触发A/B：本阶段未运行 A/B 账户，既有候选与数据门保持冻结。

## 外部调研与判断

- 参考资料：沿用预声明协议中的 [Backtrader 官方次 bar open 时序说明](https://backtrader.com/blog/posts/2017-05-01-cheat-on-open/cheat-on-open/)及 [broker 源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)，并读取本仓原 session helper。
- 我的判断：前日发单、次 session 首分钟开盘成交与入场日盘中风险路径是不同的数据要求。本次只判断固定事件的价格和物理时刻关系；即使数值相同，也不能据此替代盘中 0.5R/C2 路径、合成分钟 OHLCVOI 或证明新候选的成交可实现性。

## 本次变更

- 新增脚本：`tools/stage006_daily_open_equivalence.py`、`tools/test_stage006_daily_open_equivalence.py`。
- 修改脚本：无；Stage001、Stage002、Stage004 已运行代码和正式策略不变。
- 删除脚本：无。
- 新增参数：独立 CLI `--audit`，输出目录存在时拒绝覆盖；固定价格比较绝对容差 `1e-8`、相对容差 `1e-12`，同时单列浮点精确相等。
- 修改参数：无。
- 删除参数：无。
- 已运行源码 SHA256：`3aa7e79ed46c180f93c08b8d158ac0f42ba8ba868289c4da9d500b64ff12a3ee`。
- 冻结协议：`stages/20261017_2323_stage006_daily_open_equivalence_protocol.md`，运行时 SHA256 `d7b0ec858d8cca42fc49dde0fa508ffe4a55218be8eff03cef2f782e942f125d`。

## 回测/归因参数

- 数据区间：A0_attempt2 已接受的全部 535 条 `execution_anchor_requests`；不从账户收益或事后盈亏筛事件。
- 账户规模：N/A；金融回放 0。
- 成本口径：N/A；不计算费用、滑点、成交盈亏或权益。
- 样本过滤：不删事件。按精确 `vt_symbol × trading_date` 参数化查询同 SHA 原 SQLite，限定 `interval='d'`，只返回 `datetime, open_price`。缺失或重复真实 bar 拒绝等价，不使用 carry 或另一合约。
- 策略/归因口径：原 mapping 日历和原 `session_minutes` 核查实际物理首分钟；夜盘沿原交易日归属。方向仅从 `trades.csv` 的 `order_id, vt_symbol, direction, offset, trading_date` 五个字段精确关联，不读权益或 PnL 列。方向为买卖方向，不是持仓多空标签。
- 只读约束：SQLite 使用 `mode=ro&immutable=1`，运行前后拒绝非空 WAL；DB/mapping 与原 A 和 A0 指纹一致，helper 与 A0 指纹一致；全部输入运行前后不变。
- 唯一实际命令：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage006_daily_open_equivalence.py --audit`，退出码 0，用时 4.75 秒。未重复审计。

## 结果

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。
- 其他关键指标：535 个精确 key 查询到 535 条唯一真实日线；缺 bar 0、重复 bar 0、非法价格 0、方向未知 0。535 条 expected_start 与 actual_time 均等于原 helper 首分钟。

| Offset | 买卖方向 | 事件数 | 精确价格一致 | 容差一致 | 价格不一致 |
| --- | --- | ---: | ---: | ---: | ---: |
| Open | Long | 245 | 245 | 245 | 0 |
| Open | Short | 74 | 74 | 74 | 0 |
| Close | Long | 46 | 45 | 45 | 1 |
| Close | Short | 170 | 170 | 170 | 0 |
| 全部 | 全部 | 535 | 534 | 534 | 1 |

Open 为 319/319 一致；Close 为 215/216 一致。唯一差异保留原值：

| 合约 | 交易日 | 实际物理首分钟 | 订单 | Offset/方向 | canonical anchor | 真实日线 open | 绝对差 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| au2610.SHFE | 2026-10-14 | 2026-10-13 21:00 | BACKTESTING.560 | Close / Long（平仓买单） | 903.62 | 904.98 | 1.36 |

本阶段没有判断该差异哪一来源正确，也没有修正任何源值。由此不能声称全部 535 事件或所有普通次开盘成交都可用日线 open 等价替代。

- 下载 0、模型训练 0、原数据修改 0、PnL 列读取 0、fallback 启用 0。
- 5 个 focused 契约测试 red→green 通过：精确合约/交易日/interval；缺失及重复真实 bar 拒等价；不同/非法价格保留；周五夜盘归周一且拒自然日 09:00 替代；订单方向精确关联与未知保留。
- 已请求 `/root/first_screen_independent` 做限定独立审查；本记录写入时审查尚待返回。不得将测试或本次自审称为独立全量复算。
- 后续独立回执：2026-10-17 23:33完成，`outputs/stage006_independent_review/review_receipt.json`。535身份/方向关联及6个SQL哨点通过，结论仍为全等价不成立、不得自动fallback。唯一黄金21:00分钟OHLC平且volume=0，但缺邻分钟等证据，不能确定竞价或数据原因；保留原值和原执行合同。

## 输出文件

以下数据产物位于 `outputs/stage006_daily_open_equivalence/`：

- report：本阶段记录。
- summary：`data_open_equivalence.json`（按 offset、direction 及组合汇总）。
- orders：N/A；仅从既有订单字段关联方向，没有新增委托。
- daily：N/A；没有账户日权益。
- quality：`event_checks.csv`（535 个事件逐项检查）、`anomalies.csv`（1 个差异）、`input_manifest.json`、`attempt_started.json`。产物 SHA 见 summary 的 `artifact_sha256`。

## 结论

- 本阶段结论：固定已接受 A0 路径的 534/535 个首分钟 anchor 与精确真实日线 open 完全相同，全部开仓事件相同；存在一个明确的平仓价差异，不能泛化为全市场或新候选的数据等价合同。
- 是否进入下一步：可继续数据合同讨论，但本阶段不批准任何 fallback、C0 第三次尝试或执行修改。
- 下一步：保留不一致和既有严格数据门，结合独立核查结果决定是否需要另行预声明共同数据表达、时间可见性和精确需求。入场日盘中风险仍必须有完整真实分钟证据。

## 过拟合反思

- 运行前判断：否，固定全部已接受事件，不按结果筛选，不调策略规则。
- 运行后判断：否，保留唯一不一致，不为减少缺口强称等价；这只是已接受路径的有限数据证据，不提供新 alpha 优势证明。
- 原因：比较对象预声明，未读收益、未重训、未变动参数或原行情；历史样本选择偏差仍保留。

## 继续价值反思

- 运行前判断：是，有助于分清开盘价格表达和盘中路径要求。
- 运行后判断：是，但不能直接据此放宽执行数据门。
- 原因：已获得整体高一致性与一个反例；后续应先定义并检验共同数据合同，避免无证据地掩盖新路径缺分钟。

## 合入建议

- 是否更新本线 `LINE.md`：由 root 汇总后统一更新，本任务未改。
- 是否更新 `research/registry.md`：由 root 决定，本任务未改。
- 是否追加根目录 `memory.md/back_log.md`：否，当前仅本线限定数据证据，未形成正式候选。
- 仅归档本线工具、测试和小证据产物；不合入正式执行或生产发布通道。
