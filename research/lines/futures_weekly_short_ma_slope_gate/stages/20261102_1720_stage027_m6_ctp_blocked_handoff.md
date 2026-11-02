# Stage027 m6工程通过、真实CTP受阻与晚间接续

- 时间：2026-11-02 17:20，北京时间；line_id=futures_weekly_short_ma_slope_gate。
- 性质：正式安装候选的工程封账与失败接续，不是新金融回测，也不是已激活生产。重要突破：否；取得工程可复验结果，但尚无真实安装资格。

## 用户要求与已完成

用户明确“直接切换，就当作已经15万已经盈利了一部分就行”。已实现并审查显式existing-account启动：以新CTP实际权益E0为真实起点，E0−150000单列启动前盈余；原有真实持仓由新管理周期接管，不造历史成交或旧保护状态。场外15万仍为R150000、初始转入T0；后续风险按交易账户全部真实权益计算，缺额须新信号及用户人工到账证据。每日风险邮件与周五补资独立去重已经包含在候选；44品种及MAIN开发树隔离。

m6：`m0006_20261102T162146+0800_42fdb977fc28`，S6=`42fdb977fc28ad55ddd8c6cf8d364e97e4acf967`，R6=`4c9b645eefb509d3026246f2f16843c57341ddaa`。388物料、298默认critical、690资格并集；fresh local clone实际LFS/字节/执行位、34历史manifest均独立通过。m4/m5失败和全部旧物料原样保留。

## 真实可信运行结果

实际R6可信runner完整96套件，2408通过、失败/错误/跳过均0、96退出码全0。旁路只归档原始288文件版本，不改变producer或授予资格。独审1213项检查通过，690源同R6，工程成功与真实连接失败严格分开。

随后第一次实际Stage907/174正式只读未得到TD/MD连接、认证或登录回调，query callbacks及所有账户/持仓等行均0、broker trading day空，状态`readonly_logs_without_ctp_progress`。8项mutation attempted/called严格0。原校验器拒绝`release_builder_production_readonly_raw_capture_invalid`；第二捕获未发生，qualification.json未产出，**FAILED_NOT_QUALIFIED**。账户和持仓是UNKNOWN，不能据此认空仓，也不能复用09:04旧快照初始化。

正式env字段存在且选中、两正式framework实际Dyld优先及Python/扩展SHA已核。追加同env TCP只连通性探测：TD、MD均5秒TimeoutError。只能判断本次未建立连通，尚不能定位网络路由、防火墙、服务器窗口或其他原因，也不能据此判凭证错误。12原生失败原件按原bytes/SHA/0600私有归档；实际资金、账号、持仓与端点不入Git。

## 生产事实与接续

17时后新只读核实：canonical stable仍为`d55887e1def72629fbfa310e439dc3a879969a14`，clean，CURRENT仍旧m0008；生产五件套均缺。Stage948完整所属surface verified/blockers=[]，磁盘/域/loaded/unknown所属标签均空。未activate、promote/push master、切stable或Stage948安装，未实账户接管、发单、撤单、转资或SMTP。

唯一接续入口为`Stage027_installation_handoff.json`，实际失败独审为`Stage027_review_acceptance.json/.md`。已通过应用工具创建并view本日21:00同聊天一次性跟进，id=19、ACTIVE、COUNT=1，本地配置已核；实际创建回执见`Stage027_evening_followup_receipt.json`。本handoff仅绑定最新m6，替代m2/m3/m4/m5安装目标，不删除其历史证据。

晚间先核后续用户指示/最新独审冻结记录、stable/CURRENT/五件套/所属任务。必须从clean exactR6新跑完整trusted套件及两次正式只读；本记录提交后的ROOT文档后代不是R6，推荐已审local R6 clone补本机ignored依赖，严禁改资格source身份。真实Q_R通过后才沿原发布器activate→GitHub master→远端fresh clone→受控stable→stable原目录Q_M→正式manifest/receipt/来源registry→新签名快照→显式原子接管→真实完成日daily receipt→Stage948七任务链推进。local clone的origin是本地ROOT，不能当真实GitHub远端。

## 参数、结果与调研判断

新增/修改/删除策略参数：均无；保留空头底20%、原风险1.8/6/6/2.5、无加仓，斜率和多头过滤不启用。只修工程夹具chmod以准确构造宽权限反例，不降低生产umask或闸门。没有金融回跑，因此期末权益、收益、回撤、Sharpe、滑点、交易数/胜率均不新增、不改写；原Stage014/019历史继续保留。

调研沿用仓库正式CTP/runtime guard与不可变发布控制面，以及已查OpenAI Docs的同聊天一次性跟进能力；未进行alpha优化或GitHub策略搜索，因为本次是已授权安装接续。判断：当前失败是实际连通性未建立，不能绕过真实资金/持仓来源。

开始及结束反思：过拟合 **否**，未调参数或优化回测收益；继续价值 **有**，等待真实前置可达后完成已授权切换。前置不可达时重复连接不提高资格，保留失败，按一次晚间窗口接续。

补充治理核验：activate只要求当前HEAD clean，不要求等于releaseR；故新资格在原clean R6 clone运行后，可在ROOT纯docs后代D、690闭包/物料/历史release不变的前提下，activate原R6生成A，再由promote从A显式复制本线最新handoff。不得把Q改标签为D或复用它作stable的Q_M；独立API回执`/private/tmp/weekly19_stage027_docs_descendant_activation_readonly_receipt.md`已由handoff绑定。
