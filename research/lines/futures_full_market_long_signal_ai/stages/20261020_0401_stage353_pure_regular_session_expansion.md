# Stage353：三日运营日程纯展开函数

2026-10-20 04:01 CST；line_id=`futures_full_market_long_signal_ai`。依据root已批准350，新增纯函数与唯一tiny组。非重要alpha突破、非正式A/B/C；0真实数据/metadata/行情/网络/经济/SQL/fitcash，未读351或绑定348半成品schema，不改LINE/registry或其他文件。

## 接口与边界

[stage353_regular_sessions.py](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage353_regular_sessions.py)共106行，无CLI、loader、SDK、模型或资金依赖。

`expand_sessions(metadata, trade_date, *, calendar, night_anchors, evidence, last_day_override=None)`：metadata必须实际包含symbol、metadata_received、day、night、expire_datetime、source_receipt。evidence明确`policy=operational_regular_schedule`及truthy source_receipt；输入不修改。root可在351真实metadata获得349接受后，由354一次离线构造这个最小字典调用，本author不调用真实输入。

输出symbol/date、intervals(kind/start/end)、first_open、session_end、state/reasons、night_state、expiry_state及来源。只提供350运营时钟候选，不创建source_completed_at、Future/T0或vendor_finality资格。first_open遵守原连续时段execution-open约定；auction另列None，不猜提前五分钟，也不改Dopen政策。

仅支持已冻结19/20/21三日，夜锚固定16/19/20。calendar对目标及有夜盘时的锚日须明确True；锚间仅允许周末或已接explicitFalse，遇True交易日、未证实的工作日间隔或非bool值就unknown。小时按锚日加秒解析，25:00落锚日次日01:00；不取模、不把周一夜盘贴到周日。

模板必须list、时刻可parse、起止严格递增，day非空；不补跨午夜。模板或展开后区间重叠就unknown。night只有明确收到metadata、有receipt、day/night均有效解析后才记observed_empty或observed_intervals；缺night、None、缺day/receipt、未收到均不能冒充无夜盘。

expire_datetime必须可parse且有限；None保持unknown。目标在expiry北京日期之后返回expired、不展开；当日必须显式last_day_override含day/night/source_receipt，否则unknown，不沿普通模板猜最后日时段。其他日期传override也拒绝错用。普通日只作operational_regular_schedule，不声称已穷举所有临时公告。

## 新tiny与冻结

[唯一tiny组](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage353_regular_sessions.py)先RED（函数缺失），后GREEN1/0.002秒，py_compile exit0；无旧suite。子例覆盖Friday→Monday、25h、D21锚20日、day-only债15:15、缺省/缺receipt/缺day/模板冲突、未知到期、最后日override及退市后不展开。文字预期独立手核，没mock数学或真实metadata。

| 文件 | bytes | SHA256 |
|---|---:|---|
| stage353_regular_sessions.py | 6387 | `5ef528aa1265e9737a55e41601cb349664574436f712115267a2e39ecd71b650` |
| test_stage353_regular_sessions.py | 3812 | `11147188c465637fefb19477c5cc1a38da3ce3c9ea22cf2ace5afb41995fe508` |
| [source_bundle.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage353_regular_sessions/implementation/source_bundle.json) | 1446 | `1c659aac2dce354802d4cd3de6afd6653cfc4d04f8ba939adae511f07a9ed6bc` |
| [fixture_terminal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage353_regular_sessions/implementation/fixture_terminal.json) | 729 | `47f4c28a9a1393bc2994a6499e5f2439365e6dae7c859fa2f2fbb58f4c0a1afc` |

已直接交root/349独审，不要求复跑tiny。后续root按选约前726依赖域汇总max session_end/min Dopen，不能只取最终两赢家；本函数不做汇总或实际授权。source_completed_at应由接受后的确认session_end另行赋值，实收时间始终独立。

开始/结束反思：本次不新增收益调参，既有历史选择偏差仍在；纯展开及缺失不猜有继续价值，不增加生产资格或AI优势结论。沿350官方/Tq及作者源码判断，无新调研必要；金融指标N/A、累计fit/cash不变，完整用户目标未达。
