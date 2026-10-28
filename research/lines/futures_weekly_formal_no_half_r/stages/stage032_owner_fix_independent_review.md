# Stage032 owner V2 修复限域独立复核

- line_id：futures_weekly_formal_no_half_r；时间：2026-10-28T17:15:37.265047+08:00。
- 结论：**PASS_OWNER_FIX_BOUNDED_A_C_ATTEMPT002_REPLAY，允许新建 A/C attempt002 金融回放**。本次范围内剩余 P0=0、P1=0、P2=0。不是C002结果通过，不重新接纳C001。
- 最终adapter SHA：`e601f44f1412df7945497b1d360f44baa7d76ec699c698dd3bcba485f0f91974`；测试SHA：`1e6b3542cfaeb93ea983d97f9517d7011e5152a219cc6f273ff25339182c6ce2`。
- 仅审本次owner差异；未重跑数据/预算/整线406项审查，未金融回放、未改实现/数据、未下载行情或操作生产。主代理报告406项回归通过，该结果不冒充本审查者重跑。

## 旧结论边界与根因

原560232fc版本虽通过预审，真实C001结果已被新独立结果审查与报告拒绝。此前仅核每个fill分片数量相加、若干干净库存微型场景，没有覆盖“尚未成交的计划仓被安全减量后留下旧close队列”的完整生命周期，因此不能发现底仓越界与漏平addon。原预审、原源码和C001保持原样保存，不能覆盖历史失败。

差异核验：新增库存只在真实open fill之后建立，保存symbol、方向、真实成本、sleeve/addon和inventory_id。close意图只预约已成交且未预约余量，不扣实际数量；真实close才扣库存/预约。未成交plan和重复预约仍按原调用进入父队列，但不污染新增owner队列。每fill验证owner净量等于实际pos、预约量与队列一致；末审从零重建全部allocations并核成本、真实净仓与剩余addon状态。原父队列/资金/风控未被此修复改写。

## 直接读取 C001 原始序列的独立重放

本处是有限callback手算夹具，未运行历史策略。读取原trades.csv与trade_events.csv的日期、数量、价格、trade_id与计划平仓，逐fill独立累计owner净库存，要求任何owner都不能为负且总和等于真实pos。

| 合约 | 未成交旧计划close | 真实成交序列 | V2归属结果 |
| --- | ---: | --- | --- |
| FG401 | 22 | base10@1731、addon1@1898、实际全平11@1853 | base10、addon1，各真实成本正确；最终空库存 |
| SM505 | 28 | base27@6870、addon1@7354、止损平1@6592、base平27@6426 | 先addon1再base27；最终空库存 |
| cu2509 | 4 | base2@79060、addon1@79640、换月平3@79580 | addon1＋base2；最终空库存 |

逐合约单独将原C001 allocation送入新审计，分别明确拒绝BACKTESTING.315、424、489的base overclose，避免第一个异常掩盖后两个。

其他关键检查：

- 同一实际base2重复预约两次：新增owner只预约2，实际库存仍2，原父队列仍保留4；不会静默改原父会计。
- 选取正常strict-close-stop、roll继承、forced addon优先平仓三个现有hook回归，均通过；未重跑作者34项全集。
- 对完整已平序列篡改close entry_price，新审计拒绝成本不一致；故意留下pending_close孤儿addon，新审计拒绝末状态不一致。
- A关闭模块时，update_trade、queue、close、reduce、roll五个回调代码对象与原Stage029包装完全一致，且没有新owner库存。A001/A002的实际成交与权益完整等价仍须新回放验证。
- 原C001 trades、trade_events、allocations三文件前后SHA一致；具体SHA和修复后逐笔分配见独有outputs/stage032_preflight_review/owner_v2/independent_checks.json。

## 放行边界、调研及反思

本次仅解除owner修复的回放前阻断。普通父pending_close_lots的原有计划会计行为保持不变，不宣称本次修复了整个父框架；C002必须由新的独立结果agent全审实际fills、归属、成本、末状态与账户会计，并强制A001/A002等价。禁止修旧CSV、抹除失败或以预审代替金融结果审查。

复核官方vn.py组合模板与本机冻结实现后，采用“成交回调改变真实pos，计划只是意图”的原则；仅净仓或总量守恒不足以证明sleeve归属正确。来源：https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py 。

新增/修改/删除策略参数：无；新增/修改/删除有效金融回测结果：无，C001仍拒绝。期末权益、收益、回撤、Sharpe、滑点、交易次数与胜率在本限域复核中不重新发布。是否重要突破：否，正确性修复不是alpha突破。

开始/结束过拟合判断：本次没有调参，修复由真实库存反例驱动，不属于收益救参；策略仍有历史样本内开发风险。继续价值：有，按原固定规则做一次新attempt并独立审查有价值；若新结果失败必须保留，不扫参数、不晋级。
