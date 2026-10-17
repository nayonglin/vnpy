# Stage075 执行台账

- 授权范围：实现 Stage071；只新增两个 tools 文件、本目录和唯一 Stage075；不改旧源、LINE/registry、不提交、不金融/网络/模型。
- 已用 test-driven-development / executing-plans / verification-before-completion；父任务已有合同即为实施计划，不另造方案。
- Ruling：父任务明确最多三项必要合同测试、同分支且不另派 reviewer；因此不用 skill 默认全仓测试、worktree、提交或另起审者，也不写 .superpowers 目录。root 另派独立复核。代价是本实现不提供全仓回归保证。
- Ruling：RED 使用测试中的原政策 pass-through/context 作为无隔离行为，避免把 ModuleNotFoundError 误记为有效 RED。实现前真实运行三项均为预期语义 FAIL（7未减5、226未减1、旧cache未清）。
- Ruling：按父任务明确批准，先用真正021 parser核原request+原receipt的345值；再对每个真正021生成的fixture request写明确fixture_only wrapper，引用同一个已pin CSV。wrapper不是独立市场数据签发，不写任何engine response，未来金融实际request须重新资格。
- Ruling：完成证明键由调用者完成来源/哈希/审查后提供；模块只规范化精确键并隔离物理行，不接收旧predicate/demand为证明，不构造新资格predicate。
- Ruling：source859物理成员判定向量化；仅保留紧凑symbol计数，不生成全量removed键JSON或Python集合。
- Ruling：context进入同时脱离_LAST_MINUTE_AUDIT原对象；loader失败还原调用前cache引用，context异常撤销本scope新增audit，finally还原全部原对象。代价是失败scope成功过的过滤摘要不作为成功audit保留；测试证据独立记录失败。
- RED：3 tests，0.145秒，exit1，3个语义失败，见red.log。
- GREEN：3 tests，0.215秒，exit0，见green.log；仅本次新增3项，不重复旧suite。
- 编译：两个新文件py_compile exit0，字节码只写本目录；见compile_receipt.json。
- 真实fu投影：066固定差异+固定345CSV+原request的existing226重建；不重新读base全集，不读dead-engine RAM。旧policy冲突；新policy移225留249一行，原021 append344→345/full345；故意改保留行high仍旧值冲突，未commit。
- 限制：只是机制和fixture证明，非原B末包接受、非市场数据重签、非金融回放、非全部分钟价格质量证明。
