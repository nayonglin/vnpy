# Stage011 仅必要key的本机完成分钟批量验收合同

- line_id：futures_trend_triple_screen；冻结时间：2026-10-18 00:05 CST。
- 性质：Stage010需求的本地数据准备，金融回放/下载/训练/策略修改均为0。

## 调研与范围

复用Stage004本机来源索引、Stage002严格session聚合和Stage008已明确的OI合同。本阶段先处理已声明completed的Stage459/462/461/456当前checkout源，仅限需求涉及的合约；Stage491已全部处理，不把五份工作区同源副本当新数据，不读forming/raw来源。沿用已核TqSdk官方完成K线定义，暂不启动提供商。

## 固定合同

1. 读取Stage010冻结需求（若工具准备时尚未产生，只测试不执行）；当前checkout源文件先测SHA并与Stage004绑定的旧manifest声明一致，否则隔离。每个源只读一次，不扫备份副本。
2. 基线分钟为原base+已验Stage002 overlay；Stage008精确345行按独立receipt加入候选来源。原base/overlay字节不可改，既有key冲突不覆盖；任何新key都必须追加且不重复。
3. 只验需求对应session；即使需求仅anchor，也优先完整session核验后只追加被验完成分钟。要求正确时区/夜盘网格、唯一合法OHLCV/OI、原CSV日线OHLCV+首openOI+尾closeOI七字段匹配。缺CSV或来源语义不明单列不合格；不把所有DB来源泛化成已知openOI。CSV和已知数据库口径不被混用。
4. 多个完成源合并同一session时逐key一致才拼接，冲突隔离；检查新key与A0全部实际读取key交集，交集0可复用A0，不能重跑已完成基准。保存source/session/quarantine manifest、overlay与缺口变化；下载或下一账户attempt不得由此自动启动。
5. 原完整/部分键不因本次源缺失被删除。保留所有拒绝、不为增加接受率改阈值；本阶段不修孤立旧行情值，不用daily-open fallback。

## 验证与记录

必要测试仅覆盖旧键不覆盖、跨源一致拼接/冲突、缺CSV拒绝及full/anchor需求选择；复用已通过的聚合合同，不重写全部校验器。单次真实构建后由独立agent审新数据、源码和置信度边界。金融指标全部N/A。过拟合判断：否，不看收益改规则；继续价值：是，本机优先可减少提供商调用，结果应直接用于剩余缺口的批量获取。
