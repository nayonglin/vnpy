# Stage024 现仓与既有盈余接管独立预审

用户授权已足够支持保留真实权益和现仓的新接管流程，不需要再要求撤出盈余或先平仓。m3当前只支持15万空仓的新cohort；本次应新增明确版本的启动迁移合同，而非删除guard。此记录仅架构预审，未实现、未qualified、未激活。

资金保持初始本金150000、真场外R150000、T0=0。令接管真实权益E0、启动前盈余S0=E0−150000；接管后净PnL=Et−E0−累计新T，故Et=150000+S0+接管后净PnL+累计新T，Rt=150000−累计新T。S0不是已核weekly19历史策略收益，也不是补资，不重复加到真实Balance。gross Deposit/Withdraw从真实接管快照建检查点，不能假设为0。

优先使用可核的完整旧保护状态，通过显式mapper迁移。若旧状态不足，用户授权下可采用明确的新接管基准，但须先固定成本/计龄/保护线/peak与PnL归属规则，不能把unknown装成历史连续。Stage174的generic position.price刻意为0；PositionCost、OpenCost与逐笔原始OpenPrice不可混用，四查询聚合持仓不证明历史入场日期、保护线或最高盈利路径。entry_date重置会延后前两根完整周线保护，peak/动态线重置也会改变退出，须如实列为迁移语义。

必须同时建立ProductState.layers/方向/保护量、pos_data/target_data、position_identities与实际symbol/epoch/持仓量；风险平仓仍经Runtime.close_lifecycles真实lot与remaining处理。纠正探索消息：当前C明确enabled=False，Stage032直接返回周线wrapper，不创建或消费启用加仓分支的_da_inventory/_da_close_queue，不能把它们列为此接管的必要字段。

不得构造假空仓快照绕过Runtime构造器，也不得造历史fill/委托编号。一次接管将真实现金检查点、完整保护/身份与runtime在同actor CAS原子提交，重放幂等、跨账户/release与事后重复接管拒绝。只预热已完成真实周线，不回放历史开仓；旧执行authority与待发草案需隔离。

新迁移合同仍需新source/material/offline审查及原生产qualification、manifest、activation、data/runtime与实时行情/账户/订单/成交闸门，不能继承未qualified诊断或宣称m3已具备接管能力。不恢复已取消的自动银行和最终日结解析；人工现金模式不放宽真实CTP事实。

未知旧ledger/成本/保护路径由另一个证据任务核查，本审查未读取该旧state；没有新增回测、原生连接、订单、邮件或生产变更。过拟合：否；继续价值：有，用户需求明确且状态迁移是必要工程边界。
