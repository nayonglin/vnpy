# Stage111：外部provider运行环境选择的定向独立复核

- line_id：`futures_trend_triple_screen`；2026-10-18 07:58 CST。
- 独立reviewer：`accepted_delta_review`，非109实现者。
- **结论：P0/P1/P2=0/0/0，固定二源外部runtime选择有限接受。原840及所有金融/数据门不降低；实际batch003由root按当时真实余量决定。**

先交冻结receipt：`outputs/stage111_provider_runtime_independent_review/review_receipt.json`，SHA `394879ddf698d5bb6d20cc54e62fb433e376977f78c70a9e0ecaea72df89bfb0`，再补本文，receipt不变。source_bindings精确launcher/sitecustomize两ABS→SHA+bytes；test另integration_source_bindings，不混入原087二源合同。

## 固定身份与scope

launcher SHA `544809b18c6e8d1d74efd708cfec600b781b97da6bebd95d9e340e077f0ad93c` /12742 bytes；sitecustomize SHA `ba9ae3352dd5c20cf6f6a6e7c09de5dda174f1cb397c5f9c8fd460557f112bc5` /628；test SHA `1ab6480cd70009f1bf618878700accab6ca7bab9afd52b472f91ea74fc055a08` /5157。

真实test名为test_stage109_provider_runtime.py；最初parent消息误补_launcher后缀，实际manifest与同SHA定位后root也明确更正。查找失败不是一次测试，不因此重跑。root合同SHA `553ab50a370f02ecbd235e3b3a8c8952ad16591432d41ca168a443a27650960b`，作者implementation_receipt SHA `cbdd333a851b3e6cb49d06a465ae90a596bf9ccdda0f3f06b2549312933ea6c0`、作者finite evidence SHA `aa04dd4d290a03ad8f4ac433bb92ead140490b68aa4d9f4da9919e953eb94fd0` 已核。作者实施stage SHA `ba8d2cb7ce94391484a243869905f42da9ec81b7283e76dab254a7e87f76cea2` 后补只核身份，不重复测试。

只审启动器/本线sitecustomize、新test及必要原scope/provider调用接口；不改原065/087/owner/readiness/SDK安装包、metadata/version、鉴权、sys.executable或原限额，不新金融/packet/网络。

## 路径与guard核验

每个新解释器由PYTHONPATH局部启用sitecustomize，原022 configure_runtime先建本session/每PID空signal环境；runtime.OUTPUT只临时路由并恢复。numpy/pandas/scipy/sklearn/joblib先从原FROZEN_SITE实加载，模块路径及版本与原frozen distribution核对。随后完成原deps首次定义导入，再前置本机.py311 site并保留FROZEN_SITE，原numeric_runtime_is_frozen为真，后续deps不改序。

真实SDK metadata/distribution/dist-info/package/find_spec origin均要求本机3.10.2；METADATA/init记录SHA，api/auth/tqsim/backtest/downloader五源与原018已接受SHA核对。没有伪造metadata结果、改源或改SDKguard。数值包已加载且其package路径保持FROZEN，不能把新SDK前置误称切换数值来源。

main非probe必须有独立runtime review/P0/P1=0/精确二源，并调用原scope.load_owner真实live/owner门；target只能原scope/provider，target owner/path SHA同一。原CLI继续执行current/request、资格、570/600、840、1800/7200、每批4连接和once attempt门。PYTHONPATH及manifest env由原sys.executable子进程继承，不触碰既有金融进程、全局site-packages/.pth/用户配置。

sitecustomize捕获BaseException后os._exit(78)，不受Python默认吞启动异常影响；错误输出不含环境/凭据值。

## 唯一fresh离线实证

新具名test `ProviderRuntimeSelectionTest.test_three_generations_real_identity_and_fail_closed_inputs`，**reviewer仅一次fresh：exit0、Ran1、0failure/error、3.919s**。仅内存改finite_test_evidence目的地到111，源码/assertions不改；原启动器按真实实现向109/sessions追加新UUID sidecar，不覆盖作者session或finite evidence。

- 真实原初始化baseline仍选TqSDK3.9.4，未import SDK。
- 新三代实际PID 46080→46081→46082，子PPID与父PID相连，全部sys.executable仍本机.py311/bin/python。
- 五数值包均在原FROZEN：numpy2.4.4、pandas2.3.3、scipy1.17.1、sklearn1.8.0、joblib1.5.3。
- 三代SDK metadata/find_spec均本机3.10.2、五源pin一致，原deps前后sys.path相同。
- 原sdk_preflight真实版本/endpoint检查执行通过，trace只在原load_credentials语句之前停止；无SDK import、凭据/API/网络。
- 异常endpoint/错误owner SHA拒绝，site失败exit78且CLI正文未执行。

本次probe manifest位于109/sessions/1e8e090b870a4a4098329c2704992c16，SHA `007d37dff4850a5b6667d9d5b986b47ca983fbd97ebc087165b8fd86a2466516`；各PID解释器sidecar已核manifest/owner/source/review链。probe runtime_review=null是probe边界，不冒称真实runtime执行已签。实际非probe须绑定本111 receipt。

作者RED→GREEN和首轮GREEN deps初始化path错误只作为其历史保留；本reviewer不重复那些运行。完整命令/exit/stdout、源码/manifest/SHA及PID核验见111 evidence.json（SHA `e9f6b9aecf668747135d1f2dd70e955eafe631a5a541a41e19ff00cc4d47295c`），fresh_named_test.txt SHA `463aa75ecd80f6ccc139bf571899ff4f8b532dc165a24952b5a2c9e70849078a`。

## 接受限界

这只证明运行环境选择和凭据前原guard，不证明SDK import/API/full sdk_preflight或实际provider成功。未预加载第三方依赖只记录真实解析路径，不属于五数值冻结承诺。原受影响scope/provider/checkpoint/runner/095五源保持100固定字节；本次不重签原数据集或完整金融来源资格。

新launcher/site/manifest/runtime review是**独立外部运行sidecar**，old_financial_context_includes_this_sidecar=false。后续真实数据/账户审查须另绑定真实sidecar，不能追认它原先已在金融preflight。原batch002失败、owner与等待起点不改；审核用时不能延长840/1800/7200或自动重试网络。

真实SDK import/凭据读取/provider packet/网络/金融/模型load-fit-predict/订单/市场hash/旧suite均0。不改作者源、安装包、owner/readiness、LINE/registry/Git，不另派agent。新增alpha参数与有效成绩0，全部新绩效N/A，production_qualified=false。

调研判断来自root已固定本地合同/代码/真实离线进程，没有新外部网络或alpha研究。开始及结束过拟合判断：**否**，没有看B途中PnL或调参；继续价值：**是**，可避免因包解析错误重跑金融，但真实原门和终态仍需独立证据。

