# Stage577 开盘执行价格上限单次研究协议

- 时间：2026-10-21 06:08 CST；line_id=futures_full_market_long_signal_ai；day；分支codex/ai-training-data-expansion。
- 性质：现有现金入口的有界执行干预，用户已授权自主设计持续研究；非重要突破。独立于正式C9月池，不创建正式A/B/C或生产发布。
- 协议：research/lines/futures_full_market_long_signal_ai/outputs/stage577_open_execution_cap_protocol/protocol.json，SHA69b39cd7d330d267d73bd30a8479f05eac4dc6376687d125f69bcda5dc8ff48e。

## 调研与机制判断

先读registry/已关闭谱系，574/576独立条件GO。参考[原作者Foucault限价选择与不成交/赢家诅咒机制](https://www.sciencedirect.com/science/article/pii/S1386418198000123)及[vn.py维护者撮合源码](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)。资料不证明中国期货‘不追高’有效；官方bar limit规则用D.low会引入全天等待，不适用于本试验。本规则不是015突破等待、079预算筛除或299历史reopening因子，零价差仍是主观结构选择，不是无参数/无过拟合豁免。

## 单项变更

A复用157自身四账，不用其baseline_books旧131对照。C沿原130/156固定u信号/选月，D按原execution_quantity生成含不利滑点与tick舍入的BUY.fill_price；原qty>0且报价有效后，只加fill<=同选中epoch intent.u_close价格上限，超过则当日取消。不是裸open比较，手续费仍按原费率另计。通过者按原价执行，不clip到cap、不等盘中D.low、不改单笔SL0/rawF/20low/K；无tick/minute下载，无新模型/目标。

Dunknown和原qty0/其他拒绝先保留；未知不当作已知取消/零收益。只可用u既知close及D开盘研究报价，不能看Dhigh/low/close或后续盈亏决定。实际open+不利slip是条件研究报价模型，不是先看真实BBO还能按同拍成交的认证。

同D不重选其他月份/品种或重分取消额度，不使用D卖出释放余额。以后C按自己权益/占仓自然prepare，不能复制A未来数值预算。base/stress因滑点不同可通过不同集合，压力差含参与变化。

## 固定预算、指标和否决

0fit；最多4新cash：2020-01-01—2026-10-16、2023-01-01冷启动—2026-10-16，各base/stress。本金100万、0.25N、单family风险0.25%、总2%、缓冲保证金25%/1.10、成交量参与1%，其余原157参数不改。只读既有583263B固定信号、原母表必要列、110MB native cache和小经济projection；不读334MB动作/全分数/COMMON或重放A。

事前门：四C自身正收益/财富正，2020stress收益严格高于A且最大DD严格浅于A，其余3不低收益/不深DD；primary使用原157固定252源日circular indices/2000draw配对日log增长95%下界>0；披露全部4CI。各年度、实际交易/胜率/费用滑点、拒绝/价格取消、错过机会与后续账户路径、未知/历史stale均保留，不能只报省费用或被取消亏损者。未知阻止无条件/真实执行资格。

任一经济门失败即关闭这个固定价上限，不改裸open/反符号、close±ATR、窗口、产品、止损或风险救参；没有自动晋级/加注或完整goal完成。575先最小隔离kernel+guard和必要小行为测试，576定向源核后root唯一实际，终态后独立全面现金复核。

## 当前结果与前后反思

本冻结阶段新增fit/cash/SQL/下载0；所有财务指标N/A。累计535fit/278完成cash及1旧partial。开始新增收益后寻参：否，同史自适应择题过拟合风险：是；继续一次固定不同执行干预有条件价值：是。结束仍仅收益前协议，结果未知；完整98/95高质量long/更高收益低回撤/窄损加注目标active。LINE/registry待最终root结论统一更新，普通阶段不追加根memory/back_log。
