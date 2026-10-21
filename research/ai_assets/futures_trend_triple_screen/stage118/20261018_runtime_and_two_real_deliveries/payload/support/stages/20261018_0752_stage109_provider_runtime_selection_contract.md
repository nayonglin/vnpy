# Stage109：当前B外部补数进程的真实SDK环境选择合同

- 2026-10-18 07:52 CST，root，line_id futures_trend_triple_screen；数据启动环境正确性，非alpha，金融attempt不新增。
- 当前B81ffc8f704ce4c5eb701e97e0397b12a/PID44392/session47648在第2个实际jm2005.DCE 2020-03-10 full请求等待。108证明batch002原prepare在网络前失败：原scope.deps前置FROZEN_SITE使metadata解析旧TqSDK3.9.4；本机.py311默认真实3.10.2，四endpoint env均不存在。packet目录、network_attempt均未建立，provider连接0。保留该失败，不能重用batch002或伪造其成功。
- 原087 scope/provider、金融065、owner/readiness/099合同及已安装包均保持冻结。禁止改metadata/version函数、SDK源码、鉴权/端点/资格guard、sys.executable、FROZEN_SITE身份或运行限额；禁止金融重启或以当前异常放行3.9.4。
- 授权仅新增独立外部启动器及本线专用sitecustomize目录，PYTHONPATH只传给其新provider进程树，不写全局site-packages/.pth/用户环境，不碰现有金融进程。各新Python先依原022 configure_runtime建立空signal环境，原FROZEN_SITE加载numpy/pandas/scipy/sklearn/joblib，核实际模块路径与版本；随后把真实本机.py311 site放在前面，保留FROZEN_SITE，令原numeric_runtime_is_frozen为真且原deps不再重排。真实SDKmetadata与实际tqsdk源码必须都为原018已接受的本机3.10.2路径/字节，原sdk_preflight原样执行，不伪造检查结果。
- 必须覆盖原scope.invoke→provider prepare/run→worker所有sys.executable子进程的继承。新启动器/sitecustomize源码和参数、父子PID/实际模块路径/SDK版本及源SHA、owner SHA、实际review SHA形成独立运行sidecar闭包；原087 packet receipt没有新启动器字段的事实如实披露，最终独立数据/账户审查须绑定sidecar，不冒称新启动环境早在金融preflight内。无凭据值输出/落盘。异常须明确非零退出，不能被Python对sitecustomize异常的容错掩盖。
- 收益前唯一有限RED→GREEN行为验证：真实未选环境复现3.9.4，再在无API实例/无网络/无凭据读取的父子孙进程里证明所有数值包仍原FROZEN、SDK真实metadata/import为原3.10.2且原guard可过；错误环境/endpoint/身份输入须失败。不开实际packet、不重扫全市场，不跑旧suite或新金融。另一agent一次定向独立接受后，root才另授权当前真实请求的新batch003；每packet仍唯一attempt、每批4连接（含daily）、原570/600、840余量、1800/7200不变。
- 若方案无法同时证明真实SDK和数值来源，就保持失败不绕过，等待原B真实终态/按具体证据决定后续。首次prepare失败不计网络attempt，但不能任意自动重试网络连接或清除失败记录。
- 新增/修改/删除alpha参数和有效回测结果0，期末权益/收益/回撤/Sharpe/滑点/交易/胜率均N/A；A完整已出且母链只读审计中，B未完。全研究11attempt/3accepted（等待A独立接受），训练0，目标active、production_qualified=false。
- 外部Python官方site与importlib.metadata文档确认startup初始化及metadata依sys.path发现，不证明实际组合正确；本合同要求真实三代进程实证。开始/结束新增过拟合否，未看B盈亏或调参；继续有价值是，避免为外部包路径错误再跑金融，并保持原数据资格门。
