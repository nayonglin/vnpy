# Stage311：冻结同批整数预算政策，一次0fit/最多4cash

- 2026-10-20 02:29 CST；line_id `futures_full_market_long_signal_ai`；非重要突破、独立研究，非正式C9 A/B/C，不触发实盘资格或部署。
- 主协议：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage311_joint_integer_budget_protocol/protocol.json`；SHA256 `f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259`。303在OI新结果前提出，310独立设计；两者绑定在协议。
- 当前累计453 fit/246 cash；本阶段0fit/0cash/0SQL/0solver。拟新增0fit、最多4候选cash，旧157控制0重放。

## 唯一问题与冻结边界

固定原COMMON52、同K的4365个完整信号和原score；不使用刚被否决的OI候选、不重算choices、不读334MB actions、不训练。98品种399252母事件域保持，复用既有价格缓存及经济投影。

仅在新账户自身u状态上原统一scale<1、原accepted至少2不同family时，使用310的整数lot线性目标和原单family/总风险/保证金/容量约束；其余行原样。零可行变量仍计入原accepted family。新整数冻结额度会改变D减量/取消，故这是完整分配政策，并非纯score效果，也不是修先到先得bug。

沿310固定δ=1e-6元、资源ceil/上限floor、目标half-even，字典序解并列及同批共享10秒/100000nodes；不可支持或证据失败则整候选终止。正式运行前唯一工程更正：保留options mip_rel_gap=0，但不要求返回relative gap位级等于0，以Python整数重算和绝对bound差[0,.5)为核心，relative gap仅需有限非负且与bound一致。零目标单列处理。该更正在任何实现/求解器/金融结果前冻结，未放宽整数可行性和原预算上限；不承诺未量化数学exact。

实现只私有复制131函数globals替换reserve回调，原源码/模块不修改；313向312明确供应已配置v.kernel。312三组有独立穷举期待值的tiny fixture足够。313只直接载157缓存信号、必要mother identity与价格/经济缓存，四账户完整递归。314独立审数学/数据/账本/置信度及bug，0复跑候选或旧控制。

初资100万；2020连续/2023独立空仓×base/stress，至2026-10-16。两stress均权益严格更高且DD严格更浅才支持探索；base如实报告。完整列费滑、闭合净胜率、开仓未知/stale、family/年份/集中度、u同状态反事实和D削减；固定252块2000次配对log CI不换。失败关闭该固定包，不扫风险/目标/精度/阈值/tie救参。

## 调研与判断

复核[SciPy 1.17官方milp](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.optimize.milp.html)的double接口、整数变量、status、node/time/bound；本机1.17.1不升级。作者[SmartPredictThenOptimize源码说明](https://github.com/paulgrigas/SmartPredictThenOptimize/blob/master/README.md?plain=1)支持预测与决策层需分开验证；本次只冻结预测改算子，判断无需SPO训练或安装新框架。外部材料不能证明本策略alpha。

开始过拟合判断：有同史持续择题风险，无本次金融结果驱动调参；冻结一次可失败机制有价值，不能把利用率当收益。新增策略参数仅分配政策与固定数值规则，原风险/止损/特征参数0修改、0删除；本阶段金融结果均N/A。结束判断不变；目标仍active，先实现/独立静审，再root授权唯一actual，不问用户重复许可。

数值实现释义（02:31 CST，312未跑tiny/actual前确认，不改政策/格网）：r、m、d、score及原cap各自按原float计算，分别Decimal(str(value))；L在Decimal域相乘。资源Decimal(L)*Decimal(str(r或m))/δ后ceil，目标Decimal(L)*Decimal(str(score))*Decimal(str(d))/δ后half-even，不额外先做float乘积。协议的Decimal输入规则按此唯一解释，312 problem audit须明示。
