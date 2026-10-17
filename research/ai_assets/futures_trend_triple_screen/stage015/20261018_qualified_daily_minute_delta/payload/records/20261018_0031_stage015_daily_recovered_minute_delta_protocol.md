# Stage015 新恢复日线与首批provider分钟的必要增量资格合同

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 00:31 CST。
- 性质：数据资格增量，非金融回放。Stage014仅是三冲突消费诊断，不与本阶段编号混用。
- 前提：Stage013目前仍是已确认存活的单次连接（exec72442），不可重启；本工具可先测试，必须等其终端receipt及独立数据复审后才真实构建。

## 固定范围

1. 输入仅Stage011 remaining中获Stage013独立合格日线的精确symbol/date，加Stage012已独立验收的11个session/2475分钟；原Stage011全部完成需求不重做。16carry和3base冲突不被新日线自动放行。
2. 既有数据为原base＋Stage002 overlay＋已独立通过的Stage011 overlay；全保持原SHA、原值。读取可按相关合约/日期过滤，不构造无关全市场清洗；原13,752合格session不重复全聚合。
3. Stage013恢复日线的资格必须来自parent输入未变/worker及逐目标六字段与完成证据、独立receipt。closeOI是新provider字段，不是DB字段。把这份新日线作为完整七字段参考，允许同一session的原base/002/011及各已声明completed来源一致拼接；复用Stage011资格核心，不改旧阶段脚本或receipt。
4. 只对新增获参考的94合约相关session重验，缺恢复行/被拒绝日线的目标仍保留原缺口；新来源指纹在构建前后固定。Stage012 raw需绑定其独立receipt与精确输入SHA，不能把其范围扩至别的日期。
5. 同key任一真实冲突整session隔离，不能覆盖旧值。新append-only overlay唯一且与全部既有key disjoint，另核A0实际读集合交集0。原Stage014三冲突继续诊断，不能用其open相同或新日线匹配擅改H/L/C。
6. 合并readiness只修改本阶段实际重验的key，保留Stage011未受影响的ready结果；full和anchor分别判定。输出新overlay/source/session/remaining/summary，给出新增、仍缺和原因，原011结果不覆盖。

## 质量与下一步

少量新增测试只覆盖新日线参考只认独立qualified目标、参考缺失保持缺口、跨原数据拼接不覆盖冲突；复用已有聚合测试而不复制全部实现。唯一真实构建后独立agent检查新源与有界样本、readiness和A0交集，不全量重洗旧数据。

本阶段不授权C0新attempt、daily-open fallback、alpha修改或生产。全部金融指标N/A，金融attempt仍4/完成1。过拟合判断：否，仅补全同一固定研究的必要数据；继续价值：是，把日线恢复立即转为可用分钟覆盖，尽快取得真实候选回测，而非停在下载文件数量。
