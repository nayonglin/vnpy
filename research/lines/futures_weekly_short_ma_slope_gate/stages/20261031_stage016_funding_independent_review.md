# Stage016 场外备用金组件独立审查

- 时间：2026-10-31T16:07:15.304513+08:00；line_id=futures_weekly_short_ma_slope_gate；新迁移树/Users/mac/.codex/worktrees/weekly19-official-20261031/fian。
- 审查对象：qmt_roll_weekly19_funding.py、funding_store.py、36项原测试及1558接口文档；本审查者只新增本线stage016_funding_independent审计文件，不改实作者代码、Git index/commit、原Stage014或生产。
- 结论：PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS；条件接受离线确定性资金状态/持久化组件。未解决组件P0/P1/P2均0。真实provider资格、真实资金到账E2E、策略/邮件/执行接线和生产qualification均未接受，production_qualified=false，不能据本记录安装、激活或放行真实订单。

## 测试证据

原作者36项测试独立复跑0.021s，新增25项不同fixture反例0.119s，61项均GREEN/exit0。全部凭证与账户均为明确SYNTHETIC/FAKE手工构造；不是真实银行或CTP数据。最终测试日志在所有子进程退出后写入并SHA绑定，无open日志自引用。前后再次验证实作者3文件SHA与1558 manifest一致；审计源及日志SHA见JSON。

1. 金额/身份/因果：建议不改E/原始账户/入参；0.01部分款、精确余款、重复、超额、未知现金流、出金变化、错账户/release、原始SHA篡改与重复JSON key、回报晚于snapshot/过期等全有反例。金额strict字符串转整数分，300秒新鲜度边界有效、超微秒/未来无效；7日到期等号阻断，失败不部分扣R。
2. Friday→Monday：周五21:00但名义日为Monday的完整闭日+零起点+现金流链可让部分请求跨日续完；闭日证明缺失/错账户release/SHA/不完整、下日非零未知Deposit均阻断。未使用自然日/UTC相差猜测交易日。
3. E/R：未用场外R及建议款不加入broker E；已确认额只扣R一次，不另向E双记账。R耗尽正E仍可通过此附加资金门；E=0或负数阻断，不经base_capital回退。此测试仅覆盖资金函数，后续sizing实际消费者还须等价/集成验证。
4. 存储：0700父目录/0600文件与锁、软硬链接/非法权限、校验和、revision CAS、账本不倒退与不能复活R；WAL前故障不提交，WAL后状态替换前故障恢复一次，状态已替换而journal未清理恢复幂等，未来revision/跨release/链接journal拒绝。另以双handle线程与两个独立Python子进程同时争抢revision0，各只有一个commit成功、另一个revision_conflict。
5. 可变入参：成功/失败confirm、recommend和跨日reconcile均核原对象未污染；回执重复经重启重放不重复扣场外金。

## 两个必须保留的条件边界

**凭证完整性不是凭证真实性。** 独立test01故意完全自造schema正确、raw SHA自洽的账户/现金流，组件能记为confirmed且附加funding gate可返回None，但state.production_qualified仍false。这不是新发现的hash漏洞：模块docstring明确把真实来源交给另一个qualified capture adapter。它直接证明该函数不能单独作真实到账/下单授权。真实provider必须绑定可信原始capture来源、account/release/generation/query、Deposit/Withdraw/权威日序/闭日完整性；不能只附verified=true、source_kind字符串或自行重算SHA。真实运行的qualification/订单授权还须独立校验。

**本轮建议0不代表旧请求已结清。** 独立test13确认：已有pending而本轮admitted_entry_ids=[]时，recommendation返回no_admitted_entry/amount_fen=0，旧request仍pending，assert_open_funding_ready仍正确阻断。因此邮件必须从state.requests列出旧pending/部分到账/剩余额/expiry及blocked，不能只消费本轮recommendation.amount发“无需补资/可开新仓”。已通知root与资金作者，属于mail adapter尚待实现的消费要求；本次未将其写成核心现金守恒bug，也未修改组件。

## 条件接受合同

- 上游admitted_entry_ids须真的来自native flat/reverse、有效完成周stop及short bottom20通过、父sizing前，不能用任意字符串/已选手数充当admission资格。组件只信任该上游身份。
- 真实provider与release/account/runtime资格在组件外强制验证。所有fixture、JSON校验和、Store同用户校验均不能提供真实性或防同UID恶意改写的安全证明；不因此宣称whole production合格。
- 输出state必须CAS/WAL持久提交成功后才发建议或放行新开；遇commit异常先load/recover并重核，不因异常盲发/重发。邮件outbox exactly-once/uncertain delivery是另一接线任务，未在61项中验证。
- 发生跨日缺链、未知入出金、请求过期而实际款到等情况保持阻断；当前没有合格operator reconciliation命令，不能编辑R/ledger跳过，也不能从晚时点非零Deposit虚造下日零起点。provider需要取得真实连续原始证据，若拿不到则报告具体blocked。
- 该门不校验broker Available/冻结/真实margin/报价/生产授权，不替代其他sizing或下单门。平仓/减仓不因funding pending被误封；新profile所有真实open消费者、0E sizing、account MTM/现金不双记账仍需后续集成测试。
- WAL测试为本机Python/文件系统上的故障注入与双进程互斥，不是假称完成掉电硬件/所有网络文件系统/所有故障时点证明。文件锁是协作机制；支持范围以本机已测运行条件为准。

## 数据、逻辑、bug和置信度

组件无行情/收益数据，未跑任何回测；期末权益/收益/DD/Sharpe/滑点/交易次数/胜率/PF等均不适用。它没有用Stage014历史数值优化规则。当前审阅范围没有未解决P0/P1/P2代码bug；真实provider、capture流完整性、邮件与实际open前门未实现仍是生产资格阻断项，不能把severity0偷换为ready。

对已测离线资金守恒/幂等/恢复边界置信度较高；对真实资金来源/到账时效/券商E2E和全部生产消费者置信度未建立。本审查银行/CTP/SMTP/订单API、生产修改、金融回放、commit/index操作均0。

## 外部调研与反思

参考[Python3.11 fcntl官方文档](https://docs.python.org/3.11/library/fcntl.html)及[os.replace官方文档](https://docs.python.org/3.11/library/os.html#os.replace)并结合本机反例。判断：Unix锁/原子替换可支撑此协作存储，但不能替代完整事务恢复、真实凭证来源和生产资格；不升级现有Python/vn.py。正式资金来源仍沿上阶段[官方CTP account callback](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)参考，需实际锁定runtime/capture取证，不能用网上最新实现冒认本机E2E。

开始/结束过拟合判断：组件测试本身否，使用人工反例验证固定会计/执行纪律，不看历史收益、不扫参；原候选的同历史选择风险仍保留。继续价值：是，下一步在不改alpha下接可信原始provider、outbox和全open消费者，然后另签新的接线/生产资格；不能修改本接受边界或把本记录复用成真实到账合格。
