# Stage589 必要上界probe实现就绪（尚未actual）

- line_id：`futures_full_market_long_signal_ai`
- 时间：2026-10-21 07:10 CST
- 性质：按root592v2冻结实现，非策略引擎、非新回测；非重要突破。
- 冻结协议SHA：`6f7dbff2b321af3953c38ad05e1544338480e3bdaeacb82112453c978ab2ec20`。v1无actual；v2纠正primary窗口必须保留2023后新cutoff的完整域。

## 实现与输入边界

新增`tools/stage589_winner_addition_preflight.py`与一个小fixture。import没有读取输入或调用旧金融入口；actual由root使用唯一CLI启动，本agent没有启动。

只从已绑定042/070/156原源码AST提取纯函数与原常量，沿原organize、family winner、unit_estimate、fee/adverse quote及cutoff_for，先原winner后held sameepoch相交。namespace使用原numpy/pandas/Decimal语义，不重写成本或选月。source hash也绑定131/157。数值与缺失状态只影响必要上界和unknown，绝不写A账户。

actual数据白名单为157signals一次、经济投影一次、4A各daily/positions一次；每项同一raw buffer做SHA/解析。免fills、reservations数据、129、COMMON52、native缓存、行情、SQL、fit与cash。四summary与小manifest/source只作身份及unknown披露。输出fresh目录，保留start/attempt、失败terminal与输入读取receipt；拒绝已存在目录。

精确公式、margin-only分母、按比例entry_fee、不重复减滑点及batch-neutral前置剔除合同沿592v2。本probe忽略普通单竞争和旧仓shared capacity，不消费reserve，不评估D价格；正上界不是联合可分配数或成交。0手/拒绝且全域无相关unknown时，结论也仅在原accepted模型路径及batch-neutral前提下成立，原A执行/PITunknown不洗白。

## 关键合成fixture

5项通过，exit0；没有实际输入行读取。

1. 只以buffered margin作分母；错误m+fee会把本应可能的一手错判0。
2. 剩余数量原入场费及SELL费用，无双重slip；合成净浮盈172。
3. 原家族winner先选，不能先筛held epoch救次优。
4. primary保留2020/2023两模型时期，cold2023按日期窗自然只含2023；末日不prepare。
5. 原纯定义驱动合成账户，positive/zero/unknown三态互不混淆，原unknown保留。

首次红测为缺实现的预期失败；实现后fixture暴露AST缺原`MARGIN_BUFFER`常量，已按原源码加入，未改成本公式；最终5/5通过。未扩旧suite或扫描数据。

## 输出与下一步

source_ready：`outputs/stage589_winner_addition_preflight/source_ready.json`，包含源码/fixture SHA与root唯一CLI。实际将生成candidate_bounds、support_summary、读取receipt/terminal/manifest；summary按year/月/family分解正/零/unknown，并披露max/sum upper数量，**跨日求和不是实际可加仓手数**。没有CI、新收益或现金指标。

- source SHA：`54b120d1199f921b2788cabb6530a74292453867ffbb1990e5e1a8a4aff32a97`
- fixture SHA：`c3942e247924d4a594486f4cff313b81cd790e9451f978a8d188ccbed95017b8`
- 新fit/cash/A replay/SQL/GET：全部0；累计547fit/282cash及1旧partial。
- 新参数：无策略参数；只有协议/source SHA和fresh输出CLI绑定。
- 新权益/收益/DD/Sharpe/滑点/交易数/胜率：均N/A。
- 调研判断：沿589设计中已核vn.py维护源码及579原Turtle发布资料，preflight只判可行性，不以开源故事证明alpha。
- 过拟合前/后：本轮没有拟合/阈值扫描，不新增参数拟合；反复同历史筛机制的选择风险仍保留。
- 继续价值前/后：有，仅此一次必要上界支持测量；正值后仍需另冻cash合同，零且无未知可省现金重放。
- 等root593源码审与唯一actual，不改LINE/registry、Git或正式C9。
