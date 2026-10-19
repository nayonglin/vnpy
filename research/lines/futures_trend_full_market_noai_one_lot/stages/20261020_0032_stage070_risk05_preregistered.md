# Stage070 交易合约周线版0.5%总权益风险：运行前冻结

- 时间：2026-10-20 00:32 CST；line_id：futures_trend_full_market_noai_one_lot；继续codex/full-market-noai-one-lot原研究分支/工作树，不动Desktop另一个任务及其它研究线。
- 用户先误写0.05%，随后明确纠正0.5%=0.005，100万对应每笔5000元；尚未发生任何金融回放，不保留错误比例试验、不扫参数。用户明确选择上一轮交易合约自身周线版，而非其浏览器旧主力周线页。
- 基线N交付commit e553d1703bc4efb9c612143a6c3f2ccc9885f6b3、run_20261019_contract_weekly_long_v1、manifest859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25；100万、2015-01-05—2026-10-16/2862实际日、2014热身，93历史产品六所4328合约epoch。旧N期末1,205,102.81、收益20.5103%、DD-17.6508%、Sharpe0.161625、滑点73,090、手续费23,507.19、3126成交/1558完整、胜率33.3761%、盈亏比2.198598。此为冻结对照，不是本轮新增结果。
- 重要突破：否，固定账户定仓口径研究；不申请或暗示正式晋级。研究-only与此前日线近似/停用C2/C9日内止损重试/缺冻结供需CSV过滤授权继续有效，原生产目录及5项资格凭证缺失边界不变。

## 单一假设、参数与实现边界

用统一的账户风险比例替代按最多1手产生的不等风险暴露；不以收益选择比例。每笔信号预算=当时真实estimated_equity(含浮盈亏)×0.005，手数=floor(预算/原有效止损每手风险)，不足1手不开。旧limited/free balance基数、各riskmode比例、货币min1000/max以及streak/overheat/30d金额倍率被固定预算取代，保留raw诊断，不再将预算变大或变小。native保证金/单品资金/cluster/heat/env/相关/ATR等数量门仍按新预算原顺序执行，只能进一步减量，不从零量复活。仍不加仓、无AI、空头全case、无4品种数帽。

实际开盘要求原合同/产品/方向/信号/初始stop/授权整手数与未成交layer及order一致；预算=min(原信号预算,因果开盘权益扣前序真实成交费用后的0.5%)。总风险=手数×max(abs(open-original_stop)×乘数,tick×乘数,1元)，超额整单拒绝，不变小补单，不扩大授权。stop已穿越/权益无效/授权缺失安全拒绝；此stop预算不保证退出跳空实际亏损上限。所有long含移仓与旧单同时核原信号及开盘前的exact-contract完成周MA5>10>20>40；不足40周、坏周和相等不开多。short/closes不加周门；不因周线转弱强平。

配置新增stage068_risk_fraction=.005；修改max_position_size1→2147483647(纯int技术哨兵，不是经济手数约束)；删除原native参数无，旧货币参数保留但由显式fractional_risk_policy声明不生效。fixed_size0/min1/最大并发93及其它全部native参数与N一致，回放入口逐键白名单校验；共用行情、映射、metadata、期限表、calendar与N必须同hash。

新增068预算/收据/开盘总风险门，075只将059周门的基类与正整手授权匹配改为多手，070隔离回放。实际保证金乘全部order.volume；同产品仍只持一个合约、不以每手挤占产品名额。所有全单至少要冻结bar正量/退出报价多源最小保守量>=整单手数，否则延迟，无盘口/开盘深度/冲击模型认证。

## 数量与账本修复

069修正旧closed_ledger毛PnL未乘volume、整entry被首个partial close出队、每次分平重复全笔费用问题。完整交易按每笔初始OPEN全平后聚合，weighted exit按手数；entry和close现金费用按匹配量分别分摊；残余entry已实现片段另存partial_closes_of_residual_entries.csv，未分摊到平仓episode的入场费已在账户发生，不能再扣一次。多手不能把每手或每次分平当独立胜率样本。

074保留RSI部分平仓；planned reduction已减layer而真实CLOSE未成交时，abs(actual)=remaining layers+pending close，reconcile不能把layer补回；排入新的close只能用actual-pending余量。真实缺bar、重挂、移仓和生命周期仍走原native流程。测试包含原060与最终070各13真实栈场景。没有停用RSI或用合成结算绕过风险。

## 运行前验证及金融门槛

069行为RED：直接隔离执行旧060真实ledger，3手毛利润100而非300、4手空单100而非400、残余partial被误计完整等7项失败及一次旧partial重复平仓异常；新069六项GREEN。最初直接import旧runner因新日期vn.py日志不在沙盒可写根报PermissionError，只是测试导入副作用，改为AST提取旧ledger避免无关引擎导入，未改策略或数据。075旧实现3手长开被拒、bool True被当1手的两项RED，新075三项GREEN。070旧引擎五项行为失败及旧授权字段异常，新070六项真实集成GREEN，另补整单量不足延迟测试。068十五项GREEN，074二十六项GREEN。

首轮root联合测试从stdin启动，275项中两项既有025 ProcessPool测试因macOS spawn找不到< stdin >触发BrokenProcessPool；根因为测试启动器，不是金融或产品逻辑。已改为带main guard的真实临时脚本重跑，保留两份日志；完整最终suite另以标准python -m unittest discover确认。绝不修改025来掩盖。

独立Stage073由未参与068/069/070/074/075实现者预审及随后真实结果复核；074作者不认证自己的独立性。一次完整金融回放须预审无P0/P1且金融回归通过；新唯一输出run_20261020_contract_weekly_risk05_v1，不覆盖任何旧产物。执行资格门：全区间到最新冻结日、预算0违规、long周门0违规、1产品1合约/禁止加仓、部分平仓数量与会计全对账、期限无过期残仓、代码与数据hash不变。会计容差1e-5，风险金额/授权不加容差。失败即保留失败证据并独审，不放宽闸门救收益。

## 固定报告与判断

只做用户指定部署层N→C同区间比较，不冒充对当前完整正式实盘A的晋级试验；B独立sizing模块本身不是可交易策略。固定报告权益/收益/DD/Sharpe/手续费/滑点/成交及完整episode/胜率/盈亏比、年度、方向、手数分布与预算拒单，并生成全量规范HTML/整体曲线。暂不额外重跑多起点/季度/成本压力；如未来申请晋级，须另预登记及完整稳健验证。

开始过拟合操作判断：否，比例由用户事先明确纠正并全市场统一，不按旧2024亏损、品种或收益挑参。仍是已观察样本的后验研究，不当样本外。继续本口径验证价值：是，可把数量风险暴露统一并建立可复验基线；不预判0.5%必然改善alpha。不因结果失败再扫小数或放宽门槛。

调研：[CME风险定仓](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[vn.py官方组合策略](https://github.com/vnpy/vnpy_portfoliostrategy)、[官方模板文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)。判断：账户风险/每手止损风险决定整手数，保证金占用另设约束；取消1手帽必须连同成交、部分平仓、费用和复盘一起验证，不能只改一个risk_ratio。

新增回测结果：无(此记录在首次金融回放前写入)；修改/删除旧结果：均无。结束判断、真实结果、独立审核和最终HTML见后续交付stage，TODO只完成当前固定假设，不改正式/生产/其它线。
