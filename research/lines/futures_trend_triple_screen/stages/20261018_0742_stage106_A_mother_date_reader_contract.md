# Stage106：A独立母链审计的真实日期类型适配合同

- 2026-10-18 07:42 CST，root，line_id futures_trend_triple_screen；仅后处理正确性，非alpha。
- 105真实095审计exit1，前序完整现金/库存/成本/指标/来源已过，母链标量块因raw usage.signal_date为pd.Timestamp而CSV candidate.date为ISO字符串导致同日不相等；首笔BACKTESTING.1 rb2005.SHFE真实2020-01-08普通flat已对应opened候选。冻结原095/105失败不改，不能重跑A金融。
- 授权095原作者只新增独立stage106 reader adapter：导入冻结原095、保存原a_mothers，仅在调用原母链函数之前复制t并规范化其signal_date。仅接受严格YYYY-MM-DD字符串或naive且等于normalize的pd.Timestamp；非午夜/带时区/非法类型拒绝，不截断遮掩错误时钟。候选/rollover日期另核为严格ISO日，其他母链、成本、现金、数量、retry/换月数学全文复用，禁止放宽真实plan匹配。
- 审计输出改到唯一新stage106审核目录，保留原095 run_id failure，不覆盖任何失败。新receipt必须绑定原095、适配器、105实际失败和104root completion，并明确金融重放0；账户raw/seal/summary/context及actual terminal不改。
- 单一新增有限日期行为验证：真实首笔对象先RED不能匹配，再GREEN同日匹配，并验证非午夜/有时区拒绝；不跑旧suite或完整金融。另一agent对适配范围、原数学不变、拒绝条件和失败谱系作一次定向独立复核后，才以原104同一completion做一次新的完整独立审计（只读sealed账户）。不得因新审计目录改变金融attempt计数。
- 此母标签读取问题不影响已过现金和成本段，真实交易并非缺少计划。root允许B在该独立后处理并行完成时启动，继承102真实readiness及冻结金融源，不为审计reader修改现有金融闭包；若定位出现真实价格、仓位、资金错误则停止新金融决定并先报告。
- 新增/修改/删除alpha参数及金融结果0，当前A终态待完整独立接受，母胜率N/A；全研究10金融attempt/3accepted、训练0。开始/结束新增过拟合否，修日期可比性；继续有价值是，完整母链核对不可省，但不需要再跑策略。目标active、production_qualified=false。

## 实施前同义边界澄清

原作者静态核对发现原095后置roll lineage同样比较t.signal_date与CSV字符串；只在a_mothers局部copy会遗漏同一个reader缺陷。root改为**唯一raw_exports返回边界**适配：先完整调用冻结原raw_exports做raw↔导出/身份核验，接收返回的trades、usage、clock、hashes、identity，再只copy usage并严格规范其signal_date为ISO日后返回；不修改原payload/原usage对象/clock/任何数值。095原audit后续merge、a_mothers及roll/retry全部算术全文不改，A/B均共享该日期字段语义。禁止另写a_mothers补丁或并行多处日期替换。原严格午夜/naive/字符串拒绝规则保持。此为同一P1的完整reader边界定位，不增alpha、金融或审计重跑次数；106测试须覆盖下游两个同日join使用同一规范列。
