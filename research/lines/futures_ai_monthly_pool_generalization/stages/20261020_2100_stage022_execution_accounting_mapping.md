# Stage022 日级执行与财务合同映射

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:00 CST；day。
- 只读源码映射，机制进展，非重要收益突破；研究源 halfR/retry=False、C2=True，正式未改。

## 发现与变更

新增 outputs/stage022_execution_accounting/ 下 README.md、contract.json、bindings.json；未改任何引擎/策略/配置。当前及冻结 m0008 实际 MRO 均确认：普通 stop 只比较当日 close，临时 exit_price=close；动态 stop 先读取已完成日 H/L/C，但不回看 low/high 触发。实际 Stage847 引擎继承的 Stage502 new_bars 先 fill delayed orders 再 on_bars，因此普通日终退出、partial、roll 两腿均是下一 session opening actual fill。execution_price_override 只进 order.price，不覆盖 delayed engine 的 opening fill。

临时关闭先写 provisional realized、outcome/streak 和 pending lot；actual CLOSE 再 FIFO 校正 realized 差额，未回改已写 outcome/streak。新固定 R 源应按 actual tape 独立 MTM，不能直接用临时 close 事件收益。roll 旧平/新开分别计 actual fills 和费用，不把跨合约价差当 PNL。

当前 Stage827 canonical session anchor、signal-to-layer 同步、chronological synthetic queue、physical/trading date 分离以及内部权益边界均与冻结版有差异；仅日信号 AST 相同不能证明财务源一致。完整映射、公式、边界和源码 SHA 见 outputs/stage022_execution_accounting/README.md、contract.json、bindings.json。

## 调研和校验

已查阅 vn.py 官方 GitHub upstream backtesting.py，外部只支持 actual tape accounting 思路，本地已安装字节与显式 override 才是合同证据。20 文件绑定、84 方法记录、5 静态断言通过；无 import/金融回放。没有参数新增/修改/删除，没有回测结果新增/修改/删除。权益、收益、回撤、Sharpe、总滑点、交易次数、胜率全部 N/A。金融回测/模型 fit/净 60 日标签/下载/订单/生产修改均 0。

## 下一步与反思

建议先实现隔离单位 R、新身份的 pending-order + actual-tape 日级执行合同，普通 exit=下一 session open；保留 C2 未知路径，明确 60 日末 MTM 与 D61 平仓目标的差别。历史 PIT 费用/合约参数、全市场 session/open anchors、18 个 C2 双触未知和完整层/partial/roll 实现仍是门槛。不得用缺失分钟关闭 C2，不得只留已知品种后重排标签。

开始/结束新增收益选参过拟合：否，只有源码因果与时钟核查，无金融表现选参；继续价值：是，纠正日终决策/次 session actual fill 时钟是可靠训练源前置。没有证明 alpha 改善。
