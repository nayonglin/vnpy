# Stage048：实际多品种/物理旧键的通用provider交付reader

- line_id：futures_trend_triple_screen；时间：2026-10-18T04:29:48.152337+08:00；非重要策略突破，不改alpha。
- 当前B同一进程已通过11个实际wait（前2+batch001交付9），batch001因045单target边界正常拒绝2020-01-23的2品种联合anchor；不是金融失败。新047/048一次对齐原021原生多symbol和物理旧键语义，旧039/041/043/044/045/046均保持immutable。
- 继承043独立完整reader的精确request/raw/proof/actual terminal/单attempt/七值/日线/完整packet/Stage021 parse算法。新048仅显式选择固定037或041 provider及其sourceSHA（同一request packet不能混family），独立输出/本协议绑定，并按request physical existing集合筛新增键给A0隔离检查。
- 所有required数据仍须完整合法已完成，full校全日七值、anchor只验合法首分钟/真实完成/日线open与已知openOI；existing/missing都必须唯一且属于required。新keys=required-existing；A0只对真实新增keys要求交集0。
- reader不假装已经独立重载原engine巨大cache逐值比较旧键。实际原021.ensure SHA150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b在所有symbol commit前对重叠七值np.array_equal，冲突则拒绝，最后只append缺失key；此强制runtime保护保持不变。receipt只证明交付数据正确与新增键隔离，旧键字节保护由真实调用该冻结gate证实。不得手改mapping/覆盖原行情。
- 所有原CSV/DB/原raw只读，正常SDK/端点/鉴权不变；root explicit固定source/reader后才调用，真实子进程terminal才可以签。source进入B inputs后immutable；无网络、金融、模型、pointer写入。
- 验证：限定源码差异、双provider作用域拒绝混用/未知目录、真实新旧物理key筛分（包括全部旧键）、core合法值函数AST继承，后续真正actualrequest解析和完整金融038另审；不重跑旧suite。
- 策略参数与金融结果新增/修改/删除0；权益/收益/回撤/Sharpe/滑点/交易数/胜率=N/A。新增过拟合否（只执行固定策略数据合同），继续价值是（补齐已遇联合请求并沿用原gate常规旧键保护），总体目标active、production_qualified=false。
