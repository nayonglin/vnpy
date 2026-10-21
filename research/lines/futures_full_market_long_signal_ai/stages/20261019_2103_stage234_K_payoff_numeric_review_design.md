# Stage234：固定 K 单动作收益的独立数值审查方法草案

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 21:03 CST。非重要突破；仅审核方法设计，**230 尚未冻结，未实现 reviewer、未启动测试或 actual**。
- 开始前读取 registry、本线 LINE、226–229、129/070/042 收益与时钟必要源码及132 cache schema；未读取原 actions、mother、NPZ、行情、旧模型或旧现金。内存 registry 没有本任务对应条目，不引用旧记忆作为事实。
- 本次新 label/fit/cash/SQL=0/0/0/0；累计仍 433fit/234cash。完整目标仍是全市场高质量 long → 检验小止损 → 再检验增加投注，当前均未完成资格。

## 调研与判断

- [能源中心官方手续费调整通知](https://www.ine.com.cn/publicnotice/notice/202603/t20260309_830634.html)的搜索索引显示收费可按金额并区分平今，正文直接打开被 WAF 拦截；[上期所官方历史年报](https://www.shfe.com.cn/upload/dir_20130604/76882_20130604.pdf)的搜索索引也同时出现金额比例、元/手与日期变更。只用其确认“静态研究费用不能宣称历史券商真实成本”这一边界，不据索引重建费率，不扩大抓取。
- 核读 [vn.py 作者 GitHub 的 DailyResult.calculate_pnl](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)：成交额手续费、乘数和滑点需有一致记账口径。该实现把滑点单独扣除；本线129则已通过 adverse fill 把滑点计入成交价，因此不能机械再扣一次滑点。研究合同继续继承042固定 base/stress，不迁移外部费率或撮合政策。
- 独立判断：潜在支持只有时钟资格，K报价和费用仍须数值核证；14,254动作不是独立经验，不因约2%而忽略，也不能由收益变动直接推出可预测性、alpha、资金收益或旧标签bug。

## 冻结后才可实施的独立核法

1. **全母体与分支**：单次流读233全ID新投影，保持 1,552,456 action、399,252 mother、186,400 nochild，身份/原序号/父子绑定及固定 all/2020onward、year/family/product 分区守恒。紧凑投影无需复制227全部30列；必要时以独立一次227新metadata流作身份/clock join，而非再读129原表，是否需要由230锁定读取预算。
2. **复用与空值**：原 `closed_before_K` 只检验两cost旧PnL/R/known date/phase精确复制，不走旧路径。cancel仅 policy diagnostic=0、trade Y=null；unknown before/on K、unclassified、pending/intent不可补known。非primary动作保持完整身份与230指定未测状态，不能由旧known自动取得K目标。
3. **K点源映射**：只为潜在14254条读取同一accepted132 cache的 `epochs/offsets/days/values/valid` 五个member各一次；不使用旧restore helper，因为它会整cache hash并读取N/low20/run。直接由epoch找到offset片段，独立searchsorted(K_global_index)，检验在该epoch片段内、day严格相等、flat_index=offset+local_index、valid和raw open，缺点不拿下一有效日或末日。values列序为O/H/L/C/V；只抽K点O，价格合法性继承accepted valid，不重做旧价格清洗。
4. **时钟**：Kforceopen优先于同日gap/stop和旧anchor退出；只在旧prefix可继承且K点合法时完成新目标。原unknown_after_K允许新K结果不代表未知路径已修复；未知首时钟在K或之前始终吸收。新known date=K source date，phase保守用原 `after_all_source_close`；不能从成交价用open推断日线资料在open已可知。原closed_before的clock不提前。
5. **两scenario独立结果**：base/stress分别记录 known/state/known date/phase/PnL/R；一个scenario的SELL fill非正或费用不表示时，仅该scenario null，不能连带污染另一个，也不能输出共同known掩盖失败。旧129已知closed前缀两cost复制资格继续继承。
6. **算术**：独立实现下述Decimal adverse tick逻辑与scalar恒等式，不import233作者的quote/payoff/classifier；不重放原native策略。旧entry fill/fee/slip及N/M/tick来自新trace的accepted129复制证据，来源真实性继承129、233精确源码、read/stat及copy守恒证据，不冒称再次逐行对原表重验。
7. **结果和运行边界**：重算所有新K行/两scenario、null与known转换、原known两者可比较时的delta、固定分组及机械anchors；只描述单动作测量，不能累加成账户收益。0fit/预测/selection/cash/SQL/下载、无参数搜索；精确source/input/output授权、全新目录、唯一启动、异常留终态，不自动重试。新投影在同一读取流上SHA，旧大cache只核manifest继承与stat，不整文件hash。

## 独立费用恒等式

令研究reference为P、乘数M、tick为t，scenario参数 `(f_min, f_bps, s_bps, s_ticks)` 固定为 base `(2,.0001,.0001,1)`、stress `(6,.0003,.0003,3)`。

- `slip_points=max(abs(P)*s_bps,t*s_ticks)`（t有效）；无有效tick时仅比例。
- `BUY_fill=ceil_to_tick(P+slip_points)`；`SELL_fill=floor_to_tick(P-slip_points)`；无tick则使用原始和差。计算采用Decimal(str(x))，非round-to-nearest；fill必须有限且正。
- `fee(fill)=max(f_min,abs(fill)*M*f_bps)`；`slip_CNY=abs(fill-P)*M`。
- `net_CNY=M*(K_sell_fill-old_entry_fill)-old_entry_fee-K_exit_fee`。
- `net_CNY=M*(K_open-old_entry_reference)-entry_slip_CNY-K_exit_slip_CNY-entry_fee-K_exit_fee` 是独立等价核式；不再从第一式扣记录slip。
- `R0=.25*N_u*M`；`new_net_R=net_CNY/R0`；若协议保留common2N诊断则 `net_CNY/(2*N_u*M)=new_net_R/8`。u成本估计不是实际入场/退出成本，不能替代两腿fill费用。
- 拷贝分支要求解析后的数值、null与clock一致；新价/tick采用Decimal精确格点判断，CSV浮点算术容差由230冻结（建议CNY绝对1e-9加相对1e-12、R绝对1e-11加相对1e-12，禁止按结果放宽）。

## 给233的最小证据接口

- 全ID：`action_sequence_index/action_id/mother_sequence_index/mother_event_id/product_id/family_id/u_date/actual_epoch`；mother全ID、原child计数与nochild。
- 分支：primary/u资格、K target/global index/date/calendar state、原timing/label state、原exit/unknown index/date、`measurement_branch`；避免一个共同known字段代替两costknown。
- 继承证据：原entry reference/index/date、`N_u/multiplier/tick_size/cash_risk_unit`、两cost原entry fill/fee/slip、原PnL/R/known date/phase；cancel policy0与trade null分开。
- K源trace：cache小manifest binding、epoch slot、offset start/end、K local/flat index（无点哨兵）、cache day、K raw open、valid及quote状态。作者可不输出无用OHLC历史或完整路径。
- 两cost新结果：SELL fill/fee/slip、known/state/date/phase、exit reason、净CNY/netR、继承或新算来源。若各cost quote失败，保留raw open与明确失败原因。
- 流读收据：原actions48列allowlist一次读取的真实count/前后stat、copied-prefix count/field checks、cache五member各一次、缺价/非正quote计数、0新fit/cash/SQL等；小manifest/terminal/source绑定。

## 最多三个tiny合成例（仅手算设计，尚未执行）

1. **Kforce与tick/双腿费用**：F=100、N=8、M=10、tick=.2；K open=106.1，K low=100，旧trailing边界105，同日会触发旧stop。新分支必须用106.1强平而非105。base BUY=100.2、SELL=105.8、两费2+2、两slip2+3，净52CNY、2.6R、common2N=.325；stress BUY=100.6、SELL=105.4、两费6+6、两slip6+7，净36CNY、1.8R、common2N=.225。known为K日after_all_source_close。
2. **scenario分离/大跳空非封顶**：F=10、N=4、M=10、tick=1，K open=2.5，前缀已知。base BUY=11、SELL=1、两费2+2，净−104CNY、−10.4R；stress BUY=13但K SELL raw=−.5、tick floor=−1，不能成交，stress trade target和known clock均null。不得把base也设unknown，不得截成−1R或后延找好价。
3. **5动作/4母的clock-null守恒**：mother0原closed_before（任意有限旧两costPnL/R/clock逐值复制）；mother1取消（policy0/trade null）；mother2三月份动作分别unknown before/on/after K（前两永远null，after仅可用例1合法K点改known）；mother3 nochild保留。5action/4mother/1nochild守恒；不会仅输出“两个known”或把取消计入trade样本。此例只测新分支和完整母体，不构建旧全路径。

## 参数、结果和前后反思

- 本次新增/修改/删除策略参数0，新增/修改/删除回测结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A（未运行金融）。
- 开始/结束本轮按收益救参过拟合：否，未读数值Y或行情，尚无新标签/训练；整条同史反复择题风险：是，冻结及独审不能消除。
- 开始/结束继续本有限测量价值：有条件的是，能区分定义差异是否具有真实数值与clock影响；重复旧价格清洗/原策略全重放、先重训旧模型、直接加注：否。即使全部核过，也只接受测量算术，不授予alpha或资金资格。
- TODO：等待230最终冻结并核本方法差异；root授权后才写234 reviewer与最多3tiny测试，待233唯一actual完成后独审完整新产物。无LINE/registry/根账本、其他线、正式生产、Git修改。

## 230冻结后的实施与独立预审补记（2026-10-19 21:18 CST）

- 上文是收益前方法草案的历史状态。本补记以最终230为准：协议13,556B，SHA `ba46ca70fd2bc6387f0cd89d9c7bb7313283b1de38cc9893442487e7ec754f85`。root授权实施234 reviewer及最多3个tiny；actual仍仅root可唯一启动，作者不启动/轮询。
- 最终233接口已逐项静态核：原动作49列（原48+exit_reason）；全labels68列，quote evidence96列，mother16列且文件名`mothers_K.csv.gz`；summary scope为all/post2020，固定year/family/product，quantile为p50/p90/p99/max。包括无child母体的组也保留。原before-K三数值及clock/exit token精确copy；K缺点/invalid为source consistency停止，单cost不可表示仅该cost unknown；policy四字段只表示已知不行动0，不混入某个cost交易收益。
- 新增`stage234_K_payoff_review.py`与`test_stage234_K_payoff_review.py`。独立Decimal SELL、两腿费用/净R、全新K点映射；先单次读新evidence并独核全部K点，再单次新labels流作逐token join/状态/known-null/clock/分组聚合，再核完整新mother计数、两scope/全部固定组、机械16anchors及accepted227时钟计数。无227大投影二读。
- cache只一次打开/五member各一次，完整成员载入不宣称只读点字节；`N/low20/run/accepted`不读，旧cache不整hash。calendar一次。旧entry事实、原30metadata来源真实性继承已接受129及精确233源链；compact中没有的history flag/last_path不重新认证，也不对原价格或D到K路径重放。
- 三个新tiny方法先RED：缺独立源码时3个预期assert失败；实现后GREEN。既有第3方法随后补原u不具资格且calendarunknown的政策0边界，先出现缺参数TypeError，再显式复现`(None,None)`不等于`(0,U)`的失败，修正后同3方法GREEN。后续仍仅同3方法补quote invalid点拒绝和copy token逐字一致断言，没有增加第4方法。最终`Ran 3 tests in 0.028s, OK`、exit0；作者4个tiny仅实读其terminal，不复跑；旧suite/fixturefit均0。
- 231窄静态独审指出234初版在大加载前缺完整producer源链守卫。已仅补小闭包：completed/schema/protocol/输入绑定、233精确5小源与root measurement授权、started/terminal、read counters与继承stat before/after，均先于cache。231复核已回复Resolved，无开放阻断。此最后改动只涉及actual I/O guard；按root要求不重跑无变化的3tiny，最终py_compile exit0。
- 233源码/接口prepass：开放P0/P1/P2=`0/0/0`。233源25,686B SHA`cc4bac7a67ca41254ea88a2afb22d665ada6a796ace82d23e204989b1971dfee`，测试7,293B SHA`34aaa417ec7777bd237a05b5bf6be96dfdf5b3c1c40faa2cfcaff62c22d8485a`；5小源束与作者冻结文件完全相等。root可先启动233测量，本审查器source-chain工程未被作为串行阻挡。

### 最终234源与预审收据

- reviewer34,598B SHA`8b52e4176f1115b2291a676853b57f56e91c5f4741c155fdb826435ea48816e4`；测试5,495B SHA`381b445a1148c287a0d32c92d68baea70522be83ab9bd6ad3137cdc112a4aef5`。
- `outputs/stage234_K_payoff_numeric_review/source_bundle.json`：941B SHA`d7d9825b25e5bf94db7823a4b0541845c2bb4c9201d511b14202e4455cf06a9e`，其JSON直接为root review auth的source_bundle list。
- `fixture_terminal.json`：768B SHA`5324291f996502a829c3c5d6d81e6f44019aeb4c538f64b96e74dac1b8edf4d8`。
- `prepass.json`：5,695B SHA`f11321027781c171a486cfc2e01293fdb0ceca17d019da89468bfc718d7b38bb`；记录时间改用机器自动时间21:18:36.489583，覆盖此前误手写21:21的草稿值，仅小收据变化。初次生成此小收据时把作者freeze封装对象误当list触发assert，未写prepass/未启动actual；改用其source_bundle键后成功。
- CLI与完整authschema在prepass内。根授权schema为`stage234_exact_root_review_authorization_v1`，精确绑定source bundle、最终完成233 manifest及两个actual目录；fresh output为`outputs/stage234_K_payoff_numeric_review/actual_run1`。未获root实际启动不能把本prepass写成新数据独审完成。
- root通知233测量唯一session80769正在运行；本agent未读取半写actual产物、未开NPZ/原actions/mothers、未跑actual reviewer，未读取六traincache、模型或现金。后续独审仍由root启动。
- 结束新增按收益调参过拟合：否；历史同史适应性选择风险：是。继续此有限数值测量与独审有价值；其通过也只授予测量算术资格，不授予218最终共享C、alpha、真实资金/生产或增加投注资格。累计433fit/234cash不变，财务回测指标N/A，完整目标active且未完成。

## root唯一actual独审完成补记（2026-10-19 21:21 CST）

- root唯一启动234 session`96437`，进程终态`completed / exit0`，terminal墙钟`93.20177966699703`秒，receipt主体计时`93.20139883301454`秒。作者没有启动、轮询、重跑审查或读取新大投影；本补记仅实读小receipt/terminal/manifest并核其SHA闭合。
- **最终独立审查开放P0/P1/P2=`0/0/0`。** 完整核`1,552,456`新action标签、`399,252`新mother与`186,400`nochild；独核全部`14,254`新K点及`28,508`cost报价/收益结果，两scope/固定year-family-product分区、所有新known/null/copy/exit/clock和16机械anchors一致。新evidence逐token与对应完整labels联接、mother每cost三分计数一致；accepted227主域timing计数未变。
- 独立review一次calendar读取、一次NPZ打开及`epochs/offsets/days/values/valid`五member各一次；cache前后stat完全一致，继承SHA未整hash。原actions/mothers和227大投影读取0，六traincache0，原价格清洗复审0，D到K策略重放0，fit/cash/SQL=0/0/0。继承的原源真实性不被冒称本轮又逐字段重审；compact未承载的非派生metadata也未再次认证。
- 唯一233已完成manifest绑定为12,639B SHA`f028bdb67d5db85c4202fb92a9fe328ed020e30d7c3ee2707db2fa9ea3a1686e`。234 receipt3,114B SHA`8f83b0482b5f32c396a79acc20dc2558257d79bd220f003dbf37f9bcdcd54b0e`；terminal86B SHA`a6f9316bb888f567ec94a751b0e7021f165c8dcfb767fb7d24ffb428f2eeef9f`；manifest1,253B SHA`a1f301344025654278a4494ea6c9e92e5b7135575c9aac90a9e8329e6cc8331e`。小manifest对receipt/terminal的binding与本次实读完全一致，源束/230协议与预审冻结保持一致。
- 接受边界：只接受此次固定K单动作测量的数值、源点映射、状态与条件known-clock资格；无六fold train-cache/C==S/weights/scaler的最终复用认证，无alpha、账户收益/回撤、真实券商费率、首发PIT、生产或增加投注资格。root235负责研究裁决，本agent不据独审通过自动创建训练/现金实验。
- 结束反思：本轮新增按收益救参过拟合**否**，因为结果后未改测量合同、K/成本/目标或模型；同史多轮择题风险**是**，仍未消除。重复本测量/全审的继续价值**否**，本次已完成；完整全市场高质量long目标继续价值**是**，但仍未完成，小止损可靠性与增加投注尚无资格。累计仍`433fit/234cash`，本阶段账户权益/收益/DD/Sharpe/总滑点/交易次数/胜率均N/A。
