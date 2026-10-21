# Stage130：共享评分与初开月选择实现

时间：2026-10-18 21:39 CST；非突破，仅实现；从Stage128固定合同开发，不因新收益修改。

新增`stage130_contract_choice_fit.py`及9个纯合成边界fixture，沿071纯统计/写出/Ridge工具。两cutoff×main/held0/held1仅6个52槽模型，A/B同模型；逐exact product内A仅canonical、B所有u合格月最高正分，随后共同普通优先/F次序竞争单family。完整parent与全部child预测分开输出，不按未来closed过滤。

训练仅自身成熟且u可行动；family-u多动作持有区间先union，同family跨u计算concurrency/uniqueness，组质量均分动作后等u总量。保存训练身份/组区间/权重、scaler、模型/portable、充分方程和全部预测，无巨量标准化矩阵副本。held诊断按实际事前动作并去family-u重复，相同未知动作增量可识别为0但保留共同未知；不同未知动作不填0。

9个新边界0.065秒通过；最初missing module红以及一处numpy int区间JSON序列化错误保留为实现史，已修复后通过，0真实研究fit/SQL/cash。未运行旧suite；当前新增权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A，累计385/110不变。fixture通过不等于策略有效，真实执行仍需root精确代码/数据绑定，随后132独立全面复审。

开始/结束反思：按本轮收益调参否，重复历史择题风险是；继续价值是，仅固定一次假说检验，尚无加注/正式资格。调研判断沿127RBA/德银/LEAN，月份选择是独立动作但无国内窄损盈利保证。实现收据：outputs/stage130_contract_choice_fit/implementation_receipt.json。
