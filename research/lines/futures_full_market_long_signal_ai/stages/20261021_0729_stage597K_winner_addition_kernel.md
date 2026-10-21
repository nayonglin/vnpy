# Stage597K：原额度内赢家独立批次执行内核

- 时间：2026-10-21 07:29（Asia/Shanghai）；研究线 `futures_full_market_long_signal_ai`。
- 重要突破：否。本阶段仅完成已冻结596协议的隔离实现，没有历史收益证据。
- 版本：复制131现金时序于独立597内核；复用原070/042纯成本、账本与风险函数，旧源未改。每次新增BUY独立root，保留该批原始SL0/F0/basis；既有批次F0不释放。
- 开盘时序：先旧批开盘已知退出/减仓，再冻结的开盘订单，再所有批次日内止损，最后收盘估值与次日边界。开盘任何同家族SELL（包括部分）取消add；日内D.low不会追溯取消已执行开盘BUY。缺失旧bar只增加一次stale天数。
- 预算：fresh原实数target与add家族剩额target一起使用原缩放。add预批零手先剔除；缩放、容量截断后不重分。共同容量含旧同epoch剩余SELLreserve和新批往返2q，不硬截风险SELL；未知与超额保留。
- 新增参数：无；修改/删除策略参数：无。仅增加 `entry_kind`、`parent_root_ids`、`add_audit`、`add_root_ids` 诊断字段。
- 新增回测结果：N/A；修改/删除历史回测结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A（未跑历史）。
- 必要新合成验证：先8项RED（空实现），实现后7过1失败源于fixture剩余qty8却initial_qty5；修正fixture为真实可行仓位后8/8 GREEN。覆盖无合格add与131经济等价、净剩余手续费、旧F0不释放、add零手预剔除、共享容量、旧批日内止损不取消开盘add、开盘SELL取消、独立SL0/F0。
- 调研判断：沿已完成591/595的原Turtle与维护vn.py资料，仅取独立批次执行结构，不引入整套Turtle参数。新增机制可被固定4账本证伪，当前值得做一次冻结验证；不依据合成结果宣称盈利。
- 过拟合反思：当前否，机制和参数在历史actual前冻结、无窗口/品种/盈利阈值寻优；历史验证若失败不凭尾部调参挽救。
- 后续：交598一次独立源码审查，runner由548绑定；root唯一历史actual。本阶段0fit/0cash/0SQL/0下载/0旧A回放；累计仍547fit/282完成cash及1旧partial。未修改LINE/registry或正式策略。

内核SHA：`9b9ca580d3d5ffb9271b5af86dd82779ee03bbfe67dea8b507dc20b3308a1209`；合成fixture SHA：`c93934978a26aa88910b48ac4da9668a246c624d87f1f0d479631d2a2358c891`。
Receipt：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage597_winner_addition_cash/kernel_fixture_receipt.json`。

## 2026-10-21 07:30 收益前源码审修正（v2）

598和root查出实际合约与canonical anchor原本允许不同；v1额外相等gate不属596，现只删除此gate，原anchor字段/anchor_request/parent force/expiry不动。现有8合成用例统一改为actual epoch与canonical anchor不同而canonical refs稳定，全部8/8通过；没有新增fixture/旧suite或历史actual。按receiving-code-review核对原131的anchor_request后确认此修复是执行合同纠错，不是经济结果调参。旧源码、fixture和receipt完整保存在 `outputs/stage597_winner_addition_cash/kernel_source_v1/`。

当前内核SHA：`66229dccd949f7721f61ed9af029ae7296cc0c4e9ca667d513a384665a64e6bc`；当前fixture SHA：`d78b418a3b3cba25d708fb20986c47beb7a37394d84b0797f970f23ca5602e55`。本阶段仍0fit/0cash/0SQL/0下载。
