# Stage024 实际权益、现仓一次性接管合同

本合同只用于用户已明确授权的正式替换启动，不更改周线alpha或风险比例，也不授予任何委托、撤单、转资或手工邮件权限。默认入口继续要求真实15万元空仓。本次选择 `initial_account_mode=operator_existing_account_v1`，仍保留 `cash_verification_mode=operator_manual_v1`。

## 私有授权与来源

私有context中的 `startup_authorization={path,sha256}` 固定一个0600、无symlink/hardlink、父目录0700的文件。文件schema为 `weekly19.operator-existing-account.v1`，包含account_key、material_release_id、cold_start_date、completed_day、adoption_scope、authorized_positions、contract_metadata及operator_authorization。adoption_scope固定 `all_current_positions_new_management_cohort`；authorized_positions只包含逐合约真实方向和整数手数，不允许使用本策略理论仓代替。它限制本次授权范围，之后新出现或数量改变的未知仓位不能自动接管。operator_authorization记录本次明确用户指令，不能自称券商证明或资格签章。

contract_metadata引用原始真实TQ合约捕获文件及SHA。原始envelope须证明exact instrument、乘数、tick、到期日和显式交割年月，并与已接受的行情元数据和物理epoch一致。授权文件不接受人工填写成本/止损/成交/历史峰值。每次首次初始化仍从已完成同一代、同连接、当前真实CTP账户/持仓/订单查询生成实际绑定。原生OpenCost加总后除以实际手数与真实乘数，作为既有聚合开仓成本；PositionCost是不同口径，不能替代。normalized.position.price=0不能用作成本。

启动资金按真实Balance，包含已有MTM；Available也只能取真实CTP。`opening_equity`记录真实E0与本金150000的有符号差S0，分类为操作人指定的启动前盈余，不声明已核本策略历史业绩。初始gross Deposit/Withdraw建立真实观察检查点，不消费备用金。初始T=0、R=150000。之后Et=150000+S0+(Et−E0−T)+T，不能重复加旧盈余或旧浮盈。后续补资仍只填交易权益低于15万的差额，继续动态按实际全部交易权益计算风险。

## 管理周期与保护

现仓属于新接管管理周期，不是旧策略状态连续恢复：管理起点是实际切换日期，原始开仓日、旧止损、历史peak、旧连盈亏风险记忆未知。按最近完整周的原初始止损函数生成保护，必须有完整已接受历史及有效正数方向正确的保护线；不调参数硬放行。管理极值从最近完整周close作为明确参考开始，max_profit_pct初始0，随后继续原完成周线规则。重置计龄会使“两根完整周线”门重新计时，未知历史锁盈/giveback不被冒充已恢复。

完整ProductState.layers、方向、数量、已核聚合成本、保护线、pos_data/target_data及root/cycle/epoch identity与真实资金在同一私有PipelineStateStore初始原子写入。不能用假空仓先绕过构造器，不能造历史fill。再次运行只核对已有状态和真实账户，不重建层、不重置止损。正常支持/会话入口不得自动执行此接管。

## 安装顺序

1. 新source/material通过离线CI、独审、精确release真实只读资格及原正式晋升链；保留所有旧release和失败证据。
2. 已资格的稳定生产、release-manifest、qualification与activation完整一致后，准备绑定新物料的私有授权、真实来源和context。元数据、资金和原始CTP快照只私有保存，不提交Git。
3. 显式运行既有 `run_qmt_roll_weekly19_live.py --job initialize-existing-account --execution-profile weekly19-15w-r150k`，传入真实context、release-manifest、activation-receipt、production-qualification-evidence。该入口不会连接CTP、生成历史交易信号、发布委托或发送邮件；快照须事先由既有正式只读流程更新并通过来源资格。
4. 初始化只预热completed_day及之前的真实历史，decision=None。不得把启动前周线信号补成交。随后由原postclose-precompute处理cold_start_date及之后完成日并签发daily receipt，原每日风险邮件和周五资金邮件仍各自去重。状态、数据或现金待核验时维持原fail-closed，风险减少仍受真实仓位和实时执行闸门约束。
5. 最终必须按实际远端master、stable HEAD、五件套、Stage948回执及7个loaded标签报告。离线测试、私有授权文件或开发checkout都不能冒充安装完成。

本阶段无新增回测。过拟合判断为否：只处理已授权的启动与账务语义；有继续价值：保证实际资金与现仓可管理。研究本身的历史选择、零手续费等限制仍保留。
