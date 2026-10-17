# Stage050 同一 B 账户进程的有界数据批次推进

- line_id：futures_trend_triple_screen
- 当前模式：day；用户持续自主研究目标有效。
- 记录时间：2026-10-18T04:43+08:00
- 分支：codex/ai-training-data-expansion；金融启动源 HEAD 为 008575e132ea76032d904cbd407aa6f85566b349。
- 阶段性质：必要数据接合与复现保存，非策略参数迭代；不是重要突破；不新增 A/B 金融账户。

## 外部调研与判断

- CMT 的 Elder 演讲记录第6页（https://docs.cmtassociation.org/docs/MTA0405.pdf）确认周方向→日级逆向准备→顺势突破的分工；GitHub LEAN ForceIndex.cs（https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs）可参考价格变化×成交量及EMA实现。
- 我的判断：经典机制有检验价值，不能把少交易、少成本或数据通路完成当成 alpha。当前只推进收益出现前已经冻结的 B 合同，不救 C0/C_TS 的失败参数。

## 本次变更

- 新增：040精确真实日线恢复、041绑定新日线的精确分钟provider、044有界数据编排、045单需求本地resolver、046原037 reader、047联合需求resolver、048两provider/物理新旧键reader；具体协议与早期失败记录分别保留。
- 新增：Stage050临时执行链，只按固定源码串行调用044的batch004—020，每批最多4个正常provider连接，遇任一非连接额度终态停止。每批prepare仍验证原PID21822及完整命令/启动时间。
- 修改/删除策略参数：均无。没有改035/036、原allocator、AI名单、0.5R/retry或任何已经消费的来源文件。
- 新增执行参数：batch_id、max_providers=4、budget_seconds=3600；单次数据等待1800秒及原金融整次7200秒期限均不重置。
- 删除脚本/参数：无。保留原044终端ps截断候选和047变量shadow预消费修复记录，不伪装旧fixture覆盖新main路径。

## 固定回测口径与当前结果

- B原金融session70433/PID21822，启动03:47:59；本阶段未重启、未重复A0、未新增金融尝试。
- 区间2020-01-01—2026-10-14，本金150000，历史真实AI eligibility，0.5R止损及一次retry启用，原滑点；commission参数0，不能视为完整券商交易成本。
- 本阶段金融累计仍8次attempt、3个独立验收完整账户；B仍第1次且待完成，模型训练0。
- B期末权益、收益、最大回撤、Sharpe、总滑点、成交次数、胜率：均N/A，尚无真实完整终态和独立账户审查。
- 已终态批次：`[{"batch": 1, "status": "blocked", "providers": 1, "delivered": 9, "local": 8, "journal_sha256": "f205f8286e333804c169285a93ab9b357f985a7cf7c0e6e199e2409fed74ed77"}, {"batch": 2, "status": "paused_provider_batch_limit", "providers": 4, "delivered": 19, "local": 15, "journal_sha256": "bdbaf1095b65fcca2d7e5e459e97251e82d326f8cda4e9538a1a13ef478ec3bb"}, {"batch": 3, "status": "paused_provider_batch_limit", "providers": 4, "delivered": 5, "local": 1, "journal_sha256": "5e6e3a07d8154f1aa967e258a2818b0660c04ba2aea756a92ff86ba35ae0d467"}]`。
- 合计33个已交付实际请求：24个本机复用、9个新provider；这不含先前SM005本机及Au2006/Jan8的2个初始交付，也不含正在推进的后续批次。batch001因单需求resolver边界exit1，9个已合格交付保留；batch002/003均真实exit0后到达各4连接上限。
- 联合Jan23真实main验收通过，只覆盖MA005和hc2005两个实际缺失anchor，不把已合格rb再纳入请求。
- 048的非空旧物理键分支仍须实际021逐值全等后才允许更新；独立静态/有限样本不能冒称所有旧报价已经独立重读。全时段资格要求不变，anchor仅首分钟/已知openOI/完成性，不要求不必要的全日HLCV/closeOI。

## 输出与下一步

- 原金融：outputs/stage036_b_ts_account/B_TS；完整summary/raw/seal尚待实际终态。
- 数据编排：outputs/stage044_qualified_wait_driver/batch001—003，以及正在运行的后续批次。
- 同进程执行链：outputs/stage050_root_batch_chain；其controller_source.py仅控制固定CLI，financial_runs_started=0。
- 独立数据复审：Stage049，对037/041各1个真实225行样本及新048语义边界独立复核；具体receipt见对应唯一stage记录，不扩大样本结论。
- 下一步：同一进程完成→先保存完整raw与seal→独立038账户复算/预算/母链/门禁；若失败按实际终态记录，禁止从中间请求补造收益。只有候选同时提高收益、降低回撤才进入固定多周期和成本资格。

## 反思与合入建议

- 运行前/后新增过拟合判断均为否：本阶段没有查看B完整收益或调整策略参数；仍承认历史研究选择偏差，不能称为全新OOS证据。
- 运行前/后继续价值均为是：为已冻结独立B取得完整、可审计的资金结果。数据支持本身没有达成原目标。
- 本线LINE由root在相干批次终态后汇总；registry有其他脏改动，本阶段不修改；不追加根总账。
- 仅本地登记所需源码/协议/资格元数据；原始行情、数据库、私有配置、SDK凭证不入Git；不推送、不部署、不连接CTP。
