# Stage147：六折FX Ridge与旧控制零列桥实现

- line_id：`futures_full_market_long_signal_ai`；改动时间2026-10-19 00:06 CST；非重要突破，本阶段仅实现收益前冻结的145合同。唯一维护本stage与147工具/fixture；不改LINE/registry/130等旧工具。
- 读取registry、LINE、145协议/计划/独审及accepted130接口；调查结论承接144/145：共同FX不是月份专属新信息，可一次检验新状态对全域准入的观察性改善；不能用重估后月份排名变化宣称因果冲击。没有新增网络下载或新研究变量。

## 实现与全局事前闸门

新增`tools/stage147_fx_fit.py`。使用accepted130完整1552456 actions、399252 mothers、common26绑定和六折成熟规则；两cutoff=2020/2023，main与两个整family留出，目标为原net_R_stress，family哈希、成熟时钟和Ridge(alpha1/intercept/cholesky)保持。直接绑定并读取accepted130各fold `training_identity_weights`，核训练identity/原目标/成熟mask和有限正sample_weight；复用原common scaler、52列设计和portable control model。原目标始终从原动作源读取；训练CSV只作序列化交叉核对，不重建union weights，不复制巨型X，不重复旧fit。

`prepare_folds`必须全部返回成功，程序才可进入第一次`fit_cell`。该函数在全部六折检查训练身份、权重、原common输入与scaler绑定，且每个成熟训练行和**完整前向动作**的q均有限（missing0），然后一次完成六折train-only q加权均值/总体方差；任一方差非有限或非正、任何桥失败都在首个fit前整包停止。CONTROL新增两个槽为0，因此只引用旧B模型/分数/选择，不重训控制、不缩母体、不临时补训练。`bridge_preflight.json`显式保存pass/control_bridge_verified和每fold绑定/方差。

新设计固定54槽=原52+fx_missing+qstd。每个FX模型自己评分完整前向动作；显式调用130纯`make_choices`后只取B并更名FX，无全局ARMS monkeypatch；其A中间结果没有模型或现金副作用。旧B完整choice仅更名CONTROL_REUSED，不作为FX入选门。完整main与held-union的每臂各161014母行；每个FX main/held-union都保存全前向children，而非未来closed或旧正分池。

每fold保存新coef/intercept、q scaler、55维含截距的Ridge充分方程、原训练/权重/scaler/model引用和数值残差，不保存巨型normalized X。输出choices_main/holdout、child_scores、fit_records、held_daily、held_diagnostic与全量held_family_u。family-u在选中母行后去普通/F重复，保留不同动作unknown为NaN；相同未知动作增量0但另列共同未解决状态，不借未来已闭合缩样。

## 授权、验证与结果状态

actual授权schema统一`stage145_exact_root_authorization_v1`、stage=`fit`；需最终145 SHA、当前完整source bundle、精确输入和fresh `outputs/stage147_fx_fit/actual_run1`。manifest绑定146结果；146源bundle也须与当前一致。输入角色见模块`INPUT_ROLES`和implementation_receipt。实际失败保存terminal及fit_attempt/completed，早期桥失败两个计数文件为空、计数0，禁止自动重试。

5个新fixture按TDD先RED后GREEN：完整前向missing导致零列桥失败；任一fold方差失败时不能到达fit callback；54列原52/missing/scalar区分；FX全域自主选择且保留无children母；不同未知动作不填0、相同未知动作保留共同未知。无fixture Ridge fit。最后146/147九项fixture全部通过，四文件py_compile和两个CLI --help通过；不跑旧suite。日志为147的red/green/final_fixture和implementation_receipt。147源码SHA为`9e1fb9fe2a76a25cbac9ce0b89ff23cf51a495572c67d856c5a470a13811cce9`；完整bundle以receipt和函数读回为准。

本阶段新增参数只有冻结q scalar与54槽定义；原alpha、权重、目标、cutoff、风险/费用/容量/止损修改或删除0。新增/修改/删除回测结果0。actual尚未运行；新actual/fixturefit/cash/SQL/标签/下载均0；累计391fit/202cash保持。权益、收益、回撤、Sharpe、滑点、交易次数、胜率均N/A，不是新金融结论。

开始与结束新增按收益选参过拟合：否，只有一个事前冻结包；历史择题、全球FX共用和最终归档修订假设限制仍在。继续有限证伪有价值：是；零列桥失败或固定包不支持时继续救参无价值。TODO：root签发精确源后仅一次6FX fit；148最多4FX现金并复用旧控制；149独立核新增资料/训练/预测/现金/置信度/bug。无正式晋级、加注或完整目标完成声明。

