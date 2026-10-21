# Stage356：纯52研究参考的最薄本地资产闭包

记录时间：2026-10-20 04:18（Asia/Shanghai）。所属线 `futures_full_market_long_signal_ai`。非突破版本；只盘点并建议本地不可变登记，未调用登记器、未保存payload、未创建T0。固定原main2023纯52/156选择/K/原预算研究参考，不是官方C9、正式物料或生产激活。

本轮先读registry、352 next_scope及freeze skill的AI资产规则和material-contract。沿335/350已存Tq官方/维护者与交易所证据，不新增网络或行情探测。现有 `qmt_roll_ai_artifact_registry.py` 的 `canonical_publication_request` 硬写official_candidate，实验登记入口会复制后执行git add；因此本轮不调用两者，也不把正式clean HEAD、commit或发布流程搬进研究登记。其AiArtifact角色枚举还不含runtime_code；本地清单显式保存真实角色，不能直接穿过旧登记器。

资产逐行见 `outputs/stage356_reference_asset_closure/asset_inventory.json`：绝对path、repo相对logical_name、role、reproducibility_required、schema/feature_schema_version、bytes/SHA和绑定依据。357最终源码/测试及bundle已逐项纳入，59项必需资产与6项原data外部引用；其全部17个运行源码和15项输入绑定均与现有清单对齐，文件大小一致。这里“闭包齐全”仅指资产盘点完整，尚不等于358独审接受、root359已保存实体或T0已冻结。单独clock_contract已按root收益前批准口径定稿，未据成绩改变准入。

最薄闭包有四层：

- 源：320/321/322/325/339/342/336及357；320._helpers对004/042/070/129/130/156/157七个完整小源码做SHA后只AST提取白名单。七源实体必需，但不加载旧label/fit/cash CLI。336还依赖两份公开require_credentials/redact来源源码，不含私有env内容。353作为已接受354时段的推导证据保留，357直接消费354候选，不import353或330/331/346/354 runner。322仅被caller加载，本次observe不调用；旧131与312不扩大进本闭包。
- 推断：130 main/2023-01-01 portable模型2787B与scaler4680B，原26标准化、26原缺失标志及52顺序；52系数与截距直接推断，无joblib/unpickle/重训。cutoff只是继承tag/规则和130接受证据；模型未声明的最大label-known时刻不补造。
- 事实与状态：完整98品种/95family目录、确认源calendar、338 catalog/calendar、354身份/运营时段与来源metadata、344的757递推状态/9520 epoch目录/726 canonical overlay及经济compact，加331的744经济compact。经济按同原版本epoch键补并：共有项须一致，冲突或缺项留unknown，不用本次未知M补0。状态保留31非current，不能冒充新报价；不能截21bar重新播种Wilder。完整候选、missing、拒绝项和真实321 journal/objects是决策证据，不能按“生成物”标签删除。
- 溯源：接受收据、原130小manifest和331/344来源manifest；原110MB cache、SQL库、8MB projection、343原日期/原件仅绑定引用，不复制或读取实体。这个胶囊复现的是增量观察/推断，不承诺重建旧训练及全历史金融。

若后续root保存payload，必须保留repo相对目录树。336/357的ROOT相对tools层级，纯helper又跨至examples及另一线；只把tools扁平挪位会错。另一可说清的方式是“原位源码+SHA门，payload仅证据”的host-bound运行；两者均不能仅凭manifest称可跨机即用。没有复制私有凭证、装环境或连接行情。

本机以metadata观测Python3.11.5、macOS27 arm64、numpy2.2.3、pandas2.2.3、TqSdk3.10.2及其包依赖版本；完整名称/版本在JSON。无pipfreeze、安装或私有URL。推断只需numpy/pandas；Tq接收依赖另列，已安装SciPy不等于启用求解器。当前源码以实际工作文件逐字SHA为身份；Git0未刷新HEAD，若root保留HEAD只能作provenance，不能冒称clean HEAD，也不能用它代替脏源码字节。

clock_contract明确分域：source完成依赖所有因果输入/peer和已有事实所需价格；D deadline取新u原资格True全集、资格未决与既有position/pending，绝不按score、K、最终winner或旧427筛。确定历史不足、已知lifecycle过期、合格经济下真实容量不足可排除；未决只保留clock依赖，不升级交易资格。任何required时段缺失/冲突留unknown；354 full726 strict诊断原样保留。source_completed_at取确认运营session_end，receipt另存，不承诺vendor finality。这是T0前保守澄清，可能改变运行准入，不说旧执行路径等价。

建议root359在所有最终小源/资产绑定齐全后，用独立冻结journal真实321 append(kind=research_reference_freeze)，保存完整UTC receipt；T0只取其recorded_at。closure_manifest、clock_contract与journal路径进入stage359 envelope。随后原325 make_policy_identity(model,scaler,frozen_at=T0)保持原形，不加custom keys；更大闭包由envelope/auth/source_receipt另绑定。冻结journal、旧历史journal和未来模型journal身份分开。冻结前已完成而晚取的u仍历史；不初始化100万资金、不安装调度、不承诺未来自动化ready。

新增参数/模型/回测/金融结果均0；仅新增冻结前操作clock合同，不调策略参数。fit/cash/SQL/API/旧价格读取/旧suite/Git/T0均0；只hash一份766537B经济compact以登记身份，未解析经济数值。长期同史择题和前后选择偏差仍存在：本轮无收益搜索，不新增alpha证据；闭包能减少未来漏依赖和伪前瞻，值得有限继续。总体long→小止损→加注目标仍active、未完成，不认AI相对优越。

357最终源28199B、SHA65d18a5c39e8df5442eafc2f5e2fd782f9bb492743339dc6cb5b013c91877e87；author唯一integration tiny已GREEN，356未复跑。当前可交root本地保存器及358独审，未执行接收。
