# Stage191：冻结189双新臂8账本适配器准备

2026-10-19 15:46 CST；`line_id=futures_full_market_long_signal_ai`。本阶段为实现准备，非重要突破；与190共用唯一新fixture文件，但本stage只记录191现金适配器。已读registry、189协议、183设计和184裁定，不修改其他stage/LINE/registry、正式版、生产、CTP、邮件或Git。

**结论：191准备完成，实际新现金账户=0，等待root静审与后续独立授权。** `tools/stage191_registration_cash.py` SHA256=`d6a8b38d06a7e0de66d32aa098013e702e651f3501d7548adc602e211f18ba10`；共用测试SHA256=`bc7c2cbedc0cc4e00ccc00a8db291518df9f2dde502940145635f66c77085809`。接口、源码闭包和验证记录写入 `outputs/stage191_registration_cash/preparation.json`，该文件不授权actual。

仅接收190新CONTROL54/REGISTRATION54完整主scope选择，各臂自行保留原始parent/action/anchor，局部兼容131的B schema后立即还原臂名，不更改旧helper全局ARMS、不借其他臂账户。190必须12次新fit完整完成、精确189协议和所有源输入闭包一致；191再次核对186/188、187两独审及root五binding source_acceptance，no-go/部分fit不能进入cash。

现金严格为两新臂×primary2020/cold2023×base/stress共8本，各自递归；本金100万、初始止损0.25N、family risk0.0025、total0.02、buffered margin cap0.25、buffer1.1、参与率0.01、roundtrip半容量、原SL0+20low/费用/tick/slippage/immutable anchor与自有D开盘预算均不改。共同K仍由D<K准入、prev(K)请求K开盘退出，缺报价请求保持，不发明成交或现金交割。source/voluntary/effective生命周期三条并存。

8本金融执行先写financial_started、逐本started/completed、原始fills/daily/positions/budget等与checkpoint，再做报告/CI/门；每本物理完成数先于序列化/元数据增加，失败也写financial_terminal保留数目，已有financial attempt或账本拒绝重放。原累计409fit/218cash；191只在190完整12fit后启动，完整8本则421/226；部分失败按完成数保留，不为补元数据重跑完成账本。

固定070配对索引原样读，不重生、不重放旧book；四组paired mean daily log增量CI、primary2020stress收益/回撤严格优于新CONTROL54且CI低端>0、其余三组非劣、候选自身四组正收益、八本wealth正和held原标签known equal-u门均继承189。CONTROL DD未知不能以0补，差异held unknown不能以0补或认作K现金目标。所有family/year含0归因仍使用accepted纯报告算法。

源读法：原399252 mothers完整读、主scope每臂161014父行完整身份核对，原1552456动作只单次stream扫描并核完整顺序，再保留两臂自行选中动作供执行；不缩减选择宇宙。132 native cache从已accepted manifest binding和数据库/NPZ stat继承，一次NPZ数据读；不重hash大输入/数据库，不查SQL，不回放旧账户。未知登记值保留在完整选择domain。

有限验证与190共用：8项核心fixture最新8/8通过，唯一新测试命令见prepare内记录；2个现金fixture分别验证八本独立账户、缺quote推迟K到有效bar，以及第二本失败保留第一本checkpoint与2 attempted/1 completed。每次完整8-case GREEN另有9本synthetic完成，3次GREEN累计30 attempted/27 completed；不是研究现金。fixture fit=0，实际研究fit=0/cash=0；累计实际仍409/218。无旧suite/全branch执行，无真实SQL/download/交易API。

公开调研结论：同190核官方文档及GitHub维护者Ridge实现，只支持冻结纯算法复用，不提供新登记scalar的alpha证据；仓单source/公开时钟/归档修订仍为条件假设，不能凭现金门代替PIT/执行/法定期限认证。

参数记录：新增可调参数0，修改参数0，删除参数0；新增/修改/删除回测结果0。期末权益、收益、DD、Sharpe、滑点、交易次数和胜率本次均未实际运行。

开始/结束反思：是否过拟合——否，本次只适配冻结包与验证账本隔离/计数，不看新收益或改变风险参数；历史搜索条件性仍须披露。是否有继续价值——是，适配器让后续一次性固定证伪可审核；源/支持no-go立即0cash，金融门失败关闭单scalar/Ridge/commonK包，不救sign/window/coverage/lag/product/model/stop/risk。TODO：root静审、190一次性授权执行并完整完成后，root另签191精确source/input/output授权，实际全结果须由独立agent全面复审；不晋升、不加注。
