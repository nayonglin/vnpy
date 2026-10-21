# Stage139 既有88账本归因复用盘点

- line_id：`futures_full_market_long_signal_ai`；先读registry；2026-10-18 23:09 CST。
- 本阶段只读source/schema/小summary；只写本stage。无新代码/参数/回测、actual/SQL/fit/cash/下载；财务结果N/A；累计391fit/202现金不变。LINE/registry/根总账不改。

## 调研判断

查阅[pandas merge](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html)、[read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)及[GitHub官方源码文档](https://github.com/pandas-dev/pandas/blob/main/doc/source/user_guide/io.rst)。窄列gzip、唯一键外连接已足够；空键可相互匹配，连接前须拒绝。无需引入新框架或策略。

## 最小复用法

- Stage136 manifest.accounts给84本显式角色；旧AI4本经其input_bindings.baseline_cash_manifest进入131 artifacts精确取NARROW_B。baseline_books只有summary/daily引用，不含episode绑定。
- 复用133公式，**不import133**，因其顶层mkdir和执行。closed净贡献=net_pnl；open=realized_gross−entry_fees−exit_fees+unrealized；逐本总和须等于ending_equity−initial_capital。slippage已在fill价格内，不再扣。
- 102 diagnostics.compare可独立复用；不调用完整review_account/review_budgets/replay/日仓复核。只对新派生恒等式、BUY和episode字段做有限检查。
- closed/open保留root_id、event_id、mother_event_id、epoch、initial_qty、qty、risk_per_lot、费用/已实现/浮盈、ever_stale、execution_capacity_unknown。fills保留root_id/side/qty/fee/risk_per_lot/reason；budgets保留event_id、budget_kind、D_qty、D_state、budget_state、预算；entryunknown单独保留。

## 字段与身份陷阱

1. 已核042 CashLedger.enter/exit及131 kernel：initial_qty与risk_per_lot在初开写入，部分减仓仅改qty/realized_gross/exit_fees，两终态均保留初值。每root唯一BUY，qty=initial_qty、risk_per_lot相等、fee=entry_fees；可核BUY−SELL量=剩余qty。初开风险资金W=initial_qty×risk_per_lot；不是跳空损失上界，不能用u预算unit_risk_u替代D值。
2. root_id只在账内连接；episode/fill.event_id是子action，130choice.event_id是母。跨政策按mother_event_id，samechosen在同母下核chosen_action_id/epoch，不能仅按月份或root匹配。
3. 131拒绝分支可缺mother/product/epoch；必须经130 B/main/selected的子→母映射补齐。136控制用21持久化signals。131没有signals_B。预算排除existing_position_reduction后含new_entry及空budget_kind早拒绝；rejections是重复子集且含减仓，不concat。
4. 窗口保留start−1预留，至end−1的u；同事前母集合不等于同实际入场集合。空表可缺扩展列；非空关键字段缺失应失败。bool('False')为真，须显式解析布尔。

## 最小精确分解

每peer/window/cost以共同母域外连接为neither/AI_only/peer_only/both；both再分samechosen/differentchosen。前两单边贡献为+net_AI/−net_peer。both设Q=net/W：资金项=(Wa−Wp)(Qa+Qp)/2，单位项=(Qa−Qp)(Wa+Wp)/2；逐母相加精确等于净贡献差。20随机逐peer分解后等权均值，合计须等于AI增长−mean20增长；不是均值log财富或中位账户。Q仅对已入场正W定义，未入场会计贡献0不代表未知回报0。

unknown/stale为可重叠标签，不能作为互斥分桶另加或扣除制造可执行反事实；保留open/closed、入场执行未知与减仓状态。分解是事后恒等式，不证明因果或训练目标有效。

88本closed/open/fills/reservations/capacity/entryunknown绑定压缩合计77.14MB，窄列单读有望90秒内；未测速，不承诺实测。当前不需要actions/nativecache/SQL/旧模型。

开始及结束新增过拟合：否，未按收益改样本或参数；历史择题风险仍有。继续价值：是，一次账本归因能解释单位R与资金错位，但不是新alpha/晋级证据；不继续种子或救参。
