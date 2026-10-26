# Stage029 运行前独立审查

- 结论：**PASS_PREFLIGHT_OFFLINE_RESEARCH_WITH_DECLARED_LIMITATIONS**；P0=0、P1=0、P2=0。允许执行已冻结的离线回放；本记录不认证金融结果，不构成生产资格。
- 独立审查员：stage029_exit_design_review；本人金融回放0、下载0、策略/数据修改0。仅新增本审查MD/JSON。

## 代码与行为

已逐段审查 adapter、测试和 runner；SHA 见同名 JSON。26项行为测试由审查员独立重跑全部通过。额外将实际 Stage847/804 MRO 与无IO Harness 组合，确认多头更紧初始止损仍通过父级规则以周OHLC计算（手算90），空头周止损手算110；每日账户风险、保证金、换月和手数计算方法保持继承身份。

初始止损取本合约最近接受完成周，周中换月保留当日计划close用于资金/保证金定量，错误方向stop报错、不修价。动态极值/最大浮盈/阶梯锁盈/ATR midpoint取新完成周OHLC；prev2、层止损和内联MA止损全部通过fresh及请求日期门，仍为周close确认，不引入周内穿价。prev2按入场后已接受完成周计龄，当前inner.count限制epoch范围，已平重置状态不恢复旧日龄。RSI关闭、short_case2拒新开、long_case2保留；加仓/反手/排列退出关闭、target-only换月历史硬锁。无layers持仓重建的daily-stop兜底计数非0则拒验。

runner 的Q保留原行为，R显式RSI=False和新factory；actual setting/effective spec严格对照N002，只规范声明的mapping路径及R的RSI开关。原19/15万/maxpos19、源SHA、真实SQLite绑定、无AI/分钟/代理、物理epoch、持仓/成交正量日K、严格次交易日同约open、完整日历和finally输入复验保留。通过回放后仍需独立金融审查。

## 增量数据独立复验

审查员独立重算2538个来源文件SHA，变化/缺失0。旧392080条接受行逐字段不变；新33条为10/26的28条及cu2612在10/19—23的5条。每条新增与原Tq CSV的真实合约名、duration86400、OHLC/V/closeOI、原SHA和id/纳秒时间定位完全相等；新CSV尾部与新增表完全一致。

旧SQLite 1345640行全部保留，新库1345673行，33条新增六字段逐条相等；metadata和physical_epochs文件字节不变，旧mapping/physical日表字节前缀保留。当日19个main均有真实正量记录。最新完成周仍为10/19—23，10/26所在未完成周未被接受。精确SHA见同名JSON。

## 边界与后续

实现者的本线测试receipt为256通过；审查员独立重跑本轮26项。全仓1652项receipt仍有5 failures/45 errors，本审查未逐一重诊所有原因，不宣称全仓通过，也不将该结果当生产就绪证据。

Stage028的源冲突/独立证据不足、有效观察周可跳自然周、历史主力完整真实性和PIT未证继续保留；新增Tq精确原值不等于多源共识。零手续费、静态保证金/规格、日open容量和样本内反复使用仍限制结论。回放中任何guard失败必须保留失败attempt，不得把截断成绩当全窗结果或修价救参。

开始与结束反思：没有新增拟合、阈值扫描或择源救参，三项用户指定变更为一个固定结构候选；同窗反复比较风险仍在。继续有价值，允许一次冻结证伪，不表示晋级或继续参数扫描。
