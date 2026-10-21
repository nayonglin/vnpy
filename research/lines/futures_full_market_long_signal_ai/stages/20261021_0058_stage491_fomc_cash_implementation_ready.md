# Stage491：FOMC 两臂现金账实现准备（未实际运行）

- 时间：2026-10-21 00:58，北京时间。
- 研究线：`futures_full_market_long_signal_ai`；非重要突破版本；只写本阶段新文件，不改 LINE/registry。
- 开始/结束过拟合反思：本次为已冻结487的执行适配，无参数搜索；长历史反复迭代的适应性过拟合风险仍高，不能把接通接口当作有效 alpha。
- 开始/结束价值反思：有条件继续。只允许一次预冻结 FOMC 宏观包残差增量反证，与基准真实账本比较，失败后不扫描窗口或加杠杆挽救。

## 改动与不变量

新增两个外部研究臂 B_PRE_LIQUIDITY/C_PRE_LIQUIDITY_FOMC；内部临时使用原157 VOLUNTARY_RESELECT schema，再保留清晰外部身份。不修改旧模块 ARMS、风险、资金、费用、滑点、锚定合约、D开盘规则、容量或生命周期。参数继承100万元/0.25N止损/单family0.25%/总风险2%/缓冲保证金25%/margin buffer1.1/1%参与率；新增参数0、修改原策略参数0、删除参数0。

只读489新派生161014母体七字段、两份完整main choices、共享966740行16字段因果action一次；在内存筛选两臂selected union。既不重读129 mother/action/COMMON，也不使用旧157选中合约作为入场域。全部潜在forward scored epoch必须有155同源完整日历K，D<K由原157再次检查。

A严格为157自身四个账本，不使用157 baseline_references所指的131B；只读其summary/daily/diagnostics及root明确授权的一次全family年贡献。B/C各4账（2020连续/2023冷启×base/stress），最多8新账；native cache最多restore一次，SQL0、fit0、旧A回放0。每一实际完整raw book先做独立checkpoint，8账全部完成后才导出报告；任何失败保留原目录和计数，不自动重试kernel。

C-B和C-A同时接受原157严格经济门槛：primary2020 stress收益严格增加、DD严格变浅、原070 paired252日/2000次CI下端>0；其他3窗自身收益正、相对收益/DD不反向。两组held未知差异不填0。B-A只披露。所有财务指标、12配对比较、完整95family年贡献含零值、费用/滑点/胜率、unknown/stale均输出；截至2025只截同一连续账的日权益，不新开账/重置资金。

## 调研与验证

继承487已完成的官方BoE1114和作者代码调研：公告前流动性可作为异质暴露候选，但海外19商品证据不能直接认证中国全市场可交易alpha；raw FF4正号亦不解释为经济紧缩。491只实现已冻结数值包比较，无额外网络请求。

4项新synthetic边界覆盖完整母身份/新epoch、共享因果action union含资格0、C-B/C-A双严格gate与held未知/2025同账截面、8账checkpoint和报告/第3个kernel失败后禁止自动重跑。先观察4项缺实现断言失败，再实现至4通过；扩充2025 helper时观察缺函数错误后实现，最终4通过，用时0.031秒。没有运行旧测试套件；缺实现红灯不冒充行为级bug证明。

本阶段actual0、fit0、真实现金账0、cache restore0、SQL0、真实行情/旧账/489大输出读取0。合成测试中的8次/3次回调仅返回字典，不调用实际现金kernel。源码和测试/protocol的确切绑定及授权schema见 `outputs/stage491_fomc_cash/implementation_binding.json`。

期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A（未实际回测）；新增/修改/删除回测结果均0。

## 后续

等待root对精确源码与489完成handoff作预审并精确签发唯一actual授权；491不得自行启动实际。真实结果后由独立agent复核，任何结论仍不认证历史first-seen/PIT、因果识别、生产或加大投注。
