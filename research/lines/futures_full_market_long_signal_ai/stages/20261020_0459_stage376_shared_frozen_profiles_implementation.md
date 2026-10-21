# Stage376：独立空态与同一已接受输入的薄接口

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 04:59 CST；非重要突破。按375范围及root378明确授权实现，不改359/360/370/373/375、原325/320或LINE/registry。
- **当前仅实现、唯一fixture与prepare；真实初始化/评分/fit/cash/API/SQL/Git全0。** 输入持久化恢复未实现，不能称E2E就绪。

## 两个功能与兼容判断

新增`tools/stage376_shared_frozen_profiles.py`及唯一组合fixture。`initialize(prepared_bundle_binding, output)`只允许root378固定fresh `actual_run1`，不另建授权登记系统。复用368纯helper、原325 identity、321真实UTC事件、322及纯131/070/042；同375模型/scaler/T1创建独立base/stress各100万空态，start_u5290/u20，独立account ID与新325执行journal。旧370及375冻结journal不借用。`load_context`仅恢复已创建的小状态，不造新账户。

发现的实质兼容约束是原320不只使用MAIN2023名称，还硬要求model/scaler cutoff=2023-01-01。已先报告；root在378明确授权metadata-only engine_view。真实375文件字节/SHA、实际cutoff2026-10-20和T1保留在外部profile及完整初始化journal payload；派生view只映射旧API cutoff槽，并加actual_training_cutoff/source_artifact_sha256/解释字段，数值、列序和参数不变。原325 make_policy_identity绑定**完整派生view**，没有修改或放松其源码/identity/hash校验。

外层结果明确engine_fold_tag=2023-01-01，profile显示实际训练截止；原320/156输出行中的cutoff只解释为legacy engine标签，不能说新权重在2023训练。377已只读确认该槽用于旧API guard/分组验证，未发现需要更改数值排序/经济逻辑的额外阻塞；本阶段不重训。

## 同一输入接口及未完成项

`process_pair(composed, acceptance_binding, contexts)`只接受**同一个内存composed和同一root验收binding**，无行情接收或恢复器。已定义最小handoff schema `stage376_same_composed_acceptance_v1`：root accepted、u20、completed361/passed362/accepted363及其三个实物binding、composed_identity和clock_domains_sha256。真实handoff须等今天361终态、362独审和363接受，不能现在填布尔值冒充实物。

composed fingerprint绑定原snapshot的已知339状态/market数组、canonical/compact来源及完整clock_domains；不是通用序列化格式。验证root绑定后另做accepted副本，保留原development_only出处及完整双域，再显式标为future可用；原357对象不改、未出资seal不继承。每个profile独立核模型冻结与真实T_init早于source完成，原始prescore全域D截止和自身持仓/pending依赖；unknown/late保留state_gap和原事实状态，不跳u重置。满足条件才调用原325 mode=future取得自己新的完整资金proposal收据。

357当前未返回/持久化完整composed；今天产物出来后仍需一次最小纯恢复适配。该缺项在prepare/result中写为`actual_compact_restore_ready=False`。没有为此展开recipe系统、通用日更、日历工程或复制大训练资产。

## 唯一fixture与冻结身份

先RED（缺新接口），随后同一组合方法首次GREEN 0.360s；补已有来源/自身依赖边界后最终`Ran 1 test in 0.362s, OK`。未新增测试组或跑旧suite。fixture只用合成模型/价格/临时状态，实际375仅prepare核小binding。

覆盖：真实格式新header被原320拒绝；显式view剔除声明元数据后与原对象逐项相等，原artifact未改；原核分数与独立dot数值一致；base/stress隔离、小状态恢复、旧policy state被拒；同composed/root acceptance绑定，跨batch改来源被拒；未知完成时钟及late输入保留gap与原状态。旧synthetic模型/scaler使用独立小文件binding，make_profile及validate_context逐对象核对bound实际来源，没有用新文件冒充旧模型。

- 工具19609B，SHA `b41042a2853f867dd11c59d36aa1ae8d2b6ec6c71fa827c9828bab2de5b92492`。
- fixture10250B，SHA `dc39fee82bea757a92498582fe2f86b37c38ee81c5f1b9ffbec174b4e30e8203`。
- [prepare bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage376_shared_frozen_profiles/prepare1/source_bundle.json)5928B，SHA `efa529958779c55f26b1fcd0ab3fd22dd2a78628bdafe182b6a2ce7c99eb8031`。
- 绑定378 scope3560B/SHA `ac56dba9fbfc9732f49d333c9414cffbb51e78e1114348f73ef9102e01098f0c`。作者已交377独立一次静审/fixture并停止改源。

## 反思与终态

调研判断沿371/375已核的[scikit-learn时间顺序说明](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)及[维护者评价文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)：新估计版本需自己的未见评价与完整身份。当前只解决执行接线，不提供收益证据，也不将兼容标签当新训练事实。

开始/结束过拟合：本轮无收益调参，否；历史择题偏差及新版本自由度仍是。继续价值：独立初态与诚实共享输入接线有；重复旧金融/扩大恢复工程无。金融参数及回测结果新增/修改/删除0，权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A；无新alpha、窄损加注或生产资格，完整目标active未达成。

## 2026-10-20 05:02 公共入口失败与单行修复

root首次调用于05:01:03失败，耗时0.047503875秒；`root_invocation_terminal.json`保留`TypeError: 'str' object cannot be interpreted as an integer`。失败发生在输出目录创建、日历加载、new_state及评分之前；`378/actual_run1`未创建。原fixture此前只覆盖内部初始化helper，漏掉公共入口的时间预检，这是本次测试边界缺项。

先将旧source19609B/旧fixture10250B及root终态保存为[只读失败快照](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage378_latest_model_initialization_decision/failure_20261020_050103_preflight/manifest.json)。原SHA b41042a2…b92492/dc39fee8…0e8203保留，不覆盖失败现场。

同一fixture追加public `initialize`调用，仅patch临时ACTUAL路径，复用该fixture准备bundle，无新测试组。首个临时路径未resolve被fresh路径guard拒绝（0初始化）；修正fixture路径后，RED精确复现root的TypeError（0初始化/日历读取）。生产源码只将`h._time(datetime.now(timezone.utc))`改为`h._time(datetime.now(timezone.utc).isoformat())`，适配未修改368 helper的字符串接口。已用旧快照字节替换比较确认没有其他生产源码变更。

最终同一fixture`Ran 1 test in 0.369s, OK`，公共入口在临时目录new_state2、仅小日历读取1、评分/fit/cash0；测试没有调用固定378真实目标。snapshot/view/模型/规则/双时钟逻辑未改。RED/GREEN与0真实重试记录见[修复收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage378_latest_model_initialization_decision/failure_20261020_050103_preflight/repair_red_green_receipt.json)。

新source19621B/SHA `0a9edeb45907f9542299b4afee9a718c94b373c16e41349ce0c43d588a0ca910`；fixture10912B/SHA `e940a05aab5479b49700a4bab283b1181377494da8c96ec5572d4a8d8d8b25a9`。[prepare2 bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage376_shared_frozen_profiles/prepare2/source_bundle.json)5928B/SHA `399b2228f51247926e688e8f554786e16d538db59d3cb6a76e30a1d3bd7442ed`；prepare1历史身份仍保留。

作者停止改源交377复核，没有自动真实重试；root在确认此前零初始化并接受修复后，才可另调用一次，总实际初始化仍≤1。新增过拟合否，修公共入口缺项继续有价值；无新金融结果、资格或E2E就绪声明。
