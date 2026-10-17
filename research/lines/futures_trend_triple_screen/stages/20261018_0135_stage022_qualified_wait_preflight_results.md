# Stage022：独立 runner 与完整离线预检

- 记录时间：2026-10-18 01:35 CST；line_id=futures_trend_triple_screen。
- 是否重要突破：否；本次是严格数据接合与运行资源门，尚无C0金融结果。
- 改动：独立复制001为tools/stage022_run_c0_qualified_wait.py；原001逐字节保存并保留diff。新增002/011/015/020 append栈＋016最外修正、021双用途资格等待、原子request/fingerprint/response、真实runner_used快照和新来源清单。旧001与正式源码未改。
- 新增/修改/删除alpha参数：均无。正式4源码SHA、C0已完成周许可/unknown fallback、AI、模型、资金、成本、滑点、0.5R与实际settings均保留；新增仅1800秒单次等待、7200秒全运行工程上限。

## 实际证据

1. 七项必要纯控制测试通过：交付前SHA与record、错request拒绝、超时保留请求、重复hash内容改变拒绝、859 anchor/full隔离及未出现016 key不得预授资格、原候选/model/runtime/helper AST相同、全运行超时越过第三方Exception捕获且恢复timer。没有账户或网络。
2. 首次freeze在011实际summary没有all_inputs_unchanged字段处停止，尚未写manifest；失败保存在outputs/stage022_qualified_wait/offline_prepare_failures.json。读取改为011真实的original_sources_never_opened_for_write＋独立review base/002 SHA不变＋签定input_manifest，其余015/020仍严格要求all_inputs_unchanged；所有源当前SHA仍逐文件校验，没有重建旧数据、放宽资格或隐藏失败。
3. 成功冻结一个data_stack_manifest，1590个来源指纹，SHA `2b650761fbf2bc30aa0046147b7e369a2a0a10a68ee6b520204dde8d4d7226a0`；020 receipt `307a41cf…9271`、021 receipt `4cb45007…3367`均实际通过后才消费。
4. 一次完整离线preflight通过：outputs/stage001_first_screen/preflight/C0_attempt3.json，SHA `62cbcce2a016fd6881f722769821a7a4c394e55967834e21338de8df1a4fb91a`；记录1950个实际输入指纹，806个metadata合约，77368条周特征。effective parameters及requested settings逐值同A0。
5. 冻结数值栈sklearn1.8.0/numpy2.4.4/pandas2.3.3/scipy1.17.1/joblib1.5.3；模型5行、19特征手工概率核对最大误差0，model fits=0、模型字节未改。
6. 新runner SHA `aaa0cc50c7c817c885afd6eb3630b28f714da21486a1ec2dfb8fbeb39437582c`；原001 SHA `928df4baae38548ba54126efc157d04174cec1bbe641cdb5e7be38cfd26969d4`；source_diff SHA `f7aec3c7e16bd3749706d76afe35e03ee08a7c6f751d52879a96fd77d4e9fd95`。

## 边界与后续

- C0_attempt3目录尚不存在；真实金融回放0、提供商连接0、订单/撤单/CTP/模型拟合0。累计金融attempt/completed仍4/1。期末权益、总收益、最大回撤、Sharpe、总滑点、成交次数和胜率均N/A；无新增/修改/删除回测结果。
- 时序：Stage502已安装当前batch datetime/bars后，021门冻结原context；成交、strategy.update_trade、847扫描/retry、on_bars和dailyclose均在门后。不能将其描述为整批行情安装前暂停。
- 初始资格是继承已接受基准＋用途受限859，不是全表逐价重新认证；full排除残余859，anchor只额外接受Stage010 canonical首键，016实际加载的已签1500scope另准入。未来新full若落于未合格859仍需等待真实签定数据，不能用日线open或改旧值兜底。
- 最终请求路径为C0_attempt3/data_wait/request_<canonicalSHA>/request.json，同目录request_fingerprint.json立即落盘，response绑定独立receipt/data SHA。023只准备外部真实补数，不自行签review或写response。
- 独立接合审查已通过：`outputs/stage022_independent_review/review_receipt.json`，SHA `f8bd3aba4c3136861066688b50c84538c5654d32b6c20318b82507b29b269fae`；`qualified_research_c0_wait_runner=true`，P0/P1=0，33项关键SHA及主diff/原19helper AST、数据用途、原子握手、超时与动态record门已核。未重复测试或preflight，实际runner_used分支尚未通过真实回放执行。
- 保留一个已接受P2：独立CLI先ensure新数据栈后，原`_GLOBAL_MINUTE_BY_SYMBOL`引用不会恢复到进程进入前的旧引用；本次单次CLI退出、经济结果和磁盘数据不受影响。不能声称整个接合恢复了所有全局引用，也不因此修改冻结代码或重复预检。021门自身的方法与策略原dict恢复合同仍有效。
- root准备好023及其有限review后统一启动真正的C0 attempt3。完整2020至今同一候选仍是目标，不以离线预检代替账户结论。
- 调研与判断：沿用已核Elder与官方TqSDK接口结论，本次没有新网络；经典三重滤网不能证明alpha。是否过拟合：否，本次无收益选参；是否有继续价值：是，让真实路径按需补数并在同一engine继续，避免全量overapprox补数与逐缺口金融重跑。