## 00:10 CST：root唯一actual完成读回

root精确授权为`outputs/stage145_fx_information_protocol/authorize147_fit.json`（5926字节，SHA `dadd18d7148180d393ac163d2e766f547b513488e94bf3e9db159c516e0100bc`），冻结145及147源未改。root唯一actual_run1完成；`actual_terminal.json`为completed/exit0，77.847025833秒，6attempt=6completed；controlfit/SQL/cash/download均0，automatic_retry=false。实施agent只读回并更新本stage，没有新actual或源修改。

全局`bridge_preflight.json`为passed，`control_bridge_verified=true`、`all_six_preflight_before_first_fit=true`。完整966740前向动作missing0，全部六折成熟训练missing0且q加权方差有限正；2020和2023总体方差分别约3.341060399e-6和4.655352846e-6。q是同日全球状态，等u训练权重令不同family留出的同cutoff q分布近乎一致，这不是多份独立宏观创新证据。

原399252母体与1552456动作保留，新FX children为1933480=966740 main+966740 held-union；main与held-union各臂均完整161014母行，没有取旧B pool、closed或positive子集代替母体。全期selected为：

| scope | CONTROL_REUSED | FX |
| --- | ---: | ---: |
| main | 4917 | 4952 |
| holdout_0 | 2471 | 2497 |
| holdout_1 | 3861 | 3856 |

入选数不是现金成交或胜率；不同入选也不能直接当收益改善。本阶段只确认实际计数与桥终态，训练/分数/选择的独立内容核验由149负责，经济判断仍须148现金与unknown门。

实际绑定（均位于本线目录）：

- manifest：`outputs/stage147_fx_fit/actual_run1/manifest.json`，21310字节，SHA `2fb1895f6240cbe4f5c16196e1a80944c8daca04c8e248708df329e7ac9dafce`。
- bridge：同目录`bridge_preflight.json`，8885字节，SHA `9c2dfa4d14e3af418f7a538ea4c3cfff5032928bfa8d08fa6f55009656310ddb`。
- terminal：同目录`actual_terminal.json`，345字节，SHA `fbdaeeefb9f67c82ec1d316947bd4cc5be7d6e8f1e26861bbeb79adb015ca9e0`。
- summary：同目录`summary.json`，945字节，SHA `6fbc47b9f99cbf41cd77933de26c679d019fb7141522bbcb4197b7e37cec3021`。
- fit_records：同目录`fit_records.json`，31431字节，SHA `85008b5c6429e85b12b5cecd283f7356f20bc1f7d27648934f4ad11dc0a6d7b7`，含六fold新模型/正规方程及accepted130训练/权重/scaler引用。
- 全新child scores：同目录`child_scores.csv.gz`，124263888字节，SHA `a850697f7626e6858a323d537dad747ceff26fcf97941aa91a50fd8689ed7572`。
- choices main/held：同目录`choices_main.csv.gz` SHA `faeb022e5dc05856a507711af3b30aabef1b506a3b589ba4f629f87f0841b8ae`；`choices_holdout.csv.gz` SHA `46f2f168c1cd77a37429dd64a7e1ff6fcdd1e4faa36307c0cbd93c655339d147`。
- 全family-u差异：同目录`held_family_u.csv.gz`，SHA `bd1b96780e656d57d2b9cfb964c0f7980572d20cf953a988d70e08fb9f846278`，连同held_daily/held_diagnostic保留不同未知和共同未解决状态。
- root CLI：`outputs/stage145_fx_information_protocol/actual147_cli.log`，746字节，SHA `8dfe45eb5f5b9d034c20a3b030ec8214bd441cb0862c8cf54bcd43c98b952ff9`，顺序记录六fold完成及最终completed。

本次新增6实际FX fit，累计397fit/202cash；148在途状态不在本文提前计入。没有模型重试、control fit、旧cash回放、新标签/SQL/下载、风险/stop/capacity参数变更。新增金融回测结果仍无；权益、总收益、最大回撤、Sharpe、总滑点、成交次数及胜率均N/A，不能从selected数推断。

结束新增按收益选参过拟合：否，六折与单一q事先冻结，未用本次结果改源或参数；历史择题和归档修订限制仍在。继续既定148/149验证有价值：是，拟合成功本身不能回答新增信息是否改善成本后组合，也不解除未知执行。后续不扩窗/翻符号/改模型救参，不提升风险或签正式资格；goal保持未完成。
