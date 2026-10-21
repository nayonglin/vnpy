# Stage412：网络执行修正及原资金状态独立有界复审

记录时间：2026-10-20 15:22 CST。line_id=`futures_full_market_long_signal_ai`，非重要突破。不改LINE/registry/其他stage/作者源/金融状态，不读修正后batch raw、不跑contextloader、initialize、模型或金融回测。

## 裁决

**接受一次明确记录的操作环境修正；剩余P0/P1/P2为0/0/0。** 这不是原单批、no-retry采集计划的完全遵守，也不能冒称无偏差确认性cohort。单纯操作偏差不自动否决因果前瞻使用：修正后输入仍须由414独立源审与363另接受，两个模型继续同一输入、各自原资金状态和真实新封签/时钟。若unknown或late仍记gap，不倒签、不把下载时刻当source_completed_at、不用第一次空输入无资金seal。

原33703第一次采集实际exit1/no_raw；本审依赖已完成362actual_run1独审及原terminal，核收据/terminal字节SHA未变。0 raw、0 score、0 model inference、0 financialD、0 funded decision；但有空输入unfunded_research_decision。不能把它叫“策略没有信号”，也不能借其decision_sealed_at替代未来资金封签。

411修正的amendment/authorization/plan三者字节引用吻合。与原360授权逐字段比较，变化只有operational_amendment、original_authorization、source_attempt_number、source_attempt_output、strict_original_single_acquisition_adherence五个显式附加字段；所有原有字段（输入、sourcebundle、模型/scaler引用、freeze、预算、窗口、observe-only模式等）完全不变。原冻结357入口28199字节SHA仍为65d18a5c39e8df5442eafc2f5e2fd782f9bb492743339dc6cb5b013c91877e87。874×3、单新API实例、批内0retry、15:15≤CST<21:00未改；总尝试明确变成2而不是伪装第1次成功，不授权第3次。

网络诊断边界：本审读取root在411记录的两域sandbox内gaierror8、outside于07:16:40Z成功DNS及原362认证域失败证据，没有重复DNS/HTTP或读凭证。本审并未独立重跑网络，也不由DNS解析成功保证认证、全行情或永久连通。证据支持将第一次视为执行环境隔离，修正amendment于07:18:43Z记录，早于root后来报告的07:19:59Z修正批次终态。第一次没有任何可比较价格/分数，因此并非在两份已见数值之间挑收益更好的快照；后续不得依据新batch结果选择是否承认该尝试。

## 原账户及冻结物料

只读取384列明12个原小文件做当前SHA对照：370/378各base+stress资金文件、初始化envelope、原model_journal/policy/journal初始化payload。12/12与384原绑定完全一致；两个资金journal均只有sequence0的paper_state_initialized，没有空采集追加、资金决策或事后覆盖。另四个两模型/scaler原小文件SHA完全不变。未调用加载器或重建状态。

四个账户ID各异，各初始1,000,000；仓位/pending/fills/closed均0，fees/slippage/realized均0，phase=awaiting_u，start_u=next_u=5290，last_u/last_D/sealed均null。资金与journal不会因为第一次空输入unfunded研究seal而被视作已推进或允许重置。风险/成本kernel随原状态字节一起未变：单风险0.0025、总风险0.02、保证金上限0.25、buffer1.10，以及原base/stress成本。没有新的funded封签资格由412产生。

root发来修正后9175已exit0/有观察的状态后，本审仍未读其任何新raw或分数，未把root摘要当源合格证据；414另审。对原四资金账户的当前核证发生在双方尚未process_pair时，412不接管后续process或源审，避免并行写入。

## 调研判断、反思和执行边界

先读registry、411三小物料、原362收据与384绑定。本次纯执行修正独审不开展新alpha来源调查；网络因果判断依据本机已记录的同两域控制诊断，不伪称新增网上/GitHub研究。新收益择参过拟合：否，第一次零数值、模型风险输入均未变；操作计划偏差：是，必须明确。继续价值：是，可在不改策略条件下修正已定位的环境错误；无价值的是额外第3次、反复重跑suite或事后挑源，本审不授权。

本次网络/行情API/SQL/Y/fit/cash/模型推理/contextload/initialize/账户journal写入全0，无fixture、无旧suite、无新脚本。新增/修改/删除金融参数和金融结果均0；权益/收益/回撤/Sharpe/滑点/交易次数/胜率均N/A，完整目标未达成、goal active。机器证据见outputs/stage412_network_correction_review/actual_review_receipt.json。本审完成即止。
